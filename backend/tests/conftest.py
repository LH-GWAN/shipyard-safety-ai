from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.timeutil import KST


@pytest.fixture(scope="function")
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    """테스트마다 독립된 SQLite 파일을 사용하는 API 클라이언트."""
    from app.core.config import get_settings
    from app.db.session import reset_engine

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()
    reset_engine()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def session(client) -> Iterator:
    from app.db.session import get_session_factory

    with get_session_factory()() as db_session:
        yield db_session


@pytest.fixture
def data_dir():
    from app.core.config import get_settings

    return get_settings().data_dir


def kst(day: str, hour: int, minute: int = 0) -> datetime:
    year, month, date_ = (int(part) for part in day.split("-"))
    return datetime(year, month, date_, hour, minute, tzinfo=KST)


def work_item_payload(**overrides) -> dict:
    base = {
        "id": "T001",
        "title": "테스트 용접 작업",
        "description": "테스트용 합성 데이터",
        "work_type": "HOT_WORK",
        "zone_id": "A_BLOCK_1",
        "start_at": kst("2026-03-16", 9).isoformat(),
        "end_at": (kst("2026-03-16", 9) + timedelta(hours=3)).isoformat(),
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


@pytest.fixture
def csv_bytes():
    def _build(rows: list[str], header: str | None = None) -> bytes:
        default_header = (
            "id,title,work_type,zone_id,start_at,end_at,description,"
            "uses_flammable_material,gas_measurement_completed,ventilation_confirmed,"
            "watcher_assigned,status"
        )
        return "\n".join([header or default_header, *rows]).encode("utf-8")

    return _build
