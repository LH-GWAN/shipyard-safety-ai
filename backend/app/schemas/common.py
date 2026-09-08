"""공통 응답 스키마."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(examples=["UNKNOWN_ZONE"])
    message: str = Field(examples=["등록되지 않은 구역입니다."])
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str = "ok"
    llm_enabled: bool = False
    llm_provider: str = "mock"
    zone_count: int = 0
