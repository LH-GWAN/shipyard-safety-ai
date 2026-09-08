from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.repositories.zone_repository import ZoneRepository
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="상태 확인")
def health(session: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        llm_enabled=settings.llm_enabled,
        llm_provider=(settings.llm_provider or "mock") if settings.llm_enabled else "mock",
        zone_count=len(ZoneRepository(session).list_all()),
    )
