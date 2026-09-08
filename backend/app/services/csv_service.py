"""CSV 업로드 검증과 저장.

기본 모드는 validate-only이며, commit=true인 경우에만 유효한 행을 저장한다.
잘못된 행이 있어도 정상 행의 검증결과는 그대로 반환한다.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import HTTP_413_TOO_LARGE, AppError, ErrorCode
from app.core.timeutil import is_aware, to_kst
from app.domain.enums import SourceType, WorkStatus, WorkType
from app.models.orm import WorkItemORM, to_db_datetime, utcnow
from app.repositories.work_item_repository import WorkItemRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.csv_import import CsvImportResponse, CsvRowError, CsvValidRow
from app.schemas.work_item import WorkItemCreate

REQUIRED_COLUMNS = ["id", "title", "work_type", "zone_id", "start_at", "end_at"]
OPTIONAL_COLUMNS = [
    "description",
    "uses_flammable_material",
    "gas_measurement_completed",
    "ventilation_confirmed",
    "watcher_assigned",
    "status",
]
BOOLEAN_TRUE = {"true", "TRUE", "1"}
BOOLEAN_FALSE = {"false", "FALSE", "0"}
SENSITIVE_FIELDS = {"description"}
FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_for_spreadsheet(value: str | None) -> str | None:
    """CSV 수식 삽입을 막기 위해 화면 재출력/다운로드 값 앞에 작은따옴표를 붙인다."""
    if value is None:
        return None
    if value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


class CsvImportService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.items = WorkItemRepository(session)
        self.zones = ZoneRepository(session)

    # ------------------------------------------------------------------ 진입점
    def import_csv(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        content: bytes,
        commit: bool,
        overwrite: bool,
    ) -> CsvImportResponse:
        self._check_file(filename, content_type, content)
        text = self._decode(content)
        rows = self._read_rows(text)

        zone_ids = {zone.id for zone in self.zones.list_all()}
        errors: list[CsvRowError] = []
        valid_rows: list[CsvValidRow] = []
        seen_ids: set[str] = set()

        for offset, raw_row in enumerate(rows):
            row_number = offset + 2  # 헤더가 1행
            payload, row_errors = self._parse_row(raw_row, row_number, zone_ids, seen_ids, overwrite)
            if row_errors:
                errors.extend(row_errors)
                continue
            assert payload is not None
            seen_ids.add(payload.id or "")
            valid_rows.append(CsvValidRow(row_number=row_number, work_item=payload))

        created_count = 0
        updated_count = 0
        if commit and valid_rows:
            created_count, updated_count = self._persist([row.work_item for row in valid_rows])

        return CsvImportResponse(
            total_rows=len(rows),
            valid_count=len(valid_rows),
            invalid_count=len({error.row_number for error in errors}),
            created_count=created_count,
            updated_count=updated_count,
            valid_rows=valid_rows,
            errors=errors,
            committed=bool(commit and valid_rows),
        )

    # ------------------------------------------------------------------ 파일 검사
    def _check_file(self, filename: str | None, content_type: str | None, content: bytes) -> None:
        if len(content) > self.settings.max_csv_bytes:
            raise AppError(
                ErrorCode.CSV_LIMIT_EXCEEDED,
                f"CSV 파일 크기가 제한({self.settings.max_csv_bytes} bytes)을 초과했습니다.",
                HTTP_413_TOO_LARGE,
                {"size": len(content), "limit": self.settings.max_csv_bytes},
            )
        if not content.strip():
            raise AppError(
                ErrorCode.INVALID_CSV_FILE,
                "빈 파일입니다.",
                status.HTTP_400_BAD_REQUEST,
            )
        if filename and not filename.lower().endswith(".csv"):
            raise AppError(
                ErrorCode.INVALID_CSV_FILE,
                "확장자가 .csv인 파일만 업로드할 수 있습니다.",
                status.HTTP_400_BAD_REQUEST,
                {"filename": filename},
            )
        if content_type and not (
            content_type.startswith("text/")
            or content_type in {"application/csv", "application/vnd.ms-excel", "application/octet-stream"}
        ):
            raise AppError(
                ErrorCode.INVALID_CSV_FILE,
                f"지원하지 않는 MIME 유형입니다: {content_type}",
                status.HTTP_400_BAD_REQUEST,
                {"content_type": content_type},
            )

    @staticmethod
    def _decode(content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp949"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise AppError(
            ErrorCode.INVALID_CSV_FILE,
            "텍스트로 해석할 수 없는 파일입니다.",
            status.HTTP_400_BAD_REQUEST,
        )

    def _read_rows(self, text: str) -> list[dict[str, str]]:
        reader = csv.DictReader(io.StringIO(text))
        header = [column.strip() for column in (reader.fieldnames or [])]
        missing = [column for column in REQUIRED_COLUMNS if column not in header]
        if missing:
            raise AppError(
                ErrorCode.INVALID_CSV_HEADER,
                "필수 열이 누락되었습니다: " + ", ".join(missing),
                status.HTTP_400_BAD_REQUEST,
                {"missing_columns": missing, "required_columns": REQUIRED_COLUMNS},
            )
        rows: list[dict[str, str]] = []
        for raw in reader:
            rows.append({(key or "").strip(): (value if value is not None else "") for key, value in raw.items()})
            if len(rows) > self.settings.max_csv_rows:
                raise AppError(
                    ErrorCode.CSV_LIMIT_EXCEEDED,
                    f"CSV 행 수가 제한({self.settings.max_csv_rows}행)을 초과했습니다.",
                    HTTP_413_TOO_LARGE,
                    {"limit": self.settings.max_csv_rows},
                )
        return rows

    # ------------------------------------------------------------------ 행 파싱
    def _parse_row(
        self,
        raw: dict[str, str],
        row_number: int,
        zone_ids: set[str],
        seen_ids: set[str],
        overwrite: bool,
    ) -> tuple[WorkItemCreate | None, list[CsvRowError]]:
        errors: list[CsvRowError] = []

        def error(field: str, code: str, message: str, value: str | None = None) -> None:
            errors.append(
                CsvRowError(
                    row_number=row_number,
                    field=field,
                    code=code,
                    message=message,
                    raw_value=None if field in SENSITIVE_FIELDS else sanitize_for_spreadsheet(value),
                )
            )

        values = {key: (raw.get(key) or "").strip() for key in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}

        work_item_id = values["id"]
        if not work_item_id:
            error("id", ErrorCode.INVALID_CSV_VALUE, "id는 비어 있을 수 없습니다.", raw.get("id"))
        elif work_item_id in seen_ids:
            error("id", ErrorCode.DUPLICATE_WORK_ITEM_ID, "같은 파일 안에 중복된 id가 있습니다.", work_item_id)
        elif not overwrite and self.items.exists(work_item_id):
            error(
                "id",
                ErrorCode.DUPLICATE_WORK_ITEM_ID,
                "이미 등록된 id입니다. 덮어쓰려면 overwrite=true로 요청하십시오.",
                work_item_id,
            )

        title = values["title"]
        if not title:
            error("title", ErrorCode.INVALID_CSV_VALUE, "title은 비어 있을 수 없습니다.", raw.get("title"))
        elif len(title) > 100:
            error("title", ErrorCode.INVALID_CSV_VALUE, "title은 100자 이하여야 합니다.", title[:20] + "…")

        work_type = self._parse_enum(values["work_type"], WorkType, "work_type", error)
        zone_id = values["zone_id"]
        if not zone_id:
            error("zone_id", ErrorCode.INVALID_CSV_VALUE, "zone_id는 비어 있을 수 없습니다.", raw.get("zone_id"))
        elif zone_id not in zone_ids:
            error("zone_id", ErrorCode.UNKNOWN_ZONE, "등록되지 않은 구역입니다.", zone_id)

        start_at = self._parse_datetime(values["start_at"], "start_at", error)
        end_at = self._parse_datetime(values["end_at"], "end_at", error)
        if start_at and end_at and end_at <= start_at:
            error(
                "end_at",
                ErrorCode.INVALID_TIME_RANGE,
                "종료시각은 시작시각보다 늦어야 합니다.",
                values["end_at"],
            )

        booleans: dict[str, bool | None] = {}
        for field in (
            "uses_flammable_material",
            "gas_measurement_completed",
            "ventilation_confirmed",
            "watcher_assigned",
        ):
            booleans[field] = self._parse_boolean(values[field], field, error)

        item_status = WorkStatus.DRAFT
        if values["status"]:
            parsed_status = self._parse_enum(values["status"], WorkStatus, "status", error)
            if parsed_status is not None:
                item_status = parsed_status

        description = values["description"] or None
        if description and len(description) > self.settings.max_description_length:
            error(
                "description",
                ErrorCode.INVALID_CSV_VALUE,
                f"description은 {self.settings.max_description_length}자 이하여야 합니다.",
            )

        if errors:
            return None, errors

        return (
            WorkItemCreate(
                id=work_item_id,
                title=title,
                description=description,
                work_type=work_type,
                zone_id=zone_id,
                start_at=start_at,
                end_at=end_at,
                status=item_status,
                source_type=SourceType.CSV,
                **booleans,
            ),
            [],
        )

    @staticmethod
    def _parse_enum(value: str, enum_cls, field: str, error) -> object | None:
        if not value:
            error(field, ErrorCode.INVALID_CSV_VALUE, f"{field}은(는) 비어 있을 수 없습니다.", value)
            return None
        try:
            return enum_cls(value)
        except ValueError:
            allowed = ", ".join(member.value for member in enum_cls)
            error(
                field,
                ErrorCode.INVALID_CSV_VALUE,
                f"허용되지 않는 값입니다. 허용값: {allowed}",
                value,
            )
            return None

    @staticmethod
    def _parse_datetime(value: str, field: str, error) -> datetime | None:
        if not value:
            error(field, ErrorCode.INVALID_CSV_VALUE, f"{field}은(는) 비어 있을 수 없습니다.", value)
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            error(
                field,
                ErrorCode.INVALID_CSV_VALUE,
                "ISO 8601 형식이어야 합니다. 예: 2026-03-16T09:00:00+09:00",
                value,
            )
            return None
        if not is_aware(parsed):
            error(field, ErrorCode.TIMEZONE_REQUIRED, "표준시간대 정보가 필요합니다.", value)
            return None
        return to_kst(parsed)

    @staticmethod
    def _parse_boolean(value: str, field: str, error) -> bool | None:
        if value == "":
            return None  # 빈 셀은 '정보 없음'을 뜻한다.
        if value in BOOLEAN_TRUE:
            return True
        if value in BOOLEAN_FALSE:
            return False
        error(
            field,
            ErrorCode.INVALID_CSV_VALUE,
            "true/false, TRUE/FALSE, 1/0 중 하나여야 합니다. 빈 셀은 정보 없음으로 처리됩니다.",
            value,
        )
        return None

    # ------------------------------------------------------------------ 저장
    def _persist(self, payloads: list[WorkItemCreate]) -> tuple[int, int]:
        created = 0
        updated = 0
        for payload in payloads:
            assert payload.id is not None
            existing = self.items.get(payload.id)
            target = existing or WorkItemORM(id=payload.id, created_at=utcnow())
            target.title = payload.title
            target.description = payload.description
            target.work_type = payload.work_type.value
            target.zone_id = payload.zone_id
            target.start_at = to_db_datetime(payload.start_at)
            target.end_at = to_db_datetime(payload.end_at)
            target.uses_flammable_material = payload.uses_flammable_material
            target.gas_measurement_completed = payload.gas_measurement_completed
            target.ventilation_confirmed = payload.ventilation_confirmed
            target.watcher_assigned = payload.watcher_assigned
            target.status = payload.status.value
            target.source_type = SourceType.CSV.value
            target.external_id = payload.external_id
            target.updated_at = utcnow()
            if existing is None:
                self.session.add(target)
                created += 1
            else:
                updated += 1
        self.session.commit()
        return created, updated
