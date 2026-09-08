import { DISCLAIMER } from "@/lib/labels";

export function Disclaimer() {
  return (
    <p
      data-testid="disclaimer"
      className="rounded border border-slate-400 bg-white px-3 py-2 text-xs font-medium text-slate-800"
    >
      {DISCLAIMER}
    </p>
  );
}
