"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { toKstIso, toLocalInput } from "@/lib/format";
import { SAFETY_FIELD_LABEL, WORK_STATUS_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import {
  WORK_STATUSES,
  WORK_TYPES,
  type WorkItem,
  type WorkItemInput,
  type WorkStatus,
  type WorkType,
  type Zone,
} from "@/types/domain";

type TriState = "null" | "true" | "false";

const SAFETY_FIELDS = [
  "uses_flammable_material",
  "gas_measurement_completed",
  "ventilation_confirmed",
  "watcher_assigned",
] as const;

type SafetyField = (typeof SAFETY_FIELDS)[number];

function toTriState(value: boolean | null | undefined): TriState {
  if (value === null || value === undefined) return "null";
  return value ? "true" : "false";
}

function fromTriState(value: TriState): boolean | null {
  if (value === "null") return null;
  return value === "true";
}

export interface WorkItemFormProps {
  zones: Zone[];
  initial?: Partial<WorkItem>;
  allowIdInput?: boolean;
  submitLabel: string;
  onSubmit: (payload: WorkItemInput) => Promise<void>;
}

export function WorkItemForm({ zones, initial, allowIdInput = false, submitLabel, onSubmit }: WorkItemFormProps) {
  const [id, setId] = useState(initial?.id ?? "");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [workType, setWorkType] = useState<WorkType>((initial?.work_type as WorkType) ?? "HOT_WORK");
  const [zoneId, setZoneId] = useState(initial?.zone_id ?? zones[0]?.id ?? "");
  const [startAt, setStartAt] = useState(toLocalInput(initial?.start_at));
  const [endAt, setEndAt] = useState(toLocalInput(initial?.end_at));
  const [status, setStatus] = useState<WorkStatus>((initial?.status as WorkStatus) ?? "DRAFT");
  const [flags, setFlags] = useState<Record<SafetyField, TriState>>({
    uses_flammable_material: toTriState(initial?.uses_flammable_material),
    gas_measurement_completed: toTriState(initial?.gas_measurement_completed),
    ventilation_confirmed: toTriState(initial?.ventilation_confirmed),
    watcher_assigned: toTriState(initial?.watcher_assigned),
  });

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function validate(): Record<string, string> {
    const errors: Record<string, string> = {};
    if (!title.trim()) errors.title = "작업명을 입력하십시오.";
    if (title.trim().length > 100) errors.title = "작업명은 100자 이하여야 합니다.";
    if (!zoneId) errors.zone_id = "구역을 선택하십시오.";
    if (!startAt) errors.start_at = "시작시각을 입력하십시오.";
    if (!endAt) errors.end_at = "종료시각을 입력하십시오.";
    if (startAt && endAt && toKstIso(endAt) <= toKstIso(startAt)) {
      errors.end_at = "종료시각은 시작시각보다 늦어야 합니다.";
    }
    if ((description ?? "").length > 2000) errors.description = "설명은 2,000자 이하여야 합니다.";
    return errors;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const payload: WorkItemInput = {
      id: allowIdInput ? (id.trim() || null) : undefined,
      title: title.trim(),
      description: description.trim() ? description.trim() : null,
      work_type: workType,
      zone_id: zoneId,
      start_at: toKstIso(startAt),
      end_at: toKstIso(endAt),
      uses_flammable_material: fromTriState(flags.uses_flammable_material),
      gas_measurement_completed: fromTriState(flags.gas_measurement_completed),
      ventilation_confirmed: fromTriState(flags.ventilation_confirmed),
      watcher_assigned: fromTriState(flags.watcher_assigned),
      status,
    };

    setBusy(true);
    try {
      await onSubmit(payload);
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(`${error.message} (오류 코드: ${error.code})`);
      } else {
        setFormError("저장 중 오류가 발생했습니다.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {formError ? (
        <p role="alert" className="rounded border border-red-400 bg-red-50 px-3 py-2 text-sm text-red-900">
          {formError}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {allowIdInput ? (
          <label className="block text-sm">
            <span className="font-medium text-slate-800">작업 ID (생략 시 자동 생성)</span>
            <input
              value={id}
              onChange={(event) => setId(event.target.value)}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
              placeholder="예: W041"
            />
          </label>
        ) : null}

        <label className="block text-sm">
          <span className="font-medium text-slate-800">작업명 *</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            aria-invalid={Boolean(fieldErrors.title)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          />
          {fieldErrors.title ? <span className="mt-1 block text-xs text-red-700">{fieldErrors.title}</span> : null}
        </label>

        <label className="block text-sm">
          <span className="font-medium text-slate-800">작업 종류 *</span>
          <select
            value={workType}
            onChange={(event) => setWorkType(event.target.value as WorkType)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          >
            {WORK_TYPES.map((type) => (
              <option key={type} value={type}>
                {WORK_TYPE_LABEL[type]}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="font-medium text-slate-800">구역 *</span>
          <select
            value={zoneId}
            onChange={(event) => setZoneId(event.target.value)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          >
            <option value="">선택하십시오</option>
            {zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zone.name} ({zone.id})
              </option>
            ))}
          </select>
          {fieldErrors.zone_id ? <span className="mt-1 block text-xs text-red-700">{fieldErrors.zone_id}</span> : null}
        </label>

        <label className="block text-sm">
          <span className="font-medium text-slate-800">시작시각 (KST) *</span>
          <input
            type="datetime-local"
            value={startAt}
            onChange={(event) => setStartAt(event.target.value)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          />
          {fieldErrors.start_at ? (
            <span className="mt-1 block text-xs text-red-700">{fieldErrors.start_at}</span>
          ) : null}
        </label>

        <label className="block text-sm">
          <span className="font-medium text-slate-800">종료시각 (KST) *</span>
          <input
            type="datetime-local"
            value={endAt}
            onChange={(event) => setEndAt(event.target.value)}
            aria-invalid={Boolean(fieldErrors.end_at)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          />
          {fieldErrors.end_at ? <span className="mt-1 block text-xs text-red-700">{fieldErrors.end_at}</span> : null}
        </label>

        <label className="block text-sm">
          <span className="font-medium text-slate-800">검토 상태</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as WorkStatus)}
            className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
          >
            {WORK_STATUSES.map((value) => (
              <option key={value} value={value}>
                {WORK_STATUS_LABEL[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="block text-sm">
        <span className="font-medium text-slate-800">작업 설명</span>
        <textarea
          value={description ?? ""}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
        />
        {fieldErrors.description ? (
          <span className="mt-1 block text-xs text-red-700">{fieldErrors.description}</span>
        ) : null}
      </label>

      <fieldset className="rounded border border-slate-300 bg-white p-3">
        <legend className="px-1 text-sm font-medium text-slate-800">안전조치 정보</legend>
        <p className="mb-2 text-xs text-slate-600">
          &quot;미입력&quot;은 정보가 확인되지 않았음을, &quot;아니오&quot;는 미실시·미확인으로 입력했음을 뜻합니다.
        </p>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {SAFETY_FIELDS.map((field) => (
            <label key={field} className="block text-sm">
              <span className="font-medium text-slate-800">{SAFETY_FIELD_LABEL[field]}</span>
              <select
                value={flags[field]}
                onChange={(event) =>
                  setFlags((previous) => ({ ...previous, [field]: event.target.value as TriState }))
                }
                className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
              >
                <option value="null">미입력</option>
                <option value="true">예</option>
                <option value="false">아니오</option>
              </select>
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={busy}
        className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
      >
        {busy ? "저장 중..." : submitLabel}
      </button>
    </form>
  );
}
