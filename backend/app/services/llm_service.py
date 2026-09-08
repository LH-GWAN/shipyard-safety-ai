"""자연어 작업설명 구조화 서비스."""

from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import HTTP_422_UNPROCESSABLE, AppError, ErrorCode
from app.core.logging import log_event
from app.llm.base import (
    AllowedZone,
    LLMAdapter,
    LLMOutputInvalidError,
    LLMUnavailableError,
    ParsedWorkItemDraft,
    compute_missing_fields,
)
from app.llm.factory import get_llm_adapter
from app.repositories.zone_repository import ZoneRepository
from app.schemas.llm import ParseDescriptionResponse

MOCK_NOTICE = "키워드 인식 방식(모의 어댑터)으로 읽은 결과입니다. 더 자세한 결과를 얻으려면 LLM API 키가 필요합니다."
REAL_NOTICE = "LLM 구조화 결과입니다. 위험 판정과 등급은 규칙 엔진이 결정하며 LLM이 변경하지 않습니다."


class DescriptionParsingService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        adapter: LLMAdapter | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.zones = ZoneRepository(session)
        self._adapter = adapter

    def adapter(self) -> LLMAdapter:
        if self._adapter is not None:
            return self._adapter
        try:
            return get_llm_adapter(self.settings)
        except LLMUnavailableError as exc:
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                str(exc),
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

    def parse(self, text: str) -> ParseDescriptionResponse:
        adapter = self.adapter()
        allowed = [AllowedZone(id=zone.id, name=zone.name) for zone in self.zones.list_all()]
        try:
            draft = adapter.parse_work_description(text, allowed)
        except LLMUnavailableError as exc:
            log_event("llm_unavailable", provider=adapter.provider, reason=type(exc).__name__)
            raise AppError(
                ErrorCode.LLM_UNAVAILABLE,
                "LLM 공급자를 사용할 수 없습니다. 직접 입력 또는 CSV 업로드를 이용하십시오.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {"provider": adapter.provider},
            ) from exc
        except LLMOutputInvalidError as exc:
            log_event("llm_output_invalid", provider=adapter.provider)
            raise AppError(
                ErrorCode.LLM_OUTPUT_INVALID,
                "구조화 결과가 형식 검증을 통과하지 못했습니다. 직접 입력으로 작성하십시오.",
                HTTP_422_UNPROCESSABLE,
                {"provider": adapter.provider, "reason": str(exc)},
            ) from exc

        draft = self._enforce_allowed_zone(draft, {zone.id for zone in allowed})
        # 자연어 원문 전체는 로그에 남기지 않는다.
        log_event(
            "description_parsed",
            provider=adapter.provider,
            is_mock=adapter.is_mock,
            text_length=len(text),
            missing_field_count=len(draft.missing_fields),
        )
        return ParseDescriptionResponse(
            draft=draft,
            llm_enabled=self.settings.llm_enabled,
            provider=adapter.provider,
            is_mock=adapter.is_mock,
            notice=MOCK_NOTICE if adapter.is_mock else REAL_NOTICE,
        )

    @staticmethod
    def _enforce_allowed_zone(draft: ParsedWorkItemDraft, allowed_ids: set[str]) -> ParsedWorkItemDraft:
        zone_id = draft.values.zone_id
        if zone_id and zone_id not in allowed_ids:
            draft.evidence.setdefault("zone_id", zone_id)
            draft.ambiguities.append(f"허용 구역과 일치하지 않는 위치 표현입니다: {zone_id}")
            draft.values.zone_id = None
            draft.field_confidence["zone_id"] = None
        draft.missing_fields = compute_missing_fields(draft.values)
        return draft
