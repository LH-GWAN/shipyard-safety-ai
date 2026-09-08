from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.schedule import DEFAULT_BUFFER_MINUTES
from app.schemas.analysis import AlertOut, AnalysisResultOut


class ShiftPreviewRequest(BaseModel):
    alert_id: str
    move_work_item_id: str
    buffer_minutes: int = Field(default=DEFAULT_BUFFER_MINUTES, ge=0, le=240)


class ShiftChange(BaseModel):
    work_item_id: str
    title: str
    before_start_at: datetime
    before_end_at: datetime
    after_start_at: datetime
    after_end_at: datetime
    duration_minutes: int
    buffer_minutes: int
    reference_work_item_id: str


class ShiftPreviewResponse(BaseModel):
    preview_token: str
    alert_id: str
    change: ShiftChange
    resolved_alerts: list[AlertOut]
    new_alerts: list[AlertOut]
    remaining_alert_count: int
    before_alert_count: int
    after_alert_count: int


class ShiftApplyRequest(BaseModel):
    alert_id: str
    move_work_item_id: str
    buffer_minutes: int = Field(default=DEFAULT_BUFFER_MINUTES, ge=0, le=240)
    preview_token: str = Field(
        min_length=1,
        description="preview-shift 응답의 토큰. 사용자가 변경안을 확인했음을 보증하는 필수 값이다.",
    )


class ShiftApplyResponse(BaseModel):
    change: ShiftChange
    analysis: AnalysisResultOut
    resolved_alerts: list[AlertOut]
    new_alerts: list[AlertOut]
