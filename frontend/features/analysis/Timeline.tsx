"use client";

import { formatDateTime, formatTime } from "@/lib/format";
import { WORK_TYPE_LABEL } from "@/lib/labels";
import type { WorkItem } from "@/types/domain";

/** 구역(세로) × 시간(가로)의 단순 2차원 타임라인. 장식용 그래프가 아니라 입력값 그대로를 배치한다. */
export function Timeline({ items, alertItemIds }: { items: WorkItem[]; alertItemIds: Set<string> }) {
  if (items.length === 0) return null;

  const starts = items.map((item) => new Date(item.start_at).getTime());
  const ends = items.map((item) => new Date(item.end_at).getTime());
  const min = Math.min(...starts);
  const max = Math.max(...ends);
  const span = Math.max(max - min, 1);

  const zones = Array.from(new Set(items.map((item) => item.zone_name ?? item.zone_id))).sort();

  return (
    <div className="overflow-x-auto rounded border border-slate-300 bg-white p-3">
      <p className="mb-2 text-sm font-semibold text-slate-800">
        구역별 시간 배치 ({formatDateTime(new Date(min).toISOString())} ~ {formatDateTime(new Date(max).toISOString())})
      </p>
      <div className="min-w-[720px] space-y-1">
        {zones.map((zone) => (
          <div key={zone} className="flex items-center gap-2">
            <span className="w-32 shrink-0 truncate text-xs text-slate-700">{zone}</span>
            <div className="relative h-8 flex-1 rounded bg-slate-100">
              {items
                .filter((item) => (item.zone_name ?? item.zone_id) === zone)
                .map((item) => {
                  const left = ((new Date(item.start_at).getTime() - min) / span) * 100;
                  const width = Math.max(
                    ((new Date(item.end_at).getTime() - new Date(item.start_at).getTime()) / span) * 100,
                    1.5,
                  );
                  const flagged = alertItemIds.has(item.id);
                  return (
                    <span
                      key={item.id}
                      title={`${item.title} (${WORK_TYPE_LABEL[item.work_type]}) ${formatTime(item.start_at)}~${formatTime(item.end_at)}`}
                      style={{ left: `${left}%`, width: `${width}%` }}
                      className={`absolute top-1 flex h-6 items-center overflow-hidden rounded border px-1 text-[10px] ${
                        flagged
                          ? "border-red-600 bg-red-100 text-red-900"
                          : "border-slate-400 bg-white text-slate-800"
                      }`}
                    >
                      {flagged ? "⚠ " : ""}
                      {item.id}
                    </span>
                  );
                })}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-600">⚠ 표시는 경보에 포함된 작업입니다.</p>
    </div>
  );
}
