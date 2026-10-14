import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  CircleDashed,
  Clock,
  Download,
  ExternalLink,
  FileSignature,
  IndianRupee,
  Lock,
  ShieldCheck,
  Star,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Rail } from "@/components/deals/Rail";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { ReportButton } from "@/components/shared/ReportButton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { api, post } from "@/lib/api";
import type { FairPrice } from "@/lib/api-types";
import type { Deal, DealAction, PaymentsMode, PostCheck } from "@/lib/deal-types";
import { STAGE_LABEL } from "@/lib/deal-types";
import { inr, possessive, shortDate, timeOfDay } from "@/lib/format";
import { fundEscrow } from "@/lib/payments";
import { cn } from "@/lib/utils";
import { useLoadWipe, DetailSkeleton } from "@/components/shared/Skeletons";

type Role = "creator" | "brand";

export function useDeal(id: string, role: Role) {
  return useQuery({
    queryKey: ["deal", id, role],
    queryFn: () => api<Deal>(`/deals/${id}`),
    refetchInterval: 3000,
  });
}

export default function DealView({ role }: { role: Role }) {
  const { id = "" } = useParams();
  const q = useDeal(id, role);
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<null | "counter" | "url" | "pay" | "sign" | "revision" | "terms">(null);
  const [pending, setPending] = useState<DealAction | null>(null);

  const act = useMutation({
    // The server takes the acting side from the session.
    mutationFn: (body: Record<string, unknown>) => {
      // One key per deal state and action: a double-click or retry sends the same key, and the server ignores the repeat.
      const now = qc.getQueryData<Deal>(["deal", id, role]);
      return post<Deal>(`/deals/${id}/action`, { ...body, request_key: `${id}:${now?.timeline.length ?? 0}:${String(body.action)}` });
    },
    onSuccess: (d) => {
      qc.setQueryData(["deal", id, role], d);
      qc.invalidateQueries({ predicate: (x) => x.queryKey[0] !== "deal" });
      setDialog(null);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const ready = useLoadWipe(!!q.data);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data || !ready) return <DetailSkeleton label="Loading deal" />;
  const d = q.data;
  const other = role === "creator" ? { name: d.brand.name, hue: d.brand.hue, generic: false } : { name: d.creator.name, hue: d.creator.avatar_hue, generic: d.creator.is_reference };
  const back = role === "creator" ? "/creator/deals" : d.collective ? `/brand/collectives/${d.collective.id}` : "/brand/deals";

  const run = (a: DealAction) => {
    if (a.needs === "amount") return setDialog("counter");
    if (a.needs === "url") return setDialog("url");
    if (a.needs === "payment") return setDialog("pay");
    if (a.needs === "note") return setDialog("revision");
    if (a.needs === "terms") return setDialog("terms");
    if (a.id === "sign" || a.id === "accept" || a.id === "accept_counter") {
      setPending(a);
      return setDialog("sign");
    }
    act.mutate({ action: a.id });
  };

  return (
    <div className="space-y-5">
      <Link to={back} className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> {role === "creator" ? "Deals" : d.collective ? "Collective" : "Deals"}
      </Link>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Avatar name={other.name} hue={other.hue} size={44} generic={other.generic} className={role === "creator" ? "rounded-xl" : undefined} />
          <div>
            <h1 className="flex flex-wrap items-center gap-2 font-display text-xl font-semibold tracking-tight sm:text-2xl">
              {other.name}
              {role === "creator" && (d.brand.verified ? <BadgeCheck className="size-4 text-accent" aria-label="Verified" /> : <Badge size="sm" variant="warn">Unverified</Badge>)}
              {d.kind === "collective" && (
                <Badge size="sm" variant="accent">
                  <Users aria-hidden /> Collective
                </Badge>
              )}
            </h1>
            <p className="text-sm text-muted">
              {d.listing ? d.listing.title : "Direct booking"} · {d.deliverables}
              {d.usage_rights_days > 0 && ` · ${d.usage_rights_days} days usage`}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="num font-display text-2xl font-semibold">{inr(d.amount)}</p>
          <p className="text-xs text-muted">
            {d.status_label ?? STAGE_LABEL[d.stage]}
            {d.fair_total ? ` · fair ${inr(d.fair_total)}` : ""}
          </p>
        </div>
      </header>

      {d.alerts.map((a) => (
        <div
          key={a.text}
          role="status"
          className={cn(
            "flex flex-wrap items-center gap-3 rounded-2xl border p-3.5",
            a.kind === "low_offer" || a.kind === "revision" ? "border-warn/40 bg-warn-soft" : "border-line bg-surface-2",
          )}
        >
          {a.kind === "low_offer" || a.kind === "revision" ? (
            <AlertTriangle className="size-5 shrink-0 text-warn" aria-hidden />
          ) : (
            <Clock className="size-5 shrink-0 text-muted" aria-hidden />
          )}
          <div className="min-w-[200px] flex-1">
            <p className="text-sm font-semibold">{a.text}</p>
            {a.detail && <p className="text-xs text-fg-2">{a.detail}</p>}
            {a.kind === "low_offer" && a.fair && (
              <p className="text-xs text-fg-2">
                {role === "creator"
                  ? `Your fair price for ${d.deliverables} is ${inr(a.fair)}, priced on your reach.`
                  : `${possessive(d.creator.name)} fair price for ${d.deliverables} is ${inr(a.fair)}, priced on their reach. Offers this far below fair are often countered.`}
              </p>
            )}
          </div>
          {a.kind === "low_offer" && role === "creator" && d.actions.some((x) => x.id === "counter") && (
            <Button size="sm" variant="primary" onClick={() => setDialog("counter")}>
              Counter at {inr(a.fair ?? d.amount)}
            </Button>
          )}
        </div>
      ))}

      <section aria-labelledby="rail" className="card-surface rounded-2xl p-5">
        <h2 id="rail" className="sr-only">
          Progress
        </h2>
        <Rail steps={d.steps} declined={d.stage === "declined"} />
        {d.stage === "declined" && <p className="mt-3 text-sm text-muted">This deal was declined. Nothing was charged.</p>}

        {d.counter && !d.counter.accepted_at && !d.counter.declined_at && (
          <p className="mt-4 rounded-xl bg-accent-soft p-3 text-sm">
            {role === "creator" ? "You countered" : `${d.creator.name} countered`} at <span className="num font-semibold">{inr(d.counter.amount)}</span>
            {role === "creator" ? `. Waiting for ${d.brand.name}.` : "."}
          </p>
        )}

        {d.actions.length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
            {d.actions.map((a) => (
              <Button key={a.id} variant={a.kind === "primary" ? "primary" : a.kind === "secondary" ? "outline" : "ghost"} onClick={() => run(a)} loading={act.isPending && act.variables?.action === a.id}>
                {a.label}
              </Button>
            ))}
          </div>
        )}
        {d.actions.length === 0 && d.stage !== "paid" && d.stage !== "declined" && (
          <p className="mt-4 flex items-center gap-1.5 border-t border-line pt-4 text-sm text-muted">
            <Clock className="size-4" aria-hidden /> Waiting for {role === "creator" ? d.brand.name : d.creator.name}.
          </p>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-labelledby="money" className="card-surface rounded-2xl p-5">
          <h2 id="money" className="flex items-center gap-1.5 text-sm font-semibold">
            <Lock className="size-4 text-muted" aria-hidden /> Escrow and payout
          </h2>
          {d.escrow ? (
            <dl className="mt-3 space-y-2 text-[13px]">
              <Row k={d.escrow.mode === "simulated" ? "In escrow (simulated)" : "In escrow"} v={inr(d.escrow.amount ?? d.amount)} />
              <Row k="Payment" v={`${d.escrow.mode === "razorpay-test" ? "Razorpay test mode" : "Simulated, no money moved"} · ${d.escrow.ref}`} />
              <Row k="Funded" v={`${shortDate(d.escrow.funded_at)}, ${timeOfDay(d.escrow.funded_at)}`} />
              {d.collective && <Row k="Your split of the collective" v={`${((d.collective.split ?? 0) * 100).toFixed(1)}% of ${inr(d.collective.total)}`} />}
            </dl>
          ) : (
            <p className="mt-3 text-sm text-muted">
              {d.kind === "collective" ? "Funded once for the whole collective." : `${d.brand.name} funds escrow after both sides sign. You post only once the money is held.`}
            </p>
          )}
          {d.payouts.map((p) => (
            <div key={p.at} className="mt-3 flex items-center gap-2.5 rounded-xl bg-surface-2 p-3 text-sm text-fg-2">
              <CheckCircle2 className="size-4 shrink-0 text-muted" aria-hidden />
              <span>
                {p.mode === "simulated" ? `Simulated payout of ${inr(p.amount)} recorded ${shortDate(p.at)}. No money moved.` : `${inr(p.amount)} paid out ${shortDate(p.at)}.`}
              </span>
            </div>
          ))}
          {d.payout?.status === "not_connected" && (
            <p className="mt-3 rounded-xl bg-surface-2 p-3 text-sm text-fg-2">Approved. Payout isn't connected yet, so nothing has been paid out.</p>
          )}
          {d.invoice && (
            <Button asChild size="sm" variant="outline" className="mt-3">
              <a href={`/api/invoices/${d.invoice.id}.pdf`} target="_blank" rel="noreferrer">
                <Download aria-hidden /> Invoice {d.invoice.number}
              </a>
            </Button>
          )}
        </section>

        <section aria-labelledby="post" className="card-surface rounded-2xl p-5">
          <h2 id="post" className="flex items-center gap-1.5 text-sm font-semibold">
            <ShieldCheck className="size-4 text-muted" aria-hidden /> Post and review
          </h2>
          {d.proof_url ? (
            <a href={d.proof_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 break-all text-sm text-accent underline-offset-4 hover:underline">
              {d.proof_url} <ExternalLink className="size-3.5 shrink-0" aria-hidden />
            </a>
          ) : (
            <p className="mt-3 text-sm text-muted">The post link appears here once it's submitted.</p>
          )}
          {d.verification && (
            <p className="mt-3 text-xs text-muted">
              {d.verification.approved_by === "auto" ? "Approved automatically: the brand didn't review it in time." : `Approved by ${d.brand.name}.`}
            </p>
          )}
          {(d.verification ?? d.post_check) && <PostChecks check={(d.verification ?? d.post_check)!} />}
          {(d.stage === "verified" || d.stage === "paid") && <AfterDeal deal={d} role={role} />}
          {!d.verification && d.auto_release_on && (
            <p className="mt-3 text-xs text-muted">If {d.brand.name} doesn't review it, the post is approved automatically on {shortDate(d.auto_release_on)}.</p>
          )}
          {d.revisions.length > 0 && (
            <div className="mt-3 border-t border-line pt-3">
              <p className="text-xs font-semibold text-muted">Revisions asked for ({d.revisions.length})</p>
              <ul className="mt-1.5 space-y-1 text-[13px] text-fg-2">
                {d.revisions.map((r) => (
                  <li key={r.at}>
                    {shortDate(r.at)}: {r.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      {d.contract && (
        <section aria-labelledby="contract" className="card-surface rounded-2xl p-5">
          <h2 id="contract" className="flex items-center gap-1.5 text-sm font-semibold">
            <FileSignature className="size-4 text-muted" aria-hidden /> Contract
          </h2>
          <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-fg-2">
            {d.contract.terms.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ol>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <Sig who={d.creator.name} at={d.contract.signed_by_creator} name={d.contract.creator_signature} />
            <Sig who={d.brand.name} at={d.contract.signed_by_brand} name={d.contract.brand_signature} />
          </div>
          {d.versions && d.versions.length > 0 && <Versions deal={d} />}
        </section>
      )}
      {d.submissions && d.submissions.length > 0 && <Submissions deal={d} />}

      <section aria-labelledby="tl" className="card-surface rounded-2xl p-5">
        <h2 id="tl" className="text-sm font-semibold">
          Timeline
        </h2>
        <ol className="mt-3 space-y-2.5">
          {d.timeline.map((e, i) => (
            <li key={`${e.at}-${i}`} className="flex gap-3 text-[13px]">
              <span className="num w-24 shrink-0 text-xs text-muted">
                {shortDate(e.at)}, {timeOfDay(e.at)}
              </span>
              <span className="text-fg-2">{e.note}</span>
            </li>
          ))}
        </ol>
      </section>

      {d.message && (
        <p className="text-sm text-fg-2">
          <span className="font-medium text-fg">Message from {d.brand.name}:</span> {d.message}
        </p>
      )}
      <div className="flex justify-end">
        <ReportButton type="deal" id={d.id} role={role} label="Report a problem with this deal" />
      </div>

      {dialog === "counter" && <CounterDialog deal={d} onClose={() => setDialog(null)} onSubmit={(amount, note) => act.mutate({ action: "counter", amount, note })} pending={act.isPending} />}
      {dialog === "url" && <PostDialog onClose={() => setDialog(null)} onSubmit={(links, note) => act.mutate({ action: "submit_post", links, note: note || null })} pending={act.isPending} />}
      {dialog === "terms" && <TermsDialog deal={d} onClose={() => setDialog(null)} onSubmit={(body) => act.mutate({ action: "propose", ...body })} pending={act.isPending} />}
      {dialog === "revision" && (
        <RevisionDialog deal={d} onClose={() => setDialog(null)} onSubmit={(note) => act.mutate({ action: "request_revision", note })} pending={act.isPending} />
      )}
      {dialog === "sign" && pending && (
        <SignDialog
          deal={d}
          role={role}
          action={pending}
          onClose={() => setDialog(null)}
          onSubmit={(name) => act.mutate({ action: pending.id, name })}
          pending={act.isPending}
        />
      )}
      {dialog === "pay" && (
        <PayDialog
          deal={d}
          onClose={() => setDialog(null)}
          onPaid={async () => {
            await qc.invalidateQueries();
            setDialog(null);
            toast.success(d.payments_mode === "simulated" ? `${inr(d.amount)} in simulated escrow` : `${inr(d.amount)} paid into escrow (test mode)`, {
              description: `${d.creator.name} can post now.`,
            });
          }}
        />
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className="num text-right font-medium">{v}</dd>
    </div>
  );
}

function Sig({ who, at, name }: { who: string; at?: string | null; name?: string }) {
  return (
    <div className={cn("rounded-xl border p-3", at ? "border-success/40 bg-success-soft" : "border-dashed border-line-strong")}>
      <p className="text-xs text-muted">{who}</p>
      {at ? (
        <>
          <p className="font-display text-base italic text-fg">{name ?? who}</p>
          <p className="num text-[11px] text-muted">
            E-signed {shortDate(at)}, {timeOfDay(at)}
          </p>
        </>
      ) : (
        <p className="text-sm text-muted">Not signed yet</p>
      )}
    </div>
  );
}

function CounterDialog({ deal, onClose, onSubmit, pending }: { deal: Deal; onClose: () => void; onSubmit: (amount: number, note: string) => void; pending: boolean }) {
  const fair = deal.fair_total ?? deal.amount;
  const fp = useQuery({
    queryKey: ["fair", deal.creator.id, deal.brand.id],
    queryFn: () => api<FairPrice>(`/creators/${deal.creator.id}/fair-price?lister_id=${deal.brand.id}`),
  });
  const reasons = fp.data ? fp.data.steps.slice(0, 3).map((s) => s.reason) : [];
  const [amount, setAmount] = useState(String(fair));
  const [note, setNote] = useState("");
  const defaultNote = reasons.length ? `My rate is priced on reach, not followers. ${reasons[0]}` : "My rate is priced on reach, not followers.";
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title={`Counter ${deal.brand.name}`} description={`They offered ${inr(deal.amount)} for ${deal.deliverables}.`}>
        <div className="rounded-xl bg-surface-2 p-3 text-sm">
          <p className="flex items-center gap-1.5 font-medium">
            <IndianRupee className="size-4 text-accent" aria-hidden /> Your fair price: {inr(fair)}
          </p>
          <ul className="mt-1.5 space-y-1 text-xs text-fg-2">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-1.5 text-[11px] text-muted">Your note is saved with the counter; the brand sees the new amount.</p>
        </div>
        <div className="mt-4">
          <Label htmlFor="counter-amt">Counter amount (₹)</Label>
          <Input id="counter-amt" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div className="mt-3">
          <Label htmlFor="counter-note">Note</Label>
          <Textarea id="counter-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder={defaultNote} className="min-h-20" />
          <p className="mt-2 text-xs text-muted">If {deal.brand.name} accepts, the contract is e-signed in your name at this amount.</p>
        </div>
        <Button variant="primary" size="lg" className="mt-5 w-full" loading={pending} onClick={() => onSubmit(Number(amount.replace(/[^\d]/g, "")), note || defaultNote)}>
          Send counter
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/** After approval: the brand rates the creator once; the creator can add the post's views. */
function AfterDeal({ deal, role }: { deal: Deal; role: Role }) {
  const qc = useQueryClient();
  const [stars, setStars] = useState(0);
  const [note, setNote] = useState("");
  const [views, setViews] = useState("");
  const refresh = () => void qc.invalidateQueries({ queryKey: ["deal", deal.id, role] });
  const rate = useMutation({
    mutationFn: () => post(`/deals/${deal.id}/rating`, { stars, note: note || null }),
    onSuccess: () => (refresh(), toast.success("Thanks for rating")),
    onError: (e) => toast.error((e as Error).message),
  });
  const report = useMutation({
    mutationFn: () => post(`/deals/${deal.id}/results`, { views: Number(views.replace(/[^\d]/g, "")) }),
    onSuccess: () => (refresh(), toast.success("Views saved", { description: "Shown as self-reported until your connected account confirms them." })),
    onError: (e) => toast.error((e as Error).message),
  });
  return (
    <div className="mt-4 border-t border-line pt-4 text-sm">
      {deal.predicted && (
        <p className="text-xs text-muted">
          Expected when the offer was accepted: about {deal.predicted.views.toLocaleString("en-IN")} views ({deal.predicted.basis}).
        </p>
      )}
      {role === "brand" &&
        (deal.rating ? (
          <p className="mt-2">
            You rated this creator {deal.rating.stars}/5{deal.rating.note ? `: “${deal.rating.note}”` : "."}
          </p>
        ) : (
          <div className="mt-2 space-y-2">
            <p className="font-medium">Rate the creator</p>
            <div role="radiogroup" aria-label="Rating out of 5" className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  role="radio"
                  aria-checked={stars === n}
                  aria-label={`${n} out of 5`}
                  onClick={() => setStars(n)}
                  className="rounded-md p-1 text-accent hover:bg-surface-2"
                >
                  <Star className={stars >= n ? "size-5 fill-current" : "size-5"} aria-hidden />
                </button>
              ))}
            </div>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={280} placeholder="A short note (optional)" aria-label="Note with your rating" className="min-h-16" />
            <Button size="sm" variant="primary" disabled={!stars} loading={rate.isPending} onClick={() => rate.mutate()}>
              Save rating
            </Button>
            <p className="text-xs text-muted">Once per deal. It shows as an average on the creator's public page.</p>
          </div>
        ))}
      {role === "creator" && (
        <div className="mt-2 space-y-2">
          {deal.rating && <p>{deal.brand.name} rated you {deal.rating.stars}/5.</p>}
          <p className="font-medium">How did the post do?</p>
          <div className="flex flex-wrap items-center gap-2">
            <Input value={views} onChange={(e) => setViews(e.target.value)} inputMode="numeric" placeholder={deal.result ? String(deal.result.views) : "Views so far"} aria-label="Views on the post" className="h-9 w-40 text-sm" />
            <Button size="sm" variant="outline" disabled={!views} loading={report.isPending} onClick={() => report.mutate()}>
              Save views
            </Button>
          </div>
          <p className="text-xs text-muted">Shown as self-reported on your case study. A connected account's numbers replace it.</p>
        </div>
      )}
    </div>
  );
}

function PostChecks({ check }: { check: PostCheck }) {
  return (
    <div className="mt-3">
      <p className="text-xs text-muted">
        {check.source === "not_connected"
          ? check.note ?? "Automatic checks need the creator's connected account. The brand reviews the link."
          : `Checked through ${check.source}${check.checked_at ? `, ${shortDate(check.checked_at)} ${timeOfDay(check.checked_at)}` : ""}`}
      </p>
      <ul className="mt-2 space-y-1">
        {check.checks.map((c) => (
          <li key={c.label} className="flex items-start gap-2 text-[13px]">
            {c.status === "passed" ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            ) : c.status === "failed" ? (
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
            ) : (
              <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
            )}
            <span>
              {c.label}
              <span className="text-muted"> · {c.status === "not_checked" ? "not checked" : c.status}</span>
              {c.detail && <span className="block text-xs text-muted">{c.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RevisionDialog({ deal, onClose, onSubmit, pending }: { deal: Deal; onClose: () => void; onSubmit: (note: string) => void; pending: boolean }) {
  const [note, setNote] = useState("");
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="Ask for a revision" description={`${deal.creator.name} sees your note and submits a new link. The fee stays in escrow.`}>
        <Label htmlFor="revision-note">What needs to change?</Label>
        <Textarea id="revision-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} className="min-h-24" placeholder="For example: tag us in the caption and add the paid-partnership label." />
        <Button variant="primary" size="lg" className="mt-5 w-full" disabled={note.trim().length < 3} loading={pending} onClick={() => onSubmit(note.trim())}>
          Send revision request
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function PostDialog({ onClose, onSubmit, pending }: { onClose: () => void; onSubmit: (links: string[], note: string) => void; pending: boolean }) {
  const [links, setLinks] = useState(["https://www.instagram.com/reel/"]);
  const [note, setNote] = useState("");
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="Submit your deliverables" description="The brand reviews them and approves or asks for a revision.">
        <div className="space-y-2">
          {links.map((l, i) => (
            <div key={i}>
              <Label htmlFor={`post-url-${i}`}>{i === 0 ? "Instagram reel or YouTube Short link" : `Link ${i + 1}`}</Label>
              <Input id={`post-url-${i}`} type="url" inputMode="url" value={l} onChange={(e) => setLinks((all) => all.map((x, j) => (j === i ? e.target.value : x)))} />
            </div>
          ))}
        </div>
        {links.length < 5 && (
          <Button variant="ghost" size="sm" className="mt-2" onClick={() => setLinks((all) => [...all, "https://www.instagram.com/"])}>
            Add another link
          </Button>
        )}
        <Label htmlFor="post-note" className="mt-3">
          Note for the brand (optional)
        </Label>
        <Textarea id="post-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} className="min-h-16" />
        <p className="mt-2 text-xs text-muted">The brand has 3 days to review it. If they don't respond, it's approved automatically a few days later.</p>
        <Button variant="primary" size="lg" className="mt-5 w-full" loading={pending} onClick={() => onSubmit(links.map((x) => x.trim()).filter(Boolean), note.trim())}>
          Submit
        </Button>
      </DialogContent>
    </Dialog>
  );
}

const KIND_LABEL: Record<string, string> = { reel: "Reels", story: "Stories", short: "Shorts", carousel: "Carousels", live: "Live sessions", link_in_bio: "Link in bio" };

function termsLine(t: Deal["terms"]) {
  const parts = t.deliverables.map((x) => `${x.count} ${KIND_LABEL[x.kind]?.toLowerCase() ?? x.kind}`);
  return [inr(t.amount), parts.join(" + "), t.post_by ? `post by ${shortDate(t.post_by)}` : null, t.usage_rights_days ? `${t.usage_rights_days} days usage` : null, t.exclusivity_days ? `${t.exclusivity_days} days exclusivity` : null]
    .filter(Boolean)
    .join(" · ");
}

/** Propose changes to any term. The proposal becomes a new contract version. */
function TermsDialog({ deal, onClose, onSubmit, pending }: { deal: Deal; onClose: () => void; onSubmit: (body: Record<string, unknown>) => void; pending: boolean }) {
  const t = deal.terms;
  const count = (k: string) => String(t.deliverables.find((x) => x.kind === k)?.count ?? 0);
  const [amount, setAmount] = useState(String(t.amount));
  const [reels, setReels] = useState(count("reel"));
  const [stories, setStories] = useState(count("story"));
  const [postBy, setPostBy] = useState(t.post_by ?? "");
  const [usage, setUsage] = useState(String(t.usage_rights_days));
  const [excl, setExcl] = useState(String(t.exclusivity_days));
  const [note, setNote] = useState("");
  const n = (x: string) => Number(x.replace(/[^\d]/g, "")) || 0;
  const others = t.deliverables.filter((x) => x.kind !== "reel" && x.kind !== "story");
  const submit = () =>
    onSubmit({
      amount: n(amount),
      deliverables: [...(n(reels) ? [{ kind: "reel", count: n(reels) }] : []), ...(n(stories) ? [{ kind: "story", count: n(stories) }] : []), ...others],
      post_by: postBy || null,
      usage_rights_days: n(usage),
      exclusivity_days: n(excl),
      note: note || null,
    });
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="Propose changes" description={`Now on the table: ${termsLine(t)}. Your proposal becomes a new contract version the other side can accept.`}>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label htmlFor="tp-amount">Fee (₹)</Label>
            <Input id="tp-amount" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tp-reels">Reels</Label>
            <Input id="tp-reels" inputMode="numeric" value={reels} onChange={(e) => setReels(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tp-stories">Stories</Label>
            <Input id="tp-stories" inputMode="numeric" value={stories} onChange={(e) => setStories(e.target.value)} />
          </div>
          <div className="col-span-2">
            <Label htmlFor="tp-postby">Post by</Label>
            <Input id="tp-postby" type="date" value={postBy} onChange={(e) => setPostBy(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tp-usage">Usage rights (days)</Label>
            <Input id="tp-usage" inputMode="numeric" value={usage} onChange={(e) => setUsage(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tp-excl">Exclusivity (days)</Label>
            <Input id="tp-excl" inputMode="numeric" value={excl} onChange={(e) => setExcl(e.target.value)} />
          </div>
          <div className="col-span-2">
            <Label htmlFor="tp-note">Why (optional)</Label>
            <Textarea id="tp-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} className="min-h-16" />
          </div>
        </div>
        <Button variant="primary" size="lg" className="mt-5 w-full" loading={pending} onClick={submit}>
          Send proposal
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/** Every version of the terms, with its hash and who accepted it. */
function Versions({ deal }: { deal: Deal }) {
  const side = (s: string) => (s === "brand" ? deal.brand.name : deal.creator.name);
  return (
    <div className="mt-4 border-t border-line pt-3">
      <p className="text-xs font-semibold text-muted">Contract versions</p>
      <ol className="mt-2 space-y-2">
        {[...deal.versions].reverse().map((v) => (
          <li key={v.number} className="rounded-xl border border-line px-3 py-2 text-xs">
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">Version {v.number}</span>
              {deal.agreed_version === v.number && <Badge size="sm" variant="success">Agreed</Badge>}
              <span className="text-muted">
                by {side(v.author)} · {shortDate(v.at)}, {timeOfDay(v.at)}
              </span>
            </p>
            <p className="mt-1 text-fg-2">{termsLine(v.terms)}</p>
            {v.note && <p className="mt-0.5 text-fg-2">“{v.note}”</p>}
            <p className="mt-1 text-muted">
              Accepted by {v.accepted_by.map((a) => `${side(a.side)} (${shortDate(a.at)})`).join(", ") || "nobody yet"} ·{" "}
              <span className="font-mono" title={v.hash}>
                {v.hash.slice(0, 12)}
              </span>
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** What the creator submitted, round by round, and the revisions asked for. */
function Submissions({ deal }: { deal: Deal }) {
  return (
    <section aria-labelledby="subs" className="card-surface rounded-2xl p-5">
      <h2 id="subs" className="text-sm font-semibold">
        Submissions {deal.revision_round > 0 && <span className="font-normal text-muted">· {deal.revision_round} revision round{deal.revision_round === 1 ? "" : "s"}</span>}
      </h2>
      <ol className="mt-2 space-y-2">
        {deal.submissions.map((s) => (
          <li key={s.round} className="text-[13px]">
            <p className="font-medium">
              Round {s.round} · {shortDate(s.at)}, {timeOfDay(s.at)}
            </p>
            <ul className="mt-0.5 space-y-0.5">
              {s.links.map((l) => (
                <li key={l}>
                  <a href={l} target="_blank" rel="noreferrer" className="break-all text-accent hover:underline">
                    {l}
                  </a>
                </li>
              ))}
            </ul>
            {s.note && <p className="text-fg-2">“{s.note}”</p>}
            {deal.revisions[s.round - 1] && <p className="mt-0.5 text-xs text-warn">Revision asked: {deal.revisions[s.round - 1].reason}</p>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function SignDialog({ deal, role, action, onClose, onSubmit, pending }: { deal: Deal; role: Role; action: DealAction; onClose: () => void; onSubmit: (name: string) => void; pending: boolean }) {
  const [name, setName] = useState(role === "creator" ? deal.creator.name : deal.brand.name);
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title="E-sign the contract" description={`${deal.terms ? termsLine(deal.terms) : `${deal.deliverables} for ${inr(deal.amount)}`}${deal.versions?.length ? ` · version ${deal.versions.length}` : ""}`}>
        <ol className="max-h-48 list-decimal space-y-1 overflow-y-auto rounded-xl bg-surface-2 p-3 pl-7 text-xs leading-relaxed text-fg-2">
          {(deal.contract?.terms ?? []).map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ol>
        <div className="mt-4">
          <Label htmlFor="sig-name">Type your full name to sign</Label>
          <Input id="sig-name" value={name} onChange={(e) => setName(e.target.value)} className="font-display italic" />
        </div>
        <p className="mt-2 text-xs text-muted">Your typed name and the time are recorded with the contract.</p>
        <Button variant="primary" size="lg" className="mt-5 w-full" disabled={name.trim().length < 2} loading={pending} onClick={() => onSubmit(name.trim())}>
          <FileSignature aria-hidden /> {action.label}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

export function PayDialog({
  deal,
  onClose,
  onPaid,
  path,
  amount,
  mode: mode_ = "simulated",
}: {
  deal?: Deal;
  onClose: () => void;
  onPaid: () => void;
  path?: string;
  amount?: number;
  mode?: PaymentsMode;
}) {
  const total = amount ?? deal?.amount ?? 0;
  const [busy, setBusy] = useState(false);
  const mode = deal?.payments_mode ?? mode_;
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        title="Fund escrow"
        description={
          mode === "razorpay-test"
            ? "Razorpay test mode: use a test card or UPI. No real money moves."
            : mode === "simulated"
              ? "Demo mode: this records a simulated payment. No money moves."
              : "Payments aren't connected on this server, so funding isn't possible yet."
        }
      >
        <div className="rounded-2xl border border-line bg-surface-2 p-4 text-center">
          <p className="text-xs text-muted">Pay into DealMeet escrow</p>
          <p className="num mt-1 font-display text-3xl font-semibold">{inr(total)}</p>
          <p className="mt-1 text-xs text-muted">Held until the post is approved{deal?.kind === "collective" ? ", for each member" : ""}.</p>
        </div>
        <Button
          variant="primary"
          size="lg"
          className="mt-5 w-full"
          loading={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await fundEscrow(path ?? `/deals/${deal?.id}/pay`, deal?.listing?.title ?? "Creator collaboration");
              onPaid();
            } catch (e) {
              toast.error((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Lock aria-hidden /> Pay {inr(total)} {mode === "simulated" ? "(simulated)" : "with Razorpay"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
