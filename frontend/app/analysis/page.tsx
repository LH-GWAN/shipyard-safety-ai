import { AnalysisView } from "@/features/analysis/AnalysisView";

export default function AnalysisPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">분석 결과</h1>
      <AnalysisView />
    </div>
  );
}
