"use client";

import { useState } from "react";
import { ErrorState, Notice } from "@/components/StateViews";
import { WorkItemForm } from "@/features/work-items/WorkItemForm";
import { api, ApiError } from "@/lib/api";
import { SAFETY_FIELD_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import type { ParseDescriptionResult, WorkItem, WorkItemInput, Zone } from "@/types/domain";

const FIELD_LABEL: Record<string, string> = {
  title: "작업명",
  work_type: "작업 종류",
  zone_id: "구역",
  start_at: "시작시각",
  end_at: "종료시각",
  ...SAFETY_FIELD_LABEL,
};

function displayValue(field: string, value: unknown): string {
  if (value === null || value === undefined) return "미입력";
  if (field === "work_type") return WORK_TYPE_LABEL[value as keyof typeof WORK_TYPE_LABEL] ?? String(value);
  if (typeof value === "boolean") return value ? "예" : "아니오";
  return String(value);
}

export function NaturalLanguagePanel({
  zones,
  onSaved,
}: {
  zones: Zone[];
  onSaved?: (item: WorkItem) => void;
}) {
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState<ParseDescriptionResult | null>(null);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  async function handleParse() {
    if (!text.trim()) {
      setError({ message: "작업설명을 입력하십시오.", code: "EMPTY_TEXT" });
      return;
    }
    setParsing(true);
    setError(null);
    setSavedId(null);
    try {
      setResult(await api.parseDescription(text.trim()));
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "구조화에 실패했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
      setResult(null);
    } finally {
      setParsing(false);
    }
  }

  const draft = result?.draft;
  const initial: Partial<WorkItem> | undefined = draft
    ? {
        title: draft.values.title ?? "",
        work_type: draft.values.work_type ?? "OTHER",
        zone_id: draft.values.zone_id ?? "",
        start_at: draft.values.start_at ?? undefined,
        end_at: draft.values.end_at ?? undefined,
        uses_flammable_material: draft.values.uses_flammable_material,
        gas_measurement_completed: draft.values.gas_measurement_completed,
        ventilation_confirmed: draft.values.ventilation_confirmed,
        watcher_assigned: draft.values.watcher_assigned,
        description: text.trim(),
      }
    : undefined;

  return (
    <div className="space-y-4">
      <label className="block text-sm">
        <span className="font-medium text-slate-800">작업설명 원문</span>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={4}
          aria-label="작업설명 원문"
          placeholder="예: 2026-03-16T09:00:00+09:00부터 2026-03-16T12:00:00+09:00까지 A_BLOCK_1에서 보강재 용접 작업"
          className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
        />
      </label>

      <button
        type="button"
        onClick={handleParse}
        disabled={parsing}
        className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-60"
      >
        {parsing ? "구조화 중..." : "구조화 요청"}
      </button>

      {parsing ? <p role="status" className="text-sm text-slate-600">구조화 결과를 기다리는 중입니다.</p> : null}
      {error ? <ErrorState message={error.message} code={error.code} /> : null}

      {result && draft ? (
        <section className="space-y-3" aria-label="구조화 결과">
          <Notice tone={result.is_mock ? "warn" : "info"}>
            {result.notice} (공급자: {result.provider})
          </Notice>
          <Notice>
            LLM은 자연어를 구조화하는 보조 기능입니다. 위험 판정과 경보 등급은 규칙 엔진이 결정합니다. 아래 값을 확인·수정한
            뒤 저장하십시오.
          </Notice>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-sm">
              <caption className="pb-2 text-left text-sm font-semibold text-slate-800">필드별 추출값과 근거</caption>
              <thead>
                <tr className="bg-slate-100 text-left">
                  <th className="border border-slate-300 px-2 py-1">필드</th>
                  <th className="border border-slate-300 px-2 py-1">추출값</th>
                  <th className="border border-slate-300 px-2 py-1">신뢰도</th>
                  <th className="border border-slate-300 px-2 py-1">근거(원문 표현)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(draft.values).map(([field, value]) => (
                  <tr key={field}>
                    <td className="border border-slate-300 px-2 py-1">{FIELD_LABEL[field] ?? field}</td>
                    <td className="border border-slate-300 px-2 py-1">{displayValue(field, value)}</td>
                    <td className="border border-slate-300 px-2 py-1">
                      {draft.field_confidence?.[field] === null || draft.field_confidence?.[field] === undefined
                        ? "-"
                        : draft.field_confidence[field]?.toFixed(2)}
                    </td>
                    <td className="border border-slate-300 px-2 py-1">{draft.evidence?.[field] ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {draft.ambiguities.length > 0 ? (
            <div className="rounded border border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-semibold">확인이 필요한 표현</p>
              <ul className="mt-1 list-disc pl-5">
                {draft.ambiguities.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {savedId ? (
            <Notice>작업계획 {savedId}을(를) 저장했습니다.</Notice>
          ) : (
            <div className="rounded border border-slate-300 bg-white p-4">
              <p className="mb-3 text-sm font-semibold text-slate-800">수정 후 저장</p>
              <WorkItemForm
                key={`${draft.values.title}-${draft.values.start_at}`}
                zones={zones}
                initial={initial}
                allowIdInput
                submitLabel="확인 후 저장"
                onSubmit={async (payload: WorkItemInput) => {
                  const saved = await api.createWorkItem({ ...payload, source_type: "LLM" });
                  setSavedId(saved.id);
                  onSaved?.(saved);
                }}
              />
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
