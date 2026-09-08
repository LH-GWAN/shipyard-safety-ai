from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.work_item import WorkItemCreate


class CsvRowError(BaseModel):
    row_number: int = Field(description="헤더를 1행으로 계산한 행 번호")
    field: str | None
    code: str
    message: str
    raw_value: str | None = Field(default=None, description="개인정보 우려가 있는 값은 반환하지 않는다.")


class CsvValidRow(BaseModel):
    row_number: int
    work_item: WorkItemCreate


class CsvImportResponse(BaseModel):
    total_rows: int
    valid_count: int
    invalid_count: int
    created_count: int
    updated_count: int
    valid_rows: list[CsvValidRow]
    errors: list[CsvRowError]
    committed: bool
