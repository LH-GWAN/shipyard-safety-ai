"""테이블 생성과 구역 시드."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.data_files import load_zones
from app.core.logging import log_event
from app.db.session import get_engine, get_session_factory
from app.models.orm import Base, ZoneORM


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


def seed_zones(session: Session, settings: Settings | None = None) -> int:
    """zones.json의 구역을 DB에 반영한다(있으면 갱신)."""
    settings = settings or get_settings()
    zones = load_zones(settings.zones_path)
    for zone in zones:
        existing = session.get(ZoneORM, zone.id)
        if existing is None:
            session.add(ZoneORM(id=zone.id, name=zone.name, adjacent_zone_ids=list(zone.adjacent_zone_ids)))
        else:
            existing.name = zone.name
            existing.adjacent_zone_ids = list(zone.adjacent_zone_ids)
    session.commit()
    return len(zones)


def init_db() -> None:
    create_tables()
    with get_session_factory()() as session:
        count = seed_zones(session)
    log_event("db_initialized", zone_count=count)
