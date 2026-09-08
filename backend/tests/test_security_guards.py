"""보안·안전 불변식 회귀 테스트.

문제점 점검 항목 12(품질 및 보안 검증)에서 요구한 성질을 코드로 고정한다.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.domain import rules as rules_module
from app.services import llm_service

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_rule_engine_does_not_depend_on_llm_http_or_db():
    """위험 판정 코드는 LLM·HTTP·DB에 의존하지 않는다."""
    source = inspect.getsource(rules_module)
    for forbidden in ("app.llm", "httpx", "requests", "sqlalchemy", "session", "random"):
        assert forbidden not in source, forbidden


def test_rule_engine_never_uses_current_time():
    source = inspect.getsource(rules_module)
    for forbidden in ("datetime.now", "utcnow", "time.time"):
        assert forbidden not in source, forbidden


def test_natural_language_text_is_not_written_to_logs(client, monkeypatch):
    """자연어 원문 전체는 로그에 남기지 않고 길이만 기록한다."""
    captured: list[tuple[str, dict]] = []
    monkeypatch.setattr(llm_service, "log_event", lambda message, **context: captured.append((message, context)))

    secret_sentence = "A_BLOCK_1에서 용접, 담당자 연락처는 비밀입니다"
    response = client.post("/api/work-items/parse-description", json={"text": secret_sentence})
    assert response.status_code == 200

    assert captured, "로그 이벤트가 기록되지 않았습니다."
    for _, context in captured:
        for value in context.values():
            assert secret_sentence not in str(value)
    assert any("text_length" in context for _, context in captured)


def test_csv_error_response_does_not_echo_description(client):
    long_description = "개인정보가 포함될 수 있는 설명 " * 200
    header = (
        "id,title,work_type,zone_id,start_at,end_at,description,"
        "uses_flammable_material,gas_measurement_completed,ventilation_confirmed,watcher_assigned,status"
    )
    row = (
        f"S001,설명 초과,HOT_WORK,TANK_A,2026-03-16T09:00:00+09:00,"
        f"2026-03-16T12:00:00+09:00,{long_description},,,,,DRAFT"
    )
    files = {"file": ("work_items.csv", f"{header}\n{row}".encode(), "text/csv")}
    body = client.post("/api/work-items/import-csv", files=files).json()

    assert body["invalid_count"] == 1
    payload = str(body)
    assert "개인정보가 포함될 수 있는 설명" not in payload


def test_internal_stack_trace_is_not_exposed(client, monkeypatch):
    """예상치 못한 예외가 나도 내부 스택 추적을 응답에 노출하지 않는다."""
    from app.api import routes_zones

    def explode(*args, **kwargs):
        raise RuntimeError("internal detail: /secret/path/module.py line 42")

    monkeypatch.setattr(routes_zones.ZoneRepository, "list_all", explode)

    with pytest.raises(RuntimeError):
        # TestClient는 기본적으로 예외를 다시 던지므로, 핸들러 동작은 raise_server_exceptions=False로 확인한다.
        client.get("/api/zones")

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as safe_client:
        monkeypatch.setattr(routes_zones.ZoneRepository, "list_all", explode)
        response = safe_client.get("/api/zones")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "internal detail" not in str(body)
    assert "Traceback" not in str(body)


def test_llm_api_key_is_read_only_on_backend():
    """LLM 키를 프런트엔드 코드나 클라이언트 번들에서 읽지 않는다."""
    frontend_dir = REPO_ROOT / "frontend"
    scanned = 0
    for path in frontend_dir.rglob("*.ts*"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "LLM_API_KEY" not in text, path
    assert scanned > 0


def test_no_secret_literals_in_repository_sources():
    # 이 파일 자신이 패턴 문자열을 담고 있으므로 조합해서 만들고 자기 자신은 제외한다.
    patterns = ("sk-" + "ant-", "sk-" + "proj-", "AK" + "IA")
    this_file = Path(__file__).resolve()
    for folder in ("backend/app", "backend/tests", "data", "evaluation"):
        for path in (REPO_ROOT / folder).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".csv", ".md"}:
                continue
            if path.resolve() == this_file:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                assert pattern not in text, f"{path}: {pattern}"


def test_upload_limits_are_enforced_by_settings(client):
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.max_csv_bytes == 2 * 1024 * 1024
    assert settings.max_csv_rows == 1000
    assert settings.max_description_length == 2000
