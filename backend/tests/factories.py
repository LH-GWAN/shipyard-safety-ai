"""규칙 엔진 테스트용 도메인 객체 팩토리."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.timeutil import KST
from app.domain.enums import Severity, WorkType
from app.domain.models import RuleSpec, WorkItemData, ZoneData
from app.domain.rules import RuleEvaluator
from app.domain.zones import ZoneGraph

DAY = datetime(2026, 3, 16, tzinfo=KST)

RULE_IDS = ("R001", "R002", "R003", "R101", "R102", "R103")


def make_rules(disabled: tuple[str, ...] = ()) -> list[RuleSpec]:
    return [
        RuleSpec(
            id=rule_id,
            name=rule_id,
            description="테스트 규칙",
            severity=Severity.HIGH,
            enabled=rule_id not in disabled,
            reference_title="테스트 참고자료",
            reference_url=None,
            version="1.0.0",
            reviewed=True,
        )
        for rule_id in RULE_IDS
    ]


def make_zone_graph() -> ZoneGraph:
    return ZoneGraph(
        [
            ZoneData(id="Z1", name="1구역", adjacent_zone_ids=("Z2",)),
            ZoneData(id="Z2", name="2구역", adjacent_zone_ids=()),
            ZoneData(id="Z3", name="3구역", adjacent_zone_ids=()),
        ]
    )


def make_item(
    item_id: str,
    work_type: WorkType,
    zone_id: str = "Z1",
    start_hour: float = 9,
    end_hour: float = 12,
    **flags,
) -> WorkItemData:
    return WorkItemData(
        id=item_id,
        title=f"{item_id} 작업",
        work_type=work_type,
        zone_id=zone_id,
        start_at=DAY + timedelta(hours=start_hour),
        end_at=DAY + timedelta(hours=end_hour),
        **flags,
    )


def evaluate(items, disabled: tuple[str, ...] = (), analysis_id: str = "AN_TEST"):
    evaluator = RuleEvaluator(make_rules(disabled), make_zone_graph())
    return evaluator.evaluate(items, analysis_id)
