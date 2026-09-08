from __future__ import annotations

from pydantic import BaseModel, Field

from app.llm.base import ParsedWorkItemDraft


class ParseDescriptionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000, examples=["3월 16일 09시부터 12시까지 A_BLOCK_1에서 용접 작업"])


class ParseDescriptionResponse(BaseModel):
    draft: ParsedWorkItemDraft
    llm_enabled: bool
    provider: str
    is_mock: bool
    notice: str
