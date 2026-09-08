"use client";

import { useState } from "react";
import { ErrorState, Notice } from "@/components/StateViews";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { WORK_TYPE_LABEL } from "@/lib/labels";
import type { CsvImportResult } from "@/types/domain";

const REQUIRED_COLUMNS = "id,title,work_type,zone_id,start_at,end_at";
const OPTIONAL_COLUMNS =
  "description,uses_flammable_material,gas_measurement_completed,ventilation_confirmed,watcher_assigned,status";

export function CsvUploadPanel({ onSaved }: { onSaved?: (result: CsvImportResult) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [overwrite, setOverwrite] = useState(false);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);

  async function run(commit: boolean) {
    if (!file) {
      setError({ message: "CSV 파일을 선택하십시오.", code: "NO_FILE" });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.importCsv(file, { commit, overwrite });
      setResult(response);
      if (commit && response.committed) onSaved?.(response);
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "업로드에 실패했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Notice>
        필수 열: <code>{REQUIRED_COLUMNS}</code>
        <br />
        선택 열: <code>{OPTIONAL_COLUMNS}</code>
        <br />
        시각은 <code>2026-03-16T09:00:00+09:00</code>처럼 표준시간대를 포함해야 하며, 선택 불리언 열의 빈 셀은 미입력으로 처리됩니다.
      </Notice>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium text-slate-800">
          CSV 파일
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="CSV 파일"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setResult(null);
            }}
            className="ml-2 text-sm"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-800">
          <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
          기존 ID 덮어쓰기
        </label>
        <button
          type="button"
          onClick={() => run(false)}
          disabled={busy}
          className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-60"
        >
          검증만 실행
        </button>
        <button
          type="button"
          onClick={() => run(true)}
          disabled={busy || !result || result.valid_count === 0}
          className="rounded bg-slate-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
        >
          유효 행 저장
        </button>
      </div>

      {busy ? <p role="status" className="text-sm text-slate-600">CSV를 처리하는 중입니다.</p> : null}
      {error ? <ErrorState message={error.message} code={error.code} /> : null}

      {result ? (
        <section className="space-y-3" aria-label="CSV 검증 결과">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              { label: "전체 행", value: result.total_rows },
              { label: "유효 행", value: result.valid_count },
              { label: "오류 행", value: result.invalid_count },
              { label: "신규 저장", value: result.created_count },
              { label: "갱신 저장", value: result.updated_count },
            ].map((item) => (
              <div key={item.label} className="rounded border border-slate-300 bg-white p-3 text-center">
                <p className="text-xs text-slate-600">{item.label}</p>
                <p className="text-lg font-bold text-slate-900">{item.value}</p>
              </div>
            ))}
          </div>

          {result.committed ? (
            <Notice>유효한 {result.valid_count}개 행을 저장했습니다.</Notice>
          ) : (
            <Notice tone="warn">
              검증만 수행했습니다. 데이터베이스는 변경되지 않았습니다. 저장하려면 &quot;유효 행 저장&quot;을 누르십시오.
            </Notice>
          )}

          {result.errors.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <caption className="pb-2 text-left text-sm font-semibold text-slate-800">
                  행별 오류 ({result.errors.length}건) · 헤더를 1행으로 계산합니다.
                </caption>
                <thead>
                  <tr className="bg-slate-100 text-left">
                    <th className="border border-slate-300 px-2 py-1">행</th>
                    <th className="border border-slate-300 px-2 py-1">필드</th>
                    <th className="border border-slate-300 px-2 py-1">오류 코드</th>
                    <th className="border border-slate-300 px-2 py-1">내용</th>
                    <th className="border border-slate-300 px-2 py-1">입력값</th>
                  </tr>
                </thead>
                <tbody>
                  {result.errors.map((rowError, index) => (
                    <tr key={`${rowError.row_number}-${rowError.field}-${index}`}>
                      <td className="border border-slate-300 px-2 py-1">{rowError.row_number}</td>
                      <td className="border border-slate-300 px-2 py-1">{rowError.field ?? "-"}</td>
                      <td className="border border-slate-300 px-2 py-1">{rowError.code}</td>
                      <td className="border border-slate-300 px-2 py-1">{rowError.message}</td>
                      <td className="border border-slate-300 px-2 py-1">{rowError.raw_value ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-700">행 오류가 없습니다.</p>
          )}

          {result.valid_rows.length > 0 ? (
            <details className="rounded border border-slate-300 bg-white p-3">
              <summary className="cursor-pointer text-sm font-semibold text-slate-800">
                유효 행 미리보기 ({result.valid_rows.length}건)
              </summary>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-100 text-left">
                      <th className="border border-slate-300 px-2 py-1">행</th>
                      <th className="border border-slate-300 px-2 py-1">ID</th>
                      <th className="border border-slate-300 px-2 py-1">작업명</th>
                      <th className="border border-slate-300 px-2 py-1">종류</th>
                      <th className="border border-slate-300 px-2 py-1">구역</th>
                      <th className="border border-slate-300 px-2 py-1">시작</th>
                      <th className="border border-slate-300 px-2 py-1">종료</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.valid_rows.slice(0, 50).map((row) => (
                      <tr key={row.row_number}>
                        <td className="border border-slate-300 px-2 py-1">{row.row_number}</td>
                        <td className="border border-slate-300 px-2 py-1">{row.work_item.id}</td>
                        <td className="border border-slate-300 px-2 py-1">{row.work_item.title}</td>
                        <td className="border border-slate-300 px-2 py-1">
                          {WORK_TYPE_LABEL[row.work_item.work_type]}
                        </td>
                        <td className="border border-slate-300 px-2 py-1">{row.work_item.zone_id}</td>
                        <td className="border border-slate-300 px-2 py-1">{formatDateTime(row.work_item.start_at)}</td>
                        <td className="border border-slate-300 px-2 py-1">{formatDateTime(row.work_item.end_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
