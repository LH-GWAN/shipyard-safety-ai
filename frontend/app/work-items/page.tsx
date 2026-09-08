import { Disclaimer } from "@/components/Disclaimer";
import { WorkItemListView } from "@/features/work-items/WorkItemListView";

export default function WorkItemsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">작업 목록</h1>
      <Disclaimer />
      <WorkItemListView />
    </div>
  );
}
