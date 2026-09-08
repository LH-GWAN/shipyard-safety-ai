"""시간 변경안 계산 단위 테스트."""

from __future__ import annotations

import pytest

from app.domain.enums import WorkType
from app.domain.schedule import compute_shift
from tests.factories import evaluate, make_item


def test_duration_is_preserved():
    move = make_item("B", WorkType.PAINTING, "Z1", 11, 14)
    reference = make_item("A", WorkType.HOT_WORK, "Z1", 9, 12)
    proposal = compute_shift(move, reference, buffer_minutes=30)

    assert proposal.duration_minutes == 180
    assert proposal.after_start_at.hour == 12 and proposal.after_start_at.minute == 30
    assert proposal.after_end_at.hour == 15 and proposal.after_end_at.minute == 30
    assert (proposal.after_end_at - proposal.after_start_at) == (move.end_at - move.start_at)


def test_zero_buffer_starts_right_after_reference_end():
    proposal = compute_shift(
        make_item("B", WorkType.PAINTING, "Z1", 11, 14),
        make_item("A", WorkType.HOT_WORK, "Z1", 9, 12),
        buffer_minutes=0,
    )
    assert proposal.after_start_at.hour == 12


def test_buffer_out_of_range_is_rejected():
    move = make_item("B", WorkType.PAINTING, "Z1", 11, 14)
    reference = make_item("A", WorkType.HOT_WORK, "Z1", 9, 12)
    for buffer in (-1, 241):
        with pytest.raises(ValueError):
            compute_shift(move, reference, buffer_minutes=buffer)


def test_shift_resolves_original_alert():
    move = make_item("B", WorkType.PAINTING, "Z1", 11, 14)
    reference = make_item("A", WorkType.HOT_WORK, "Z1", 9, 12)
    assert len(evaluate([move, reference])) == 1

    proposal = compute_shift(move, reference, buffer_minutes=30)
    shifted = make_item("B", WorkType.PAINTING, "Z1", 12.5, 15.5)
    assert shifted.start_at == proposal.after_start_at
    assert evaluate([shifted, reference]) == []


def test_shift_can_create_a_new_alert_with_another_work_item():
    """이동한 작업이 다른 작업과 새로 겹치면 신규 경보가 생길 수 있다."""
    move = make_item("B", WorkType.PAINTING, "Z1", 11, 14)
    reference = make_item("A", WorkType.HOT_WORK, "Z1", 9, 12)
    other = make_item("C", WorkType.HOT_WORK, "Z1", 13, 16)

    before = evaluate([move, reference, other])
    assert {alert.duplicate_key for alert in before} == {"R001|A,B", "R001|B,C"}

    proposal = compute_shift(move, reference, buffer_minutes=30)
    shifted = make_item("B", WorkType.PAINTING, "Z1", 12.5, 15.5)
    assert shifted.end_at == proposal.after_end_at
    after = evaluate([shifted, reference, other])
    assert {alert.duplicate_key for alert in after} == {"R001|B,C"}
