"use client";

import Link from "next/link";
import { formatDateTime } from "@/lib/format";
import { SOURCE_TYPE_LABEL, WORK_STATUS_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import type { WorkItem } from "@/types/domain";

export function WorkItemTable({
  items,
  onDelete,
}: {
  items: WorkItem[];
  onDelete?: (item: WorkItem) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-collapse text-sm">
        <thead>
          <tr className="bg-slate-100 text-left">
            <th className="border border-slate-300 px-2 py-1">작업명</th>
            <th className="border border-slate-300 px-2 py-1">종류</th>
            <th className="border border-slate-300 px-2 py-1">구역</th>
            <th className="border border-slate-300 px-2 py-1">시작시각</th>
            <th className="border border-slate-300 px-2 py-1">종료시각</th>
            <th className="border border-slate-300 px-2 py-1">입력출처</th>
            <th className="border border-slate-300 px-2 py-1">검토상태</th>
            <th className="border border-slate-300 px-2 py-1">경보</th>
            <th className="border border-slate-300 px-2 py-1">관리</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="border border-slate-300 px-2 py-1">
                <span className="block font-medium text-slate-900">{item.title}</span>
                <span className="text-xs text-slate-600">{item.id}</span>
              </td>
              <td className="border border-slate-300 px-2 py-1">{WORK_TYPE_LABEL[item.work_type]}</td>
              <td className="border border-slate-300 px-2 py-1">{item.zone_name ?? item.zone_id}</td>
              <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.start_at)}</td>
              <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.end_at)}</td>
              <td className="border border-slate-300 px-2 py-1">{SOURCE_TYPE_LABEL[item.source_type]}</td>
              <td className="border border-slate-300 px-2 py-1">{WORK_STATUS_LABEL[item.status]}</td>
              <td className="border border-slate-300 px-2 py-1">
                {item.has_alert === null ? "분석 전" : item.has_alert ? "경보 있음" : "경보 없음"}
              </td>
              <td className="border border-slate-300 px-2 py-1">
                <div className="flex gap-2">
                  <Link
                    href={`/work-items/${encodeURIComponent(item.id)}`}
                    className="rounded border border-slate-500 px-2 py-0.5 text-xs text-slate-800 hover:bg-slate-100"
                  >
                    편집
                  </Link>
                  {onDelete ? (
                    <button
                      type="button"
                      onClick={() => onDelete(item)}
                      className="rounded border border-red-500 px-2 py-0.5 text-xs text-red-800 hover:bg-red-50"
                    >
                      삭제
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
