"""분석 실행과 결과 저장."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.logging import log_event
from app.domain.models import AlertData, WorkItemData
from app.domain.rules import RuleEvaluator, make_alert_id
from app.models.orm import AlertORM, AnalysisORM, WorkItemORM, from_db_datetime, utcnow
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.work_item_repository import WorkItemRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.analysis import AlertListResponse, AlertOut, AnalysisResultOut, SeverityCounts
from app.services.converters import alert_orm_to_out, orm_to_domain
from app.services.rule_catalog import get_rules


class AnalysisService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.items = WorkItemRepository(session)
        self.zones = ZoneRepository(session)
        self.analyses = AnalysisRepository(session)

    # ------------------------------------------------------------------ 평가
    def evaluator(self) -> RuleEvaluator:
        return RuleEvaluator(get_rules(), self.zones.graph())

    def partition(self, rows: list[WorkItemORM]) -> tuple[list[WorkItemData], list[str]]:
        """분석 가능한 작업과 입력 오류로 제외된 작업 ID를 나눈다."""
        zone_graph = self.zones.graph()
        analyzable: list[WorkItemData] = []
        invalid: list[str] = []
        for row in rows:
            if row.start_at is None or row.end_at is None or row.end_at <= row.start_at:
                invalid.append(row.id)
                continue
            if row.zone_id not in zone_graph:
                invalid.append(row.id)
                continue
            analyzable.append(orm_to_domain(row))
        return analyzable, invalid

    def evaluate(self, items: list[WorkItemData], analysis_id: str = "") -> list[AlertData]:
        return self.evaluator().evaluate(items, analysis_id)

    # ------------------------------------------------------------------ 실행
    def select_rows(self, day: date | None, work_item_ids: list[str] | None) -> list[WorkItemORM]:
        if work_item_ids:
            rows = self.items.list_by_ids(work_item_ids)
            found = {row.id for row in rows}
            missing = [wid for wid in work_item_ids if wid not in found]
            if missing:
                raise AppError(
                    ErrorCode.WORK_ITEM_NOT_FOUND,
                    "존재하지 않는 작업 ID가 포함되어 있습니다.",
                    status.HTTP_404_NOT_FOUND,
                    {"missing_ids": missing},
                )
            return rows
        if day is not None:
            return self.items.list_by_day(day)
        return self.items.list_all()

    def run(self, day: date | None = None, work_item_ids: list[str] | None = None) -> AnalysisResultOut:
        started = time.perf_counter()
        rows = self.select_rows(day, work_item_ids)
        analyzable, invalid = self.partition(rows)

        analysis_id = f"AN_{uuid.uuid4().hex[:16]}"
        alerts = self.evaluate(analyzable, analysis_id)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)

        analyzed_at = utcnow()
        severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for alert in alerts:
            severity_counts[alert.severity.value] = severity_counts.get(alert.severity.value, 0) + 1

        record = AnalysisORM(
            id=analysis_id,
            analyzed_at=analyzed_at,
            total_work_items=len(rows),
            analyzed_work_items=len(analyzable),
            invalid_work_items=len(invalid),
            alert_count=len(alerts),
            severity_counts=severity_counts,
            duration_ms=duration_ms,
            alerts=[
                AlertORM(
                    id=alert.id,
                    analysis_id=analysis_id,
                    order_index=index,
                    rule_id=alert.rule_id,
                    severity=alert.severity.value,
                    work_item_ids=list(alert.work_item_ids),
                    message=alert.message,
                    evidence=alert.evidence,
                    recommended_action=alert.recommended_action,
                    created_at=analyzed_at,
                )
                for index, alert in enumerate(alerts)
            ],
        )
        self.analyses.add(record)
        log_event(
            "analysis_completed",
            analysis_id=analysis_id,
            analyzed_work_items=len(analyzable),
            alert_count=len(alerts),
            duration_ms=duration_ms,
        )
        return self.to_result(record)

    # ------------------------------------------------------------------ 조회
    def get_result(self, analysis_id: str) -> AnalysisResultOut:
        return self.to_result(self._get_or_404(analysis_id))

    def get_alerts(self, analysis_id: str) -> AlertListResponse:
        record = self._get_or_404(analysis_id)
        alerts = [alert_orm_to_out(alert) for alert in self.analyses.alerts_of(record.id)]
        return AlertListResponse(analysis_id=record.id, items=alerts, total=len(alerts))

    def latest_result(self) -> AnalysisResultOut | None:
        record = self.analyses.latest()
        return self.to_result(record) if record else None

    def _get_or_404(self, analysis_id: str) -> AnalysisORM:
        record = self.analyses.get(analysis_id)
        if record is None:
            raise AppError(
                ErrorCode.ANALYSIS_NOT_FOUND,
                f"분석 결과를 찾을 수 없습니다: {analysis_id}",
                status.HTTP_404_NOT_FOUND,
            )
        return record

    @staticmethod
    def to_result(record: AnalysisORM) -> AnalysisResultOut:
        return AnalysisResultOut(
            analysis_id=record.id,
            analyzed_at=from_db_datetime(record.analyzed_at),
            total_work_items=record.total_work_items,
            analyzed_work_items=record.analyzed_work_items,
            invalid_work_items=record.invalid_work_items,
            alert_count=record.alert_count,
            severity_counts=SeverityCounts(**record.severity_counts),
            duration_ms=record.duration_ms,
            alerts=[alert_orm_to_out(alert) for alert in record.alerts],
        )


def alert_data_to_out(alert: AlertData) -> AlertOut:
    return AlertOut(
        id=alert.id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        work_item_ids=list(alert.work_item_ids),
        message=alert.message,
        evidence=alert.evidence,
        recommended_action=alert.recommended_action,
        created_at=datetime.now(UTC),
    )


__all__ = ["AnalysisService", "alert_data_to_out", "make_alert_id"]
