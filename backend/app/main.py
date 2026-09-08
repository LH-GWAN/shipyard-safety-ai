"""YardGuard FastAPI 애플리케이션."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_analysis,
    routes_health,
    routes_schedule,
    routes_work_items,
    routes_zones,
)
from app.core.config import get_settings
from app.core.errors import DataFileError, register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, configure_logging, log_event
from app.db.init_db import init_db

DESCRIPTION = """
YardGuard는 조선소의 여러 작업계획을 작업 시작 전에 비교해 위험한 동시작업과
필수 안전조치 정보 누락을 찾는 사전 검토 보조 도구입니다.

본 API의 결과는 합성 데이터와 사전 정의된 규칙에 기반한 검토 보조정보이며,
작업허가 승인, 법적 적합성 판정, 작업중지 명령이나 설비 제어 기능을 제공하지 않습니다.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    try:
        init_db()
    except DataFileError as exc:
        # 데이터 파일 오류는 시작 시점에 명확한 메시지로 남긴다.
        log_event("data_file_error", message=str(exc))
        raise
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)

    app.include_router(routes_health.router)
    app.include_router(routes_zones.router)
    app.include_router(routes_work_items.router)
    app.include_router(routes_analysis.router)
    app.include_router(routes_schedule.router)
    return app


app = create_app()
