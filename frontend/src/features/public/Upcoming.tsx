import { Construction } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/shared/Bits";
import { Button } from "@/components/ui/button";

/** Temporary stand-in for screens that later build phases replace. */
export function Upcoming({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold">{title}</h1>
      <div className="card-surface mt-6 rounded-[var(--radius-card)]">
        <EmptyState
          icon={<Construction className="size-5" />}
          title="Being built in the next phase"
          body={body}
          action={
            <Button asChild variant="outline" size="sm">
              <Link to="/">Back to start</Link>
            </Button>
          }
        />
      </div>
    </div>
  );
}
