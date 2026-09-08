"""시간 중첩 계산 단위 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.timeutil import KST
from app.domain.enums import WorkType
from app.domain.models import WorkItemData
from app.domain.overlap import overlap_minutes, overlap_window, overlaps


def item(item_id: str, start_hour: int, end_hour: int, zone: str = "Z1") -> WorkItemData:
    day = datetime(2026, 3, 16, tzinfo=KST)
    return WorkItemData(
        id=item_id,
        title=item_id,
        work_type=WorkType.OTHER,
        zone_id=zone,
        start_at=day + timedelta(hours=start_hour),
        end_at=day + timedelta(hours=end_hour),
    )


def test_overlaps_general_case():
    assert overlaps(item("A", 9, 12), item("B", 11, 14)) is True


def test_overlaps_returns_false_when_separated():
    assert overlaps(item("A", 8, 10), item("B", 12, 15)) is False


def test_boundary_touch_is_not_overlap():
    """A의 종료시각과 B의 시작시각이 같으면 중첩이 아니다."""
    assert overlaps(item("A", 9, 12), item("B", 12, 15)) is False
    assert overlaps(item("B", 12, 15), item("A", 9, 12)) is False


def test_containment_is_overlap():
    assert overlaps(item("A", 8, 18), item("B", 10, 11)) is True


def test_overlap_window_and_minutes():
    a, b = item("A", 9, 12), item("B", 11, 14)
    start, end = overlap_window(a, b)
    assert (start.hour, end.hour) == (11, 12)
    assert overlap_minutes(a, b) == 60


def test_overlap_window_is_none_without_overlap():
    assert overlap_window(item("A", 9, 12), item("B", 12, 13)) is None
    assert overlap_minutes(item("A", 9, 12), item("B", 12, 13)) == 0
