from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import RuleType
from app.schemas.analysis import (
    AlertListResponse,
    AnalysisResultOut,
    AnalysisRunRequest,
    RuleListResponse,
    RuleOut,
)
from app.schemas.common import ErrorResponse
from app.services.analysis_service import AnalysisService
from app.services.rule_catalog import get_rules

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analysis/run", response_model=AnalysisResultOut, summary="규칙 검사 실행")
def run_analysis(
    request: Request,
    payload: AnalysisRunRequest | None = None,
    session: Session = Depends(get_db),
) -> AnalysisResultOut:
    payload = payload or AnalysisRunRequest()
    result = AnalysisService(session).run(day=payload.date, work_item_ids=payload.work_item_ids)
    request.state.analysis_id = result.analysis_id
    return result


@router.get("/analysis/latest", response_model=AnalysisResultOut | None, summary="최근 분석 결과 조회")
def latest_analysis(session: Session = Depends(get_db)) -> AnalysisResultOut | None:
    return AnalysisService(session).latest_result()


@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisResultOut,
    responses={404: {"model": ErrorResponse}},
    summary="분석 결과 조회",
)
def get_analysis(analysis_id: str, session: Session = Depends(get_db)) -> AnalysisResultOut:
    return AnalysisService(session).get_result(analysis_id)


@router.get(
    "/analysis/{analysis_id}/alerts",
    response_model=AlertListResponse,
    responses={404: {"model": ErrorResponse}},
    summary="분석 경보 목록 조회",
)
def get_analysis_alerts(analysis_id: str, session: Session = Depends(get_db)) -> AlertListResponse:
    return AnalysisService(session).get_alerts(analysis_id)


@router.get("/rules", response_model=RuleListResponse, summary="규칙 카탈로그 조회")
def list_rules() -> RuleListResponse:
    items = [
        RuleOut(
            id=rule.id,
            name=rule.name,
            description=rule.description,
            rule_type=rule.rule_type,
            severity=rule.severity,
            enabled=rule.enabled,
            reference_title=rule.reference_title,
            reference_url=rule.reference_url,
            reference_articles=list(rule.reference_articles),
            reference_note=rule.reference_note,
            reference_verified_at=rule.reference_verified_at,
            requires_site_validation=rule.requires_site_validation,
            version=rule.version,
            reviewed=rule.reviewed,
        )
        for rule in get_rules()
    ]
    return RuleListResponse(
        items=items,
        total=len(items),
        alert_rule_count=sum(1 for rule in items if rule.rule_type is RuleType.ALERT),
        input_validation_rule_count=sum(1 for rule in items if rule.rule_type is RuleType.INPUT_VALIDATION),
    )
