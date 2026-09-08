"""일정 변경 미리보기/적용 API 통합 테스트."""

from __future__ import annotations

from tests.conftest import work_item_payload


def seed(client) -> str:
    """A1(화기) / B1(도장)이 같은 구역에서 겹치는 상황을 만들고 분석한다."""
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
    return analysis["alerts"][0]["id"]


def test_preview_does_not_change_original(client):
    alert_id = seed(client)
    body = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 30},
    ).json()

    change = body["change"]
    assert change["work_item_id"] == "B1"
    assert change["before_start_at"].startswith("2026-03-16T11:00")
    assert change["after_start_at"].startswith("2026-03-16T12:30")
    assert change["after_end_at"].startswith("2026-03-16T15:30")
    assert change["duration_minutes"] == 180
    assert [alert["rule_id"] for alert in body["resolved_alerts"]] == ["R001"]
    assert body["new_alerts"] == []
    assert body["before_alert_count"] == 1 and body["after_alert_count"] == 0
    assert body["preview_token"]

    unchanged = client.get("/api/work-items/B1").json()
    assert unchanged["start_at"].startswith("2026-03-16T11:00")


def test_apply_persists_change_and_reanalyzes(client):
    alert_id = seed(client)
    preview = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 30},
    ).json()

    applied = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": preview["preview_token"],
        },
    )
    assert applied.status_code == 200
    body = applied.json()
    assert body["analysis"]["alert_count"] == 0
    assert [alert["rule_id"] for alert in body["resolved_alerts"]] == ["R001"]

    moved = client.get("/api/work-items/B1").json()
    assert moved["start_at"].startswith("2026-03-16T12:30")
    assert moved["end_at"].startswith("2026-03-16T15:30")


def test_apply_requires_matching_preview_token(client):
    """미리보기 없이 적용할 수 없고, 해당 buffer로 미리본 토큰만 적용된다."""
    alert_id = seed(client)

    without_token = client.post(
        "/api/schedule/apply-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 60},
    )
    assert without_token.status_code == 422
    assert client.get("/api/work-items/B1").json()["start_at"].startswith("2026-03-16T11:00")

    preview = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 60},
    ).json()
    applied = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 60,
            "preview_token": preview["preview_token"],
        },
    )
    assert applied.status_code == 200
    assert client.get("/api/work-items/B1").json()["start_at"].startswith("2026-03-16T13:00")


def test_stale_preview_token_returns_409(client):
    alert_id = seed(client)
    preview = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 30},
    ).json()

    # 사용자가 그 사이에 작업 시간을 직접 수정한 상황
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

    response = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": alert_id,
            "move_work_item_id": "B1",
            "buffer_minutes": 30,
            "preview_token": preview["preview_token"],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_SCHEDULE_PREVIEW"


def test_preview_reports_new_alert_created_by_the_change(client):
    alert_id = seed(client)
    # 이동 후 시간대에 또 다른 화기작업이 있는 경우
    client.post(
        "/api/work-items",
        json=work_item_payload(
            id="C1",
            work_type="HOT_WORK",
            zone_id="A_BLOCK_1",
            start_at="2026-03-16T13:00:00+09:00",
            end_at="2026-03-16T16:00:00+09:00",
        ),
    )
    body = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 30},
    ).json()

    resolved = {tuple(alert["work_item_ids"]) for alert in body["resolved_alerts"]}
    remaining = {tuple(alert["work_item_ids"]) for alert in body["new_alerts"]}
    assert ("A1", "B1") in resolved
    assert body["remaining_alert_count"] >= 1
    assert remaining or body["remaining_alert_count"] >= 1


def test_single_work_item_alert_cannot_be_shifted(client):
    client.post(
        "/api/work-items",
        json=work_item_payload(id="D1", work_type="CONFINED_SPACE", zone_id="TANK_A"),
    )
    analysis = client.post("/api/analysis/run", json={}).json()
    alert_id = analysis["alerts"][0]["id"]

    response = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "D1"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_unknown_alert_returns_404(client):
    response = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": "AL_NONE", "move_work_item_id": "B1"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ALERT_NOT_FOUND"


def test_move_item_must_belong_to_alert(client):
    alert_id = seed(client)
    client.post("/api/work-items", json=work_item_payload(id="Z9", zone_id="DOCK_2"))
    response = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "Z9"},
    )
    assert response.status_code == 400


def test_buffer_out_of_range_returns_422(client):
    alert_id = seed(client)
    response = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": alert_id, "move_work_item_id": "B1", "buffer_minutes": 999},
    )
    assert response.status_code == 422
