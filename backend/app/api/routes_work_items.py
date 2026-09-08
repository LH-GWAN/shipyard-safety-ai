from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.errors import HTTP_413_TOO_LARGE, AppError, ErrorCode
from app.domain.enums import WorkStatus, WorkType
from app.schemas.common import ErrorResponse
from app.schemas.csv_import import CsvImportResponse
from app.schemas.llm import ParseDescriptionRequest, ParseDescriptionResponse
from app.schemas.work_item import WorkItemCreate, WorkItemListResponse, WorkItemOut, WorkItemUpdate
from app.services.csv_service import CsvImportService
from app.services.llm_service import DescriptionParsingService
from app.services.work_item_service import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, WorkItemService

router = APIRouter(prefix="/api/work-items", tags=["work-items"])

ERROR_RESPONSES = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("", response_model=WorkItemListResponse, summary="작업계획 목록 조회")
def list_work_items(
    session: Session = Depends(get_db),
    date_: date | None = Query(default=None, alias="date", description="KST 기준 날짜"),
    work_type: WorkType | None = Query(default=None),
    zone_id: str | None = Query(default=None),
    status_: WorkStatus | None = Query(default=None, alias="status"),
    has_alert: bool | None = Query(default=None, description="최근 분석 결과 기준"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> WorkItemListResponse:
    return WorkItemService(session).list(
        day=date_,
        work_type=work_type.value if work_type else None,
        zone_id=zone_id,
        item_status=status_.value if status_ else None,
        has_alert=has_alert,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=WorkItemOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
    summary="작업계획 등록",
)
def create_work_item(payload: WorkItemCreate, session: Session = Depends(get_db)) -> WorkItemOut:
    return WorkItemService(session).create(payload)


@router.post(
    "/import-csv",
    response_model=CsvImportResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
    summary="CSV 업로드(기본값 validate-only)",
)
async def import_csv(
    file: UploadFile = File(..., description="UTF-8 CSV 파일"),
    commit: bool = Query(default=False, description="true인 경우에만 유효한 행을 저장한다."),
    overwrite: bool = Query(default=False, description="이미 존재하는 id를 덮어쓸지 여부"),
    session: Session = Depends(get_db),
) -> CsvImportResponse:
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.max_csv_bytes:
        raise AppError(
            ErrorCode.CSV_LIMIT_EXCEEDED,
            f"CSV 파일 크기가 제한({settings.max_csv_bytes} bytes)을 초과했습니다.",
            HTTP_413_TOO_LARGE,
            {"size": len(content), "limit": settings.max_csv_bytes},
        )
    return CsvImportService(session, settings).import_csv(
        filename=file.filename,
        content_type=file.content_type,
        content=content,
        commit=commit,
        overwrite=overwrite,
    )


@router.post(
    "/parse-description",
    response_model=ParseDescriptionResponse,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="자연어 작업설명 구조화(초안 반환, 저장하지 않음)",
)
def parse_description(
    payload: ParseDescriptionRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> ParseDescriptionResponse:
    del request
    return DescriptionParsingService(session).parse(payload.text)


@router.get("/{work_item_id}", response_model=WorkItemOut, responses=ERROR_RESPONSES, summary="작업계획 상세 조회")
def get_work_item(work_item_id: str, session: Session = Depends(get_db)) -> WorkItemOut:
    return WorkItemService(session).get(work_item_id)


@router.put("/{work_item_id}", response_model=WorkItemOut, responses=ERROR_RESPONSES, summary="작업계획 수정")
def update_work_item(work_item_id: str, payload: WorkItemUpdate, session: Session = Depends(get_db)) -> WorkItemOut:
    return WorkItemService(session).update(work_item_id, payload)


@router.delete(
    "/{work_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="작업계획 삭제",
)
def delete_work_item(work_item_id: str, session: Session = Depends(get_db)) -> None:
    WorkItemService(session).delete(work_item_id)
