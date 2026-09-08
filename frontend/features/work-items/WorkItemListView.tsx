"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { EmptyState, ErrorState, LoadingState } from "@/components/StateViews";
import { WorkItemTable } from "@/features/work-items/WorkItemTable";
import { api, ApiError } from "@/lib/api";
import { WORK_STATUS_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import { WORK_STATUSES, WORK_TYPES, type Paginated, type WorkItem, type Zone } from "@/types/domain";

interface Filters {
  date: string;
  work_type: string;
  zone_id: string;
  status: string;
  has_alert: string;
}

const EMPTY_FILTERS: Filters = { date: "", work_type: "", zone_id: "", status: "", has_alert: "" };
const PAGE_SIZE = 20;

export function WorkItemListView() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [zones, setZones] = useState<Zone[]>([]);
  const [data, setData] = useState<Paginated<WorkItem> | null>(null);
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
        const response = await api.listWorkItems({
          date: applied.date || null,
          work_type: applied.work_type || null,
          zone_id: applied.zone_id || null,
          status: applied.status || null,
          has_alert: applied.has_alert === "" ? null : applied.has_alert === "true",
          page,
          page_size: PAGE_SIZE,
        });
        if (active) setData(response);
      } catch (caught) {
        const apiError = caught as ApiError;
        if (active) {
          setError({
            message: apiError.message ?? "목록을 불러오지 못했습니다.",
            code: apiError.code ?? "UNKNOWN_ERROR",
          });
          setData(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [applied, page, reloadToken]);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const response = await api.listZones();
        if (active) setZones(response.items);
      } catch {
        if (active) setZones([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handleDelete(item: WorkItem) {
    try {
      await api.deleteWorkItem(item.id);
      reload();
    } catch (caught) {
      const apiError = caught as ApiError;
      setError({ message: apiError.message ?? "삭제하지 못했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-4">
      <section aria-label="필터" className="rounded border border-slate-300 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <label className="block text-sm">
            <span className="font-medium text-slate-800">날짜</span>
            <input
              type="date"
              value={filters.date}
              onChange={(event) => setFilters({ ...filters, date: event.target.value })}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-800">작업 종류</span>
            <select
              value={filters.work_type}
              onChange={(event) => setFilters({ ...filters, work_type: event.target.value })}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
            >
              <option value="">전체</option>
              {WORK_TYPES.map((type) => (
                <option key={type} value={type}>
                  {WORK_TYPE_LABEL[type]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-800">구역</span>
            <select
              value={filters.zone_id}
              onChange={(event) => setFilters({ ...filters, zone_id: event.target.value })}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
            >
              <option value="">전체</option>
              {zones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-800">검토 상태</span>
            <select
              value={filters.status}
              onChange={(event) => setFilters({ ...filters, status: event.target.value })}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
            >
              <option value="">전체</option>
              {WORK_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {WORK_STATUS_LABEL[value]}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-800">경보 여부</span>
            <select
              value={filters.has_alert}
              onChange={(event) => setFilters({ ...filters, has_alert: event.target.value })}
              className="mt-1 w-full rounded border border-slate-400 px-2 py-1.5"
            >
              <option value="">전체</option>
              <option value="true">경보 있음</option>
              <option value="false">경보 없음</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => {
              setPage(1);
              setApplied(filters);
            }}
            className="rounded bg-slate-800 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-700"
          >
            필터 적용
          </button>
          <button
            type="button"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setApplied(EMPTY_FILTERS);
              setPage(1);
            }}
            className="rounded border border-slate-500 px-3 py-1.5 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          >
            필터 초기화
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-600">경보 여부는 가장 최근 분석 결과를 기준으로 표시합니다.</p>
      </section>

      {loading ? <LoadingState label="작업 목록을 불러오는 중입니다." /> : null}
      {error ? <ErrorState message={error.message} code={error.code} onRetry={reload} /> : null}

      {!loading && !error && data ? (
        data.items.length === 0 ? (
          <EmptyState
            title="표시할 작업계획이 없습니다."
            description="필터를 초기화하거나 새 작업계획을 등록하십시오."
            action={
              <Link
                href="/work-items/new"
                className="inline-block rounded bg-slate-800 px-3 py-1.5 text-sm font-semibold text-white"
              >
                작업 등록으로 이동
              </Link>
            }
          />
        ) : (
          <>
            <p className="text-sm text-slate-700">
              전체 {data.total}건 중 {data.items.length}건 표시 (페이지 {data.page}/{totalPages})
            </p>
            <WorkItemTable items={data.items} onDelete={handleDelete} />
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                className="rounded border border-slate-500 px-3 py-1 text-sm disabled:opacity-50"
              >
                이전
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => value + 1)}
                className="rounded border border-slate-500 px-3 py-1 text-sm disabled:opacity-50"
              >
                다음
              </button>
            </div>
          </>
        )
      ) : null}
    </div>
  );
}
