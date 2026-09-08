"""분석 실행/조회 API 통합 테스트."""

from __future__ import annotations

import json

from tests.conftest import work_item_payload


def seed_conflict(client) -> None:
    client.post(
        "/api/work-items",
        json=work_item_payload(id="A1", work_type="HOT_WORK", zone_id="A_BLOCK_1"),
    )
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="B1",
            work_type="PAINTING",
            zone_id="A_BLOCK_1",
            start_at="2026-03-16T11:00:00+09:00",
            end_at="2026-03-16T14:00:00+09:00",
        ),
    )
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="C1",
            work_type="CONFINED_SPACE",
            zone_id="TANK_A",
            start_at="2026-03-17T09:00:00+09:00",
            end_at="2026-03-17T12:00:00+09:00",
        ),
    )


def test_run_analysis_over_all_items(client):
    seed_conflict(client)
    body = client.post("/api/analysis/run", json={}).json()

    assert body["total_work_items"] == 3
    assert body["analyzed_work_items"] == 3
    assert body["invalid_work_items"] == 0
    assert body["alert_count"] == 4  # R001 1건 + 밀폐공간 3건
    assert body["severity_counts"] == {"HIGH": 4, "MEDIUM": 0, "LOW": 0}
    assert body["duration_ms"] >= 0
    assert body["alerts"][0]["rule_id"] == "R001"
    assert body["alerts"][0]["work_item_ids"] == ["A1", "B1"]
    assert body["alerts"][0]["recommended_action"]


def test_run_analysis_by_date(client):
    seed_conflict(client)
    body = client.post("/api/analysis/run", json={"date": "2026-03-17"}).json()
    assert body["total_work_items"] == 1
    assert {alert["rule_id"] for alert in body["alerts"]} == {"R101", "R102", "R103"}


def test_run_analysis_by_work_item_ids(client):
    seed_conflict(client)
    body = client.post("/api/analysis/run", json={"work_item_ids": ["A1", "B1"]}).json()
    assert body["total_work_items"] == 2
    assert body["alert_count"] == 1


def test_run_analysis_with_unknown_work_item_id(client):
    seed_conflict(client)
    response = client.post("/api/analysis/run", json={"work_item_ids": ["A1", "NOPE"]})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORK_ITEM_NOT_FOUND"


def test_get_analysis_and_alerts(client):
    seed_conflict(client)
    analysis_id = client.post("/api/analysis/run", json={}).json()["analysis_id"]

    fetched = client.get(f"/api/analysis/{analysis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_id"] == analysis_id

    alerts = client.get(f"/api/analysis/{analysis_id}/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["total"] == 4
    assert alerts.json()["items"][0]["evidence"]["spatial_relation"] == "SAME"


def test_unknown_analysis_id_returns_404(client):
    for path in ("/api/analysis/AN_NONE", "/api/analysis/AN_NONE/alerts"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_latest_analysis_endpoint(client):
    assert client.get("/api/analysis/latest").json() is None
    seed_conflict(client)
    analysis_id = client.post("/api/analysis/run", json={}).json()["analysis_id"]
    assert client.get("/api/analysis/latest").json()["analysis_id"] == analysis_id


def test_rules_endpoint_exposes_reviewed_catalog(client):
    body = client.get("/api/rules").json()
    assert body["total"] >= 6
    rule_ids = {rule["id"] for rule in body["items"]}
    assert {"R001", "R002", "R003", "R101", "R102", "R103"} <= rule_ids
    assert all(rule["reviewed"] for rule in body["items"])


def test_full_dataset_analysis_matches_expected_alerts(client, data_dir):
    csv_text = (data_dir / "work_items.csv").read_text(encoding="utf-8")
    files = {"file": ("work_items.csv", csv_text.encode("utf-8"), "text/csv")}
    client.post("/api/work-items/import-csv", files=files, params={"commit": True})

    body = client.post("/api/analysis/run", json={}).json()
    expected = json.loads((data_dir / "expected_alerts.json").read_text(encoding="utf-8"))["expected_alerts"]

    actual_keys = {(alert["rule_id"], tuple(alert["work_item_ids"])) for alert in body["alerts"]}
    expected_keys = {(row["rule_id"], tuple(row["work_item_ids"])) for row in expected}
    assert actual_keys == expected_keys
    assert body["alert_count"] == len(expected)


def test_openapi_document_is_available(client):
    schema = client.get("/openapi.json").json()
    for path in (
        "/health",
        "/api/zones",
        "/api/work-items",
        "/api/work-items/{work_item_id}",
        "/api/work-items/import-csv",
        "/api/work-items/parse-description",
        "/api/analysis/run",
        "/api/analysis/{analysis_id}",
        "/api/analysis/{analysis_id}/alerts",
        "/api/schedule/preview-shift",
        "/api/schedule/apply-shift",
    ):
        assert path in schema["paths"], path
