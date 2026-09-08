from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.orm import AlertORM, AnalysisORM


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, analysis: AnalysisORM) -> AnalysisORM:
        self.session.add(analysis)
        self.session.commit()
        return analysis

    def get(self, analysis_id: str) -> AnalysisORM | None:
        return self.session.get(AnalysisORM, analysis_id)

    def latest(self) -> AnalysisORM | None:
        stmt = select(AnalysisORM).order_by(desc(AnalysisORM.analyzed_at), desc(AnalysisORM.id)).limit(1)
        return self.session.scalars(stmt).first()

    def alerts_of(self, analysis_id: str) -> list[AlertORM]:
        stmt = select(AlertORM).where(AlertORM.analysis_id == analysis_id).order_by(AlertORM.order_index)
        return list(self.session.scalars(stmt))

    def get_alert(self, alert_id: str) -> AlertORM | None:
        return self.session.get(AlertORM, alert_id)
