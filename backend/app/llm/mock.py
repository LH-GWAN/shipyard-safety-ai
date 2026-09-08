"""결정론적 모의 어댑터.

명시적 키워드와 ISO 8601 날짜시간만 추출한다. 무작위값이나 추정을 사용하지 않는다.
"""

from __future__ import annotations

import re

from app.domain.enums import WorkType
from app.llm.base import (
    AllowedZone,
    DraftValues,
    LLMAdapter,
    ParsedWorkItemDraft,
    compute_missing_fields,
)

KEYWORDS: list[tuple[tuple[str, ...], WorkType]] = [
    (("밀폐공간", "탱크 내부"), WorkType.CONFINED_SPACE),
    (("유기용제", "시너"), WorkType.SOLVENT_WORK),
    (("도장",), WorkType.PAINTING),
    (("용접", "절단", "화기"), WorkType.HOT_WORK),
]

ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})")


class MockLLMAdapter(LLMAdapter):
    provider = "mock"
    is_mock = True

    def parse_work_description(self, text: str, allowed_zones: list[AllowedZone]) -> ParsedWorkItemDraft:
        evidence: dict[str, str] = {}
        ambiguities: list[str] = []
        raw = text.strip()

        work_type, work_type_evidence = self._match_work_type(raw)
        if work_type_evidence:
            evidence["work_type"] = work_type_evidence

        zone_id, zone_evidence = self._match_zone(raw, allowed_zones)
        if zone_evidence:
            evidence["zone_id"] = zone_evidence
        elif zone_id is None:
            ambiguities.append("허용된 구역 ID 또는 구역명과 정확히 일치하는 표현을 찾지 못했습니다.")

        matches = [m.group(0) for m in ISO_DATETIME.finditer(raw)]
        start_raw = matches[0] if matches else None
        end_raw = matches[1] if len(matches) > 1 else None
        if start_raw:
            evidence["start_at"] = start_raw
        if end_raw:
            evidence["end_at"] = end_raw
        if len(matches) > 2:
            ambiguities.append("시각 표현이 3개 이상 발견되어 앞의 두 개만 사용했습니다.")
        if not matches:
            ambiguities.append("표준시간대를 포함한 ISO 8601 시각 표현을 찾지 못했습니다.")

        title = self._title_candidate(raw)
        if title:
            evidence["title"] = title

        values = DraftValues(
            title=title,
            work_type=work_type,
            zone_id=zone_id,
            start_at=self._normalize(start_raw),
            end_at=self._normalize(end_raw),
        )
        confidence = {
            "title": 0.4 if title else None,
            "work_type": 0.9 if work_type else None,
            "zone_id": 0.9 if zone_id else None,
            "start_at": 0.9 if values.start_at else None,
            "end_at": 0.9 if values.end_at else None,
            "uses_flammable_material": None,
            "gas_measurement_completed": None,
            "ventilation_confirmed": None,
            "watcher_assigned": None,
        }
        return ParsedWorkItemDraft(
            values=values,
            field_confidence=confidence,
            evidence=evidence,
            ambiguities=ambiguities,
            missing_fields=compute_missing_fields(values),
            provider=self.provider,
        )

    @staticmethod
    def _match_work_type(text: str) -> tuple[WorkType | None, str | None]:
        for keywords, work_type in KEYWORDS:
            for keyword in keywords:
                if keyword in text:
                    return work_type, keyword
        return None, None

    @staticmethod
    def _match_zone(text: str, allowed_zones: list[AllowedZone]) -> tuple[str | None, str | None]:
        for zone in allowed_zones:
            if zone.id and zone.id in text:
                return zone.id, zone.id
        for zone in allowed_zones:
            if zone.name and zone.name in text:
                return zone.id, zone.name
        return None, None

    @staticmethod
    def _normalize(value: str | None) -> str | None:
        if value is None:
            return None
        return value.replace(" ", "T")

    @staticmethod
    def _title_candidate(text: str) -> str | None:
        first_line = text.splitlines()[0].strip() if text.strip() else ""
        if not first_line:
            return None
        return first_line[:100]
