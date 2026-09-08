from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ZoneData
from app.domain.zones import ZoneGraph
from app.models.orm import ZoneORM


class ZoneRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[ZoneORM]:
        return list(self.session.scalars(select(ZoneORM).order_by(ZoneORM.id)))

    def get(self, zone_id: str) -> ZoneORM | None:
        return self.session.get(ZoneORM, zone_id)

    def add(self, zone: ZoneORM) -> ZoneORM:
        self.session.add(zone)
        self.session.commit()
        return zone

    def to_domain(self) -> list[ZoneData]:
        return [
            ZoneData(id=z.id, name=z.name, adjacent_zone_ids=tuple(z.adjacent_zone_ids or [])) for z in self.list_all()
        ]

    def graph(self) -> ZoneGraph:
        return ZoneGraph(self.to_domain())
