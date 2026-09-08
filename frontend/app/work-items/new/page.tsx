import { Disclaimer } from "@/components/Disclaimer";
import { WorkItemCreateView } from "@/features/work-items/WorkItemCreateView";

export default async function NewWorkItemPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab } = await searchParams;
  const initialTab = tab === "csv" || tab === "nl" ? tab : "manual";
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">작업 등록</h1>
      <Disclaimer />
      <WorkItemCreateView initialTab={initialTab} />
    </div>
  );
}
