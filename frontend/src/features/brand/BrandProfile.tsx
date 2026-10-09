import { BadgeCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { inr } from "@/lib/format";
import { useBrand } from "./BrandShell";

export default function BrandProfile() {
  const q = useBrand();
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-64 rounded-xl" />;
  const b = q.data;
  const rows: [string, React.ReactNode][] = [
    ["Category", b.category],
    ["Goal", b.goal ?? "—"],
    ["Monthly creator budget", b.budget_monthly ? inr(b.budget_monthly) : "—"],
    ["Target ages", b.target.ages.join(", ") || "Any"],
    ["Gender", b.target.gender === "any" ? "Everyone" : b.target.gender === "female" ? "Mostly women" : "Mostly men"],
    ["Languages", b.target.languages.join(", ")],
    ["Regions", b.target.regions.join(", ")],
    ["Priority cities", b.target.cities.join(", ") || "Pan-India"],
  ];
  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3.5">
        <Avatar name={b.name} hue={b.hue} size={48} className="rounded-xl" />
        <div>
          <h1 className="flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            {b.name} {b.verified && <BadgeCheck className="size-5 text-accent" aria-label="Verified" />}
          </h1>
          <p className="text-sm text-muted">{b.description}</p>
        </div>
      </div>
      <dl className="card-surface mt-6 divide-y divide-line rounded-xl">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[180px_1fr] gap-3 px-4 py-3 text-sm">
            <dt className="text-muted">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-xs text-muted">
        Matching uses this target to score audience fit. Creators share data with you only by consent; every view is logged in their ledger.{" "}
        {b.created_at || b.guest ? <Badge size="sm">Not verified</Badge> : <Badge size="sm">Fictional brand</Badge>}
      </p>
      <Button asChild variant="outline" size="sm" className="mt-4">
        <Link to="/brand/onboarding">Set up another brand</Link>
      </Button>
    </div>
  );
}
