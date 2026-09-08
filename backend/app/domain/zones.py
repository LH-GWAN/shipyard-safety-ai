"""구역 인접관계 그래프와 공간관계 계산."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import SpatialRelation
from app.domain.models import ZoneData


class ZoneGraph:
    """인접관계를 항상 양방향으로 정규화해 보관한다."""

    def __init__(self, zones: Iterable[ZoneData]) -> None:
        self._zones: dict[str, ZoneData] = {}
        self._adjacency: dict[str, set[str]] = {}
        for zone in zones:
            if zone.id in self._zones:
                raise ValueError(f"중복된 구역 ID입니다: {zone.id}")
            self._zones[zone.id] = zone
            self._adjacency.setdefault(zone.id, set())

        unknown: list[str] = []
        for zone in self._zones.values():
            for neighbour in zone.adjacent_zone_ids:
                if neighbour == zone.id:
                    raise ValueError(f"구역 {zone.id}가 자기 자신을 인접구역으로 지정했습니다.")
                if neighbour not in self._zones:
                    unknown.append(f"{zone.id} -> {neighbour}")
                    continue
                # 단방향 선언도 양방향으로 정규화한다.
                self._adjacency[zone.id].add(neighbour)
                self._adjacency[neighbour].add(zone.id)
        if unknown:
            raise ValueError("존재하지 않는 구역 ID를 인접구역으로 참조했습니다: " + ", ".join(sorted(unknown)))

    def __contains__(self, zone_id: object) -> bool:
        return zone_id in self._zones

    def __len__(self) -> int:
        return len(self._zones)

    @property
    def zone_ids(self) -> list[str]:
        return sorted(self._zones)

    def get(self, zone_id: str) -> ZoneData | None:
        return self._zones.get(zone_id)

    def name_of(self, zone_id: str) -> str:
        zone = self._zones.get(zone_id)
        return zone.name if zone else zone_id

    def neighbours(self, zone_id: str) -> set[str]:
        return set(self._adjacency.get(zone_id, set()))

    def relation(self, zone_a: str, zone_b: str) -> SpatialRelation:
        if zone_a == zone_b:
            return SpatialRelation.SAME
        if zone_b in self._adjacency.get(zone_a, set()):
            return SpatialRelation.ADJACENT
        return SpatialRelation.UNRELATED

    def is_spatially_overlapping(self, zone_a: str, zone_b: str) -> bool:
        return self.relation(zone_a, zone_b) is not SpatialRelation.UNRELATED
