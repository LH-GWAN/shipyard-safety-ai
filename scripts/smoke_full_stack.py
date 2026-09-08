"""백엔드와 프런트엔드가 함께 동작하는지 확인하는 HTTP 스모크 테스트.

두 서버를 띄운 상태에서 실행한다. 외부 의존성(브라우저 자동화)이 필요 없다.

실행:
    .venv/bin/python scripts/smoke_full_stack.py
    .venv/bin/python scripts/smoke_full_stack.py --api http://localhost:8000 --web http://localhost:3000
    .venv/bin/python scripts/smoke_full_stack.py --skip-web      # 백엔드만 확인
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "data" / "work_items.csv"
WEB_PAGES = ["/", "/work-items", "/work-items/new", "/analysis"]

passed = 0
failed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  [OK]   {label}{(' - ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  [FAIL] {label}{(' - ' + detail) if detail else ''}")


def call(api: str, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"} if data else {}
    request = urllib.request.Request(api + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode()
            return response.status, (json.loads(payload) if payload else {})
    except urllib.error.HTTPError as error:
        payload = error.read().decode()
        return error.code, (json.loads(payload) if payload else {})


def upload_csv(api: str, commit: bool) -> tuple[int, dict]:
    boundary = "----yardguardsmoke"
    content = CSV_PATH.read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="work_items.csv"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{api}/api/work-items/import-csv?commit={'true' if commit else 'false'}&overwrite=true",
        data=body,
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


def main() -> int:
    parser = argparse.ArgumentParser(description="YardGuard 통합 스모크 테스트")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--skip-web", action="store_true", help="프런트엔드 확인 생략")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    print("1) 백엔드 상태")
    status, health = call(api, "/health")
    check("GET /health 200", status == 200, f"status={status}")
    check("구역 시드 완료", health.get("zone_count", 0) >= 8, f"zone_count={health.get('zone_count')}")
    check("LLM 키 없이 동작(모의 어댑터)", health.get("llm_provider") in {"mock", "anthropic", "openai"})

    print("2) 합성 작업계획 로드")
    status, validate_only = upload_csv(api, commit=False)
    check("CSV 검증 전용 200", status == 200, f"status={status}")
    check("검증 결과 유효 행 존재", validate_only.get("valid_count", 0) > 0)
    check("검증 전용은 저장하지 않음", validate_only.get("committed") is False)
    status, committed = upload_csv(api, commit=True)
    check("CSV 저장 200", status == 200, f"status={status}")
    check(
        "저장 건수 보고",
        (committed.get("created_count", 0) + committed.get("updated_count", 0)) > 0,
        f"created={committed.get('created_count')} updated={committed.get('updated_count')}",
    )

    print("3) 작업 목록 조회")
    status, listing = call(api, "/api/work-items?page=1&page_size=20")
    check("GET /api/work-items 200", status == 200)
    check("작업 40건 등록", listing.get("total") == 40, f"total={listing.get('total')}")

    print("4) 분석 실행")
    status, analysis = call(api, "/api/analysis/run", "POST", {})
    check("POST /api/analysis/run 200", status == 200)
    check("경보 19건 생성", analysis.get("alert_count") == 19, f"alert_count={analysis.get('alert_count')}")

    print("5) 기대 경보 대조")
    expected = json.loads((REPO_ROOT / "data" / "expected_alerts.json").read_text(encoding="utf-8"))
    expected_keys = {(row["rule_id"], tuple(row["work_item_ids"])) for row in expected["expected_alerts"]}
    actual_keys = {(a["rule_id"], tuple(a["work_item_ids"])) for a in analysis.get("alerts", [])}
    check("누락 경보 없음", not (expected_keys - actual_keys), str(sorted(expected_keys - actual_keys)[:3]))
    check("예상하지 않은 경보 없음", not (actual_keys - expected_keys), str(sorted(actual_keys - expected_keys)[:3]))

    print("6) 경보 상세 조회")
    analysis_id = analysis.get("analysis_id", "")
    status, alerts = call(api, f"/api/analysis/{analysis_id}/alerts")
    check("GET /api/analysis/{id}/alerts 200", status == 200)
    conflict = next(
        (a for a in alerts.get("items", []) if a["rule_id"] == "R001" and a["work_item_ids"] == ["W001", "W002"]),
        None,
    )
    check("화기·도장 충돌 경보 존재", conflict is not None)
    check("근거에 중첩시간 포함", bool(conflict and conflict["evidence"].get("overlap_minutes")))

    print("7) 일정 변경 미리보기")
    preview = {}
    if conflict:
        status, preview = call(
            api,
            "/api/schedule/preview-shift",
            "POST",
            {"alert_id": conflict["id"], "move_work_item_id": "W002", "buffer_minutes": 30},
        )
        check("POST /api/schedule/preview-shift 200", status == 200)
        check("미리보기 토큰 발급", bool(preview.get("preview_token")))
        status, unchanged = call(api, "/api/work-items/W002")
        check("미리보기는 원본을 변경하지 않음", unchanged.get("start_at", "").startswith("2026-03-16T11:00"))

    print("8) 토큰 없는 적용 거부")
    if conflict:
        status, _ = call(
            api,
            "/api/schedule/apply-shift",
            "POST",
            {"alert_id": conflict["id"], "move_work_item_id": "W002", "buffer_minutes": 30},
        )
        check("토큰 없으면 422", status == 422, f"status={status}")

    print("9) 유효한 토큰으로 적용 + 재분석")
    if conflict and preview.get("preview_token"):
        status, applied = call(
            api,
            "/api/schedule/apply-shift",
            "POST",
            {
                "alert_id": conflict["id"],
                "move_work_item_id": "W002",
                "buffer_minutes": 30,
                "preview_token": preview["preview_token"],
            },
        )
        check("POST /api/schedule/apply-shift 200", status == 200, f"status={status}")
        check("적용 후 경보 18건", applied.get("analysis", {}).get("alert_count") == 18)
        status, moved = call(api, "/api/work-items/W002")
        check("작업 시간 변경 반영", moved.get("start_at", "").startswith("2026-03-16T12:30"))

    print("10) 자연어 모의 구조화")
    status, parsed = call(
        api,
        "/api/work-items/parse-description",
        "POST",
        {"text": "2026-03-16T13:00:00+09:00부터 2026-03-16T16:00:00+09:00까지 A_BLOCK_1에서 도장 작업"},
    )
    check("POST /api/work-items/parse-description 200", status == 200)
    check("작업 종류 추출", parsed.get("draft", {}).get("values", {}).get("work_type") == "PAINTING")
    check("모의 어댑터 사용 표시", parsed.get("is_mock") is True)

    if not args.skip_web:
        print("11) 프런트엔드 페이지 응답")
        web = args.web.rstrip("/")
        for page in WEB_PAGES:
            try:
                with urllib.request.urlopen(web + page, timeout=20) as response:
                    check(f"GET {page} 200", response.status == 200, f"status={response.status}")
            except Exception as error:  # 서버 미실행 등
                check(f"GET {page} 200", False, f"{type(error).__name__}: {error}")

    print(f"\n결과: 통과 {passed}건 / 실패 {failed}건")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
