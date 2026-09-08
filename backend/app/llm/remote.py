"""실제 LLM 공급자 어댑터.

LLM_PROVIDER와 LLM_API_KEY가 모두 설정된 경우에만 사용한다.
공급자별 요청/응답 처리는 이 모듈 안에 가둔다.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.llm.base import (
    OUTPUT_JSON_SCHEMA,
    SYSTEM_INSTRUCTION,
    AllowedZone,
    LLMAdapter,
    LLMOutputInvalidError,
    LLMUnavailableError,
    ParsedWorkItemDraft,
    compute_missing_fields,
)

TOOL_NAME = "emit_work_item_draft"


def _user_prompt(text: str, allowed_zones: list[AllowedZone]) -> str:
    zone_lines = "\n".join(f"- {zone.id} ({zone.name})" for zone in allowed_zones)
    return f"허용 구역 목록:\n{zone_lines}\n\n다음 작업설명에서 명시된 사실만 추출하라.\n작업설명:\n{text}"


class AnthropicAdapter(LLMAdapter):
    provider = "anthropic"
    is_mock = False

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def parse_work_description(self, text: str, allowed_zones: list[AllowedZone]) -> ParsedWorkItemDraft:
        payload = {
            "model": self._model,
            "max_tokens": 1024,
            "system": SYSTEM_INSTRUCTION,
            "tools": [
                {
                    "name": TOOL_NAME,
                    "description": "작업설명에서 추출한 구조화 초안을 반환한다.",
                    "input_schema": OUTPUT_JSON_SCHEMA,
                }
            ],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
            "messages": [{"role": "user", "content": _user_prompt(text, allowed_zones)}],
        }
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailableError(f"anthropic 호출에 실패했습니다: {type(exc).__name__}") from exc

        for block in body.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == TOOL_NAME:
                return _validate(block.get("input", {}), self.provider)
        raise LLMOutputInvalidError("구조화 결과 블록을 찾지 못했습니다.")


class OpenAIAdapter(LLMAdapter):
    provider = "openai"
    is_mock = False

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def parse_work_description(self, text: str, allowed_zones: list[AllowedZone]) -> ParsedWorkItemDraft:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": _user_prompt(text, allowed_zones)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": TOOL_NAME, "schema": OUTPUT_JSON_SCHEMA, "strict": False},
            },
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMUnavailableError(f"openai 호출에 실패했습니다: {type(exc).__name__}") from exc

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMOutputInvalidError("구조화 결과가 JSON이 아닙니다.") from exc
        return _validate(parsed, self.provider)


def _validate(raw: dict[str, Any], provider: str) -> ParsedWorkItemDraft:
    """공급자 응답을 Pydantic으로 다시 검증한다."""
    try:
        draft = ParsedWorkItemDraft.model_validate({**raw, "provider": provider})
    except ValidationError as exc:
        raise LLMOutputInvalidError(_summarize(exc)) from exc
    if not draft.missing_fields:
        draft.missing_fields = compute_missing_fields(draft.values)
    return draft


def _summarize(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors()[:5]:
        loc = ".".join(str(p) for p in error.get("loc", []))
        parts.append(f"{loc}: {error.get('msg')}")
    return "; ".join(parts) or "구조화 결과 검증에 실패했습니다."
