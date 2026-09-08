from __future__ import annotations

from pydantic import BaseModel, Field


class ZoneCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64, examples=["A_BLOCK_1"])
    name: str = Field(min_length=1, max_length=200, examples=["A블록 1구역"])
    adjacent_zone_ids: list[str] = Field(default_factory=list)


class ZoneOut(BaseModel):
    id: str
    name: str
    adjacent_zone_ids: list[str]


class ZoneListResponse(BaseModel):
    items: list[ZoneOut]
    total: int
