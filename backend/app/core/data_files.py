"""data/ 하위 합성 데이터 파일 로더."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.errors import DataFileError
from app.domain.enums import Severity
from app.domain.models import RuleSpec, RuleType, ZoneData
from app.domain.zones import ZoneGraph


def load_zones(path: Path) -> list[ZoneData]:
    payload = _read_json(path)
    raw_zones = payload.get("zones") if isinstance(payload, dict) else payload
    if not isinstance(raw_zones, list) or not raw_zones:
        raise DataFileError(f"{path}: zones 배열이 비어 있거나 형식이 잘못되었습니다.")

    zones: list[ZoneData] = []
    for index, raw in enumerate(raw_zones):
        try:
            zones.append(
                ZoneData(
                    id=str(raw["id"]),
                    name=str(raw["name"]),
                    adjacent_zone_ids=tuple(str(z) for z in raw.get("adjacent_zone_ids", [])),
                )
            )
        except (KeyError, TypeError) as exc:
            raise DataFileError(f"{path}: {index}번째 구역 정의가 잘못되었습니다({exc}).") from exc
    # 인접관계 무결성은 그래프 생성 시 검증한다.
    try:
        ZoneGraph(zones)
    except ValueError as exc:
        raise DataFileError(f"{path}: {exc}") from exc
    return zones


def load_rules(path: Path) -> list[RuleSpec]:
    payload = _read_json(path)
    raw_rules = payload.get("rules") if isinstance(payload, dict) else payload
    if not isinstance(raw_rules, list) or not raw_rules:
        raise DataFileError(f"{path}: rules 배열이 비어 있거나 형식이 잘못되었습니다.")

    rules: list[RuleSpec] = []
    for index, raw in enumerate(raw_rules):
        try:
            rules.append(
                RuleSpec(
                    id=str(raw["id"]),
                    name=str(raw["name"]),
                    description=str(raw["description"]),
                    severity=Severity(str(raw["severity"])),
                    enabled=bool(raw["enabled"]),
                    reference_title=str(raw["reference_title"]),
                    reference_url=raw.get("reference_url"),
                    version=str(raw["version"]),
                    reviewed=bool(raw["reviewed"]),
                    rule_type=RuleType(str(raw.get("rule_type", "ALERT"))),
                    reference_articles=tuple(str(a) for a in raw.get("reference_articles", [])),
                    reference_note=str(raw.get("reference_note", "")),
                    reference_verified_at=raw.get("reference_verified_at"),
                    requires_site_validation=bool(raw.get("requires_site_validation", True)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataFileError(f"{path}: {index}번째 규칙 정의가 잘못되었습니다({exc}).") from exc
    return rules


def _read_json(path: Path) -> object:
    if not path.exists():
        raise DataFileError(f"데이터 파일을 찾을 수 없습니다: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataFileError(f"{path}: JSON 형식 오류({exc}).") from exc
