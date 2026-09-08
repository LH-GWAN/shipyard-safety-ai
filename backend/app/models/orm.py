"""SQLAlchemy ORM 모델.

시간 값은 DB에 UTC naive datetime으로 저장하고, 조회 시 KST aware 값으로 변환한다.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.timeutil import KST


class Base(DeclarativeBase):
    pass


def to_db_datetime(value: datetime) -> datetime:
    """timezone-aware datetime을 UTC naive로 변환한다."""
    return value.astimezone(UTC).replace(tzinfo=None)


def from_db_datetime(value: datetime) -> datetime:
    """DB의 UTC naive datetime을 KST aware로 변환한다."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(KST)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ZoneORM(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adjacent_zone_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class WorkItemORM(Base):
    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_type: Mapped[str] = mapped_column(String(32), nullable=False)
    zone_id: Mapped[str] = mapped_column(String(64), ForeignKey("zones.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    uses_flammable_material: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gas_measurement_completed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ventilation_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    watcher_assigned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AnalysisORM(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_work_items: Mapped[int] = mapped_column(Integer, nullable=False)
    analyzed_work_items: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_work_items: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_count: Mapped[int] = mapped_column(Integer, nullable=False)
    severity_counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    duration_ms: Mapped[float] = mapped_column(nullable=False)

    alerts: Mapped[list[AlertORM]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="AlertORM.order_index",
    )


class AlertORM(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String(64), ForeignKey("analyses.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    work_item_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    analysis: Mapped[AnalysisORM] = relationship(back_populates="alerts")
