"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorState, LoadingState, Notice } from "@/components/StateViews";
import { WorkItemForm } from "@/features/work-items/WorkItemForm";
import { api, ApiError } from "@/lib/api";
import type { WorkItem, Zone } from "@/types/domain";

export function WorkItemEditView({ workItemId }: { workItemId: string }) {
  const router = useRouter();
  const [item, setItem] = useState<WorkItem | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [zoneList, workItem] = await Promise.all([api.listZones(), api.getWorkItem(workItemId)]);
        setZones(zoneList.items);
        setItem(workItem);
      } catch (caught) {
        const apiError = caught as ApiError;
        setError({ message: apiError.message ?? "작업계획을 불러오지 못했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
      } finally {
        setLoading(false);
      }
    })();
  }, [workItemId]);

  if (loading) return <LoadingState label="작업계획을 불러오는 중입니다." />;
  if (error) return <ErrorState message={error.message} code={error.code} />;
  if (!item) return null;

  return (
    <div className="space-y-4">
      {savedMessage ? <Notice>{savedMessage}</Notice> : null}
      <section className="rounded border border-slate-300 bg-white p-4">
        <WorkItemForm
          zones={zones}
          initial={item}
          submitLabel="변경사항 저장"
          onSubmit={async (payload) => {
            const saved = await api.updateWorkItem(item.id, payload);
            setItem(saved);
            setSavedMessage(`작업계획 ${saved.id}을(를) 수정했습니다.`);
          }}
        />
      </section>
      <button
        type="button"
        onClick={async () => {
          await api.deleteWorkItem(item.id);
          router.push("/work-items");
        }}
        className="rounded border border-red-500 px-3 py-1.5 text-sm font-semibold text-red-800 hover:bg-red-50"
      >
        이 작업계획 삭제
      </button>
    </div>
  );
}
