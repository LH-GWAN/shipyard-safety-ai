"""3분 시연 경로 전체를 한 번에 검증하는 통합 스모크 테스트.

docs/demo-script.md의 순서를 그대로 따라간다. 외부 API 키와 네트워크가 필요 없다.
"""

from __future__ import annotations

import json


def test_full_demo_path(client, data_dir):
    # 1. 백엔드 상태 확인
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["llm_enabled"] is False  # 키 없이 시연 가능
    assert health["zone_count"] == 12

    # 2. 합성 작업계획 로드(검증 → 저장)
    csv_bytes = (data_dir / "work_items.csv").read_bytes()
    files = {"file": ("work_items.csv", csv_bytes, "text/csv")}

    validate_only = client.post("/api/work-items/import-csv", files=files).json()
    assert validate_only["total_rows"] == 40
    assert validate_only["valid_count"] == 40
    assert validate_only["committed"] is False
    assert client.get("/api/work-items").json()["total"] == 0  # 검증만으로는 저장되지 않는다

    committed = client.post("/api/work-items/import-csv", files=files, params={"commit": True}).json()
    assert committed["created_count"] == 40
    assert committed["committed"] is True

    # 3. 작업 목록 조회
    listing = client.get("/api/work-items", params={"page": 1, "page_size": 20}).json()
    assert listing["total"] == 40
    assert len(listing["items"]) == 20

    # 4. 분석 실행
    analysis = client.post("/api/analysis/run", json={}).json()
    analysis_id = analysis["analysis_id"]
    assert analysis["analyzed_work_items"] == 40
    assert analysis["invalid_work_items"] == 0

    # 5. 기대 경보와 일치하는지 확인
    expected = json.loads((data_dir / "expected_alerts.json").read_text(encoding="utf-8"))
    expected_keys = {(row["rule_id"], tuple(row["work_item_ids"])) for row in expected["expected_alerts"]}
    actual_keys = {(alert["rule_id"], tuple(alert["work_item_ids"])) for alert in analysis["alerts"]}
    assert actual_keys == expected_keys
    assert analysis["alert_count"] == 19
    assert analysis["severity_counts"] == {"HIGH": 19, "MEDIUM": 0, "LOW": 0}

    # 6. 경보 상세 조회 - 화기/도장 충돌과 밀폐공간 정보 누락
    alerts = client.get(f"/api/analysis/{analysis_id}/alerts").json()["items"]
    conflict = next(a for a in alerts if a["rule_id"] == "R001" and a["work_item_ids"] == ["W001", "W002"])
    assert conflict["evidence"]["spatial_relation"] == "SAME"
    assert conflict["evidence"]["overlap_minutes"] == 60
    assert conflict["recommended_action"]

    missing_gas = next(a for a in alerts if a["rule_id"] == "R101" and a["work_item_ids"] == ["W026"])
    declared_false = next(a for a in alerts if a["rule_id"] == "R101" and a["work_item_ids"] == ["W027"])
    assert missing_gas["evidence"]["value_state"] == "MISSING"
    assert declared_false["evidence"]["value_state"] == "DECLARED_FALSE"
    assert missing_gas["message"] != declared_false["message"]

    # 규칙 근거(적용 규칙) 조회
    rules = client.get("/api/rules").json()
    assert rules["alert_rule_count"] == 6
    assert rules["input_validation_rule_count"] == 1
    r001 = next(rule for rule in rules["items"] if rule["id"] == "R001")
    assert r001["reference_articles"]

    # 7. 일정 변경 미리보기(원본 불변)
    preview = client.post(
        "/api/schedule/preview-shift",
        json={"alert_id": conflict["id"], "move_work_item_id": "W002", "buffer_minutes": 30},
    ).json()
    assert preview["change"]["after_start_at"].startswith("2026-03-16T12:30")
    assert preview["after_alert_count"] == 18
    assert client.get("/api/work-items/W002").json()["start_at"].startswith("2026-03-16T11:00")

    # 8. 토큰 없이 적용 시도는 거부된다
    rejected = client.post(
        "/api/schedule/apply-shift",
        json={"alert_id": conflict["id"], "move_work_item_id": "W002", "buffer_minutes": 30},
    )
    assert rejected.status_code == 422
    assert client.get("/api/work-items/W002").json()["start_at"].startswith("2026-03-16T11:00")

    # 9. 유효한 토큰으로 적용 → 전체 재분석
    applied = client.post(
        "/api/schedule/apply-shift",
        json={
            "alert_id": conflict["id"],
            "move_work_item_id": "W002",
            "buffer_minutes": 30,
            "preview_token": preview["preview_token"],
        },
    ).json()
    assert applied["analysis"]["alert_count"] == 18
    assert applied["analysis"]["analysis_id"] != analysis_id
    assert client.get("/api/work-items/W002").json()["start_at"].startswith("2026-03-16T12:30")

    # 10. 재분석 결과 저장·조회 확인
    latest = client.get("/api/analysis/latest").json()
    assert latest["analysis_id"] == applied["analysis"]["analysis_id"]
    assert client.get(f"/api/analysis/{latest['analysis_id']}").status_code == 200

    # 11. 자연어 모의 구조화(저장하지 않음)
    parsed = client.post(
        "/api/work-items/parse-description",
        json={"text": "2026-03-16T13:00:00+09:00부터 2026-03-16T16:00:00+09:00까지 A_BLOCK_1에서 도장 작업"},
    ).json()
    assert parsed["is_mock"] is True
    assert parsed["draft"]["values"]["work_type"] == "PAINTING"
    assert parsed["draft"]["values"]["zone_id"] == "A_BLOCK_1"
    assert client.get("/api/work-items").json()["total"] == 40  # 초안은 저장되지 않는다

    # 12. 경보 여부 필터가 최근 분석을 반영
    with_alert = client.get("/api/work-items", params={"has_alert": True, "page_size": 100}).json()
    assert with_alert["total"] > 0
    assert all(item["has_alert"] for item in with_alert["items"])
