"""일정 변경 적용 시 미리보기 토큰 검증 통합 테스트.

사용자가 미리보기로 확인하지 않은 변경은 적용할 수 없어야 한다.
"""

from __future__ import annotations

from tests.conftest import work_item_payload


def seed(client) -> tuple[str, dict]:
    """A1(화기) / B1(도장)이 겹치는 상황을 만들고 (경보 ID, B1 초기값)을 돌려준다."""
    client.post("/api/work-items", json=work_item_payload(id="A1", work_type="HOT_WORK", zone_id="A_BLOCK_1"))
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
    analysis = client.post("/api/analysis/run", json={}).json()
    alert_id = analysis["alerts"][0]["id"]
    return alert_id, client.get("/api/work-items/B1").json()


def preview(client, alert_id: str, buffer: int = 30) -> dict:
    return client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": buffer},
    ).json()


def times_of(client, work_item_id: str) -> tuple[str, str]:
    item = client.get(f"/api/work-items/{work_item_id}").json()
    return item["start_at"], item["end_at"]


def test_apply_without_token_is_rejected(client):
    alert_id, before = seed(client)

    response = client.post(
        "/api/schedule/apply-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 30},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert times_of(client, "B1") == (before["start_at"], before["end_at"])


def test_apply_with_empty_token_is_rejected(client):
    alert_id, before = seed(client)

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": "",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert times_of(client, "B1") == (before["start_at"], before["end_at"])


def test_apply_with_whitespace_token_is_rejected(client):
    alert_id, before = seed(client)

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"
    assert times_of(client, "B1") == (before["start_at"], before["end_at"])


def test_apply_with_wrong_token_returns_409(client):
    alert_id, before = seed(client)

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": "0" * 32,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"
    assert times_of(client, "B1") == (before["start_at"], before["end_at"])


def test_token_becomes_stale_after_work_item_is_edited(client):
    alert_id, _ = seed(client)
    token = preview(client, alert_id)["preview_token"]

    client.put(
        "/api/work-items/B1",
        json=work_item_payload(
            id="B1",
            work_type="PAINTING",
            zone_id="A_BLOCK_1",
            start_at="2026-03-16T11:30:00+09:00",
            end_at="2026-03-16T14:30:00+09:00",
        ),
    )
    edited = times_of(client, "B1")

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": token,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"
    assert times_of(client, "B1") == edited


def test_token_is_bound_to_buffer_minutes(client):
    alert_id, before = seed(client)
    token_for_30 = preview(client, alert_id, buffer=30)["preview_token"]

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 60,
            "preview_token": token_for_30,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"
    assert times_of(client, "B1") == (before["start_at"], before["end_at"])


def test_token_is_bound_to_move_work_item(client):
    alert_id, _ = seed(client)
    a1_before = times_of(client, "A1")
    b1_before = times_of(client, "B1")
    token_for_b1 = preview(client, alert_id)["preview_token"]

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "A1",
            "buffer_minutes": 30,
            "preview_token": token_for_b1,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"
    assert times_of(client, "A1") == a1_before
    assert times_of(client, "B1") == b1_before


def test_valid_token_applies_change_and_reanalyzes(client):
    alert_id, _ = seed(client)
    token = preview(client, alert_id)["preview_token"]

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": token,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["alert_count"] == 0
    assert body["analysis"]["analyzed_work_items"] == 2
    assert [alert["rule_id"] for alert in body["resolved_alerts"]] == ["R001"]
    assert times_of(client, "B1") == ("2026-03-16T12:30:00+09:00", "2026-03-16T15:30:00+09:00")

    # 적용 후 새 분석 결과가 저장되어 조회 가능해야 한다.
    latest = client.get("/api/analysis/latest").json()
    assert latest["analysis_id"] == body["analysis"]["analysis_id"]


def test_token_cannot_be_reused_after_successful_apply(client):
    alert_id, _ = seed(client)
    token = preview(client, alert_id)["preview_token"]
    client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": token,
        },
    )
    after_first = times_of(client, "B1")

    replay = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": token,
        },
    )

    assert replay.status_code == 409
    assert times_of(client, "B1") == after_first


def test_openapi_marks_preview_token_as_required(client):
    schema = client.get("/openapi.json").json()
    request_schema = schema["components"]["schemas"]["ShiftApplyRequest"]
    assert "preview_token" in request_schema["required"]
    assert request_schema["properties"]["preview_token"]["minLength"] == 1
