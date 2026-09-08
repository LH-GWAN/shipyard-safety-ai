"""중복 제거, 정렬, Alert ID 재현성 단위 테스트."""

from __future__ import annotations

from app.domain.enums import WorkType
from app.domain.rules import make_alert_id
from tests.factories import evaluate, make_item


def test_pair_alert_ids_are_sorted_lexicographically():
    alerts = evaluate(
        [
            make_item("B", WorkType.PAINTING, "Z1", 11, 14),
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
        ]
    )
    assert alerts[0].work_item_ids == ("A", "B")


def test_single_item_alert_uses_one_element_list():
    alerts = evaluate([make_item("C1", WorkType.CONFINED_SPACE)])
    assert all(len(alert.work_item_ids) == 1 for alert in alerts)


def test_duplicate_key_produces_single_alert():
    """같은 rule_id와 같은 작업 조합은 하나의 경보로 남는다."""
    items = [
        make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
        make_item("B", WorkType.PAINTING, "Z1", 11, 14),
    ]
    alerts = evaluate(items)
    keys = [alert.duplicate_key for alert in alerts]
    assert len(keys) == len(set(keys)) == 1


def test_sorted_by_severity_then_earliest_start_then_rule_then_ids():
    items = [
        # 늦은 시간의 밀폐공간 경보
        make_item("Z9", WorkType.CONFINED_SPACE, "Z3", 15, 18),
        # 이른 시간의 작업쌍 경보
        make_item("A", WorkType.HOT_WORK, "Z1", 8, 11),
        make_item("B", WorkType.PAINTING, "Z1", 9, 12),
    ]
    alerts = evaluate(items)
    assert alerts[0].rule_id == "R001"
    assert [alert.rule_id for alert in alerts[1:]] == ["R101", "R102", "R103"]


def test_evaluation_is_deterministic_regardless_of_input_order():
    items = [
        make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
        make_item("B", WorkType.PAINTING, "Z1", 11, 14),
        make_item("C", WorkType.CONFINED_SPACE, "Z3", 9, 12),
    ]
    first = evaluate(items)
    second = evaluate(list(reversed(items)))
    assert [(a.rule_id, a.work_item_ids, a.id) for a in first] == [(b.rule_id, b.work_item_ids, b.id) for b in second]


def test_alert_id_is_reproducible_from_analysis_id_and_duplicate_key():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z1", 11, 14),
        ],
        analysis_id="AN_FIXED",
    )
    assert alerts[0].id == make_alert_id("AN_FIXED", "R001|A,B")


def test_pair_evidence_contains_required_fields():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z2", 11, 14),
        ]
    )
    evidence = alerts[0].evidence
    assert {"work_items", "spatial_relation", "overlap_start", "overlap_end", "overlap_minutes"} <= set(evidence)
    assert [item["id"] for item in evidence["work_items"]] == ["A", "B"]
    assert {"work_type", "zone_id", "zone_name"} <= set(evidence["work_items"][0])
    assert alerts[0].recommended_action
