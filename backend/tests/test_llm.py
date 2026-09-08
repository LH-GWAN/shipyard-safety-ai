"""LLM 구조화 기능 테스트(모의 어댑터, 대체 동작, 잘못된 출력 차단)."""

from __future__ import annotations

import pytest

from app.llm.base import (
    AllowedZone,
    LLMOutputInvalidError,
    LLMUnavailableError,
    ParsedWorkItemDraft,
)
from app.llm.mock import MockLLMAdapter
from app.llm.remote import _validate

ZONES = [AllowedZone(id="A_BLOCK_1", name="A블록 1구역"), AllowedZone(id="TANK_A", name="탱크 A")]


# --------------------------------------------------------------------- 모의 어댑터
@pytest.mark.parametrize(
    "text,expected",
    [
        ("A_BLOCK_1에서 용접 작업", "HOT_WORK"),
        ("절단 작업 예정", "HOT_WORK"),
        ("화기 작업", "HOT_WORK"),
        ("외판 도장 예정", "PAINTING"),
        ("유기용제 세척", "SOLVENT_WORK"),
        ("시너로 세척", "SOLVENT_WORK"),
        ("밀폐공간 내부 점검", "CONFINED_SPACE"),
        ("탱크 내부 청소", "CONFINED_SPACE"),
    ],
)
def test_mock_adapter_maps_keywords(text: str, expected: str):
    draft = MockLLMAdapter().parse_work_description(text, ZONES)
    assert draft.values.work_type.value == expected


def test_mock_adapter_extracts_zone_by_id_and_name():
    by_id = MockLLMAdapter().parse_work_description("A_BLOCK_1 용접", ZONES)
    by_name = MockLLMAdapter().parse_work_description("A블록 1구역 용접", ZONES)
    assert by_id.values.zone_id == "A_BLOCK_1"
    assert by_name.values.zone_id == "A_BLOCK_1"
    assert by_name.evidence["zone_id"] == "A블록 1구역"


def test_mock_adapter_leaves_unknown_zone_as_null_with_ambiguity():
    draft = MockLLMAdapter().parse_work_description("3번 도크 근처에서 용접", ZONES)
    assert draft.values.zone_id is None
    assert draft.ambiguities


def test_mock_adapter_extracts_iso_datetimes_only():
    draft = MockLLMAdapter().parse_work_description(
        "2026-03-16T09:00:00+09:00부터 2026-03-16T12:00:00+09:00까지 A_BLOCK_1 용접", ZONES
    )
    assert draft.values.start_at.hour == 9
    assert draft.values.end_at.hour == 12

    without_iso = MockLLMAdapter().parse_work_description("내일 오전에 A_BLOCK_1 용접", ZONES)
    assert without_iso.values.start_at is None
    assert "start_at" in without_iso.missing_fields


def test_mock_adapter_is_deterministic():
    text = "2026-03-16T09:00:00+09:00 A_BLOCK_1 용접 작업"
    first = MockLLMAdapter().parse_work_description(text, ZONES)
    second = MockLLMAdapter().parse_work_description(text, ZONES)
    assert first.model_dump() == second.model_dump()


def test_mock_adapter_never_infers_safety_fields():
    draft = MockLLMAdapter().parse_work_description("밀폐공간 작업, 환기 완료", ZONES)
    assert draft.values.ventilation_confirmed is None
    assert draft.values.gas_measurement_completed is None
    assert draft.values.watcher_assigned is None
    assert draft.values.uses_flammable_material is None


# ------------------------------------------------------------------- 출력 재검증
def test_invalid_enum_from_provider_is_rejected():
    with pytest.raises(LLMOutputInvalidError):
        _validate({"values": {"work_type": "WELDING"}, "field_confidence": {}}, "openai")


def test_naive_datetime_from_provider_is_rejected():
    with pytest.raises(LLMOutputInvalidError):
        _validate({"values": {"start_at": "2026-03-16T09:00:00"}}, "openai")


def test_out_of_range_confidence_is_rejected():
    with pytest.raises(LLMOutputInvalidError):
        _validate({"values": {}, "field_confidence": {"title": 1.5}}, "anthropic")


def test_valid_provider_output_is_accepted():
    draft = _validate(
        {
            "values": {"title": "용접", "work_type": "HOT_WORK", "start_at": "2026-03-16T09:00:00+09:00"},
            "field_confidence": {"work_type": 0.8},
            "evidence": {"work_type": "용접"},
            "ambiguities": [],
            "missing_fields": [],
        },
        "anthropic",
    )
    assert draft.provider == "anthropic"
    assert "zone_id" in draft.missing_fields


