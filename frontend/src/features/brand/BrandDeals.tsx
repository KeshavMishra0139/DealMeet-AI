import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, EmptyState, ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import type { CollectiveView, DealRow } from "@/lib/deal-types";
import { STAGE_LABEL } from "@/lib/deal-types";
import { count, inr, shortDate } from "@/lib/format";
import { useBrandId } from "@/lib/session";

export default function BrandDeals() {
  const id = useBrandId();
  const q = useQuery({ queryKey: ["brand-deals", id], queryFn: () => api<{ deals: DealRow[]; collectives: CollectiveView[] }>(`/brands/${id}/deals`), refetchInterval: 4000 });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-xl" />;
  return (
    <div>
      <h1 className="font-display text-2xl font-semibold tracking-tight">Deals</h1>
      <p className="mt-1 text-sm text-fg-2">Escrow-protected. You fund before posts go live and release after you confirm.</p>

      {q.data.collectives.length > 0 && (
        <section aria-labelledby="cols" className="mt-6">
          <h2 id="cols" className="mb-2 text-sm font-semibold">
            Collectives
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {q.data.collectives.map((c) => (
              <li key={c.id}>
                <Link to={`/brand/collectives/${c.id}`} className="card-surface block rounded-xl p-4 hover:border-accent/50">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Users className="size-4 text-accent" aria-hidden /> {c.listing.title}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {c.members.length} creators{c.combined_reach != null && ` · ${count(c.combined_reach)} combined reach`} · {inr(c.total)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge size="sm" variant={c.funded ? "success" : "warn"}>
                      {c.funded ? "Escrow funded" : "Escrow not funded"}
                    </Badge>
                    {Object.entries(c.stages).map(([s, n]) => (
                      <Badge key={s} size="sm">
                        {n} {STAGE_LABEL[s as keyof typeof STAGE_LABEL] ?? s}
                      </Badge>
                    ))}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="singles" className="mt-6">
        <h2 id="singles" className="mb-2 text-sm font-semibold">
          Individual deals
        </h2>
        {q.data.deals.length === 0 ? (
          <div className="card-surface rounded-xl">
            <EmptyState title="No deals yet" body="Send an offer from a campaign's matches to start one." />
          </div>
        ) : (
          <div className="card-surface overflow-x-auto rounded-xl">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead className="border-b border-line bg-surface-2 text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Creator</th>
                  <th scope="col" className="px-3 py-2 font-medium">Campaign</th>
                  <th scope="col" className="px-3 py-2 font-medium">Stage</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Amount</th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {q.data.deals.map((d) => (
                  <tr key={d.id} className="group hover:bg-surface-2">
                    <td className="px-4 py-2.5">
                      <Link to={`/brand/deals/${d.id}`} className="flex items-center gap-2.5 font-medium group-hover:text-accent">
                        <Avatar name={d.creator.name} hue={d.creator.avatar_hue} size={26} generic={d.creator.is_reference} />
                        {d.creator.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-fg-2">{d.listing?.title ?? "Direct"}</td>
                    <td className="px-3 py-2.5">
                      <Badge size="sm" variant={d.actions.length ? "accent" : d.stage === "paid" ? "success" : "outline"}>
                        {d.actions.length && !["offer"].includes(d.stage) ? "Your move" : d.counter && !d.counter.accepted_at && !d.counter.declined_at ? "Counter received" : STAGE_LABEL[d.stage]}
                      </Badge>
                    </td>
                    <td className="num px-3 py-2.5 text-right font-medium">{inr(d.amount)}</td>
                    <td className="num px-4 py-2.5 text-right text-muted">{d.updated ? shortDate(d.updated) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
