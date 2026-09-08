"""ORM ↔ 도메인/스키마 변환."""

from __future__ import annotations

from app.domain.enums import WorkType
from app.domain.models import AlertData, WorkItemData
from app.models.orm import AlertORM, WorkItemORM, from_db_datetime
from app.schemas.analysis import AlertOut
from app.schemas.work_item import WorkItemOut


def orm_to_domain(item: WorkItemORM) -> WorkItemData:
    return WorkItemData(
        id=item.id,
        title=item.title,
        work_type=WorkType(item.work_type),
        zone_id=item.zone_id,
        start_at=from_db_datetime(item.start_at),
        end_at=from_db_datetime(item.end_at),
        uses_flammable_material=item.uses_flammable_material,
        gas_measurement_completed=item.gas_measurement_completed,
        ventilation_confirmed=item.ventilation_confirmed,
        watcher_assigned=item.watcher_assigned,
    )


def orm_to_out(item: WorkItemORM, zone_name: str | None = None, has_alert: bool | None = None) -> WorkItemOut:
    return WorkItemOut(
        id=item.id,
        title=item.title,
        description=item.description,
        work_type=item.work_type,
        zone_id=item.zone_id,
        zone_name=zone_name,
        start_at=from_db_datetime(item.start_at),
        end_at=from_db_datetime(item.end_at),
        uses_flammable_material=item.uses_flammable_material,
        gas_measurement_completed=item.gas_measurement_completed,
        ventilation_confirmed=item.ventilation_confirmed,
        watcher_assigned=item.watcher_assigned,
        status=item.status,
        source_type=item.source_type,
        external_id=item.external_id,
        created_at=from_db_datetime(item.created_at),
        updated_at=from_db_datetime(item.updated_at),
        has_alert=has_alert,
    )


def alert_orm_to_out(alert: AlertORM) -> AlertOut:
    return AlertOut(
        id=alert.id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        work_item_ids=list(alert.work_item_ids),
        message=alert.message,
        evidence=alert.evidence,
        recommended_action=alert.recommended_action,
        created_at=from_db_datetime(alert.created_at),
    )


def alert_data_to_out(alert: AlertData, created_at) -> AlertOut:
    return AlertOut(
        id=alert.id,
        rule_id=alert.rule_id,
        severity=alert.severity,
        work_item_ids=list(alert.work_item_ids),
        message=alert.message,
        evidence=alert.evidence,
        recommended_action=alert.recommended_action,
        created_at=created_at,
    )