# ------------------------------------------------------------------- 어댑터 선택
def test_factory_returns_mock_without_api_key(monkeypatch):
    from app.core.config import Settings
    from app.llm.factory import get_llm_adapter

    adapter = get_llm_adapter(Settings(llm_provider=None, llm_api_key=None))
    assert adapter.is_mock is True
    assert adapter.provider == "mock"


def test_factory_returns_real_adapter_when_configured():
    from app.core.config import Settings
    from app.llm.factory import get_llm_adapter

    adapter = get_llm_adapter(Settings(llm_provider="anthropic", llm_api_key="test-key"))
    assert adapter.is_mock is False
    assert adapter.provider == "anthropic"


def test_factory_rejects_unknown_provider():
    from app.core.config import Settings
    from app.llm.factory import get_llm_adapter

    with pytest.raises(LLMUnavailableError):
        get_llm_adapter(Settings(llm_provider="unknown", llm_api_key="test-key"))


# ------------------------------------------------------------------------ API
def test_parse_description_uses_mock_and_does_not_save(client):
    response = client.post(
        "/api/work-items/parse-description",
        json={"text": "2026-03-16T09:00:00+09:00부터 2026-03-16T12:00:00+09:00까지 A_BLOCK_1에서 용접"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is True
    assert body["llm_enabled"] is False
    assert "모의 어댑터" in body["notice"]
    assert body["draft"]["values"]["work_type"] == "HOT_WORK"
    assert body["draft"]["values"]["zone_id"] == "A_BLOCK_1"
    assert client.get("/api/work-items").json()["total"] == 0


def test_parse_description_requires_text(client):
    assert client.post("/api/work-items/parse-description", json={"text": ""}).status_code == 422


def test_provider_failure_returns_503(client, monkeypatch):
    from app.llm.base import LLMAdapter
    from app.services import llm_service

    class FailingAdapter(LLMAdapter):
        provider = "anthropic"
        is_mock = False

        def parse_work_description(self, text, allowed_zones):
            raise LLMUnavailableError("timeout")

    monkeypatch.setattr(llm_service, "get_llm_adapter", lambda settings=None: FailingAdapter())
    response = client.post("/api/work-items/parse-description", json={"text": "용접 작업"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_invalid_structured_output_returns_422(client, monkeypatch):
    from app.llm.base import LLMAdapter
    from app.services import llm_service

    class BrokenAdapter(LLMAdapter):
        provider = "openai"
        is_mock = False

        def parse_work_description(self, text, allowed_zones):
            raise LLMOutputInvalidError("work_type: 허용되지 않는 값")

    monkeypatch.setattr(llm_service, "get_llm_adapter", lambda settings=None: BrokenAdapter())
    response = client.post("/api/work-items/parse-description", json={"text": "용접 작업"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LLM_OUTPUT_INVALID"


def test_zone_outside_allowed_list_is_dropped(client, monkeypatch):
    from app.llm.base import DraftValues, LLMAdapter
    from app.services import llm_service

    class HallucinatingAdapter(LLMAdapter):
        provider = "openai"
        is_mock = False

        def parse_work_description(self, text, allowed_zones):
            return ParsedWorkItemDraft(
                values=DraftValues(title="용접", zone_id="GHOST_ZONE"),
                provider=self.provider,
            )

    monkeypatch.setattr(llm_service, "get_llm_adapter", lambda settings=None: HallucinatingAdapter())
    body = client.post("/api/work-items/parse-description", json={"text": "용접 작업"}).json()
    assert body["draft"]["values"]["zone_id"] is None
    assert any("허용 구역" in item for item in body["draft"]["ambiguities"])


def test_csv_and_analysis_work_without_llm(client, data_dir):
    """LLM이 없어도 CSV 업로드와 규칙 검사는 정상 동작한다."""
    csv_text = (data_dir / "work_items.csv").read_text(encoding="utf-8")
    files = {"file": ("work_items.csv", csv_text.encode("utf-8"), "text/csv")}
    imported = client.post("/api/work-items/import-csv", files=files, params={"commit": True})
    assert imported.status_code == 200
    assert client.post("/api/analysis/run", json={}).json()["alert_count"] == 19
