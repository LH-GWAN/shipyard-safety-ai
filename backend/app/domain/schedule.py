"""규칙형 시간 변경안 계산(순수 함수). 일정 최적화나 AI 추천이 아니다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.models import WorkItemData

DEFAULT_BUFFER_MINUTES = 30
MIN_BUFFER_MINUTES = 0
MAX_BUFFER_MINUTES = 240


@dataclass(frozen=True)
class ShiftProposal:
    work_item_id: str
    before_start_at: datetime
    before_end_at: datetime
    after_start_at: datetime
    after_end_at: datetime
    buffer_minutes: int
    reference_work_item_id: str
    duration_minutes: int


def compute_shift(
    move_item: WorkItemData,
    reference_item: WorkItemData,
    buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
) -> ShiftProposal:
    """이동 작업의 duration을 보존한 채 상대 작업 종료 + buffer 이후로 옮긴다."""
    if not MIN_BUFFER_MINUTES <= buffer_minutes <= MAX_BUFFER_MINUTES:
        raise ValueError("buffer_minutes는 0~240 범위여야 합니다.")

    duration = move_item.end_at - move_item.start_at
    new_start = reference_item.end_at + timedelta(minutes=buffer_minutes)
    new_end = new_start + duration
    return ShiftProposal(
        work_item_id=move_item.id,
        before_start_at=move_item.start_at,
        before_end_at=move_item.end_at,
        after_start_at=new_start,
        after_end_at=new_end,
        buffer_minutes=buffer_minutes,
        reference_work_item_id=reference_item.id,
        duration_minutes=int(duration.total_seconds() // 60),
    )
