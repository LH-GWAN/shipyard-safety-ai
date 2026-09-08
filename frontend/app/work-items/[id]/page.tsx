import { Disclaimer } from "@/components/Disclaimer";
import { WorkItemEditView } from "@/features/work-items/WorkItemEditView";

export default async function EditWorkItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">작업계획 편집</h1>
      <Disclaimer />
      <WorkItemEditView workItemId={id} />
    </div>
  );
}
