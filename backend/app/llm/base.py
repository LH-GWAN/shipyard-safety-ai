"""LLM 어댑터 인터페이스.

LLM은 자연어를 구조화하는 보조 기능이다. 위험 판정, 등급 결정, 작업 승인에 사용하지 않는다.
"""

from __future__ import annotations

import abc
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.timeutil import is_aware
from app.domain.enums import WorkType

SYSTEM_INSTRUCTION = (
    "당신은 조선소 작업설명 구조화 모듈이다. 입력에 명시된 사실만 추출한다. "
    "없는 값은 null로 반환한다. 작업의 안전성, 허가 가능 여부와 위험등급을 판단하지 않는다. "
    "시간, 구역, 위험물질과 안전조치를 추정하거나 생성하지 않는다. "
    "허용 구역과 일치하지 않는 위치는 zone_id=null로 두고 원문을 evidence에 남긴다. "
    "모순되거나 모호한 표현은 ambiguities에 기록한다."
)

# 실제 공급자의 Structured Outputs에 전달하는 JSON Schema. 코드에서 관리한다.
OUTPUT_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["values", "field_confidence", "evidence", "ambiguities", "missing_fields"],
    "properties": {
        "values": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title",
                "work_type",
                "zone_id",
                "start_at",
                "end_at",
                "uses_flammable_material",
                "gas_measurement_completed",
                "ventilation_confirmed",
                "watcher_assigned",
            ],
            "properties": {
                "title": {"type": ["string", "null"]},
                "work_type": {
                    "type": ["string", "null"],
                    "enum": [*[w.value for w in WorkType], None],
                },
                "zone_id": {"type": ["string", "null"]},
                "start_at": {"type": ["string", "null"], "description": "ISO 8601, 표준시간대 포함"},
                "end_at": {"type": ["string", "null"], "description": "ISO 8601, 표준시간대 포함"},
                "uses_flammable_material": {"type": ["boolean", "null"]},
                "gas_measurement_completed": {"type": ["boolean", "null"]},
                "ventilation_confirmed": {"type": ["boolean", "null"]},
                "watcher_assigned": {"type": ["boolean", "null"]},
            },
        },
        "field_confidence": {"type": "object", "additionalProperties": {"type": ["number", "null"]}},
        "evidence": {"type": "object", "additionalProperties": {"type": "string"}},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
    },
}

DRAFT_FIELDS = tuple(OUTPUT_JSON_SCHEMA["properties"]["values"]["properties"].keys())


class LLMError(Exception):
    """LLM 계층 공통 오류."""


class LLMUnavailableError(LLMError):
    """공급자 호출 실패, 시간초과, 설정 오류."""


class LLMOutputInvalidError(LLMError):
    """스키마 검증에 실패한 구조화 결과."""


class DraftValues(BaseModel):
    """LLM이 채운 필드 값. 저장 전 반드시 이 모델로 재검증한다."""

    title: str | None = Field(default=None, max_length=100)
    work_type: WorkType | None = None
    zone_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    uses_flammable_material: bool | None = None
    gas_measurement_completed: bool | None = None
    ventilation_confirmed: bool | None = None
    watcher_assigned: bool | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and not is_aware(value):
            raise ValueError("시각에는 표준시간대 정보가 있어야 합니다.")
        return value


class ParsedWorkItemDraft(BaseModel):
    values: DraftValues
    field_confidence: dict[str, float | None] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)
    ambiguities: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    provider: str = "mock"

    @field_validator("field_confidence")
    @classmethod
    def _bounded_confidence(cls, value: dict[str, float | None]) -> dict[str, float | None]:
        for key, score in value.items():
            if score is not None and not 0.0 <= score <= 1.0:
                raise ValueError(f"{key}의 confidence는 0.0~1.0이어야 합니다.")
        return value


class AllowedZone(BaseModel):
    id: str
    name: str


class LLMAdapter(abc.ABC):
    """공급자별 구현은 이 인터페이스 뒤에 둔다."""

    provider: str = "mock"
    is_mock: bool = True

    @abc.abstractmethod
    def parse_work_description(self, text: str, allowed_zones: list[AllowedZone]) -> ParsedWorkItemDraft:
        """자연어 작업설명을 구조화 초안으로 변환한다."""


def compute_missing_fields(values: DraftValues) -> list[str]:
    return [name for name in DRAFT_FIELDS if getattr(values, name, None) is None]
