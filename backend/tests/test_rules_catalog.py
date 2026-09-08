"""규칙 카탈로그의 구성과 근거 메타데이터 검증."""

from __future__ import annotations

from app.domain.models import RuleType
from app.services.rule_catalog import get_rules

ALERT_RULE_IDS = {"R001", "R002", "R003", "R101", "R102", "R103"}
VALIDATION_RULE_IDS = {"R104"}


def test_catalog_has_six_alert_rules_and_one_validation_rule():
    rules = get_rules()
    alert_rules = {rule.id for rule in rules if rule.rule_type is RuleType.ALERT}
    validation_rules = {rule.id for rule in rules if rule.rule_type is RuleType.INPUT_VALIDATION}

    assert alert_rules == ALERT_RULE_IDS
    assert validation_rules == VALIDATION_RULE_IDS
    assert len(rules) == 7


def test_alert_rules_carry_verified_legal_reference():
    for rule in get_rules():
        if rule.rule_type is not RuleType.ALERT:
            continue
        assert rule.reference_url == "https://www.law.go.kr/법령/산업안전보건기준에관한규칙", rule.id
        assert rule.reference_articles, rule.id
        assert all(article.startswith("제") for article in rule.reference_articles), rule.id
        assert rule.reference_verified_at == "2026-09-06", rule.id
        assert rule.requires_site_validation is True, rule.id
        assert rule.reference_note, rule.id


def test_input_validation_rule_has_no_legal_reference_url():
    rule = next(rule for rule in get_rules() if rule.id == "R104")
    assert rule.rule_type is RuleType.INPUT_VALIDATION
    assert rule.reference_url is None
    assert rule.reference_articles == ()


def test_reference_notes_do_not_claim_legal_determination():
    """근거 설명이 법적 판정이나 작업 금지로 읽히지 않아야 한다."""
    forbidden = ["법 위반이다", "작업을 중지", "허가를 발행", "법적으로 금지"]
    for rule in get_rules():
        for phrase in forbidden:
            assert phrase not in rule.reference_note, f"{rule.id}: {phrase}"


def test_rules_api_reports_rule_type_counts(client):
    body = client.get("/api/rules").json()
    assert body["total"] == 7
    assert body["alert_rule_count"] == 6
    assert body["input_validation_rule_count"] == 1

    by_id = {rule["id"]: rule for rule in body["items"]}
    assert by_id["R101"]["reference_articles"] == ["제619조의2제1항", "제619조제1항"]
    assert by_id["R101"]["requires_site_validation"] is True
    assert by_id["R104"]["rule_type"] == "INPUT_VALIDATION"
    assert by_id["R104"]["reference_url"] is None


def test_only_alert_rules_can_produce_alerts(client, data_dir):
    """입력 검증 규칙(R104)은 경보로 집계되지 않는다."""
    csv_text = (data_dir / "work_items.csv").read_text(encoding="utf-8")
    files = {"file": ("work_items.csv", csv_text.encode("utf-8"), "text/csv")}
    client.post("/api/work-items/import-csv", files=files, params={"commit": True})

    alerts = client.post("/api/analysis/run", json={}).json()["alerts"]
    produced = {alert["rule_id"] for alert in alerts}
    assert produced <= ALERT_RULE_IDS
    assert "R104" not in produced
