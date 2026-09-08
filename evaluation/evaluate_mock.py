"""결정론적 모의 어댑터에 대한 자연어 구조화 평가.

API 키와 네트워크가 필요 없다.
실행: python evaluation/evaluate_mock.py [--save]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scoring import load_cases, print_summary, run_adapter, summarize, to_report  # noqa: E402

from app.llm.mock import MockLLMAdapter  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="모의 어댑터 구조화 정확도를 측정한다.")
    parser.add_argument("--save", action="store_true", help="결과를 evaluation/results에 JSON으로 저장")
    args = parser.parse_args()

    payload = load_cases()
    results = run_adapter(MockLLMAdapter(), payload["cases"])
    summary = summarize(results)
    print_summary("mock", summary, results)

    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RESULTS_DIR / f"mock_{stamp}.json"
        path.write_text(
            json.dumps(to_report("mock", results, summary), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n결과 저장: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
