"""합성 데이터의 예상 경보와 규칙 엔진 결과가 일치하는지 검증한다."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.data_files import load_rules, load_zones
from app.domain.enums import WorkType
from app.domain.models import WorkItemData
from app.domain.rules import RuleEvaluator
from app.domain.zones import ZoneGraph

BOOLEANS = {"true": True, "TRUE": True, "1": True, "false": False, "FALSE": False, "0": False}


def parse_bool(value: str) -> bool | None:
    value = (value or "").strip()
    return BOOLEANS.get(value) if value else None


def load_dataset(data_dir: Path) -> list[WorkItemData]:
    items: list[WorkItemData] = []
    with (data_dir / "work_items.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            items.append(
                WorkItemData(
                    id=row["id"].strip(),
                    title=row["title"].strip(),
                    work_type=WorkType(row["work_type"].strip()),
                    zone_id=row["zone_id"].strip(),
                    start_at=datetime.fromisoformat(row["start_at"].strip()),
                    end_at=datetime.fromisoformat(row["end_at"].strip()),
                    uses_flammable_material=parse_bool(row.get("uses_flammable_material", "")),
                    gas_measurement_completed=parse_bool(row.get("gas_measurement_completed", "")),
                    ventilation_confirmed=parse_bool(row.get("ventilation_confirmed", "")),
                    watcher_assigned=parse_bool(row.get("watcher_assigned", "")),
                )
            )
    return items


@pytest.fixture(scope="module")
def dataset():
    data_dir = get_settings().data_dir
    items = load_dataset(data_dir)
    evaluator = RuleEvaluator(load_rules(data_dir / "rules.json"), ZoneGraph(load_zones(data_dir / "zones.json")))
    expected = json.loads((data_dir / "expected_alerts.json").read_text(encoding="utf-8"))
    return items, evaluator, expected


def test_dataset_size_is_within_specification(dataset):
    items, _, _ = dataset
    assert 30 <= len(items) <= 40


def test_actual_alerts_match_expected_alerts(dataset):
    items, evaluator, expected = dataset
    alerts = evaluator.evaluate(items, "AN_DATASET")

    actual_keys = {(alert.rule_id, tuple(alert.work_item_ids)) for alert in alerts}
    expected_keys = {(row["rule_id"], tuple(row["work_item_ids"])) for row in expected["expected_alerts"]}

    assert sorted(expected_keys - actual_keys) == [], "누락된 경보가 있습니다."
    assert sorted(actual_keys - expected_keys) == [], "예상하지 않은 경보가 있습니다."
    assert len(alerts) == len(expected["expected_alerts"])


def test_expected_evidence_matches(dataset):
    items, evaluator, expected = dataset
    alerts = {(a.rule_id, tuple(a.work_item_ids)): a for a in evaluator.evaluate(items, "AN_DATASET")}

    for row in expected["expected_alerts"]:
        alert = alerts[(row["rule_id"], tuple(row["work_item_ids"]))]
        assert alert.severity.value == row["severity"]
        for key, value in row["evidence"].items():
            assert alert.evidence[key] == value, f"{row['scenario_id']}.{key}"


def test_negative_scenarios_have_no_alert(dataset):
    items, evaluator, expected = dataset
    alerts = evaluator.evaluate(items, "AN_DATASET")

    for scenario in expected["negative_scenarios"]:
        target = set(scenario["work_item_ids"])
        for alert in alerts:
            assert set(alert.work_item_ids) != target, scenario["scenario_id"]


def test_analysis_of_full_dataset_is_fast(dataset):
    """합성 데이터 기준 개발 목표(5초 이내) 확인. 현장 성능 주장이 아니다."""
    items, evaluator, _ = dataset
    started = time.perf_counter()
    evaluator.evaluate(items, "AN_PERF")
    duration = time.perf_counter() - started
    print(f"\n[측정] 작업 {len(items)}건 규칙 검사: {duration * 1000:.1f} ms")
    assert duration < 5.0
