import type { AnalysisResult, Alert, SafetyRule, WorkItem, Zone } from "@/types/domain";

export const zones: Zone[] = [
  { id: "A_BLOCK_1", name: "A블록 1구역", adjacent_zone_ids: ["A_BLOCK_2"] },
  { id: "A_BLOCK_2", name: "A블록 2구역", adjacent_zone_ids: [] },
  { id: "TANK_A", name: "탱크 A", adjacent_zone_ids: [] },
];

export const rules: SafetyRule[] = [
  {
    id: "R001",
    name: "화기작업과 도장작업 충돌",
    description: "화기작업과 도장작업의 시간·공간 중첩",
    rule_type: "ALERT",
    severity: "HIGH",
    enabled: true,
    reference_title: "산업안전보건기준에 관한 규칙 제241조(화재위험작업 시의 준수사항)",
    reference_url: "https://www.law.go.kr/법령/산업안전보건기준에관한규칙",
    reference_articles: ["제241조제2항제3호"],
    reference_note: "가연성물질이 있는 장소의 화재위험작업 시 방호조치를 요구한다.",
    reference_verified_at: "2026-09-06",
    requires_site_validation: true,
    version: "1.1.0",
    reviewed: true,
  },
  {
    id: "R101",
    name: "밀폐공간 가스측정 정보 미충족",
    description: "밀폐공간 가스측정 값 확인",
    rule_type: "ALERT",
    severity: "HIGH",
    enabled: true,
    reference_title: "산업안전보건기준에 관한 규칙 제619조의2(산소 및 유해가스 농도의 측정)",
    reference_url: "https://www.law.go.kr/법령/산업안전보건기준에관한규칙",
    reference_articles: ["제619조의2제1항"],
    reference_note: "작업 시작 전 산소 및 유해가스 농도 측정을 요구한다.",
    reference_verified_at: "2026-09-06",
    requires_site_validation: true,
    version: "1.1.0",
    reviewed: true,
  },
];

export function makeWorkItem(overrides: Partial<WorkItem> = {}): WorkItem {
  return {
    id: "W001",
    title: "A블록 1구역 보강재 용접",
    description: null,
    work_type: "HOT_WORK",
    zone_id: "A_BLOCK_1",
    zone_name: "A블록 1구역",
    start_at: "2026-03-16T09:00:00+09:00",
    end_at: "2026-03-16T12:00:00+09:00",
    uses_flammable_material: null,
    gas_measurement_completed: null,
    ventilation_confirmed: null,
    watcher_assigned: null,
    status: "REVIEWED",
    source_type: "CSV",
    external_id: null,
    created_at: "2026-03-10T09:00:00+09:00",
    updated_at: "2026-03-10T09:00:00+09:00",
    has_alert: true,
    ...overrides,
  };
}

export const pairAlert: Alert = {
  id: "AL_pair",
  rule_id: "R001",
  severity: "HIGH",
  work_item_ids: ["W001", "W002"],
  message: "화기작업 'A블록 1구역 보강재 용접'과(와) 도장작업 'A블록 1구역 외판 도장'이(가) 동일 구역에서 60분간 시간 중첩됩니다.",
  evidence: {
    work_items: [
      {
        id: "W001",
        title: "A블록 1구역 보강재 용접",
        work_type: "HOT_WORK",
        zone_id: "A_BLOCK_1",
        zone_name: "A블록 1구역",
        start_at: "2026-03-16T09:00:00+09:00",
        end_at: "2026-03-16T12:00:00+09:00",
        uses_flammable_material: null,
      },
      {
        id: "W002",
        title: "A블록 1구역 외판 도장",
        work_type: "PAINTING",
        zone_id: "A_BLOCK_1",
        zone_name: "A블록 1구역",
        start_at: "2026-03-16T11:00:00+09:00",
        end_at: "2026-03-16T14:00:00+09:00",
        uses_flammable_material: null,
      },
    ],
    spatial_relation: "SAME",
    overlap_start: "2026-03-16T11:00:00+09:00",
    overlap_end: "2026-03-16T12:00:00+09:00",
    overlap_minutes: 60,
  },
  recommended_action: "두 작업의 시간을 분리하거나 작업 구역을 분리하는 방안을 검토하십시오.",
  created_at: "2026-03-15T10:00:00+09:00",
};

export const confinedAlert: Alert = {
  id: "AL_confined",
  rule_id: "R101",
  severity: "HIGH",
  work_item_ids: ["W026"],
  message: "밀폐공간 작업 '탱크 B 내부 점검'의 가스측정 정보가 확인되지 않았습니다. 가스측정 여부가 입력되지 않았습니다.",
  evidence: {
    work_item_id: "W026",
    field: "gas_measurement_completed",
    value: null,
    value_state: "MISSING",
    zone_id: "TANK_A",
    zone_name: "탱크 A",
    start_at: "2026-03-18T08:00:00+09:00",
    end_at: "2026-03-18T12:00:00+09:00",
  },
  recommended_action: "밀폐공간 작업 전 가스농도 측정 결과를 입력하십시오.",
  created_at: "2026-03-15T10:00:00+09:00",
};

export function makeAnalysis(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
  return {
    analysis_id: "AN_test",
    analyzed_at: "2026-03-15T10:00:00+09:00",
    total_work_items: 2,
    analyzed_work_items: 2,
    invalid_work_items: 0,
    alert_count: 2,
    severity_counts: { HIGH: 2, MEDIUM: 0, LOW: 0 },
    duration_ms: 1.2,
    alerts: [pairAlert, confinedAlert],
    ...overrides,
  };
}
