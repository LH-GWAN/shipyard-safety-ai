import type { ReactNode } from "react";

export function LoadingState({ label = "불러오는 중입니다." }: { label?: string }) {
  return (
    <div role="status" className="rounded border border-slate-300 bg-white p-6 text-sm text-slate-600">
      {label}
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-slate-400 bg-white p-8 text-center">
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      {description ? <p className="mt-1 text-sm text-slate-600">{description}</p> : null}
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, code, onRetry }: { message: string; code?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded border border-red-400 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-semibold">오류가 발생했습니다.</p>
      <p className="mt-1">{message}</p>
      {code ? <p className="mt-1 text-xs text-red-800">오류 코드: {code}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded border border-red-500 px-3 py-1 text-xs font-semibold text-red-800 hover:bg-red-100"
        >
          다시 시도
        </button>
      ) : null}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn"; children: ReactNode }) {
  const styles =
    tone === "warn"
      ? "border-amber-500 bg-amber-50 text-amber-900"
      : "border-slate-300 bg-slate-50 text-slate-700";
  return <p className={`rounded border px-3 py-2 text-xs ${styles}`}>{children}</p>;
}
