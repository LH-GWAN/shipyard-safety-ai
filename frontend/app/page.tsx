import { DashboardView } from "@/features/dashboard/DashboardView";

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">대시보드</h1>
      <DashboardView />
    </div>
  );
}
