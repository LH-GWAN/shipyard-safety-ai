"""합성 작업계획(data/work_items.csv)을 데이터베이스에 적재하는 개발용 스크립트.

실행: python -m scripts.load_sample_data [--overwrite]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.services.csv_service import CsvImportService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="합성 CSV 데이터를 적재합니다.")
    parser.add_argument("--overwrite", action="store_true", help="이미 존재하는 작업 ID를 덮어씁니다.")
    args = parser.parse_args()

    configure_logging()
    settings = get_settings()
    init_db()

    csv_path = settings.work_items_csv_path
    if not csv_path.exists():
        print(f"CSV 파일을 찾을 수 없습니다: {csv_path}")
        return 1

    with get_session_factory()() as session:
        result = CsvImportService(session, settings).import_csv(
            filename=csv_path.name,
            content_type="text/csv",
            content=csv_path.read_bytes(),
            commit=True,
            overwrite=args.overwrite,
        )

    print(
        f"전체 {result.total_rows}행 · 유효 {result.valid_count}행 · 오류 {result.invalid_count}행 · "
        f"신규 {result.created_count}건 · 갱신 {result.updated_count}건"
    )
    for error in result.errors[:10]:
        print(f"  [{error.row_number}행] {error.field}: {error.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
