/**
 * 백엔드(app/domain/enums.py, app/schemas/*)와 동일한 공통 계약.
 * enum 값과 필드명을 임의로 변형하지 않는다.
 */

export const WORK_TYPES = ["HOT_WORK", "PAINTING", "SOLVENT_WORK", "CONFINED_SPACE", "OTHER"] as const;
export type WorkType = (typeof WORK_TYPES)[number];

export const WORK_STATUSES = ["DRAFT", "REVIEWED"] as const;
export type WorkStatus = (typeof WORK_STATUSES)[number];

export const SOURCE_TYPES = ["MANUAL", "CSV", "LLM"] as const;
export type SourceType = (typeof SOURCE_TYPES)[number];

export const SEVERITIES = ["HIGH", "MEDIUM", "LOW"] as const;
export type Severity = (typeof SEVERITIES)[number];

export type SpatialRelation = "SAME" | "ADJACENT" | "UNRELATED";

export interface Zone {
  id: string;
  name: string;
  adjacent_zone_ids: string[];
}

export interface WorkItem {
  id: string;
  title: string;
  description: string | null;
  work_type: WorkType;
  zone_id: string;
  zone_name: string | null;
  start_at: string;
  end_at: string;
  uses_flammable_material: boolean | null;
  gas_measurement_completed: boolean | null;
  ventilation_confirmed: boolean | null;
  watcher_assigned: boolean | null;
  status: WorkStatus;
  source_type: SourceType;
  external_id: string | null;
  created_at: string;
  updated_at: string;
  has_alert: boolean | null;
}

export interface WorkItemInput {
  id?: string | null;
  title: string;
  description: string | null;
  work_type: WorkType;
  zone_id: string;
  start_at: string;
  end_at: string;
  uses_flammable_material: boolean | null;
  gas_measurement_completed: boolean | null;
  ventilation_confirmed: boolean | null;
  watcher_assigned: boolean | null;
  status: WorkStatus;
  source_type?: SourceType;
  external_id?: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CsvRowError {
  row_number: number;
  field: string | null;
  code: string;
  message: string;
  raw_value: string | null;
}

export interface CsvImportResult {
  total_rows: number;
  valid_count: number;
  invalid_count: number;
  created_count: number;
  updated_count: number;
  valid_rows: { row_number: number; work_item: WorkItemInput }[];
  errors: CsvRowError[];
  committed: boolean;
}

export interface Alert {
  id: string;
  rule_id: string;
  severity: Severity;
  work_item_ids: string[];
  message: string;
  evidence: Record<string, unknown>;
  recommended_action: string;
  created_at: string;
}

export interface AnalysisResult {
  analysis_id: string;
  analyzed_at: string;
  total_work_items: number;
  analyzed_work_items: number;
  invalid_work_items: number;
  alert_count: number;
  severity_counts: { HIGH: number; MEDIUM: number; LOW: number };
  duration_ms: number;
  alerts: Alert[];
}

export type RuleType = "ALERT" | "INPUT_VALIDATION";

export interface SafetyRule {
  id: string;
  name: string;
  description: string;
  rule_type: RuleType;
  severity: Severity;
  enabled: boolean;
  reference_title: string;
  reference_url: string | null;
  reference_articles: string[];
  reference_note: string;
  reference_verified_at: string | null;
  requires_site_validation: boolean;
  version: string;
  reviewed: boolean;
}

export interface ParsedDraft {
  values: {
    title: string | null;
    work_type: WorkType | null;
    zone_id: string | null;
    start_at: string | null;
    end_at: string | null;
    uses_flammable_material: boolean | null;
    gas_measurement_completed: boolean | null;
    ventilation_confirmed: boolean | null;
    watcher_assigned: boolean | null;
  };
  field_confidence: Record<string, number | null>;
  evidence: Record<string, string>;
  ambiguities: string[];
  missing_fields: string[];
  provider: string;
}

export interface ParseDescriptionResult {
  draft: ParsedDraft;
  llm_enabled: boolean;
  provider: string;
  is_mock: boolean;
  notice: string;
}

export interface ShiftChange {
  work_item_id: string;
  title: string;
  before_start_at: string;
  before_end_at: string;
  after_start_at: string;
  after_end_at: string;
  duration_minutes: number;
  buffer_minutes: number;
  reference_work_item_id: string;
}

export interface ShiftPreview {
  preview_token: string;
  alert_id: string;
  change: ShiftChange;
  resolved_alerts: Alert[];
  new_alerts: Alert[];
  remaining_alert_count: number;
  before_alert_count: number;
  after_alert_count: number;
}

export interface ShiftApplyResult {
  change: ShiftChange;
  analysis: AnalysisResult;
  resolved_alerts: Alert[];
  new_alerts: Alert[];
}

export interface HealthStatus {
  status: string;
  llm_enabled: boolean;
  llm_provider: string;
  zone_count: number;
}
