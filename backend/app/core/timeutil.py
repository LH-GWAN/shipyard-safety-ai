"""표준시간대 처리 유틸리티. 기본 표준시간대는 Asia/Seoul이다."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None


def to_kst(value: datetime) -> datetime:
    return value.astimezone(KST)


def iso(value: datetime) -> str:
    """API/근거 표기용 ISO 8601 문자열(KST 기준)."""
    return to_kst(value).isoformat()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """KST 기준 하루의 [시작, 종료) 구간."""
    start = datetime(day.year, day.month, day.day, tzinfo=KST)
    return start, start + timedelta(days=1)
