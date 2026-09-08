"""결정론적 규칙 엔진.

같은 입력에는 항상 같은 경보가 나온다. 현재시각, 무작위값, LLM 응답을 판정에 사용하지 않는다.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from app.core.timeutil import iso
from app.domain.enums import (
    SEVERITY_ORDER,
    SPATIAL_RELATION_KR,
    Severity,
    SpatialRelation,
    WorkType,
)
from app.domain.models import AlertData, RuleSpec, WorkItemData
from app.domain.overlap import overlap_window
from app.domain.zones import ZoneGraph

PAIR_RECOMMENDED_ACTION = (
    "두 작업의 시간을 분리하거나 작업 구역을 분리하는 방안을 검토하고, "
    "불가피한 경우 현장 안전관리자가 차단막·환기·화기감시 등 추가 통제조치 적용 여부를 확인하십시오."
)

CONFINED_FIELDS: dict[str, tuple[str, str, str, str]] = {
    # rule_id -> (필드명, 항목 한글명, null 메시지, false 메시지)
    "R101": (
        "gas_measurement_completed",
        "가스측정",
        "가스측정 여부가 입력되지 않았습니다.",
        "가스측정 미실시로 입력되었습니다.",
    ),
    "R102": (
        "ventilation_confirmed",
        "환기",
        "환기 확인 여부가 입력되지 않았습니다.",
        "환기 미확인으로 입력되었습니다.",
    ),
    "R103": (
        "watcher_assigned",
        "감시인",
        "감시인 배치 여부가 입력되지 않았습니다.",
        "감시인 미배치로 입력되었습니다.",
    ),
}

CONFINED_RECOMMENDED_ACTION: dict[str, str] = {
    "R101": "밀폐공간 작업 전 가스농도 측정 결과를 입력하고, 현장 안전관리자가 측정 실시 여부를 확인하십시오.",
    "R102": "밀폐공간 작업 중 환기 유지 계획을 입력하고, 현장 안전관리자가 환기 상태를 확인하십시오.",
    "R103": "밀폐공간 작업의 외부 감시인 배치 정보를 입력하고, 현장 안전관리자가 배치 여부를 확인하십시오.",
}


def make_alert_id(analysis_id: str, duplicate_key: str) -> str:
    """analysis_id와 중복키로부터 재현 가능한 Alert ID를 만든다."""
    digest = hashlib.sha1(f"{analysis_id}|{duplicate_key}".encode()).hexdigest()
    return f"AL_{digest[:16]}"


class RuleEvaluator:
    """WorkItem 목록에 규칙을 적용해 Alert 목록을 만든다."""

    def __init__(self, rules: Iterable[RuleSpec], zone_graph: ZoneGraph) -> None:
        self.rules: dict[str, RuleSpec] = {rule.id: rule for rule in rules}
        self.zone_graph = zone_graph

    # ------------------------------------------------------------------ 공개 API
    def evaluate(self, items: Sequence[WorkItemData], analysis_id: str = "") -> list[AlertData]:
        alerts: list[AlertData] = []
        ordered = sorted(items, key=lambda item: item.id)

        for index, first in enumerate(ordered):
            for second in ordered[index + 1 :]:
                alerts.extend(self._evaluate_pair(first, second, analysis_id))
            alerts.extend(self._evaluate_single(first, analysis_id))

        return self._deduplicate_and_sort(alerts, ordered)

    # --------------------------------------------------------------- 작업쌍 규칙
    def _evaluate_pair(self, a: WorkItemData, b: WorkItemData, analysis_id: str) -> list[AlertData]:
        window = overlap_window(a, b)
        if window is None:
            return []
        relation = self.zone_graph.relation(a.zone_id, b.zone_id)
        if relation is SpatialRelation.UNRELATED:
            return []

        results: list[AlertData] = []
        pair_ids = tuple(sorted((a.id, b.id)))
        minutes = int((window[1] - window[0]).total_seconds() // 60)
        evidence = self._pair_evidence(a, b, relation, window, minutes)

        hot, other = self._hot_and_other(a, b)
        conflict_rule: str | None = None
        if hot is not None and other is not None:
            if other.work_type is WorkType.PAINTING:
                conflict_rule = "R001"
            elif other.work_type is WorkType.SOLVENT_WORK:
                conflict_rule = "R002"

        if conflict_rule and self._enabled(conflict_rule):
            label = "도장작업" if conflict_rule == "R001" else "유기용제 작업"
            message = (
                f"화기작업 '{hot.title}'과(와) {label} '{other.title}'이(가) "
                f"{SPATIAL_RELATION_KR[relation.value]} 구역에서 {minutes}분간 시간 중첩됩니다."
            )
            results.append(
                self._build_alert(analysis_id, conflict_rule, pair_ids, message, evidence, PAIR_RECOMMENDED_ACTION)
            )

        # R003: 동일 작업쌍에서 R001/R002가 성립하면 생성하지 않는다.
        if conflict_rule is None and self._enabled("R003") and hot is not None and other is not None:
            if other.uses_flammable_material is True:
                flammable_evidence = dict(evidence)
                flammable_evidence["flammable_work_item_id"] = other.id
                message = (
                    f"화기작업 '{hot.title}'과(와) 가연성 물질을 사용하는 작업 '{other.title}'이(가) "
                    f"{SPATIAL_RELATION_KR[relation.value]} 구역에서 {minutes}분간 시간 중첩됩니다."
                )
                results.append(
                    self._build_alert(
                        analysis_id, "R003", pair_ids, message, flammable_evidence, PAIR_RECOMMENDED_ACTION
                    )
                )
        return results

    @staticmethod
    def _hot_and_other(a: WorkItemData, b: WorkItemData) -> tuple[WorkItemData | None, WorkItemData | None]:
        """한쪽만 화기작업인 조합을 (화기작업, 상대작업)으로 돌려준다."""
        a_hot = a.work_type is WorkType.HOT_WORK
        b_hot = b.work_type is WorkType.HOT_WORK
        if a_hot and not b_hot:
            return a, b
        if b_hot and not a_hot:
            return b, a
        return None, None

    def _pair_evidence(
        self,
        a: WorkItemData,
        b: WorkItemData,
        relation: SpatialRelation,
        window: tuple,
        minutes: int,
    ) -> dict:
        return {
            "work_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "work_type": item.work_type.value,
                    "zone_id": item.zone_id,
                    "zone_name": self.zone_graph.name_of(item.zone_id),
                    "start_at": iso(item.start_at),
                    "end_at": iso(item.end_at),
                    "uses_flammable_material": item.uses_flammable_material,
                }
                for item in sorted((a, b), key=lambda item: item.id)
            ],
            "spatial_relation": relation.value,
            "overlap_start": iso(window[0]),
            "overlap_end": iso(window[1]),
            "overlap_minutes": minutes,
        }

    # --------------------------------------------------------------- 단일 작업 규칙
    def _evaluate_single(self, item: WorkItemData, analysis_id: str) -> list[AlertData]:
        if item.work_type is not WorkType.CONFINED_SPACE:
            return []

        results: list[AlertData] = []
        for rule_id, (field_name, label, null_message, false_message) in CONFINED_FIELDS.items():
            if not self._enabled(rule_id):
                continue
            value = getattr(item, field_name)
            if value is True:
                continue
            detail = null_message if value is None else false_message
            message = f"밀폐공간 작업 '{item.title}'의 {label} 정보가 확인되지 않았습니다. {detail}"
            evidence = {
                "work_item_id": item.id,
                "title": item.title,
                "work_type": item.work_type.value,
                "zone_id": item.zone_id,
                "zone_name": self.zone_graph.name_of(item.zone_id),
                "start_at": iso(item.start_at),
                "end_at": iso(item.end_at),
                "field": field_name,
                "value": value,
                "value_state": "MISSING" if value is None else "DECLARED_FALSE",
            }
            results.append(
                self._build_alert(
                    analysis_id,
                    rule_id,
                    (item.id,),
                    message,
                    evidence,
                    CONFINED_RECOMMENDED_ACTION[rule_id],
                )
            )
        return results

    # ------------------------------------------------------------------- 보조 함수
    def _enabled(self, rule_id: str) -> bool:
        rule = self.rules.get(rule_id)
        return bool(rule and rule.enabled)

    def _severity(self, rule_id: str) -> Severity:
        rule = self.rules.get(rule_id)
        return rule.severity if rule else Severity.HIGH

    def _build_alert(
        self,
        analysis_id: str,
        rule_id: str,
        work_item_ids: tuple[str, ...],
        message: str,
        evidence: dict,
        recommended_action: str,
    ) -> AlertData:
        duplicate_key = f"{rule_id}|{','.join(work_item_ids)}"
        return AlertData(
            id=make_alert_id(analysis_id, duplicate_key),
            rule_id=rule_id,
            severity=self._severity(rule_id),
            work_item_ids=work_item_ids,
            message=message,
            evidence=evidence,
            recommended_action=recommended_action,
        )

    def _deduplicate_and_sort(self, alerts: Sequence[AlertData], items: Sequence[WorkItemData]) -> list[AlertData]:
        unique: dict[str, AlertData] = {}
        for alert in alerts:
            unique.setdefault(alert.duplicate_key, alert)

        start_by_id = {item.id: item.start_at for item in items}

        def sort_key(alert: AlertData):
            earliest = min(start_by_id[i] for i in alert.work_item_ids if i in start_by_id)
            return (
                SEVERITY_ORDER.get(alert.severity.value, 99),
                earliest,
                alert.rule_id,
                alert.work_item_ids,
            )

        return sorted(unique.values(), key=sort_key)
