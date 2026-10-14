import { Plus } from "lucide-react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { Button } from "@/components/ui/button";
import { RowBones } from "@/components/shared/Skeletons";
import { useBrandId } from "@/lib/session";
import { CampaignTable, useConsole } from "./BrandHome";

export default function Campaigns() {
  const id = useBrandId();
  const q = useConsole(id);
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-sm text-fg-2">Open a campaign to see ranked matches and ready-made collectives.</p>
        </div>
        <Button asChild variant="primary" size="sm">
          <Link to="/brand/campaigns/new">
            <Plus aria-hidden /> New campaign
          </Link>
        </Button>
      </div>
      <div className="mt-5">
        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
        {!q.data && !q.isError && <RowBones rows={3} />}
        {q.data && <CampaignTable campaigns={q.data.campaigns} />}
      </div>
    </div>
  );
}
