import type { Severity, SourceType, SpatialRelation, WorkStatus, WorkType } from "@/types/domain";

export const WORK_TYPE_LABEL: Record<WorkType, string> = {
  HOT_WORK: "화기작업",
  PAINTING: "도장작업",
  SOLVENT_WORK: "유기용제 작업",
  CONFINED_SPACE: "밀폐공간 작업",
  OTHER: "기타",
};

export const WORK_STATUS_LABEL: Record<WorkStatus, string> = {
  DRAFT: "미검토",
  REVIEWED: "검토완료",
};

export const SOURCE_TYPE_LABEL: Record<SourceType, string> = {
  MANUAL: "직접 입력",
  CSV: "CSV",
  LLM: "자연어",
};

/** 색상만으로 등급을 구분하지 않기 위해 기호와 문자열을 함께 사용한다. */
export const SEVERITY_LABEL: Record<Severity, string> = {
  HIGH: "높음",
  MEDIUM: "보통",
  LOW: "낮음",
};

export const SEVERITY_MARK: Record<Severity, string> = {
  HIGH: "●●●",
  MEDIUM: "●●○",
  LOW: "●○○",
};

export const SPATIAL_RELATION_LABEL: Record<SpatialRelation, string> = {
  SAME: "동일 구역",
  ADJACENT: "인접 구역",
  UNRELATED: "무관한 구역",
};

export const SAFETY_FIELD_LABEL: Record<string, string> = {
  uses_flammable_material: "가연성 물질 사용",
  gas_measurement_completed: "가스측정 완료",
  ventilation_confirmed: "환기 확인",
  watcher_assigned: "감시인 배치",
};

export const DISCLAIMER = "본 결과는 사전 검토 보조정보이며, 안전관리자의 최종 확인이 필요합니다.";

/** null(정보 없음)과 false(미실시로 입력)를 구분해 표시한다. */
export function triStateLabel(value: boolean | null): string {
  if (value === null || value === undefined) return "미입력";
  return value ? "예" : "아니오(미실시)";
}
