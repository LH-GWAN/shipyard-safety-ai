"""작업쌍 규칙(R001~R003) 단위 테스트."""

from __future__ import annotations

from app.domain.enums import WorkType
from tests.factories import evaluate, make_item


def rule_ids(alerts) -> list[str]:
    return [alert.rule_id for alert in alerts]


def test_r001_same_zone_positive():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z1", 11, 14),
        ]
    )
    assert rule_ids(alerts) == ["R001"]
    alert = alerts[0]
    assert alert.work_item_ids == ("A", "B")
    assert alert.severity.value == "HIGH"
    assert alert.evidence["spatial_relation"] == "SAME"
    assert alert.evidence["overlap_minutes"] == 60
    assert alert.evidence["overlap_start"].startswith("2026-03-16T11:00")
    assert alert.evidence["overlap_end"].startswith("2026-03-16T12:00")


def test_r001_adjacent_zone_positive():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z2", 13, 16),
            make_item("B", WorkType.PAINTING, "Z1", 15, 17),
        ]
    )
    assert rule_ids(alerts) == ["R001"]
    assert alerts[0].evidence["spatial_relation"] == "ADJACENT"


def test_r001_negative_when_zones_unrelated():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z3", 10, 13),
        ]
    )
    assert alerts == []


def test_r001_negative_on_boundary_touch():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z1", 12, 15),
        ]
    )
    assert alerts == []


def test_r002_positive_and_negative():
    positive = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 8, 11),
            make_item("B", WorkType.SOLVENT_WORK, "Z1", 10, 12),
        ]
    )
    assert rule_ids(positive) == ["R002"]

    negative = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 8, 11),
            make_item("B", WorkType.SOLVENT_WORK, "Z3", 10, 12),
        ]
    )
    assert negative == []


def test_r003_positive_with_flammable_true():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.OTHER, "Z2", 10, 13, uses_flammable_material=True),
        ]
    )
    assert rule_ids(alerts) == ["R003"]
    assert alerts[0].evidence["flammable_work_item_id"] == "B"
    assert alerts[0].evidence["overlap_minutes"] == 120


def test_r003_negative_when_flammable_null_or_false():
    for value in (None, False):
        alerts = evaluate(
            [
                make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
                make_item("B", WorkType.OTHER, "Z1", 10, 13, uses_flammable_material=value),
            ]
        )
        assert alerts == [], value


def test_r003_suppressed_when_r001_applies():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z1", 10, 13, uses_flammable_material=True),
        ]
    )
    assert rule_ids(alerts) == ["R001"]


def test_r003_suppressed_when_r002_applies():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 8, 11),
            make_item("B", WorkType.SOLVENT_WORK, "Z1", 9, 10, uses_flammable_material=True),
        ]
    )
    assert rule_ids(alerts) == ["R002"]


def test_two_hot_works_do_not_create_pair_alert():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12, uses_flammable_material=True),
            make_item("B", WorkType.HOT_WORK, "Z1", 10, 13, uses_flammable_material=True),
        ]
    )
    assert alerts == []


def test_disabled_rule_is_not_evaluated():
    alerts = evaluate(
        [
            make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
            make_item("B", WorkType.PAINTING, "Z1", 11, 14),
        ],
        disabled=("R001",),
    )
    assert alerts == []
