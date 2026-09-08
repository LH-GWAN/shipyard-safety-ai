from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.timeutil import day_bounds
from app.models.orm import WorkItemORM, to_db_datetime


@dataclass(frozen=True)
class WorkItemFilters:
    day: date | None = None
    work_type: str | None = None
    zone_id: str | None = None
    status: str | None = None


class WorkItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, work_item_id: str) -> WorkItemORM | None:
        return self.session.get(WorkItemORM, work_item_id)

    def exists(self, work_item_id: str) -> bool:
        return self.get(work_item_id) is not None

    def list_all(self) -> list[WorkItemORM]:
        return list(self.session.scalars(select(WorkItemORM).order_by(WorkItemORM.start_at, WorkItemORM.id)))

    def list_by_ids(self, ids: list[str]) -> list[WorkItemORM]:
        if not ids:
            return []
        stmt = select(WorkItemORM).where(WorkItemORM.id.in_(ids)).order_by(WorkItemORM.start_at, WorkItemORM.id)
        return list(self.session.scalars(stmt))

    def list_by_day(self, day: date) -> list[WorkItemORM]:
        start, end = day_bounds(day)
        stmt = (
            select(WorkItemORM)
            .where(WorkItemORM.start_at < to_db_datetime(end), WorkItemORM.end_at > to_db_datetime(start))
            .order_by(WorkItemORM.start_at, WorkItemORM.id)
        )
        return list(self.session.scalars(stmt))

    def search(self, filters: WorkItemFilters, page: int, page_size: int) -> tuple[list[WorkItemORM], int]:
        stmt = self._apply_filters(select(WorkItemORM), filters)
        total = self.session.scalar(self._apply_filters(select(func.count()).select_from(WorkItemORM), filters))
        stmt = stmt.order_by(WorkItemORM.start_at, WorkItemORM.id).offset((page - 1) * page_size).limit(page_size)
        return list(self.session.scalars(stmt)), int(total or 0)

    @staticmethod
    def _apply_filters(stmt: Select, filters: WorkItemFilters) -> Select:
        if filters.day is not None:
            start, end = day_bounds(filters.day)
            stmt = stmt.where(
                WorkItemORM.start_at < to_db_datetime(end),
                WorkItemORM.end_at > to_db_datetime(start),
            )
        if filters.work_type:
            stmt = stmt.where(WorkItemORM.work_type == filters.work_type)
        if filters.zone_id:
            stmt = stmt.where(WorkItemORM.zone_id == filters.zone_id)
        if filters.status:
            stmt = stmt.where(WorkItemORM.status == filters.status)
        return stmt

    def add(self, item: WorkItemORM) -> WorkItemORM:
        self.session.add(item)
        self.session.commit()
        return item

    def add_many(self, items: list[WorkItemORM]) -> None:
        self.session.add_all(items)
        self.session.commit()

    def commit(self) -> None:
        self.session.commit()

    def delete(self, item: WorkItemORM) -> None:
        self.session.delete(item)
        self.session.commit()

    def latest_updated_at(self) -> datetime | None:
        return self.session.scalar(select(func.max(WorkItemORM.updated_at)))
