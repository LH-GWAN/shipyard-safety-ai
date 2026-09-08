"""실제 LLM 공급자에 대한 자연어 구조화 평가.

주의: 이 스크립트는 실제 API를 호출하며 비용이 발생한다.
LLM_PROVIDER와 LLM_API_KEY가 설정되어 있고 --confirm 을 명시했을 때만 실행된다.
일반 테스트(pytest, npm test)와 CI에서는 절대 호출하지 않는다.

실행 예: LLM_PROVIDER=anthropic LLM_API_KEY=... python evaluation/evaluate_remote.py --confirm
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scoring import load_cases, print_summary, run_adapter, summarize, to_report  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.llm.factory import get_llm_adapter  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="실제 LLM 공급자의 구조화 정확도를 측정한다.")
    parser.add_argument("--confirm", action="store_true", help="실제 API 호출과 비용 발생에 동의")
    parser.add_argument("--limit", type=int, default=0, help="앞에서부터 N개 문장만 평가(비용 절감)")
    parser.add_argument("--save", action="store_true", help="결과를 evaluation/results에 JSON으로 저장")
    args = parser.parse_args()

    settings = Settings()
    if not settings.llm_enabled:
        print("LLM_PROVIDER와 LLM_API_KEY가 설정되지 않았습니다. 원격 평가를 건너뜁니다.")
        print("모의 어댑터 평가는 다음 명령으로 실행하십시오: python evaluation/evaluate_mock.py")
        return 2
    if not args.confirm:
        print("실제 API를 호출하고 비용이 발생합니다. 실행하려면 --confirm 을 추가하십시오.")
        return 2

    adapter = get_llm_adapter(settings)
    if adapter.is_mock:
        print("모의 어댑터가 선택되었습니다. 설정을 확인하십시오.")
        return 2

    payload = load_cases()
    cases = payload["cases"][: args.limit] if args.limit else payload["cases"]
    print(f"공급자 {adapter.provider} 로 {len(cases)}개 문장을 평가합니다. (실제 API 호출)")

    results = run_adapter(adapter, cases)
    summary = summarize(results)
    print_summary(adapter.provider, summary, results)

    if args.save:
        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RESULTS_DIR / f"{adapter.provider}_{stamp}.json"
        path.write_text(
            json.dumps(to_report(adapter.provider, results, summary), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\n결과 저장: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
