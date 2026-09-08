from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import Severity
from app.domain.models import RuleType


class AnalysisRunRequest(BaseModel):
    date: DateType | None = Field(default=None, description="KST 기준 분석 대상 날짜")
    work_item_ids: list[str] | None = Field(default=None, description="분석 대상 작업 ID 목록")


class AlertOut(BaseModel):
    id: str
    rule_id: str
    severity: Severity
    work_item_ids: list[str]
    message: str
    evidence: dict[str, Any]
    recommended_action: str
    created_at: datetime


class SeverityCounts(BaseModel):
    HIGH: int = 0
    MEDIUM: int = 0
    LOW: int = 0


class AnalysisResultOut(BaseModel):
    analysis_id: str
    analyzed_at: datetime
    total_work_items: int
    analyzed_work_items: int
    invalid_work_items: int
    alert_count: int
    severity_counts: SeverityCounts
    duration_ms: float
    alerts: list[AlertOut]


class AlertListResponse(BaseModel):
    analysis_id: str
    items: list[AlertOut]
    total: int


class RuleOut(BaseModel):
    id: str
    name: str
    description: str
    rule_type: RuleType
    severity: Severity
    enabled: bool
    reference_title: str
    reference_url: str | None
    reference_articles: list[str] = Field(default_factory=list)
    reference_note: str = ""
    reference_verified_at: str | None = None
    requires_site_validation: bool = True
    version: str
    reviewed: bool


class RuleListResponse(BaseModel):
    items: list[RuleOut]
    total: int
    alert_rule_count: int = Field(description="경보를 생성하는 규칙 수")
    input_validation_rule_count: int = Field(description="경보를 생성하지 않는 입력 검증 규칙 수")
