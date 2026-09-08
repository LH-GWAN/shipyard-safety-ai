"""WorkItem CRUD API 통합 테스트."""

from __future__ import annotations

from tests.conftest import work_item_payload


def test_create_get_update_delete_work_item(client):
    created = client.post("/api/work-items", json=work_item_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["id"] == "T001"
    assert body["source_type"] == "MANUAL"
    assert body["zone_name"] == "A블록 1구역"
    assert body["start_at"].endswith("+09:00")

    fetched = client.get("/api/work-items/T001")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "테스트 용접 작업"

    updated = client.put(
        "/api/work-items/T001",
        json=work_item_payload(title="수정된 작업명", status="REVIEWED"),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "수정된 작업명"
    assert updated.json()["status"] == "REVIEWED"

    deleted = client.delete("/api/work-items/T001")
    assert deleted.status_code == 204
    assert client.get("/api/work-items/T001").status_code == 404
    assert client.get("/api/work-items/T001").json()["error"]["code"] == "WORK_ITEM_NOT_FOUND"


def test_server_generates_id_when_omitted(client):
    payload = work_item_payload()
    payload.pop("id")
    response = client.post("/api/work-items", json=payload)
    assert response.status_code == 201
    assert response.json()["id"].startswith("WI_")


def test_unknown_zone_is_rejected(client):
    response = client.post("/api/work-items", json=work_item_payload(zone_id="NO_SUCH_ZONE"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_ZONE"


def test_invalid_time_range_is_rejected(client):
    response = client.post(
        "/api/work-items",
        json=work_item_payload(
            start_at="2026-03-16T12:00:00+09:00",
            end_at="2026-03-16T09:00:00+09:00",
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TIME_RANGE"


def test_equal_start_and_end_is_rejected(client):
    response = client.post(
        "/api/work-items",
        json=work_item_payload(
            start_at="2026-03-16T09:00:00+09:00",
            end_at="2026-03-16T09:00:00+09:00",
        ),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_TIME_RANGE"


def test_naive_datetime_is_rejected(client):
    response = client.post("/api/work-items", json=work_item_payload(start_at="2026-03-16T09:00:00"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TIMEZONE_REQUIRED"


def test_blank_title_is_rejected(client):
    response = client.post("/api/work-items", json=work_item_payload(title="   "))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_enum_case_is_rejected(client):
    response = client.post("/api/work-items", json=work_item_payload(work_type="hot_work"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_id_returns_409(client):
    assert client.post("/api/work-items", json=work_item_payload()).status_code == 201
    duplicate = client.post("/api/work-items", json=work_item_payload(title="다른 작업"))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_WORK_ITEM_ID"


def test_null_and_false_are_distinguished(client):
    client.post("/api/work-items", json=work_item_payload(id="N1", gas_measurement_completed=None))
    client.post("/api/work-items", json=work_item_payload(id="N2", gas_measurement_completed=False))
    assert client.get("/api/work-items/N1").json()["gas_measurement_completed"] is None
    assert client.get("/api/work-items/N2").json()["gas_measurement_completed"] is False


def test_update_of_missing_item_returns_404(client):
    response = client.put("/api/work-items/NOPE", json=work_item_payload())
    assert response.status_code == 404


def test_list_filters_and_pagination(client):
    client.post("/api/work-items", json=work_item_payload(id="L1", zone_id="A_BLOCK_1"))
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="L2",
            zone_id="PAINT_SHOP",
            work_type="PAINTING",
            status="REVIEWED",
            start_at="2026-03-17T09:00:00+09:00",
            end_at="2026-03-17T12:00:00+09:00",
        ),
    )

    assert client.get("/api/work-items").json()["total"] == 2
    assert client.get("/api/work-items", params={"date": "2026-03-16"}).json()["total"] == 1
    assert client.get("/api/work-items", params={"work_type": "PAINTING"}).json()["total"] == 1
    assert client.get("/api/work-items", params={"zone_id": "PAINT_SHOP"}).json()["total"] == 1
    assert client.get("/api/work-items", params={"status": "REVIEWED"}).json()["total"] == 1

    paged = client.get("/api/work-items", params={"page": 1, "page_size": 1}).json()
    assert paged["total"] == 2 and len(paged["items"]) == 1 and paged["page_size"] == 1

    assert client.get("/api/work-items", params={"page_size": 500}).status_code == 422


def test_has_alert_filter_uses_latest_analysis(client):
    client.post(
        "/api/work-items",
        json=work_item_payload(id="H1", work_type="HOT_WORK", zone_id="A_BLOCK_1"),
    )
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="P1",
            work_type="PAINTING",
            zone_id="A_BLOCK_1",
            start_at="2026-03-16T11:00:00+09:00",
            end_at="2026-03-16T14:00:00+09:00",
        ),
    )
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="S1",
            work_type="OTHER",
            zone_id="DOCK_2",
            start_at="2026-03-16T11:00:00+09:00",
            end_at="2026-03-16T14:00:00+09:00",
        ),
    )
    client.post("/api/analysis/run", json={})

    with_alert = client.get("/api/work-items", params={"has_alert": True}).json()
    without_alert = client.get("/api/work-items", params={"has_alert": False}).json()
    assert {item["id"] for item in with_alert["items"]} == {"H1", "P1"}
    assert {item["id"] for item in without_alert["items"]} == {"S1"}
    assert all(item["has_alert"] for item in with_alert["items"])


def test_zone_endpoints(client):
    zones = client.get("/api/zones").json()
    assert zones["total"] == 12
    assert any(zone["id"] == "TANK_A" for zone in zones["items"])

    created = client.post(
        "/api/zones",
        json={"id": "NEW_ZONE", "name": "신규 구역", "adjacent_zone_ids": ["DOCK_1"]},
    )
    assert created.status_code == 201

    duplicate = client.post("/api/zones", json={"id": "NEW_ZONE", "name": "중복"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_ZONE_ID"

    unknown = client.post(
        "/api/zones",
        json={"id": "OTHER_ZONE", "name": "구역", "adjacent_zone_ids": ["NOPE"]},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "UNKNOWN_ZONE"


def test_health_reports_mock_llm_when_key_is_absent(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["llm_enabled"] is False
    assert body["llm_provider"] == "mock"
    assert body["zone_count"] == 12
