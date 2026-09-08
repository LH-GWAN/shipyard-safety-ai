"""설정에 따라 LLM 어댑터를 선택한다."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.llm.base import LLMAdapter, LLMUnavailableError
from app.llm.mock import MockLLMAdapter
from app.llm.remote import AnthropicAdapter, OpenAIAdapter

_MOCK = MockLLMAdapter()


def get_llm_adapter(settings: Settings | None = None) -> LLMAdapter:
    """키가 없으면 결정론적 모의 어댑터를 사용한다."""
    settings = settings or get_settings()
    if not settings.llm_enabled:
        return _MOCK

    provider = (settings.llm_provider or "").strip().lower()
    api_key = settings.llm_api_key or ""
    if provider == "anthropic":
        return AnthropicAdapter(api_key, settings.llm_model, settings.llm_timeout_seconds)
    if provider == "openai":
        return OpenAIAdapter(api_key, settings.llm_model, settings.llm_timeout_seconds)
    raise LLMUnavailableError(f"지원하지 않는 LLM 공급자입니다: {settings.llm_provider}")
