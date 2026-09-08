"""밀폐공간 규칙(R101~R103) 단위 테스트."""

from __future__ import annotations

import pytest

from app.domain.enums import WorkType
from tests.factories import evaluate, make_item

FIELD_BY_RULE = {
    "R101": "gas_measurement_completed",
    "R102": "ventilation_confirmed",
    "R103": "watcher_assigned",
}
ALL_TRUE = {
    "gas_measurement_completed": True,
    "ventilation_confirmed": True,
    "watcher_assigned": True,
}


@pytest.mark.parametrize("rule_id,field", FIELD_BY_RULE.items())
def test_confined_rule_triggers_on_null(rule_id: str, field: str):
    flags = {**ALL_TRUE, field: None}
    alerts = evaluate([make_item("C1", WorkType.CONFINED_SPACE, **flags)])
    assert [alert.rule_id for alert in alerts] == [rule_id]
    assert alerts[0].evidence["value"] is None
    assert alerts[0].evidence["value_state"] == "MISSING"
    assert "입력되지 않았습니다" in alerts[0].message


@pytest.mark.parametrize("rule_id,field", FIELD_BY_RULE.items())
def test_confined_rule_triggers_on_false(rule_id: str, field: str):
    flags = {**ALL_TRUE, field: False}
    alerts = evaluate([make_item("C1", WorkType.CONFINED_SPACE, **flags)])
    assert [alert.rule_id for alert in alerts] == [rule_id]
    assert alerts[0].evidence["value"] is False
    assert alerts[0].evidence["value_state"] == "DECLARED_FALSE"
    assert "입력되지 않았습니다" not in alerts[0].message


@pytest.mark.parametrize("rule_id,field", FIELD_BY_RULE.items())
def test_null_and_false_messages_differ(rule_id: str, field: str):
    null_alert = evaluate([make_item("C1", WorkType.CONFINED_SPACE, **{**ALL_TRUE, field: None})])[0]
    false_alert = evaluate([make_item("C1", WorkType.CONFINED_SPACE, **{**ALL_TRUE, field: False})])[0]
    assert null_alert.rule_id == false_alert.rule_id == rule_id
    assert null_alert.message != false_alert.message


def test_no_alert_when_all_true():
    assert evaluate([make_item("C1", WorkType.CONFINED_SPACE, **ALL_TRUE)]) == []


def test_all_three_alerts_when_all_missing():
    alerts = evaluate([make_item("C1", WorkType.CONFINED_SPACE)])
    assert [alert.rule_id for alert in alerts] == ["R101", "R102", "R103"]
    assert all(alert.work_item_ids == ("C1",) for alert in alerts)


def test_confined_rules_do_not_apply_to_other_work_types():
    assert evaluate([make_item("H1", WorkType.HOT_WORK)]) == []
