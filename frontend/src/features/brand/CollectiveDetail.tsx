import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Lock, Send } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import type { CollectiveView } from "@/lib/deal-types";
import { STAGE_LABEL } from "@/lib/deal-types";
import { count, inr, pct } from "@/lib/format";
import { PayDialog } from "../deals/DealView";

export default function CollectiveDetail() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const [pay, setPay] = useState(false);
  const q = useQuery({ queryKey: ["collective-view", id], queryFn: () => api<CollectiveView>(`/collectives/${id}`), refetchInterval: 3000 });
  const release = useMutation({
    mutationFn: () => post<CollectiveView>(`/collectives/${id}/release`),
    onSuccess: (c) => {
      qc.setQueryData(["collective-view", id], c);
      qc.invalidateQueries();
      toast.success("Verified posts paid", { description: "Each creator received their split by UPI." });
    },
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-xl" />;
  const c = q.data;
  const live = c.members.filter((m) => m.stage === "live").length;

  return (
    <div>
      <Link to="/brand/deals" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Deals
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{c.listing.title}</h1>
          <p className="mt-1 text-sm text-fg-2">
            {c.members.length} creators · {count(c.combined_reach)} combined reach · one escrow payment, automatic split
          </p>
        </div>
        <div className="text-right">
          <p className="num font-display text-2xl font-semibold">{inr(c.total)}</p>
          <p className="text-xs text-muted">{inr(c.paid_out)} paid out so far</p>
        </div>
      </div>

      <div className="card-surface mt-5 flex flex-wrap items-center gap-3 rounded-xl p-4">
        {c.funded ? (
          <p className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="size-4 text-success" aria-hidden /> Escrow funded · {c.escrow?.ref}. Members move to posting as soon as they accept.
            {c.refunded > 0 && <span className="text-fg-2">{inr(c.refunded)} from declined shares returned to you.</span>}
          </p>
        ) : (
          <>
            <p className="flex-1 text-sm">
              <span className="font-semibold">Fund once for the whole pack.</span> <span className="text-fg-2">Any share a creator declines comes back to you.</span>
            </p>
            <Button variant="primary" onClick={() => setPay(true)}>
              <Lock aria-hidden /> Fund escrow {inr(c.total)}
            </Button>
          </>
        )}
        {live > 0 && (
          <Button variant="primary" onClick={() => release.mutate()} loading={release.isPending}>
            <Send aria-hidden /> Confirm {live} live post{live > 1 ? "s" : ""} and pay
          </Button>
        )}
      </div>

      <div className="card-surface mt-4 overflow-x-auto rounded-xl">
        <table className="w-full min-w-[560px] text-left text-[13px]">
          <thead className="border-b border-line bg-surface-2 text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Creator</th>
              <th scope="col" className="px-3 py-2 font-medium">Stage</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Split</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Payout</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {c.members.map((m) => (
              <tr key={m.creator_id}>
                <td className="px-4 py-2.5">
                  <Link to={`/brand/deals/${m.deal_id}`} className="flex items-center gap-2.5 font-medium hover:text-accent">
                    <Avatar name={m.name} hue={m.avatar_hue} size={26} generic={m.is_reference} />
                    {m.name}
                  </Link>
                </td>
                <td className="px-3 py-2.5">
                  <Badge size="sm" variant={m.paid ? "success" : m.stage === "live" ? "warn" : "outline"}>
                    {STAGE_LABEL[m.stage] ?? m.stage}
                  </Badge>
                </td>
                <td className="num px-3 py-2.5 text-right">{pct(m.split, 1)}</td>
                <td className="num px-4 py-2.5 text-right font-medium">{inr(m.price)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pay && (
        <PayDialog
          path={`/collectives/${id}/fund`}
          amount={c.total}
          onClose={() => setPay(false)}
          onPaid={async () => {
            await qc.invalidateQueries();
            setPay(false);
            toast.success(`${inr(c.total)} held in escrow for the collective`);
          }}
        />
      )}
    </div>
  );
}
