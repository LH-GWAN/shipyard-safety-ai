"""규칙 엔진이 사용하는 순수 도메인 자료구조.

이 모듈은 HTTP, 데이터베이스, LLM, UI에 의존하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.domain.enums import Severity, WorkType


@dataclass(frozen=True)
class ZoneData:
    id: str
    name: str
    adjacent_zone_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkItemData:
    """분석 대상 작업계획. 시간 필드는 반드시 timezone-aware여야 한다."""

    id: str
    title: str
    work_type: WorkType
    zone_id: str
    start_at: datetime
    end_at: datetime
    uses_flammable_material: bool | None = None
    gas_measurement_completed: bool | None = None
    ventilation_confirmed: bool | None = None
    watcher_assigned: bool | None = None

    def duration_minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)


class RuleType(str, Enum):
    """경보를 생성하는 규칙과 입력 검증 전용 규칙을 구분한다."""

    ALERT = "ALERT"
    INPUT_VALIDATION = "INPUT_VALIDATION"


@dataclass(frozen=True)
class RuleSpec:
    id: str
    name: str
    description: str
    severity: Severity
    enabled: bool
    reference_title: str
    reference_url: str | None
    version: str
    reviewed: bool
    rule_type: RuleType = RuleType.ALERT
    reference_articles: tuple[str, ...] = ()
    reference_note: str = ""
    reference_verified_at: str | None = None
    requires_site_validation: bool = True


@dataclass(frozen=True)
class AlertData:
    id: str
    rule_id: str
    severity: Severity
    work_item_ids: tuple[str, ...]
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""
    created_at: datetime | None = None

    @property
    def duplicate_key(self) -> str:
        return f"{self.rule_id}|{','.join(self.work_item_ids)}"
