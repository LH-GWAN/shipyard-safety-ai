"use client";

import { SeverityBadge } from "@/components/SeverityBadge";
import { formatDateTime, formatMinutes } from "@/lib/format";
import { SAFETY_FIELD_LABEL, SPATIAL_RELATION_LABEL, WORK_TYPE_LABEL } from "@/lib/labels";
import type { Alert, SafetyRule, SpatialRelation, WorkType } from "@/types/domain";

interface EvidenceWorkItem {
  id: string;
  title: string;
  work_type: WorkType;
  zone_id: string;
  zone_name: string;
  start_at: string;
  end_at: string;
  uses_flammable_material: boolean | null;
}

export function AlertDetail({ alert, rule }: { alert: Alert; rule?: SafetyRule }) {
  const evidence = alert.evidence as Record<string, unknown>;
  const relatedItems = (evidence.work_items as EvidenceWorkItem[] | undefined) ?? [];
  const relation = evidence.spatial_relation as SpatialRelation | undefined;
  const field = evidence.field as string | undefined;
  const valueState = evidence.value_state as string | undefined;

  return (
    <section aria-label="경보 상세" className="space-y-3 rounded border border-slate-400 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <span className="rounded border border-slate-400 px-2 py-0.5 text-xs font-semibold text-slate-800">
          규칙 {alert.rule_id}
        </span>
        <span className="text-xs text-slate-600">경보 ID {alert.id}</span>
      </div>

      <p className="text-sm font-semibold text-slate-900">{alert.message}</p>

      {rule ? (
        <div className="rounded border border-slate-300 bg-slate-50 p-3 text-xs text-slate-700">
          <p className="font-semibold text-slate-800">
            적용 규칙: {rule.name} (버전 {rule.version})
          </p>
          <p className="mt-1">{rule.description}</p>
          <p className="mt-2">
            근거 자료: {rule.reference_title}
            {rule.reference_articles.length > 0 ? ` · ${rule.reference_articles.join(", ")}` : ""}
          </p>
          {rule.reference_url ? (
            <p className="mt-1">
              <a
                href={rule.reference_url}
                target="_blank"
                rel="noreferrer"
                className="underline hover:text-slate-900"
              >
                국가법령정보센터에서 조문 보기
              </a>
              {rule.reference_verified_at ? ` (조문 확인일 ${rule.reference_verified_at})` : ""}
            </p>
          ) : null}
          {rule.reference_note ? <p className="mt-1">{rule.reference_note}</p> : null}
          {rule.requires_site_validation ? (
            <p className="mt-2 font-medium text-slate-800">
              이 경보는 법 위반 판정이 아닙니다. 현장 적용 전 회사 작업허가 기준으로 검증이 필요합니다.
            </p>
          ) : null}
        </div>
      ) : null}

      <dl className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs text-slate-600">관련 작업</dt>
          <dd className="font-medium text-slate-900">{alert.work_item_ids.join(", ")}</dd>
        </div>
        {relation ? (
          <div>
            <dt className="text-xs text-slate-600">구역 관계</dt>
            <dd className="font-medium text-slate-900">{SPATIAL_RELATION_LABEL[relation]}</dd>
          </div>
        ) : null}
        {evidence.overlap_start ? (
          <div>
            <dt className="text-xs text-slate-600">중첩 시간</dt>
            <dd className="font-medium text-slate-900">
              {formatDateTime(String(evidence.overlap_start))} ~ {formatDateTime(String(evidence.overlap_end))} (
              {formatMinutes(Number(evidence.overlap_minutes))})
            </dd>
          </div>
        ) : null}
        {field ? (
          <div>
            <dt className="text-xs text-slate-600">누락 또는 미실시 항목</dt>
            <dd className="font-medium text-slate-900">
              {SAFETY_FIELD_LABEL[field] ?? field} ·{" "}
              {valueState === "MISSING" ? "값 미입력(null)" : "미실시로 입력(false)"}
            </dd>
          </div>
        ) : null}
      </dl>

      {relatedItems.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <caption className="pb-1 text-left text-xs font-semibold text-slate-700">입력 근거(작업계획 값)</caption>
            <thead>
              <tr className="bg-slate-100 text-left">
                <th className="border border-slate-300 px-2 py-1">작업 ID</th>
                <th className="border border-slate-300 px-2 py-1">작업명</th>
                <th className="border border-slate-300 px-2 py-1">종류</th>
                <th className="border border-slate-300 px-2 py-1">구역</th>
                <th className="border border-slate-300 px-2 py-1">시작</th>
                <th className="border border-slate-300 px-2 py-1">종료</th>
                <th className="border border-slate-300 px-2 py-1">가연성 물질</th>
              </tr>
            </thead>
            <tbody>
              {relatedItems.map((item) => (
                <tr key={item.id}>
                  <td className="border border-slate-300 px-2 py-1">{item.id}</td>
                  <td className="border border-slate-300 px-2 py-1">{item.title}</td>
                  <td className="border border-slate-300 px-2 py-1">{WORK_TYPE_LABEL[item.work_type]}</td>
                  <td className="border border-slate-300 px-2 py-1">
                    {item.zone_name} ({item.zone_id})
                  </td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.start_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">{formatDateTime(item.end_at)}</td>
                  <td className="border border-slate-300 px-2 py-1">
                    {item.uses_flammable_material === null ? "미입력" : item.uses_flammable_material ? "예" : "아니오"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="rounded border border-slate-300 bg-slate-50 p-3">
        <p className="text-xs font-semibold text-slate-800">권고 확인사항</p>
        <p className="mt-1 text-sm text-slate-800">{alert.recommended_action}</p>
      </div>

      <details className="text-xs text-slate-700">
        <summary className="cursor-pointer font-semibold">근거 데이터(evidence) 원본 보기</summary>
        <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          {JSON.stringify(alert.evidence, null, 2)}
        </pre>
      </details>
    </section>
  );
}
