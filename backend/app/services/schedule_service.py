"""규칙형 시간 변경안 미리보기와 적용."""

from __future__ import annotations

import hashlib

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import HTTP_422_UNPROCESSABLE, AppError, ErrorCode
from app.core.timeutil import iso
from app.domain.models import AlertData, WorkItemData
from app.domain.schedule import ShiftProposal, compute_shift
from app.models.orm import AlertORM, WorkItemORM, from_db_datetime, to_db_datetime, utcnow
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.work_item_repository import WorkItemRepository
from app.schemas.analysis import AlertOut
from app.schemas.schedule import (
    ShiftApplyRequest,
    ShiftApplyResponse,
    ShiftChange,
    ShiftPreviewRequest,
    ShiftPreviewResponse,
)
from app.services.analysis_service import AnalysisService, alert_data_to_out


class ScheduleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.items = WorkItemRepository(session)
        self.analyses = AnalysisRepository(session)
        self.analysis = AnalysisService(session)

    # ------------------------------------------------------------------ 미리보기
    def preview(self, request: ShiftPreviewRequest) -> ShiftPreviewResponse:
        alert, move_row, reference_row = self._resolve(request.alert_id, request.move_work_item_id)
        proposal = self._propose(move_row, reference_row, request.buffer_minutes)

        before, after = self._before_after(move_row, proposal)
        resolved, added = self._diff(before, after)

        return ShiftPreviewResponse(
            preview_token=self._token(alert.id, move_row, reference_row, request.buffer_minutes),
            alert_id=alert.id,
            change=self._to_change(move_row.title, proposal),
            resolved_alerts=[alert_data_to_out(item) for item in resolved],
            new_alerts=[alert_data_to_out(item) for item in added],
            remaining_alert_count=len(after),
            before_alert_count=len(before),
            after_alert_count=len(after),
        )

    # ------------------------------------------------------------------ 적용
    def apply(self, request: ShiftApplyRequest) -> ShiftApplyResponse:
        alert, move_row, reference_row = self._resolve(request.alert_id, request.move_work_item_id)

        # 사용자가 미리보기로 확인한 변경안만 적용한다. 토큰 검증 이전에는 어떤 값도 수정하지 않는다.
        submitted_token = (request.preview_token or "").strip()
        if not submitted_token:
            raise AppError(
                ErrorCode.STALE_SCHEDULE_PREVIEW,
                "미리보기 토큰이 필요합니다. 변경안을 먼저 미리보기로 확인하십시오.",
                HTTP_422_UNPROCESSABLE,
                {"alert_id": alert.id, "field": "preview_token"},
            )
        current_token = self._token(alert.id, move_row, reference_row, request.buffer_minutes)
        if submitted_token != current_token:
            raise AppError(
                ErrorCode.STALE_SCHEDULE_PREVIEW,
                "미리보기 내용이 현재 작업 상태와 일치하지 않습니다. 다시 미리보기를 실행하십시오.",
                status.HTTP_409_CONFLICT,
                {"alert_id": alert.id},
            )

        proposal = self._propose(move_row, reference_row, request.buffer_minutes)
        before, after = self._before_after(move_row, proposal)
        resolved, added = self._diff(before, after)

        move_row.start_at = to_db_datetime(proposal.after_start_at)
        move_row.end_at = to_db_datetime(proposal.after_end_at)
        move_row.updated_at = utcnow()
        self.items.commit()

        analysis = self.analysis.run()
        return ShiftApplyResponse(
            change=self._to_change(move_row.title, proposal),
            analysis=analysis,
            resolved_alerts=[alert_data_to_out(item) for item in resolved],
            new_alerts=[alert_data_to_out(item) for item in added],
        )

    # ------------------------------------------------------------------ 내부
    def _resolve(self, alert_id: str, move_work_item_id: str) -> tuple[AlertORM, WorkItemORM, WorkItemORM]:
        alert = self.analyses.get_alert(alert_id)
        if alert is None:
            raise AppError(
                ErrorCode.ALERT_NOT_FOUND,
                f"경보를 찾을 수 없습니다: {alert_id}",
                status.HTTP_404_NOT_FOUND,
            )
        work_item_ids = list(alert.work_item_ids)
        if len(work_item_ids) != 2:
            raise AppError(
                ErrorCode.INVALID_REQUEST,
                "시간 변경안은 두 작업의 시간이 겹친 경보에만 제공합니다.",
                status.HTTP_400_BAD_REQUEST,
                {"alert_id": alert_id, "work_item_ids": work_item_ids},
            )
        if move_work_item_id not in work_item_ids:
            raise AppError(
                ErrorCode.INVALID_REQUEST,
                "이동할 작업은 해당 경보에 포함된 작업이어야 합니다.",
                status.HTTP_400_BAD_REQUEST,
                {"alert_id": alert_id, "work_item_ids": work_item_ids},
            )
        reference_id = next(wid for wid in work_item_ids if wid != move_work_item_id)

        move_row = self.items.get(move_work_item_id)
        reference_row = self.items.get(reference_id)
        if move_row is None or reference_row is None:
            raise AppError(
                ErrorCode.WORK_ITEM_NOT_FOUND,
                "경보에 포함된 작업계획을 찾을 수 없습니다.",
                status.HTTP_404_NOT_FOUND,
                {"alert_id": alert_id},
            )
        return alert, move_row, reference_row

    @staticmethod
    def _propose(move_row: WorkItemORM, reference_row: WorkItemORM, buffer_minutes: int) -> ShiftProposal:
        from app.services.converters import orm_to_domain

        try:
            return compute_shift(orm_to_domain(move_row), orm_to_domain(reference_row), buffer_minutes)
        except ValueError as exc:
            raise AppError(
                ErrorCode.INVALID_REQUEST,
                str(exc),
                HTTP_422_UNPROCESSABLE,
                {"field": "buffer_minutes"},
            ) from exc

    def _before_after(self, move_row: WorkItemORM, proposal: ShiftProposal) -> tuple[list[AlertData], list[AlertData]]:
        rows = self.items.list_all()
        current, _ = self.analysis.partition(rows)
        before = self.analysis.evaluate(current)

        modified: list[WorkItemData] = []
        for item in current:
            if item.id == move_row.id:
                modified.append(
                    WorkItemData(
                        id=item.id,
                        title=item.title,
                        work_type=item.work_type,
                        zone_id=item.zone_id,
                        start_at=proposal.after_start_at,
                        end_at=proposal.after_end_at,
                        uses_flammable_material=item.uses_flammable_material,
                        gas_measurement_completed=item.gas_measurement_completed,
                        ventilation_confirmed=item.ventilation_confirmed,
                        watcher_assigned=item.watcher_assigned,
                    )
                )
            else:
                modified.append(item)
        after = self.analysis.evaluate(modified)
        return before, after

    @staticmethod
    def _diff(before: list[AlertData], after: list[AlertData]) -> tuple[list[AlertData], list[AlertData]]:
        before_keys = {alert.duplicate_key for alert in before}
        after_keys = {alert.duplicate_key for alert in after}
        resolved = [alert for alert in before if alert.duplicate_key not in after_keys]
        added = [alert for alert in after if alert.duplicate_key not in before_keys]
        return resolved, added

    @staticmethod
    def _to_change(title: str, proposal: ShiftProposal) -> ShiftChange:
        return ShiftChange(
            work_item_id=proposal.work_item_id,
            title=title,
            before_start_at=proposal.before_start_at,
            before_end_at=proposal.before_end_at,
            after_start_at=proposal.after_start_at,
            after_end_at=proposal.after_end_at,
            duration_minutes=proposal.duration_minutes,
            buffer_minutes=proposal.buffer_minutes,
            reference_work_item_id=proposal.reference_work_item_id,
        )

    @staticmethod
    def _token(alert_id: str, move_row: WorkItemORM, reference_row: WorkItemORM, buffer_minutes: int) -> str:
        payload = "|".join(
            [
                alert_id,
                move_row.id,
                str(buffer_minutes),
                iso(from_db_datetime(move_row.start_at)),
                iso(from_db_datetime(move_row.end_at)),
                iso(from_db_datetime(reference_row.start_at)),
                iso(from_db_datetime(reference_row.end_at)),
            ]
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]


__all__ = ["ScheduleService", "AlertOut"]
