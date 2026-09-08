"""도메인 enum. 프런트엔드 types/domain.ts와 값이 동일해야 한다."""

from __future__ import annotations

from enum import Enum


class WorkType(str, Enum):
    HOT_WORK = "HOT_WORK"
    PAINTING = "PAINTING"
    SOLVENT_WORK = "SOLVENT_WORK"
    CONFINED_SPACE = "CONFINED_SPACE"
    OTHER = "OTHER"


class WorkStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"


class SourceType(str, Enum):
    MANUAL = "MANUAL"
    CSV = "CSV"
    LLM = "LLM"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SpatialRelation(str, Enum):
    SAME = "SAME"
    ADJACENT = "ADJACENT"
    UNRELATED = "UNRELATED"


SEVERITY_ORDER: dict[str, int] = {
    Severity.HIGH.value: 0,
    Severity.MEDIUM.value: 1,
    Severity.LOW.value: 2,
}

SPATIAL_RELATION_KR: dict[str, str] = {
    SpatialRelation.SAME.value: "동일",
    SpatialRelation.ADJACENT.value: "인접",
    SpatialRelation.UNRELATED.value: "무관",
}
