"""애플리케이션 공통 오류 정의와 FastAPI 예외 처리기."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

HTTP_422_UNPROCESSABLE = 422
HTTP_413_TOO_LARGE = 413


class ErrorCode:
    """안정적인 오류 코드 상수. 값은 API 계약의 일부이므로 변경하지 않는다."""

    INVALID_TIME_RANGE = "INVALID_TIME_RANGE"
    TIMEZONE_REQUIRED = "TIMEZONE_REQUIRED"
    UNKNOWN_ZONE = "UNKNOWN_ZONE"
    DUPLICATE_WORK_ITEM_ID = "DUPLICATE_WORK_ITEM_ID"
    DUPLICATE_ZONE_ID = "DUPLICATE_ZONE_ID"
    WORK_ITEM_NOT_FOUND = "WORK_ITEM_NOT_FOUND"
    INVALID_CSV_HEADER = "INVALID_CSV_HEADER"
    INVALID_CSV_VALUE = "INVALID_CSV_VALUE"
    CSV_LIMIT_EXCEEDED = "CSV_LIMIT_EXCEEDED"
    INVALID_CSV_FILE = "INVALID_CSV_FILE"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
    ANALYSIS_NOT_FOUND = "ANALYSIS_NOT_FOUND"
    ALERT_NOT_FOUND = "ALERT_NOT_FOUND"
    STALE_SCHEDULE_PREVIEW = "STALE_SCHEDULE_PREVIEW"
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATA_ERROR = "DATA_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """API 응답으로 변환 가능한 도메인/응용 계층 오류."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": {"code": self.code, "message": self.message, "details": self.details}},
        )


class DataFileError(Exception):
    """data/ 하위 합성 데이터 파일이 잘못된 경우."""


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
            fields.append({"field": ".".join(loc), "message": err.get("msg", "")})
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE,
            content=error_body(
                ErrorCode.VALIDATION_ERROR,
                "입력값 검증에 실패했습니다.",
                {"fields": fields},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            404: ErrorCode.INVALID_REQUEST,
            405: ErrorCode.INVALID_REQUEST,
            HTTP_413_TOO_LARGE: ErrorCode.CSV_LIMIT_EXCEEDED,
        }.get(exc.status_code, ErrorCode.INVALID_REQUEST)
        message = exc.detail if isinstance(exc.detail, str) else "요청을 처리할 수 없습니다."
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message))

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        # 내부 스택 추적은 응답에 노출하지 않는다. 상세 내용은 서버 로그에만 남는다.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(ErrorCode.INTERNAL_ERROR, "서버 내부 오류가 발생했습니다."),
        )
