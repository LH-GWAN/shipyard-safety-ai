"""WorkItem 검증과 CRUD."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import HTTP_422_UNPROCESSABLE, AppError, ErrorCode
from app.core.timeutil import is_aware, to_kst
from app.models.orm import WorkItemORM, to_db_datetime, utcnow
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.work_item_repository import WorkItemFilters, WorkItemRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.work_item import WorkItemCreate, WorkItemListResponse, WorkItemOut, WorkItemUpdate
from app.services.converters import orm_to_out

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class WorkItemService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = WorkItemRepository(session)
        self.zones = ZoneRepository(session)
        self.analyses = AnalysisRepository(session)

    # ------------------------------------------------------------------ 검증
    def validate_times(self, start_at: datetime, end_at: datetime) -> tuple[datetime, datetime]:
        for label, value in (("start_at", start_at), ("end_at", end_at)):
            if not is_aware(value):
                raise AppError(
                    ErrorCode.TIMEZONE_REQUIRED,
                    "시각에는 표준시간대 정보가 포함되어야 합니다. 예: 2026-03-16T09:00:00+09:00",
                    HTTP_422_UNPROCESSABLE,
                    {"field": label},
                )
        if end_at <= start_at:
            raise AppError(
                ErrorCode.INVALID_TIME_RANGE,
                "종료시각은 시작시각보다 늦어야 합니다.",
                HTTP_422_UNPROCESSABLE,
                {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            )
        return to_kst(start_at), to_kst(end_at)

    def validate_zone(self, zone_id: str) -> str:
        if self.zones.get(zone_id) is None:
            raise AppError(
                ErrorCode.UNKNOWN_ZONE,
                f"등록되지 않은 구역입니다: {zone_id}",
                HTTP_422_UNPROCESSABLE,
                {"field": "zone_id", "value": zone_id},
            )
        return zone_id

    @staticmethod
    def validate_title(title: str) -> str:
        cleaned = title.strip()
        if not cleaned:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "작업명은 공백만으로 구성될 수 없습니다.",
                HTTP_422_UNPROCESSABLE,
                {"field": "title"},
            )
        return cleaned

    # ------------------------------------------------------------------ 조회
    def get_or_404(self, work_item_id: str) -> WorkItemORM:
        item = self.repo.get(work_item_id)
        if item is None:
            raise AppError(
                ErrorCode.WORK_ITEM_NOT_FOUND,
                f"작업계획을 찾을 수 없습니다: {work_item_id}",
                status.HTTP_404_NOT_FOUND,
            )
        return item

    def get(self, work_item_id: str) -> WorkItemOut:
        item = self.get_or_404(work_item_id)
        return orm_to_out(item, self._zone_names().get(item.zone_id), self._alert_ids().__contains__(item.id))

    def list(
        self,
        day: date | None = None,
        work_type: str | None = None,
        zone_id: str | None = None,
        item_status: str | None = None,
        has_alert: bool | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> WorkItemListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
        filters = WorkItemFilters(day=day, work_type=work_type, zone_id=zone_id, status=item_status)
        zone_names = self._zone_names()
        alert_ids = self._alert_ids()

        if has_alert is None:
            rows, total = self.repo.search(filters, page, page_size)
            items = [orm_to_out(row, zone_names.get(row.zone_id), row.id in alert_ids) for row in rows]
            return WorkItemListResponse(items=items, total=total, page=page, page_size=page_size)

        # has_alert 필터는 최근 분석 결과를 기준으로 하므로 애플리케이션 계층에서 적용한다.
        rows, _ = self.repo.search(filters, 1, 10_000)
        filtered = [row for row in rows if (row.id in alert_ids) == has_alert]
        total = len(filtered)
        offset = (page - 1) * page_size
        window = filtered[offset : offset + page_size]
        items = [orm_to_out(row, zone_names.get(row.zone_id), row.id in alert_ids) for row in window]
        return WorkItemListResponse(items=items, total=total, page=page, page_size=page_size)

    # ------------------------------------------------------------------ 변경
    def create(self, payload: WorkItemCreate, overwrite: bool = False) -> WorkItemOut:
        title = self.validate_title(payload.title)
        start_at, end_at = self.validate_times(payload.start_at, payload.end_at)
        self.validate_zone(payload.zone_id)

        work_item_id = (payload.id or "").strip() or f"WI_{uuid.uuid4().hex[:12].upper()}"
        existing = self.repo.get(work_item_id)
        if existing is not None and not overwrite:
            raise AppError(
                ErrorCode.DUPLICATE_WORK_ITEM_ID,
                f"이미 존재하는 작업 ID입니다: {work_item_id}",
                status.HTTP_409_CONFLICT,
                {"id": work_item_id},
            )

        target = existing or WorkItemORM(id=work_item_id, created_at=utcnow())
        self._assign(target, payload, title, start_at, end_at)
        target.source_type = payload.source_type.value
        target.updated_at = utcnow()
        if existing is None:
            self.repo.add(target)
        else:
            self.repo.commit()
        return orm_to_out(target, self._zone_names().get(target.zone_id))

    def update(self, work_item_id: str, payload: WorkItemUpdate) -> WorkItemOut:
        item = self.get_or_404(work_item_id)
        title = self.validate_title(payload.title)
        start_at, end_at = self.validate_times(payload.start_at, payload.end_at)
        self.validate_zone(payload.zone_id)

        self._assign(item, payload, title, start_at, end_at)
        if payload.source_type is not None:
            item.source_type = payload.source_type.value
        item.updated_at = utcnow()
        self.repo.commit()
        return orm_to_out(item, self._zone_names().get(item.zone_id))

    def delete(self, work_item_id: str) -> None:
        item = self.get_or_404(work_item_id)
        self.repo.delete(item)

    # ------------------------------------------------------------------ 내부
    @staticmethod
    def _assign(
        target: WorkItemORM,
        payload: WorkItemCreate | WorkItemUpdate,
        title: str,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        target.title = title
        target.description = payload.description
        target.work_type = payload.work_type.value
        target.zone_id = payload.zone_id
        target.start_at = to_db_datetime(start_at)
        target.end_at = to_db_datetime(end_at)
        target.uses_flammable_material = payload.uses_flammable_material
        target.gas_measurement_completed = payload.gas_measurement_completed
        target.ventilation_confirmed = payload.ventilation_confirmed
        target.watcher_assigned = payload.watcher_assigned
        target.status = payload.status.value
        target.external_id = payload.external_id

    def _zone_names(self) -> dict[str, str]:
        return {zone.id: zone.name for zone in self.zones.list_all()}

    def _alert_ids(self) -> set[str]:
        latest = self.analyses.latest()
        if latest is None:
            return set()
        ids: set[str] = set()
        for alert in self.analyses.alerts_of(latest.id):
            ids.update(alert.work_item_ids)
        return ids
