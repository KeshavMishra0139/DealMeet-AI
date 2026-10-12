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
      toast.success("Posts approved", {
        description: c.payments_mode === "simulated" ? "Each creator's split is recorded as a simulated payout. No money moved." : "Payouts wait until a payout partner is connected.",
      });
    },
  });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-xl" />;
  const c = q.data;
  const live = c.members.filter((m) => m.stage === "live").length;
  const conf = c.confirmations;
  const declined = c.members.filter((m) => m.stage === "declined");

  return (
    <div>
      <Link to="/brand/deals" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Deals
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{c.listing.title}</h1>
          <p className="mt-1 text-sm text-fg-2">
            {c.members.length} creators{c.combined_reach != null && ` · ${count(c.combined_reach)} combined reach`} · one escrow payment, split by member
          </p>
        </div>
        <div className="text-right">
          <p className="num font-display text-2xl font-semibold">{inr(c.total)}</p>
          <p className="text-xs text-muted">
            {inr(c.paid_out ?? 0)} {c.escrow?.mode === "simulated" ? "in simulated payouts" : "paid out"} so far
          </p>
        </div>
      </div>

      <div className="card-surface mt-5 flex flex-wrap items-center gap-3 rounded-xl p-4">
        {c.funded ? (
          <p className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="size-4 text-success" aria-hidden /> Escrow funded{c.escrow?.mode === "simulated" ? " (simulated, no money moved)" : " (Razorpay test mode)"} ·{" "}
            {c.escrow?.ref}. Members move to posting as soon as they accept.
            {(c.refunded ?? 0) > 0 && <span className="text-fg-2">{inr(c.refunded ?? 0)} from declined shares is due back to you.</span>}
          </p>
        ) : (
          <>
            <p className="flex-1 text-sm">
              {conf.status === "active" ? (
                <>
                  <span className="font-semibold">Everyone confirmed.</span> <span className="text-fg-2">Fund once for the whole pack; each share is released after you approve that member's post.</span>
                </>
              ) : conf.status === "needs_replacement" ? (
                <>
                  <span className="font-semibold">{declined.length} member{declined.length === 1 ? "" : "s"} declined.</span> <span className="text-fg-2">Replace them below before funding. Nothing has been charged.</span>
                </>
              ) : (
                <>
                  <span className="font-semibold">
                    {conf.confirmed} of {conf.required} members confirmed.
                  </span>{" "}
                  <span className="text-fg-2">The collective starts, and can be funded, once everyone has confirmed their own terms. Nothing has been charged.</span>
                </>
              )}
            </p>
            <Button variant="primary" onClick={() => setPay(true)} disabled={conf.status !== "active"}>
              <Lock aria-hidden /> Fund escrow {inr(c.total)}
            </Button>
          </>
        )}
        {live > 0 && (
          <Button variant="primary" onClick={() => release.mutate()} loading={release.isPending}>
            <Send aria-hidden /> Approve {live} submitted post{live > 1 ? "s" : ""}
          </Button>
        )}
      </div>

      <div className="card-surface mt-4 overflow-x-auto rounded-xl">
        <table className="w-full min-w-[560px] text-left text-[13px]">
          <thead className="border-b border-line bg-surface-2 text-xs text-muted">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Creator</th>
              <th scope="col" className="px-3 py-2 font-medium">Terms</th>
              <th scope="col" className="px-3 py-2 font-medium">Stage</th>
              <th scope="col" className="px-3 py-2 font-medium">Payment</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Split</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Fee</th>
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
                <td className="px-3 py-2.5 text-xs text-fg-2">{m.deliverables ?? "Private"}</td>
                <td className="px-3 py-2.5">
                  <Badge size="sm" variant={m.paid ? "success" : m.stage === "declined" ? "danger" : m.stage === "live" ? "warn" : "outline"}>
                    {m.stage === "offer" ? "Waiting to confirm" : m.stage === "contract" ? "Confirmed" : (STAGE_LABEL[m.stage] ?? m.stage)}
                  </Badge>
                </td>
                <td className="px-3 py-2.5 text-xs text-fg-2">{m.payment_status ?? "—"}</td>
                <td className="num px-3 py-2.5 text-right">{m.split != null ? pct(m.split, 1) : "Private"}</td>
                <td className="num px-4 py-2.5 text-right font-medium">{m.price != null ? inr(m.price) : "Private"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {declined.length > 0 && !c.funded && <Replace collectiveId={id} declined={declined.map((m) => ({ id: m.creator_id, name: m.name }))} />}

      {pay && (
        <PayDialog
          path={`/collectives/${id}/fund`}
          amount={c.total}
          mode={c.payments_mode}
          onClose={() => setPay(false)}
          onPaid={async () => {
            await qc.invalidateQueries();
            setPay(false);
            toast.success(c.payments_mode === "simulated" ? `${inr(c.total)} in simulated escrow for the collective` : `${inr(c.total)} paid into escrow for the collective (test mode)`);
          }}
        />
      )}
    </div>
  );
}

interface Candidate {
  id: string;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  price: number;
  fit: number;
  why: string[];
}

/** Swap a member who declined for another creator who fits. */
function Replace({ collectiveId, declined }: { collectiveId: string; declined: { id: string; name: string }[] }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["replacements", collectiveId], queryFn: () => api<{ items: Candidate[] }>(`/collectives/${collectiveId}/replacements`) });
  const replace = useMutation({
    mutationFn: (v: { out: string; inn: string }) => post<CollectiveView>(`/collectives/${collectiveId}/replace`, { out_id: v.out, in_id: v.inn }),
    onSuccess: (c) => {
      qc.setQueryData(["collective-view", collectiveId], c);
      void qc.invalidateQueries({ queryKey: ["replacements", collectiveId] });
      toast.success("Replacement invited", { description: "They confirm their own terms like everyone else." });
    },
    onError: (e) => toast.error((e as Error).message),
  });
  const out = declined[0];
  return (
    <section aria-labelledby="replace" className="card-surface mt-4 rounded-xl p-4">
      <h2 id="replace" className="text-sm font-semibold">
        Replace {out.name}
      </h2>
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && q.data.items.length === 0 && <p className="mt-2 text-sm text-fg-2">No other creators fit this campaign right now.</p>}
      <ul className="mt-2 divide-y divide-line">
        {q.data?.items.slice(0, 5).map((cand) => (
          <li key={cand.id} className="flex flex-wrap items-center gap-3 py-2.5">
            <Avatar name={cand.name} hue={cand.avatar_hue} size={28} generic={cand.is_reference} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">
                {cand.name} <span className="text-xs font-normal text-muted">· fit {cand.fit} · {inr(cand.price)}</span>
              </p>
              <p className="truncate text-xs text-muted">{cand.why[0]}</p>
            </div>
            <Button size="sm" variant="outline" loading={replace.isPending && replace.variables?.inn === cand.id} onClick={() => replace.mutate({ out: out.id, inn: cand.id })}>
              Invite instead
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
