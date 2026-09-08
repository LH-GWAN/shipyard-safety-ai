"""자연어 구조화 평가 공통 로직.

평가 기준은 어댑터 계약(입력에 명시된 사실만 추출, 없으면 null)이며
모의 어댑터와 실제 공급자 어댑터에 동일하게 적용한다.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.data_files import load_zones  # noqa: E402
from app.llm.base import AllowedZone, LLMAdapter, ParsedWorkItemDraft  # noqa: E402

VALUE_FIELDS = (
    "work_type",
    "zone_id",
    "start_at",
    "end_at",
    "uses_flammable_material",
    "gas_measurement_completed",
    "ventilation_confirmed",
    "watcher_assigned",
)
TIME_FIELDS = ("start_at", "end_at")
BOOLEAN_FIELDS = (
    "uses_flammable_material",
    "gas_measurement_completed",
    "ventilation_confirmed",
    "watcher_assigned",
)


def load_cases(path: Path | None = None) -> dict[str, Any]:
    path = path or (Path(__file__).resolve().parent / "cases.json")
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_zones() -> list[AllowedZone]:
    zones = load_zones(REPO_ROOT / "data" / "zones.json")
    return [AllowedZone(id=zone.id, name=zone.name) for zone in zones]


def _normalize(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if field_name in TIME_FIELDS:
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return datetime.fromisoformat(str(value)).timestamp()
        except ValueError:
            return str(value)
    if hasattr(value, "value"):  # enum
        return value.value
    return value


@dataclass
class CaseResult:
    case_id: str
    category: str
    schema_valid: bool
    field_match: dict[str, bool] = field(default_factory=dict)
    hallucinated_fields: list[str] = field(default_factory=list)
    missing_fields_match: bool = False
    error: str | None = None

    @property
    def needs_user_edit(self) -> bool:
        return (not self.schema_valid) or (not all(self.field_match.values()))


def score_case(case: dict[str, Any], draft: ParsedWorkItemDraft | None, error: str | None = None) -> CaseResult:
    if draft is None:
        return CaseResult(
            case_id=case["id"],
            category=case["category"],
            schema_valid=False,
            field_match={name: False for name in VALUE_FIELDS},
            error=error,
        )

    expected = case["expected"]
    matches: dict[str, bool] = {}
    hallucinated: list[str] = []
    for name in VALUE_FIELDS:
        actual = _normalize(name, getattr(draft.values, name))
        wanted = _normalize(name, expected.get(name))
        matches[name] = actual == wanted
        # 기대값이 null인데 값을 채웠다면 임의 추정(환각)으로 집계한다.
        if wanted is None and actual is not None:
            hallucinated.append(name)

    expected_missing = {name for name in VALUE_FIELDS if expected.get(name) is None}
    reported_missing = {name for name in draft.missing_fields if name in VALUE_FIELDS}
    actual_missing = {name for name in VALUE_FIELDS if getattr(draft.values, name) is None}

    return CaseResult(
        case_id=case["id"],
        category=case["category"],
        schema_valid=True,
        field_match=matches,
        hallucinated_fields=hallucinated,
        missing_fields_match=(reported_missing == actual_missing == expected_missing),
    )


def run_adapter(adapter: LLMAdapter, cases: list[dict[str, Any]]) -> list[CaseResult]:
    zones = allowed_zones()
    results: list[CaseResult] = []
    for case in cases:
        try:
            draft = adapter.parse_work_description(case["text"], zones)
            results.append(score_case(case, draft))
        except Exception as exc:  # 어댑터 실패도 평가 대상이다.
            results.append(score_case(case, None, error=f"{type(exc).__name__}: {exc}"))
    return results


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results) or 1

    def accuracy(name: str) -> float:
        return round(sum(1 for r in results if r.field_match.get(name)) / total, 4)

    time_hits = sum(1 for r in results if all(r.field_match.get(f) for f in TIME_FIELDS))
    boolean_hits = sum(1 for r in results if all(r.field_match.get(f) for f in BOOLEAN_FIELDS))

    return {
        "case_count": len(results),
        "work_type_accuracy": accuracy("work_type"),
        "zone_id_accuracy": accuracy("zone_id"),
        "time_accuracy": round(time_hits / total, 4),
        "start_at_accuracy": accuracy("start_at"),
        "end_at_accuracy": accuracy("end_at"),
        "boolean_field_accuracy": round(boolean_hits / total, 4),
        "missing_fields_accuracy": round(sum(1 for r in results if r.missing_fields_match) / total, 4),
        "schema_valid_rate": round(sum(1 for r in results if r.schema_valid) / total, 4),
        "user_edit_required_rate": round(sum(1 for r in results if r.needs_user_edit) / total, 4),
        "hallucination_count": sum(len(r.hallucinated_fields) for r in results),
        "hallucinated_cases": [r.case_id for r in results if r.hallucinated_fields],
    }


def to_report(provider: str, results: list[CaseResult], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": provider,
        "summary": summary,
        "cases": [
            {
                "case_id": r.case_id,
                "category": r.category,
                "schema_valid": r.schema_valid,
                "needs_user_edit": r.needs_user_edit,
                "field_match": r.field_match,
                "hallucinated_fields": r.hallucinated_fields,
                "missing_fields_match": r.missing_fields_match,
                "error": r.error,
            }
            for r in results
        ],
    }


def print_summary(provider: str, summary: dict[str, Any], results: list[CaseResult]) -> None:
    print(f"\n=== 자연어 구조화 평가 결과 (provider={provider}) ===")
    print(f"평가 문장 수            : {summary['case_count']}")
    print(f"work_type 정확도        : {summary['work_type_accuracy']:.1%}")
    print(f"zone_id 정확도          : {summary['zone_id_accuracy']:.1%}")
    print(f"시간 추출 정확도        : {summary['time_accuracy']:.1%}")
    print(f"boolean 필드 정확도     : {summary['boolean_field_accuracy']:.1%}")
    print(f"missing_fields 정확도   : {summary['missing_fields_accuracy']:.1%}")
    print(f"형식 유효 응답률        : {summary['schema_valid_rate']:.1%}")
    print(f"사용자 수정 필요 비율   : {summary['user_edit_required_rate']:.1%}")
    print(f"임의 추정(환각) 건수    : {summary['hallucination_count']}")

    failed = [r for r in results if r.needs_user_edit]
    if failed:
        print("\n수정이 필요한 문장:")
        for r in failed:
            wrong = [name for name, ok in r.field_match.items() if not ok]
            print(f"  - {r.case_id} ({r.category}): {', '.join(wrong) or r.error}")
