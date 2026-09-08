import type {
  AnalysisResult,
  CsvImportResult,
  HealthStatus,
  Paginated,
  ParseDescriptionResult,
  SafetyRule,
  ShiftApplyResult,
  ShiftPreview,
  WorkItem,
  WorkItemInput,
  Zone,
} from "@/types/domain";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "content-type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "백엔드 API에 연결할 수 없습니다. 서버 실행 상태를 확인하십시오.", 0);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const error = payload?.error ?? {};
    throw new ApiError(
      error.code ?? "UNKNOWN_ERROR",
      error.message ?? "요청을 처리하지 못했습니다.",
      response.status,
      error.details ?? {},
    );
  }
  return payload as T;
}

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const queryString = search.toString();
  return queryString ? `?${queryString}` : "";
}

export const api = {
  health: () => request<HealthStatus>("/health"),

  listZones: () => request<{ items: Zone[]; total: number }>("/api/zones"),

  listRules: () =>
    request<{
      items: SafetyRule[];
      total: number;
      alert_rule_count: number;
      input_validation_rule_count: number;
    }>("/api/rules"),

  listWorkItems: (params: {
    date?: string | null;
    work_type?: string | null;
    zone_id?: string | null;
    status?: string | null;
    has_alert?: boolean | null;
    page?: number;
    page_size?: number;
  }) => request<Paginated<WorkItem>>(`/api/work-items${query(params)}`),

  getWorkItem: (id: string) => request<WorkItem>(`/api/work-items/${encodeURIComponent(id)}`),

  createWorkItem: (payload: WorkItemInput) =>
    request<WorkItem>("/api/work-items", { method: "POST", body: JSON.stringify(payload) }),

  updateWorkItem: (id: string, payload: WorkItemInput) =>
    request<WorkItem>(`/api/work-items/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deleteWorkItem: (id: string) =>
    request<void>(`/api/work-items/${encodeURIComponent(id)}`, { method: "DELETE" }),

  importCsv: (file: File, options: { commit: boolean; overwrite: boolean }) => {
    const form = new FormData();
    form.append("file", file);
    return request<CsvImportResult>(
      `/api/work-items/import-csv${query({ commit: options.commit, overwrite: options.overwrite })}`,
      { method: "POST", body: form },
    );
  },

  parseDescription: (text: string) =>
    request<ParseDescriptionResult>("/api/work-items/parse-description", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  runAnalysis: (payload: { date?: string | null; work_item_ids?: string[] | null }) =>
    request<AnalysisResult>("/api/analysis/run", { method: "POST", body: JSON.stringify(payload) }),

  latestAnalysis: () => request<AnalysisResult | null>("/api/analysis/latest"),

  getAnalysis: (analysisId: string) => request<AnalysisResult>(`/api/analysis/${analysisId}`),

  previewShift: (payload: { alert_id: string; move_work_item_id: string; buffer_minutes: number }) =>
    request<ShiftPreview>("/api/schedule/preview-shift", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /** preview_token은 필수다. 사용자가 미리보기로 확인하지 않은 변경은 적용할 수 없다. */
  applyShift: (payload: {
    alert_id: string;
    move_work_item_id: string;
    buffer_minutes: number;
    preview_token: string;
  }) => {
    if (!payload.preview_token) {
      throw new ApiError(
        "PREVIEW_REQUIRED",
        "먼저 변경안을 미리보기로 확인해야 적용할 수 있습니다.",
        0,
      );
    }
    return request<ShiftApplyResult>("/api/schedule/apply-shift", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
