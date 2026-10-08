import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BellRing, Check, ChevronRight, FileText, Handshake, Plus, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, EmptyState, ErrorState, SectionTitle } from "@/components/shared/Bits";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton } from "@/components/ui/form";
import { Dialog, DialogContent } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import type { DealRow } from "@/lib/deal-types";
import { STAGE_LABEL } from "@/lib/deal-types";
import { inr, shortDate } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";

interface DealsData {
  deals: DealRow[];
  invoices: { id: string; number: string; to: string; amount: number; issued: string; due: string; status: string; days_late: number; reminders: { at: string }[] }[];
}

export default function Deals() {
  const id = useCreatorId();
  const { t } = useI18n();
  const qc = useQueryClient();
  const [logOpen, setLogOpen] = useState(false);
  const q = useQuery({ queryKey: ["deals", id], queryFn: () => api<DealsData>(`/creators/${id}/deals`), refetchInterval: 4000 });
  const inv = useMutation({
    mutationFn: ({ invoice, action }: { invoice: string; action: "remind" | "mark_paid" }) => post(`/invoices/${invoice}`, { action }),
    onSuccess: (_, v) => {
      qc.invalidateQueries();
      toast.success(v.action === "remind" ? "Reminder sent with the invoice attached" : "Marked as paid");
    },
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-[var(--radius-card)]" />;
  const offers = q.data.deals.filter((d) => d.stage === "offer");
  const active = q.data.deals.filter((d) => ["contract", "escrow_funded", "live", "verified"].includes(d.stage));
  const done = q.data.deals.filter((d) => d.stage === "paid" || d.stage === "declined");

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("deals.title")}</h1>
          <p className="mt-1 text-[15px] text-fg-2">Every rupee is held in escrow before you post, and paid by UPI once it's verified.</p>
        </div>
        <Button variant="outline" onClick={() => setLogOpen(true)}>
          <Plus aria-hidden /> Log an outside deal
        </Button>
      </div>

      <Group title="Offers" eyebrow="Decide" rows={offers} empty="No open offers. Matched opportunities are on the Offers tab." />
      <Group title="In progress" eyebrow="On the rail" rows={active} empty="Nothing in progress right now." />

      {q.data.invoices.length > 0 && (
        <section aria-labelledby="inv" className="mt-8">
          <SectionTitle id="inv" eyebrow="Outside JodiDar" title="Invoices you're chasing" />
          <ul className="space-y-2">
            {q.data.invoices.map((i) => (
              <li key={i.id} className="card-surface flex flex-wrap items-center gap-3 rounded-2xl p-4">
                <FileText className={cn("size-5 shrink-0", i.days_late ? "text-warn" : "text-muted")} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {inr(i.amount)} from {i.to}
                  </p>
                  <p className="text-xs text-muted">
                    {i.number} · due {shortDate(i.due)}
                    {i.status === "paid" ? " · paid" : i.days_late ? ` · ${i.days_late} days late` : ""}
                    {i.reminders.length > 0 && ` · ${i.reminders.length} reminder${i.reminders.length > 1 ? "s" : ""} sent`}
                  </p>
                </div>
                <Button asChild size="sm" variant="ghost">
                  <a href={`/api/invoices/${i.id}.pdf`} target="_blank" rel="noreferrer">
                    PDF
                  </a>
                </Button>
                {i.status !== "paid" && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => inv.mutate({ invoice: i.id, action: "remind" })}>
                      <BellRing aria-hidden /> Remind
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => inv.mutate({ invoice: i.id, action: "mark_paid" })}>
                      <Check aria-hidden /> Paid
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <Group title="Finished" eyebrow="History" rows={done} empty="Paid deals and their invoices show up here." />
      <LogDealDialog open={logOpen} onOpenChange={setLogOpen} creatorId={id} />
    </div>
  );
}

function Group({ title, eyebrow, rows, empty }: { title: string; eyebrow: string; rows: DealRow[]; empty: string }) {
  return (
    <section className="mt-8" aria-label={title}>
      <SectionTitle eyebrow={eyebrow} title={title} />
      {rows.length === 0 ? (
        <div className="card-surface rounded-2xl">
          <EmptyState icon={<Handshake className="size-5" />} title={`No ${title.toLowerCase()}`} body={empty} className="py-6" />
        </div>
      ) : (
        <ul className="space-y-2">
          {rows.map((d) => (
            <li key={d.id}>
              <Link to={`/creator/deals/${d.id}`} className="card-surface group flex items-center gap-3 rounded-2xl p-4 transition-colors hover:border-accent/50">
                <Avatar name={d.brand.name} hue={d.brand.hue} size={40} className="rounded-xl" />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-1.5 font-medium">
                    {d.brand.name}
                    {d.kind === "collective" && (
                      <Badge size="sm" variant="accent">
                        <Users aria-hidden /> Collective
                      </Badge>
                    )}
                    {!d.brand.verified && <Badge size="sm" variant="warn">Unverified</Badge>}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {d.listing?.title ?? "Direct booking"} · {d.deliverables}
                  </p>
                  {d.alerts.map((a) => (
                    <p key={a.text} className={cn("mt-1 flex items-center gap-1 text-xs", a.kind === "low_offer" ? "text-warn" : "text-fg-2")}>
                      {a.kind === "low_offer" && <AlertTriangle className="size-3.5" aria-hidden />} {a.text}
                    </p>
                  ))}
                  {d.counter && !d.counter.accepted_at && !d.counter.declined_at && <p className="mt-1 text-xs text-accent">You countered at {inr(d.counter.amount)}</p>}
                </div>
                <div className="text-right">
                  <p className="num font-semibold">{inr(d.amount)}</p>
                  <Badge size="sm" variant={d.stage === "paid" ? "success" : d.stage === "declined" ? "neutral" : d.actions.length ? "accent" : "outline"}>
                    {d.actions.length && d.stage !== "paid" ? "Your move" : STAGE_LABEL[d.stage]}
                  </Badge>
                </div>
                <ChevronRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LogDealDialog({ open, onOpenChange, creatorId }: { open: boolean; onOpenChange: (v: boolean) => void; creatorId: string }) {
  const qc = useQueryClient();
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [days, setDays] = useState("7");
  const create = useMutation({
    mutationFn: () => post(`/creators/${creatorId}/invoices`, { to, amount: Number(amount.replace(/[^\d]/g, "")), due_days: Number(days) || 7 }),
    onSuccess: () => {
      qc.invalidateQueries();
      toast.success("Invoice created", { description: "We'll nudge you if it's paid late." });
      onOpenChange(false);
      setTo("");
      setAmount("");
    },
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent sheet title="Log a deal made outside JodiDar" description="We'll make the invoice and remind you when payment is late.">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <div>
            <Label htmlFor="ld-to">Brand</Label>
            <Input id="ld-to" value={to} onChange={(e) => setTo(e.target.value)} required minLength={2} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ld-amt">Amount (₹)</Label>
              <Input id="ld-amt" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="ld-days">Due in (days)</Label>
              <Input id="ld-days" type="number" min={0} max={90} value={days} onChange={(e) => setDays(e.target.value)} />
            </div>
          </div>
          <Button type="submit" variant="primary" size="lg" className="w-full" loading={create.isPending}>
            Create invoice
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
