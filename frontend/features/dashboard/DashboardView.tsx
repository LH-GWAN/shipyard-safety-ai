"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Disclaimer } from "@/components/Disclaimer";
import { ErrorState, LoadingState, Notice } from "@/components/StateViews";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AnalysisResult, HealthStatus, WorkItem } from "@/types/domain";

export function DashboardView() {
  const [date, setDate] = useState("");
  const [items, setItems] = useState<WorkItem[]>([]);
  const [total, setTotal] = useState(0);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);

  const [reloadToken, setReloadToken] = useState(0);
  const reload = useCallback(() => setReloadToken((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [list, latest, status] = await Promise.all([
          api.listWorkItems({ date: date || null, page: 1, page_size: 100 }),
          api.latestAnalysis(),
          api.health(),
        ]);
        if (!active) return;
        setItems(list.items);
        setTotal(list.total);
        setAnalysis(latest);
        setHealth(status);
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
  }, [date, reloadToken]);

  const unreviewed = items.filter((item) => item.status === "DRAFT").length;

  return (
    <div className="space-y-4">
      <Disclaimer />

      {health && !health.llm_enabled ? (
        <Notice tone="warn">
          자연어 입력은 지금 키워드 인식 방식(모의 어댑터)으로 동작합니다. 더 자세한 결과를 얻으려면 LLM API 키가
          필요합니다. 작업 등록, CSV 업로드, 규칙 검사는 키 없이도 정상 동작합니다.
        </Notice>
      ) : null}

      <section className="flex flex-wrap items-end gap-3 rounded border border-slate-300 bg-white p-4">
        <label className="text-sm">
          <span className="block font-medium text-slate-800">선택 날짜 (비우면 전체)</span>
          <input
            type="date"
            aria-label="선택 날짜"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className="mt-1 rounded border border-slate-400 px-2 py-1.5"
          />
        </label>
        <Link
          href="/work-items/new"
          className="rounded bg-slate-800 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          작업 등록
        </Link>
        <Link
          href="/work-items/new?tab=csv"
          className="rounded border border-slate-500 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        >
          CSV 업로드
        </Link>
        <Link
          href="/analysis"
          className="rounded border border-slate-500 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
        >
          분석 실행
        </Link>
      </section>

      {loading ? <LoadingState label="대시보드를 불러오는 중입니다." /> : null}
      {error ? <ErrorState message={error.message} code={error.code} onRetry={reload} /> : null}

      {!loading && !error ? (
        <section aria-label="요약" className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <SummaryCard label="전체 작업 수" value={`${total}건`} />
          <SummaryCard label="등급 높음 경보" value={`${analysis?.severity_counts.HIGH ?? 0}건`} />
          <SummaryCard label="등급 보통 경보" value={`${analysis?.severity_counts.MEDIUM ?? 0}건`} />
          <SummaryCard label="미검토 작업" value={`${unreviewed}건`} />
          <SummaryCard
            label="최근 분석시각"
            value={analysis ? formatDateTime(analysis.analyzed_at) : "분석 이력 없음"}
          />
        </section>
      ) : null}

      {!loading && !error && total === 0 ? (
        <Notice>등록된 작업계획이 없습니다. data/work_items.csv를 CSV 업로드 화면에서 불러올 수 있습니다.</Notice>
      ) : null}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-300 bg-white p-3">
      <p className="text-xs text-slate-600">{label}</p>
      <p className="mt-1 text-sm font-bold text-slate-900">{value}</p>
    </div>
  );
}
