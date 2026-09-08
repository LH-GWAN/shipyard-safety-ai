import { SEVERITY_LABEL, SEVERITY_MARK } from "@/lib/labels";
import type { Severity } from "@/types/domain";

const STYLE: Record<Severity, string> = {
  HIGH: "border-red-600 bg-red-50 text-red-900",
  MEDIUM: "border-amber-600 bg-amber-50 text-amber-900",
  LOW: "border-slate-500 bg-slate-50 text-slate-800",
};

/** 색상만으로 구분하지 않도록 기호와 문자 표기를 함께 제공한다. */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold ${STYLE[severity]}`}>
      <span aria-hidden="true">{SEVERITY_MARK[severity]}</span>
      <span>등급 {SEVERITY_LABEL[severity]}</span>
    </span>
  );
}
