"""구역 인접관계 단위 테스트."""

from __future__ import annotations

import pytest

from app.domain.enums import SpatialRelation
from app.domain.models import ZoneData
from app.domain.zones import ZoneGraph


def graph() -> ZoneGraph:
    return ZoneGraph(
        [
            ZoneData(id="A", name="A구역", adjacent_zone_ids=("B",)),
            ZoneData(id="B", name="B구역", adjacent_zone_ids=()),
            ZoneData(id="C", name="C구역", adjacent_zone_ids=()),
        ]
    )


def test_same_zone_relation():
    assert graph().relation("A", "A") is SpatialRelation.SAME


def test_adjacent_relation_is_bidirectional_even_if_declared_one_way():
    g = graph()
    assert g.relation("A", "B") is SpatialRelation.ADJACENT
    assert g.relation("B", "A") is SpatialRelation.ADJACENT


def test_unrelated_relation():
    assert graph().relation("A", "C") is SpatialRelation.UNRELATED
    assert graph().is_spatially_overlapping("A", "C") is False


def test_spatial_overlap_true_for_same_and_adjacent():
    g = graph()
    assert g.is_spatially_overlapping("A", "A") is True
    assert g.is_spatially_overlapping("B", "A") is True


def test_self_adjacency_is_rejected():
    with pytest.raises(ValueError, match="자기 자신"):
        ZoneGraph([ZoneData(id="A", name="A", adjacent_zone_ids=("A",))])


def test_unknown_adjacent_zone_is_rejected():
    with pytest.raises(ValueError, match="존재하지 않는 구역"):
        ZoneGraph([ZoneData(id="A", name="A", adjacent_zone_ids=("X",))])


def test_duplicate_zone_id_is_rejected():
    with pytest.raises(ValueError, match="중복된 구역"):
        ZoneGraph([ZoneData(id="A", name="A"), ZoneData(id="A", name="A2")])
