"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Disclaimer } from "@/components/Disclaimer";
import { SeverityBadge } from "@/components/SeverityBadge";
import { EmptyState, ErrorState, LoadingState, Notice } from "@/components/StateViews";
import { AlertDetail } from "@/features/analysis/AlertDetail";
import { ScheduleShiftPanel } from "@/features/analysis/ScheduleShiftPanel";
import { Timeline } from "@/features/analysis/Timeline";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { SEVERITY_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import { SEVERITIES, type AnalysisResult, type SafetyRule, type WorkItem } from "@/types/domain";

export function AnalysisView() {
  const [date, setDate] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [workItems, setWorkItems] = useState<WorkItem[]>([]);
  const [rules, setRules] = useState<SafetyRule[]>([]);
  const [severityFilter, setSeverityFilter] = useState("");
  const [ruleFilter, setRuleFilter] = useState("");
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [shiftMessage, setShiftMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);

  const loadWorkItems = useCallback(async (selectedDate: string) => {
    const response = await api.listWorkItems({ date: selectedDate || null, page: 1, page_size: 100 });
    setWorkItems(response.items);
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const [latest, ruleList] = await Promise.all([api.latestAnalysis(), api.listRules()]);
        if (!active) return;
        setAnalysis(latest);
        setRules(ruleList.items);
        await loadWorkItems("");
      } catch (caught) {
        const apiError = caught as ApiError;
        if (active) {
          setError({ message: apiError.message ?? "불러오지 못했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [loadWorkItems]);

  async function runAnalysis() {
    setRunning(true);
    setError(null);
    setShiftMessage(null);
    try {
      const result = await api.runAnalysis({ date: date || null });
      setAnalysis(result);
      setSelectedAlertId(result.alerts[0]?.id ?? null);
      await loadWorkItems(date);
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "분석에 실패했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
    } finally {
      setRunning(false);
    }
  }

  const filteredAlerts = useMemo(() => {
    if (!analysis) return [];
    return analysis.alerts.filter(
      (alert) =>
        (severityFilter === "" || alert.severity === severityFilter) &&
        (ruleFilter === "" || alert.rule_id === ruleFilter),
    );
  }, [analysis, severityFilter, ruleFilter]);

  const selectedAlert =
    filteredAlerts.find((alert) => alert.id === selectedAlertId) ?? filteredAlerts[0] ?? null;
  const alertItemIds = useMemo(
    () => new Set((analysis?.alerts ?? []).flatMap((alert) => alert.work_item_ids)),
    [analysis],
  );
  const ruleById = useMemo(() => new Map(rules.map((rule) => [rule.id, rule])), [rules]);
  const sortedItems = useMemo(
    () => [...workItems].sort((a, b) => a.start_at.localeCompare(b.start_at)),
    [workItems],
  );

  if (loading) return <LoadingState label="분석 화면을 준비하는 중입니다." />;

  return (
    <div className="space-y-4">
      <Disclaimer />

      <section className="flex flex-wrap items-end gap-3 rounded border border-slate-300 bg-white p-4">
        <label className="text-sm">
          <span className="block font-medium text-slate-800">분석 대상 날짜 (비우면 전체)</span>
          <input
            type="date"
            value={date}
            aria-label="분석 대상 날짜"
            onChange={(event) => setDate(event.target.value)}
            className="mt-1 rounded border border-slate-400 px-2 py-1.5"
          />
        </label>
        <button
          type="button"
          onClick={runAnalysis}
          disabled={running}
          className="rounded bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
        >
          {running ? "검사 중..." : "규칙 검사 실행"}
        </button>
      </section>

      {running ? <LoadingState label="규칙 검사를 실행하는 중입니다." /> : null}
      {error ? <ErrorState message={error.message} code={error.code} onRetry={runAnalysis} /> : null}

      {!analysis ? (
        <EmptyState
          title="아직 분석 결과가 없습니다."
          description="작업계획을 등록한 뒤 규칙 검사를 실행하십시오."
        />
      ) : (
        <>
          <section aria-label="분석 요약" className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              { label: "분석 대상 작업", value: `${analysis.analyzed_work_items} / ${analysis.total_work_items}건` },
              { label: "경보 수", value: `${analysis.alert_count}건` },
              {
                label: "등급별 경보",
                value: `높음 ${analysis.severity_counts.HIGH} · 보통 ${analysis.severity_counts.MEDIUM} · 낮음 ${analysis.severity_counts.LOW}`,
              },
              { label: "분석 시각", value: formatDateTime(analysis.analyzed_at) },
            ].map((item) => (
              <div key={item.label} className="rounded border border-slate-300 bg-white p-3">
                <p className="text-xs text-slate-600">{item.label}</p>
                <p className="mt-1 text-sm font-bold text-slate-900">{item.value}</p>
              </div>
            ))}
          </section>
          <p className="text-xs text-slate-600">
            분석 ID {analysis.analysis_id} · 소요 {analysis.duration_ms.toFixed(1)} ms
            {analysis.invalid_work_items > 0
              ? ` · 입력 오류로 제외된 작업 ${analysis.invalid_work_items}건`
              : ""}
          </p>

          <Timeline items={sortedItems} alertItemIds={alertItemIds} />

          <section className="flex flex-wrap items-end gap-3 rounded border border-slate-300 bg-white p-4">
            <label className="text-sm">
              <span className="block font-medium text-slate-800">등급 필터</span>
              <select
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value)}
                className="mt-1 rounded border border-slate-400 px-2 py-1.5"
              >
                <option value="">전체</option>
                {SEVERITIES.map((severity) => (
                  <option key={severity} value={severity}>
                    {SEVERITY_LABEL[severity]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block font-medium text-slate-800">규칙 필터</span>
              <select
                value={ruleFilter}
                onChange={(event) => setRuleFilter(event.target.value)}
                className="mt-1 rounded border border-slate-400 px-2 py-1.5"
              >
                <option value="">전체</option>
                {rules.map((rule) => (
                  <option key={rule.id} value={rule.id}>
                    {rule.id} · {rule.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => {
                setSeverityFilter("");
                setRuleFilter("");
              }}
              className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100"
            >
              필터 초기화
            </button>
          </section>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
            <section aria-label="경보 목록" className="space-y-2">
              <p className="text-sm font-semibold text-slate-800">경보 {filteredAlerts.length}건</p>
              {filteredAlerts.length === 0 ? (
                <EmptyState title="조건에 맞는 경보가 없습니다." description="필터를 초기화해 보십시오." />
              ) : (
                <ul className="space-y-2">
                  {filteredAlerts.map((alert) => (
                    <li key={alert.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedAlertId(alert.id)}
                        aria-current={selectedAlert?.id === alert.id}
                        className={`w-full rounded border p-3 text-left text-sm hover:bg-slate-50 ${
                          selectedAlert?.id === alert.id ? "border-slate-800 bg-slate-50" : "border-slate-300 bg-white"
                        }`}
                      >
                        <span className="flex flex-wrap items-center gap-2">
                          <SeverityBadge severity={alert.severity} />
                          <span className="text-xs font-semibold text-slate-700">{alert.rule_id}</span>
                        </span>
                        <span className="mt-1 block text-slate-900">{alert.message}</span>
                        <span className="mt-1 block text-xs text-slate-600">
                          관련 작업 {alert.work_item_ids.join(", ")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <div className="space-y-4">
              {shiftMessage ? <Notice>{shiftMessage}</Notice> : null}
              {selectedAlert ? (
                <>
                  <AlertDetail alert={selectedAlert} rule={ruleById.get(selectedAlert.rule_id)} />
                  <ScheduleShiftPanel
                    alert={selectedAlert}
                    onApplied={async (updated, message) => {
                      setAnalysis(updated);
                      setSelectedAlertId(updated.alerts[0]?.id ?? null);
                      setShiftMessage(message);
                      await loadWorkItems(date);
                    }}
                  />
                </>
              ) : (
                <Notice>왼쪽 목록에서 경보를 선택하면 상세 내용을 볼 수 있습니다.</Notice>
              )}
            </div>
          </div>

          <section aria-label="시간순 작업 목록" className="rounded border border-slate-300 bg-white p-4">
            <p className="mb-2 text-sm font-semibold text-slate-800">시간순 작업 목록 ({sortedItems.length}건)</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-100 text-left">
                    <th className="border border-slate-300 px-2 py-1">작업 ID</th>
                    <th className="border border-slate-300 px-2 py-1">작업명</th>
                    <th className="border border-slate-300 px-2 py-1">종류</th>
                    <th className="border border-slate-300 px-2 py-1">구역</th>
                    <th className="border border-slate-300 px-2 py-1">시작</th>
                    <th className="border border-slate-300 px-2 py-1">종료</th>
                    <th className="border border-slate-300 px-2 py-1">경보</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedItems.map((item) => (
                    <tr key={item.id}>
                      <td className="border border-slate-300 px-2 py-1">{item.id}</td>
                      <td className="border border-slate-300 px-2 py-1">{item.title}</td>
                      <td className="border border-slate-300 px-2 py-1">{WORK_TYPE_LABEL[item.work_type]}</td>
                      <td className="border border-slate-300 px-2 py-1">{item.zone_name ?? item.zone_id}</td>
                      <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.start_at)}</td>
                      <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.end_at)}</td>
                      <td className="border border-slate-300 px-2 py-1">
                        {alertItemIds.has(item.id) ? "경보 있음" : "경보 없음"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
