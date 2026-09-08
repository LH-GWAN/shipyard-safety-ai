"""실제 LLM 공급자 어댑터의 코드 경로를 API 키 없이 검증한다.

httpx 호출만 스텁으로 가로채고, 요청 구성·응답 파싱·오류 분류·재검증은 실제 코드를 실행한다.
네트워크로 나가는 요청은 없다.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.llm import remote
from app.llm.base import (
    OUTPUT_JSON_SCHEMA,
    SYSTEM_INSTRUCTION,
    AllowedZone,
    LLMOutputInvalidError,
    LLMUnavailableError,
)
from app.llm.factory import get_llm_adapter
from app.llm.remote import TOOL_NAME, AnthropicAdapter, OpenAIAdapter
from app.services.llm_service import DescriptionParsingService

ZONES = [AllowedZone(id="A_BLOCK_1", name="A블록 1구역"), AllowedZone(id="TANK_A", name="탱크 A")]

DRAFT_PAYLOAD = {
    "values": {
        "title": "보강재 용접",
        "work_type": "HOT_WORK",
        "zone_id": "A_BLOCK_1",
        "start_at": "2026-03-16T09:00:00+09:00",
        "end_at": "2026-03-16T12:00:00+09:00",
        "uses_flammable_material": None,
        "gas_measurement_completed": None,
        "ventilation_confirmed": None,
        "watcher_assigned": None,
    },
    "field_confidence": {"work_type": 0.9, "zone_id": 0.8},
    "evidence": {"work_type": "용접", "zone_id": "A_BLOCK_1"},
    "ambiguities": [],
    "missing_fields": [],
}


class StubResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def captured(monkeypatch):
    """httpx.post를 가로채 요청을 기록하고 미리 정한 응답을 돌려준다."""
    calls: list[dict] = []
    state: dict = {"response": None, "raises": None}

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002
        calls.append({"url": url, "headers": headers or {}, "json": json or {}, "timeout": timeout})
        if state["raises"] is not None:
            raise state["raises"]
        return state["response"]

    monkeypatch.setattr(remote.httpx, "post", fake_post)
    return {"calls": calls, "state": state}


# ------------------------------------------------------------------ Anthropic
def test_anthropic_request_is_built_from_code_managed_schema(captured):
    captured["state"]["response"] = StubResponse(
        {"content": [{"type": "tool_use", "name": TOOL_NAME, "input": DRAFT_PAYLOAD}]}
    )
    adapter = AnthropicAdapter("test-key", "claude-sonnet-5", 20.0)

    draft = adapter.parse_work_description("A_BLOCK_1에서 보강재 용접", ZONES)

    request = captured["calls"][0]
    assert request["url"] == "https://api.anthropic.com/v1/messages"
    assert request["headers"]["x-api-key"] == "test-key"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["timeout"] == 20.0
    assert request["json"]["model"] == "claude-sonnet-5"
    assert request["json"]["system"] == SYSTEM_INSTRUCTION
    assert request["json"]["tools"][0]["input_schema"] == OUTPUT_JSON_SCHEMA
    assert request["json"]["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    # 허용 구역 목록과 원문만 전달하고 사용자 식별정보는 보내지 않는다.
    prompt = request["json"]["messages"][0]["content"]
    assert "A_BLOCK_1 (A블록 1구역)" in prompt
    assert "보강재 용접" in prompt

    assert draft.provider == "anthropic"
    assert draft.values.work_type.value == "HOT_WORK"
    assert draft.values.start_at.hour == 9
    assert draft.field_confidence["work_type"] == 0.9


def test_anthropic_response_without_tool_block_is_output_invalid(captured):
    captured["state"]["response"] = StubResponse({"content": [{"type": "text", "text": "설명문"}]})
    with pytest.raises(LLMOutputInvalidError):
        AnthropicAdapter("test-key", "claude-sonnet-5", 20.0).parse_work_description("용접", ZONES)


def test_anthropic_invalid_enum_is_rejected_by_revalidation(captured):
    broken = {**DRAFT_PAYLOAD, "values": {**DRAFT_PAYLOAD["values"], "work_type": "WELDING"}}
    captured["state"]["response"] = StubResponse(
        {"content": [{"type": "tool_use", "name": TOOL_NAME, "input": broken}]}
    )
    with pytest.raises(LLMOutputInvalidError):
        AnthropicAdapter("test-key", "claude-sonnet-5", 20.0).parse_work_description("용접", ZONES)


def test_anthropic_naive_datetime_is_rejected_by_revalidation(captured):
    broken = {**DRAFT_PAYLOAD, "values": {**DRAFT_PAYLOAD["values"], "start_at": "2026-03-16T09:00:00"}}
    captured["state"]["response"] = StubResponse(
        {"content": [{"type": "tool_use", "name": TOOL_NAME, "input": broken}]}
    )
    with pytest.raises(LLMOutputInvalidError):
        AnthropicAdapter("test-key", "claude-sonnet-5", 20.0).parse_work_description("용접", ZONES)


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectTimeout("timeout"),
        httpx.ReadTimeout("read timeout"),
        httpx.ConnectError("connection refused"),
    ],
)
def test_anthropic_transport_failure_is_unavailable(captured, failure):
    captured["state"]["raises"] = failure
    with pytest.raises(LLMUnavailableError):
        AnthropicAdapter("test-key", "claude-sonnet-5", 20.0).parse_work_description("용접", ZONES)


def test_anthropic_http_error_status_is_unavailable(captured):
    captured["state"]["response"] = StubResponse({}, status_code=401)
    with pytest.raises(LLMUnavailableError):
        AnthropicAdapter("bad-key", "claude-sonnet-5", 20.0).parse_work_description("용접", ZONES)


# --------------------------------------------------------------------- OpenAI
def test_openai_request_uses_structured_outputs(captured):
    captured["state"]["response"] = StubResponse({"choices": [{"message": {"content": json.dumps(DRAFT_PAYLOAD)}}]})
    adapter = OpenAIAdapter("test-key", "gpt-test", 15.0)

    draft = adapter.parse_work_description("A_BLOCK_1에서 보강재 용접", ZONES)

    request = captured["calls"][0]
    assert request["url"] == "https://api.openai.com/v1/chat/completions"
    assert request["headers"]["authorization"] == "Bearer test-key"
    assert request["json"]["response_format"]["json_schema"]["schema"] == OUTPUT_JSON_SCHEMA
    assert request["json"]["messages"][0]["content"] == SYSTEM_INSTRUCTION
    assert draft.provider == "openai"
    assert draft.values.zone_id == "A_BLOCK_1"


def test_openai_non_json_content_is_output_invalid(captured):
    captured["state"]["response"] = StubResponse({"choices": [{"message": {"content": "죄송합니다"}}]})
    with pytest.raises(LLMOutputInvalidError):
        OpenAIAdapter("test-key", "gpt-test", 15.0).parse_work_description("용접", ZONES)


def test_openai_malformed_envelope_is_unavailable(captured):
    captured["state"]["response"] = StubResponse({"unexpected": True})
    with pytest.raises(LLMUnavailableError):
        OpenAIAdapter("test-key", "gpt-test", 15.0).parse_work_description("용접", ZONES)


# ----------------------------------------------------- 서비스 계층까지의 연결
def remote_settings() -> Settings:
    return Settings(llm_provider="anthropic", llm_api_key="test-key", llm_model="claude-sonnet-5")


def test_factory_and_service_use_remote_adapter_end_to_end(session, captured):
    captured["state"]["response"] = StubResponse(
        {"content": [{"type": "tool_use", "name": TOOL_NAME, "input": DRAFT_PAYLOAD}]}
    )
    settings = remote_settings()
    assert get_llm_adapter(settings).provider == "anthropic"

    result = DescriptionParsingService(session, settings).parse("A_BLOCK_1에서 보강재 용접")

    assert result.is_mock is False
    assert result.llm_enabled is True
    assert result.provider == "anthropic"
    assert result.draft.values.zone_id == "A_BLOCK_1"
    assert "모의 어댑터" not in result.notice


def test_service_maps_transport_failure_to_503(session, captured):
    captured["state"]["raises"] = httpx.ConnectTimeout("timeout")
    with pytest.raises(AppError) as caught:
        DescriptionParsingService(session, remote_settings()).parse("용접 작업")
    assert caught.value.code == "LLM_UNAVAILABLE"
    assert caught.value.status_code == 503


def test_service_maps_invalid_output_to_422(session, captured):
    captured["state"]["response"] = StubResponse({"content": [{"type": "text", "text": "설명"}]})
    with pytest.raises(AppError) as caught:
        DescriptionParsingService(session, remote_settings()).parse("용접 작업")
    assert caught.value.code == "LLM_OUTPUT_INVALID"
    assert caught.value.status_code == 422


def test_hallucinated_zone_from_remote_provider_is_dropped(session, captured):
    payload = {
        **DRAFT_PAYLOAD,
        "values": {**DRAFT_PAYLOAD["values"], "zone_id": "GHOST_ZONE"},
        "evidence": {"work_type": "용접"},
    }
    captured["state"]["response"] = StubResponse(
        {"content": [{"type": "tool_use", "name": TOOL_NAME, "input": payload}]}
    )
    result = DescriptionParsingService(session, remote_settings()).parse("없는 구역에서 용접")
    assert result.draft.values.zone_id is None
    assert any("허용 구역" in item for item in result.draft.ambiguities)
    assert result.draft.evidence["zone_id"] == "GHOST_ZONE"


def test_remote_failure_does_not_break_rules_engine(client, captured, data_dir):
    """LLM이 실패해도 CSV 업로드와 규칙 검사는 그대로 동작한다."""
    captured["state"]["raises"] = httpx.ConnectError("down")
    csv_text = (data_dir / "work_items.csv").read_text(encoding="utf-8")
    files = {"file": ("work_items.csv", csv_text.encode("utf-8"), "text/csv")}
    assert client.post("/api/work-items/import-csv", files=files, params={"commit": True}).status_code == 200
    assert client.post("/api/analysis/run", json={}).json()["alert_count"] == 19
