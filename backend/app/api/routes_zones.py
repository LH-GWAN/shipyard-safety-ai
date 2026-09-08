from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.errors import HTTP_422_UNPROCESSABLE, AppError, ErrorCode
from app.models.orm import ZoneORM
from app.repositories.zone_repository import ZoneRepository
from app.schemas.common import ErrorResponse
from app.schemas.zone import ZoneCreate, ZoneListResponse, ZoneOut

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("", response_model=ZoneListResponse, summary="구역 목록 조회")
def list_zones(session: Session = Depends(get_db)) -> ZoneListResponse:
    zones = ZoneRepository(session).list_all()
    items = [ZoneOut(id=z.id, name=z.name, adjacent_zone_ids=list(z.adjacent_zone_ids or [])) for z in zones]
    return ZoneListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=ZoneOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="구역 등록",
)
def create_zone(payload: ZoneCreate, session: Session = Depends(get_db)) -> ZoneOut:
    repo = ZoneRepository(session)
    if repo.get(payload.id) is not None:
        raise AppError(
            ErrorCode.DUPLICATE_ZONE_ID,
            f"이미 존재하는 구역 ID입니다: {payload.id}",
            status.HTTP_409_CONFLICT,
            {"id": payload.id},
        )
    if payload.id in payload.adjacent_zone_ids:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "구역은 자기 자신을 인접구역으로 지정할 수 없습니다.",
            HTTP_422_UNPROCESSABLE,
            {"field": "adjacent_zone_ids"},
        )
    unknown = [zone_id for zone_id in payload.adjacent_zone_ids if repo.get(zone_id) is None]
    if unknown:
        raise AppError(
            ErrorCode.UNKNOWN_ZONE,
            "등록되지 않은 인접구역이 있습니다: " + ", ".join(unknown),
            HTTP_422_UNPROCESSABLE,
            {"field": "adjacent_zone_ids", "unknown": unknown},
        )
    zone = repo.add(ZoneORM(id=payload.id, name=payload.name, adjacent_zone_ids=list(payload.adjacent_zone_ids)))
    return ZoneOut(id=zone.id, name=zone.name, adjacent_zone_ids=list(zone.adjacent_zone_ids or []))
