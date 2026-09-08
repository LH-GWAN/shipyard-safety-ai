from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import ErrorResponse
from app.schemas.schedule import (
    ShiftApplyRequest,
    ShiftApplyResponse,
    ShiftPreviewRequest,
    ShiftPreviewResponse,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

RESPONSES = {
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/preview-shift",
    response_model=ShiftPreviewResponse,
    responses=RESPONSES,
    summary="시간 변경안 미리보기(원본을 변경하지 않음)",
)
def preview_shift(payload: ShiftPreviewRequest, session: Session = Depends(get_db)) -> ShiftPreviewResponse:
    return ScheduleService(session).preview(payload)


@router.post(
    "/apply-shift",
    response_model=ShiftApplyResponse,
    responses=RESPONSES,
    summary="시간 변경안 적용 후 전체 재분석",
)
def apply_shift(payload: ShiftApplyRequest, session: Session = Depends(get_db)) -> ShiftApplyResponse:
    return ScheduleService(session).apply(payload)
