"""시간 중첩 계산. 구간은 [start_at, end_at) 방식으로 처리한다."""

from __future__ import annotations

from datetime import datetime

from app.domain.models import WorkItemData


def overlaps(a: WorkItemData, b: WorkItemData) -> bool:
    """a.start < b.end 이고 b.start < a.end 일 때만 중첩으로 본다."""
    return a.start_at < b.end_at and b.start_at < a.end_at


def overlap_window(a: WorkItemData, b: WorkItemData) -> tuple[datetime, datetime] | None:
    if not overlaps(a, b):
        return None
    return max(a.start_at, b.start_at), min(a.end_at, b.end_at)


def overlap_minutes(a: WorkItemData, b: WorkItemData) -> int:
    window = overlap_window(a, b)
    if window is None:
        return 0
    return int((window[1] - window[0]).total_seconds() // 60)
