"use client";

import { useState } from "react";
import { ErrorState, Notice } from "@/components/StateViews";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatMinutes } from "@/lib/format";
import type { Alert, AnalysisResult, ShiftPreview } from "@/types/domain";

export function ScheduleShiftPanel({
  alert,
  onApplied,
}: {
  alert: Alert;
  onApplied: (analysis: AnalysisResult, message: string) => void;
}) {
  const [moveId, setMoveId] = useState(alert.work_item_ids[1] ?? alert.work_item_ids[0]);
  const [buffer, setBuffer] = useState(30);
  const [preview, setPreview] = useState<ShiftPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);

  if (alert.work_item_ids.length !== 2) {
    return (
      <Notice tone="warn">
        시간 변경안은 두 작업의 시간이 겹친 경보에만 제공됩니다. 이 경보는 단일 작업의 안전조치 정보 누락 경보입니다.
      </Notice>
    );
  }

  async function handlePreview() {
    setBusy(true);
    setError(null);
    try {
      setPreview(
        await api.previewShift({ alert_id: alert.id, move_work_item_id: moveId, buffer_minutes: buffer }),
      );
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "미리보기에 실패했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  async function handleApply() {
    // 유효한 미리보기(토큰 포함)가 없으면 적용 요청을 보내지 않는다.
    if (!preview?.preview_token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.applyShift({
        alert_id: alert.id,
        move_work_item_id: moveId,
        buffer_minutes: buffer,
        preview_token: preview.preview_token,
      });
      setPreview(null);
      onApplied(
        result.analysis,
        `${result.change.work_item_id}의 시간을 변경하고 전체 작업을 다시 검사했습니다. 남은 경보 ${result.analysis.alert_count}건.`,
      );
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "적용에 실패했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="일정 변경" className="space-y-3 rounded border border-slate-400 bg-white p-4">
      <div>
        <p className="text-sm font-semibold text-slate-900">규칙형 시간 변경안</p>
        <p className="text-xs text-slate-600">
          이동 작업의 기존 소요시간을 유지한 채, 상대 작업 종료시각에 여유시간을 더한 시점으로 옮기는 단순 규칙입니다. AI
          일정 최적화가 아닙니다.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block font-medium text-slate-800">이동할 작업</span>
          <select
            value={moveId}
            onChange={(event) => {
              setMoveId(event.target.value);
              setPreview(null);
            }}
            className="mt-1 rounded border border-slate-400 px-2 py-1.5"
          >
            {alert.work_item_ids.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-slate-800">여유시간(분, 0~240)</span>
          <input
            type="number"
            min={0}
            max={240}
            value={buffer}
            onChange={(event) => {
              setBuffer(Number(event.target.value));
              setPreview(null);
            }}
            className="mt-1 w-28 rounded border border-slate-400 px-2 py-1.5"
          />
        </label>
        <button
          type="button"
          onClick={handlePreview}
          disabled={busy}
          className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-60"
        >
          변경안 미리보기
        </button>
      </div>

      {busy ? <p role="status" className="text-sm text-slate-600">처리 중입니다.</p> : null}
      {error ? <ErrorState message={error.message} code={error.code} /> : null}
      {!preview && !busy ? (
        <Notice>변경안을 미리보기로 확인한 뒤에만 적용할 수 있습니다. 이동 작업이나 여유시간을 바꾸면 미리보기 결과는 폐기됩니다.</Notice>
      ) : null}

      {preview ? (
        <div className="space-y-3">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <caption className="pb-1 text-left text-xs font-semibold text-slate-700">변경 전후 비교</caption>
              <thead>
                <tr className="bg-slate-100 text-left">
                  <th className="border border-slate-300 px-2 py-1">구분</th>
                  <th className="border border-slate-300 px-2 py-1">시작시각</th>
                  <th className="border border-slate-300 px-2 py-1">종료시각</th>
                  <th className="border border-slate-300 px-2 py-1">소요시간</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-slate-300 px-2 py-1">변경 전</td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(preview.change.before_start_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(preview.change.before_end_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">{formatMinutes(preview.change.duration_minutes)}</td>
                </tr>
                <tr>
                  <td className="border border-slate-300 px-2 py-1">변경 후</td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(preview.change.after_start_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(preview.change.after_end_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">{formatMinutes(preview.change.duration_minutes)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded border border-slate-300 p-3">
              <p className="text-xs font-semibold text-slate-800">해소되는 경보 ({preview.resolved_alerts.length}건)</p>
              <ul className="mt-1 list-disc pl-5 text-sm text-slate-800">
                {preview.resolved_alerts.map((item) => (
                  <li key={item.id}>
                    {item.rule_id} · {item.work_item_ids.join(", ")}
                  </li>
                ))}
                {preview.resolved_alerts.length === 0 ? <li>없음</li> : null}
              </ul>
            </div>
            <div className="rounded border border-amber-500 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-900">새로 생기는 경보 ({preview.new_alerts.length}건)</p>
              <ul className="mt-1 list-disc pl-5 text-sm text-amber-900">
                {preview.new_alerts.map((item) => (
                  <li key={item.id}>
                    {item.rule_id} · {item.work_item_ids.join(", ")}
                  </li>
                ))}
                {preview.new_alerts.length === 0 ? <li>없음</li> : null}
              </ul>
            </div>
          </div>

          <p className="text-sm text-slate-700">
            적용 시 전체 경보는 {preview.before_alert_count}건에서 {preview.after_alert_count}건이 됩니다.
          </p>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleApply}
              disabled={busy || !preview.preview_token}
              className="rounded bg-slate-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
            >
              변경안 적용
            </button>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100"
            >
              취소
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
