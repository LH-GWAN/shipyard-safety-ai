"""CSV 업로드 API 통합 테스트."""

from __future__ import annotations

HEADER = (
    "id,title,work_type,zone_id,start_at,end_at,description,"
    "uses_flammable_material,gas_measurement_completed,ventilation_confirmed,watcher_assigned,status"
)
VALID_ROW = (
    "C001,탱크 내부 점검,CONFINED_SPACE,TANK_A,"
    "2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,점검,,true,true,true,DRAFT"
)


def upload(client, csv_text: str, **params):
    files = {"file": ("work_items.csv", csv_text.encode("utf-8"), "text/csv")}
    return client.post("/api/work-items/import-csv", files=files, params=params)


def test_validate_only_does_not_change_database(client):
    response = upload(client, f"{HEADER}\n{VALID_ROW}")
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 1
    assert body["valid_count"] == 1
    assert body["created_count"] == 0
    assert body["committed"] is False
    assert body["valid_rows"][0]["row_number"] == 2
    assert client.get("/api/work-items").json()["total"] == 0


def test_commit_saves_valid_rows(client):
    response = upload(client, f"{HEADER}\n{VALID_ROW}", commit=True)
    body = response.json()
    assert body["created_count"] == 1 and body["committed"] is True
    saved = client.get("/api/work-items/C001").json()
    assert saved["source_type"] == "CSV"
    assert saved["gas_measurement_completed"] is True


def test_empty_optional_boolean_becomes_null(client):
    row = "C002,밀폐공간 작업,CONFINED_SPACE,TANK_B,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
    upload(client, f"{HEADER}\n{row}", commit=True)
    saved = client.get("/api/work-items/C002").json()
    assert saved["gas_measurement_completed"] is None
    assert saved["ventilation_confirmed"] is None
    assert saved["watcher_assigned"] is None
    assert saved["uses_flammable_material"] is None


def test_mixed_rows_keep_valid_results(client):
    bad_enum = "C003,잘못된 종류,hot_work,TANK_A,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
    bad_zone = "C004,없는 구역,HOT_WORK,NO_ZONE,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
    bad_time = "C005,시간 역전,HOT_WORK,TANK_A,2026-03-16T12:00:00+09:00,2026-03-16T09:00:00+09:00,,,,,,DRAFT"
    naive_time = "C006,표준시간대 없음,HOT_WORK,TANK_A,2026-03-16T09:00:00,2026-03-16T12:00:00,,,,,,DRAFT"
    bad_boolean = (
        "C007,불리언 오류,CONFINED_SPACE,TANK_A,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,예,,,,DRAFT"
    )
    csv_text = "\n".join([HEADER, VALID_ROW, bad_enum, bad_zone, bad_time, naive_time, bad_boolean])

    body = upload(client, csv_text, commit=True).json()
    assert body["total_rows"] == 6
    assert body["valid_count"] == 1
    assert body["invalid_count"] == 5
    assert body["created_count"] == 1

    codes = {(error["row_number"], error["field"], error["code"]) for error in body["errors"]}
    assert (3, "work_type", "INVALID_CSV_VALUE") in codes
    assert (4, "zone_id", "UNKNOWN_ZONE") in codes
    assert (5, "end_at", "INVALID_TIME_RANGE") in codes
    assert (6, "start_at", "TIMEZONE_REQUIRED") in codes
    assert (7, "uses_flammable_material", "INVALID_CSV_VALUE") in codes
    assert client.get("/api/work-items").json()["total"] == 1


def test_duplicate_id_in_file_and_in_database(client):
    duplicated = "\n".join([HEADER, VALID_ROW, VALID_ROW])
    body = upload(client, duplicated).json()
    assert any(error["code"] == "DUPLICATE_WORK_ITEM_ID" for error in body["errors"])

    upload(client, f"{HEADER}\n{VALID_ROW}", commit=True)
    again = upload(client, f"{HEADER}\n{VALID_ROW}").json()
    assert again["valid_count"] == 0
    assert again["errors"][0]["code"] == "DUPLICATE_WORK_ITEM_ID"

    overwritten = upload(client, f"{HEADER}\n{VALID_ROW}", commit=True, overwrite=True).json()
    assert overwritten["updated_count"] == 1
    assert overwritten["created_count"] == 0


def test_missing_required_column_returns_400(client):
    body = upload(client, "id,title,work_type\nC010,제목,HOT_WORK")
    assert body.status_code == 400
    assert body.json()["error"]["code"] == "INVALID_CSV_HEADER"
    assert "zone_id" in body.json()["error"]["details"]["missing_columns"]


def test_row_limit_returns_413(client):
    rows = [
        f"R{index:04d},작업 {index},HOT_WORK,TANK_A,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
        for index in range(1001)
    ]
    response = upload(client, "\n".join([HEADER, *rows]))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CSV_LIMIT_EXCEEDED"


def test_file_size_limit_returns_413(client):
    padding = "가" * 1000
    rows = [
        f"B{index:05d},작업 {padding},HOT_WORK,TANK_A,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
        for index in range(800)
    ]
    csv_text = "\n".join([HEADER, *rows])
    assert len(csv_text.encode("utf-8")) > 2 * 1024 * 1024
    response = upload(client, csv_text)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CSV_LIMIT_EXCEEDED"


def test_non_csv_filename_is_rejected(client):
    files = {"file": ("work_items.txt", f"{HEADER}\n{VALID_ROW}".encode(), "text/plain")}
    response = client.post("/api/work-items/import-csv", files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CSV_FILE"


def test_binary_file_is_rejected(client):
    files = {"file": ("work_items.csv", b"\xff\xfe\x00\x01\x02binary", "application/octet-stream")}
    response = client.post("/api/work-items/import-csv", files=files)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CSV_FILE"


def test_description_is_not_echoed_in_errors(client):
    long_description = "개인정보 가능성이 있는 긴 설명 " * 200
    row = (
        f"C020,설명 오류,HOT_WORK,TANK_A,2026-03-16T09:00:00+09:00,"
        f"2026-03-16T12:00:00+09:00,{long_description},,,,,DRAFT"
    )
    body = upload(client, f"{HEADER}\n{row}").json()
    description_errors = [error for error in body["errors"] if error["field"] == "description"]
    assert description_errors
    assert description_errors[0]["raw_value"] is None


def test_formula_injection_value_is_sanitized_in_errors(client):
    row = "C030,수식 주입,=cmd|' /C calc'!A0,TANK_A,2026-03-16T09:00:00+09:00,2026-03-16T12:00:00+09:00,,,,,,DRAFT"
    body = upload(client, f"{HEADER}\n{row}").json()
    work_type_error = next(error for error in body["errors"] if error["field"] == "work_type")
    assert work_type_error["raw_value"].startswith("'=")


def test_bundled_sample_dataset_imports_cleanly(client, data_dir):
    csv_text = (data_dir / "work_items.csv").read_text(encoding="utf-8")
    body = upload(client, csv_text, commit=True).json()
    assert body["total_rows"] == 40
    assert body["invalid_count"] == 0
    assert body["created_count"] == 40
