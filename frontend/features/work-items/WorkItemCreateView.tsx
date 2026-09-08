"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorState, LoadingState, Notice } from "@/components/StateViews";
import { CsvUploadPanel } from "@/features/work-items/CsvUploadPanel";
import { NaturalLanguagePanel } from "@/features/work-items/NaturalLanguagePanel";
import { WorkItemForm } from "@/features/work-items/WorkItemForm";
import { api, ApiError } from "@/lib/api";
import type { HealthStatus, Zone } from "@/types/domain";

const TABS = [
  { id: "manual", label: "직접 입력" },
  { id: "csv", label: "CSV 업로드" },
  { id: "nl", label: "자연어 입력" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function WorkItemCreateView({ initialTab = "manual" }: { initialTab?: TabId }) {
  const router = useRouter();
  const [tab, setTab] = useState<TabId>(initialTab);
  const [zones, setZones] = useState<Zone[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [zoneList, status] = await Promise.all([api.listZones(), api.health()]);
        setZones(zoneList.items);
        setHealth(status);
      } catch (caught) {
        const apiError = caught as ApiError;
        setError({ message: apiError.message ?? "초기 데이터를 불러오지 못했습니다.", code: apiError.code ?? "UNKNOWN_ERROR" });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <LoadingState label="등록 화면을 준비하는 중입니다." />;
  if (error) return <ErrorState message={error.message} code={error.code} />;

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="작업 등록 방식" className="flex gap-2 border-b border-slate-300">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => {
              setTab(item.id);
              setSavedMessage(null);
            }}
            className={`-mb-px rounded-t border-x border-t px-4 py-2 text-sm font-semibold ${
              tab === item.id
                ? "border-slate-400 bg-white text-slate-900"
                : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {savedMessage ? <Notice>{savedMessage}</Notice> : null}

      {tab === "manual" ? (
        <section aria-label="직접 입력" className="rounded border border-slate-300 bg-white p-4">
          <WorkItemForm
            zones={zones}
            allowIdInput
            submitLabel="작업계획 저장"
            onSubmit={async (payload) => {
              const saved = await api.createWorkItem({ ...payload, source_type: "MANUAL" });
              setSavedMessage(`작업계획 ${saved.id}을(를) 저장했습니다.`);
              router.refresh();
            }}
          />
        </section>
      ) : null}

      {tab === "csv" ? (
        <section aria-label="CSV 업로드" className="rounded border border-slate-300 bg-white p-4">
          <CsvUploadPanel
            onSaved={(result) => setSavedMessage(`CSV에서 ${result.created_count + result.updated_count}건을 저장했습니다.`)}
          />
        </section>
      ) : null}

      {tab === "nl" ? (
        <section aria-label="자연어 입력" className="rounded border border-slate-300 bg-white p-4">
          {health && !health.llm_enabled ? (
            <div className="mb-3">
              <Notice tone="warn">
                지금은 키워드 인식 방식(모의 어댑터)으로 문장을 읽습니다. 구역 ID(A_BLOCK_1)와 표준시간대를 포함한
                시각(2026-03-16T09:00:00+09:00)을 쓰면 잘 인식하며, 인식하지 못한 칸은 직접 채우면 됩니다. 더 자세한
                결과를 얻으려면 LLM API 키가 필요합니다.
              </Notice>
            </div>
          ) : null}
          <NaturalLanguagePanel
            zones={zones}
            onSaved={(item) => setSavedMessage(`작업계획 ${item.id}을(를) 저장했습니다.`)}
          />
        </section>
      ) : null}
    </div>
  );
}
