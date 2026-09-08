from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import SourceType, WorkStatus, WorkType


class WorkItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=100, examples=["A블록 1구역 보강재 용접"])
    description: str | None = Field(default=None, max_length=2000)
    work_type: WorkType
    zone_id: str = Field(min_length=1, max_length=64, examples=["A_BLOCK_1"])
    start_at: datetime = Field(examples=["2026-03-16T09:00:00+09:00"])
    end_at: datetime = Field(examples=["2026-03-16T12:00:00+09:00"])
    uses_flammable_material: bool | None = None
    gas_measurement_completed: bool | None = None
    ventilation_confirmed: bool | None = None
    watcher_assigned: bool | None = None
    status: WorkStatus = WorkStatus.DRAFT
    external_id: str | None = Field(default=None, max_length=128)


class WorkItemCreate(WorkItemBase):
    id: str | None = Field(default=None, max_length=64, description="생략하면 서버가 생성한다.")
    source_type: SourceType = SourceType.MANUAL


class WorkItemUpdate(WorkItemBase):
    source_type: SourceType | None = None


class WorkItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    work_type: WorkType
    zone_id: str
    zone_name: str | None = None
    start_at: datetime
    end_at: datetime
    uses_flammable_material: bool | None
    gas_measurement_completed: bool | None
    ventilation_confirmed: bool | None
    watcher_assigned: bool | None
    status: WorkStatus
    source_type: SourceType
    external_id: str | None
    created_at: datetime
    updated_at: datetime
    has_alert: bool | None = Field(default=None, description="최근 분석 결과 기준 경보 여부")


class WorkItemListResponse(BaseModel):
    items: list[WorkItemOut]
    total: int
    page: int
    page_size: int
