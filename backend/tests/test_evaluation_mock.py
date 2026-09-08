"""자연어 구조화 평가 하네스 회귀 테스트(API 키·네트워크 불필요)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALUATION_DIR = REPO_ROOT / "evaluation"
if str(EVALUATION_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATION_DIR))

from scoring import load_cases, run_adapter, summarize  # noqa: E402

from app.llm.mock import MockLLMAdapter  # noqa: E402


@pytest.fixture(scope="module")
def evaluation():
    payload = load_cases()
    results = run_adapter(MockLLMAdapter(), payload["cases"])
    return payload, results, summarize(results)


def test_case_set_covers_required_categories(evaluation):
    payload, _, _ = evaluation
    cases = payload["cases"]
    assert len(cases) >= 30

    categories = {case["category"] for case in cases}
    required = {
        "HOT_WORK_NORMAL",
        "PAINTING",
        "SOLVENT_WORK",
        "CONFINED_SPACE",
        "NO_TIME",
        "NO_ZONE",
        "AMBIGUOUS_DATE",
        "UNKNOWN_ZONE",
        "INVALID_TIME_RANGE",
        "SAFETY_TRUE",
        "SAFETY_FALSE",
        "SAFETY_UNMENTIONED",
        "MIXED_WORK",
    }
    assert required <= categories


def test_cases_contain_no_personal_or_company_identifiers(evaluation):
    """합성 문장만 사용한다."""
    payload, _, _ = evaluation
    forbidden = ["주식회사", "㈜", "협력업체명", "@", "010-", "선주"]
    for case in payload["cases"]:
        for token in forbidden:
            assert token not in case["text"], case["id"]


def test_mock_adapter_meets_documented_baseline(evaluation):
    """evaluation/README.md에 기록한 측정값이 회귀하지 않는지 확인한다."""
    _, _, summary = evaluation
    assert summary["case_count"] >= 30
    assert summary["schema_valid_rate"] == 1.0
    assert summary["time_accuracy"] == 1.0
    assert summary["work_type_accuracy"] >= 0.88
    assert summary["zone_id_accuracy"] >= 0.97
    assert summary["boolean_field_accuracy"] >= 0.83
    assert summary["user_edit_required_rate"] <= 0.28
    assert summary["hallucination_count"] <= 2


def test_mock_adapter_never_invents_times_or_safety_measures(evaluation):
    """상대 날짜·표준시간대 없는 시각·미언급 안전조치를 지어내지 않는다."""
    payload, results, _ = evaluation
    by_id = {result.case_id: result for result in results}
    for case in payload["cases"]:
        if case["category"] in {"AMBIGUOUS_DATE", "NO_TIME", "NO_TIMEZONE", "SAFETY_UNMENTIONED"}:
            result = by_id[case["id"]]
            assert result.field_match["start_at"], case["id"]
            assert result.field_match["end_at"], case["id"]
            for boolean_field in (
                "gas_measurement_completed",
                "ventilation_confirmed",
                "watcher_assigned",
            ):
                assert result.field_match[boolean_field], f"{case['id']}.{boolean_field}"


def test_evaluation_is_deterministic(evaluation):
    payload, results, summary = evaluation
    repeat = summarize(run_adapter(MockLLMAdapter(), payload["cases"]))
    assert repeat == summary
    assert len(results) == summary["case_count"]
