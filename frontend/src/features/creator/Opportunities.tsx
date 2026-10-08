import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, CalendarDays, Check, EyeOff, Lock, Plus, Search, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Avatar, EmptyState, ErrorState } from "@/components/shared/Bits";
import { Reveal } from "@/components/motion/Motion";
import { RangeValue } from "@/components/shared/Estimate";
import { ScopePicker } from "@/components/shared/ScopePicker";
import { EstimateNote, WhyPopover } from "@/components/shared/Why";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Skeleton, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { useI18n } from "@/i18n";
import { api, post } from "@/lib/api";
import { deliverable, shortDate } from "@/lib/format";
import type { ListingType, Opportunities as OppData, Opportunity, Scopes } from "@/lib/market-types";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";

const FILTERS: { value: "all" | ListingType; label: string }[] = [
  { value: "all", label: "All" },
  { value: "brand_campaign", label: "Brand campaigns" },
  { value: "collective", label: "Collectives" },
  { value: "pr_service", label: "PR services" },
  { value: "page", label: "Pages" },
  { value: "creator_collab", label: "Creator collabs" },
];

export default function Opportunities() {
  const id = useCreatorId();
  const { t } = useI18n();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["value"]>("all");
  const [q, setQ] = useState("");
  const [applyTo, setApplyTo] = useState<Opportunity | null>(null);
  const [postOpen, setPostOpen] = useState(false);
  const data = useQuery({ queryKey: ["opps", id], queryFn: () => api<OppData>(`/creators/${id}/opportunities`) });

  const items = useMemo(() => {
    const all = data.data?.items ?? [];
    return all.filter(
      (o) =>
        (filter === "all" || o.type === filter) &&
        (!q || `${o.title} ${o.summary} ${o.lister.name}`.toLowerCase().includes(q.toLowerCase())),
    );
  }, [data.data, filter, q]);

  if (data.isError) return <ErrorState error={data.error} onRetry={() => data.refetch()} />;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("opps.title")}</h1>
          <p className="mt-1 text-[15px] text-fg-2">Matched to your audience. You choose what each lister can see.</p>
        </div>
        <Button variant="outline" onClick={() => setPostOpen(true)}>
          <Plus aria-hidden /> Post a collab
        </Button>
      </div>

      <div className="sticky top-14 z-10 -mx-4 mt-5 bg-[var(--bg)]/80 px-4 py-2 backdrop-blur-xl sm:-mx-6 sm:px-6 lg:top-0 lg:mx-0 lg:px-0">
        <div role="radiogroup" aria-label="Filter by type" className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 scrollbar-none">
          {FILTERS.map((f) => {
            const n = f.value === "all" ? data.data?.items.length : data.data?.counts[f.value];
            const on = filter === f.value;
            return (
              <button
                key={f.value}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setFilter(f.value)}
                className={cn(
                  "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-[13px] font-medium transition-colors",
                  on ? "border-transparent bg-accent text-accent-fg" : "border-line-strong text-fg-2 hover:text-fg",
                )}
              >
                {f.label}
                {n !== undefined && <span className={cn("num text-[11px]", on ? "opacity-80" : "text-muted")}>{n ?? 0}</span>}
              </button>
            );
          })}
        </div>
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search brands, pages and collabs" aria-label="Search opportunities" className="h-10 pl-9 text-sm" />
        </div>
      </div>

      <div className="mt-4 space-y-3" aria-live="polite">
        {data.isLoading && Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-40 rounded-[var(--radius-card)]" />)}
        {data.data && items.length === 0 && (
          <div className="card-surface rounded-[var(--radius-card)]">
            <EmptyState icon={<Search className="size-5" />} title="Nothing matches that filter" body="Try another type, or clear the search. New listings arrive every week." />
          </div>
        )}
        {items.map((o, i) => (
          <Reveal key={o.id} delay={Math.min(i, 6) * 0.05}>
            <OppCard o={o} onApply={() => setApplyTo(o)} />
          </Reveal>
        ))}
      </div>

      {data.data && data.data.hidden.length > 0 && (
        <Popover>
          <PopoverTrigger className="mt-6 inline-flex items-center gap-2 text-xs text-muted underline decoration-dotted underline-offset-4 hover:text-fg">
            <EyeOff className="size-3.5" aria-hidden />
            {data.data.hidden.length} listings hidden: flagged as spam or duplicates
          </PopoverTrigger>
          <PopoverContent>
            <p className="font-display text-sm font-semibold">Hidden to protect you</p>
            <ul className="mt-2 space-y-2.5">
              {data.data.hidden.map((h) => (
                <li key={h.id} className="text-[13px]">
                  <p className="font-medium">{h.title}</p>
                  <p className="text-xs text-muted">{h.reasons.join(" · ")}</p>
                </li>
              ))}
            </ul>
          </PopoverContent>
        </Popover>
      )}

      {applyTo && <ApplyDialog o={applyTo} creatorId={id} onClose={() => setApplyTo(null)} />}
      <PostCollabDialog open={postOpen} onOpenChange={setPostOpen} creatorId={id} />
    </div>
  );
}

function OppCard({ o, onApply }: { o: Opportunity; onApply: () => void }) {
  const done = o.application === "applied" || o.application === "opted_in" || o.applied;
  const cta = o.type === "collective" ? "Opt in" : o.type === "creator_collab" ? "Ask to collab" : "Apply";
  const deliv = o.deliverables?.map(deliverable);
  return (
    <article className="card-surface rounded-[var(--radius-card)] p-4 sm:p-5" aria-labelledby={`${o.id}-t`}>
      <div className="flex items-start gap-3">
        <Avatar name={o.lister.name} hue={o.lister.hue} size={40} className="rounded-xl" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span className="inline-flex items-center gap-1 font-medium text-fg-2">
              {o.lister.name}
              {o.lister.verified && <BadgeCheck className="size-3.5 text-accent" aria-label="Verified" />}
            </span>
            <span aria-hidden>·</span>
            <span>{o.type_label}</span>
            {o.deadline && (
              <>
                <span aria-hidden>·</span>
                <span className="inline-flex items-center gap-1">
                  <CalendarDays className="size-3" aria-hidden /> Apply by {shortDate(o.deadline)}
                </span>
              </>
            )}
          </div>
          <h2 id={`${o.id}-t`} className="mt-1 font-display text-[17px] font-semibold leading-snug">
            {o.title}
          </h2>
          <p className="mt-1 text-[14px] leading-relaxed text-fg-2">{o.summary}</p>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {deliv?.map((d) => (
              <Badge key={d} size="sm">
                {d}
              </Badge>
            ))}
            {o.usage_rights_days > 0 && <Badge size="sm">{o.usage_rights_days} days usage</Badge>}
            {o.collective_size && (
              <Badge size="sm" variant="accent">
                <Users aria-hidden /> {o.collective_size}-creator pack
              </Badge>
            )}
          </div>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <FitPill fit={o.fit} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3 border-t border-line pt-3.5">
        <div>
          {o.value.estimate ? (
            <>
              <p className="text-[11px] text-muted">{o.value.kind === "affiliate" ? "Estimated" : o.value.kind === "collective" ? "Your share" : "You'd earn"}</p>
              <RangeValue estimate={o.value.estimate} size="md" />
              <div>
                <EstimateNote estimate={o.value.estimate} />
              </div>
              {o.value.budget_below_fair && <p className="mt-1 text-xs text-warn">Budget is below your fair price. You can counter.</p>}
            </>
          ) : (
            <p className="text-sm text-fg-2">Unpaid collab: shared reach and new followers</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="sm:hidden">
            <FitPill fit={o.fit} />
          </span>
          <WhyPopover why={o.why} subject={o.title} />
          {done ? (
            <Badge variant="success" className="h-9 px-3">
              <Check aria-hidden /> {o.application === "opted_in" ? "Opted in" : "Applied"}
            </Badge>
          ) : (
            <Button variant="primary" size="sm" className="h-9" onClick={onApply}>
              {cta}
            </Button>
          )}
        </div>
      </div>
    </article>
  );
}

export function FitPill({ fit }: { fit: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-1 text-xs" title="How well your audience fits this listing">
      <span className="text-muted">Fit</span>
      <span className="num font-semibold text-fg">{fit}</span>
    </span>
  );
}

function ApplyDialog({ o, creatorId, onClose }: { o: Opportunity; creatorId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [scopes, setScopes] = useState<Scopes>({ ...o.scopes, stats: true });
  const [message, setMessage] = useState("");
  const apply = useMutation({
    mutationFn: () => post<{ status: string }>(`/creators/${creatorId}/apply`, { listing_id: o.id, scopes, message: message || null }),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ["opps", creatorId] });
      await qc.invalidateQueries({ queryKey: ["home", creatorId] });
      await qc.invalidateQueries({ queryKey: ["privacy", creatorId] });
      toast.success(r.status === "opted_in" ? `You're in the ${o.lister.name} collective pool` : `Applied to ${o.lister.name}`, {
        description: "Track it in Deals. Change what they see any time in Privacy.",
      });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent sheet title={o.type === "collective" ? `Opt in to ${o.lister.name}` : `Apply to ${o.lister.name}`} description={o.title}>
        <p className="mb-2 flex items-center gap-1.5 text-sm font-medium">
          <Lock className="size-4 text-accent" aria-hidden /> Choose what {o.lister.name} can see
        </p>
        <ScopePicker value={scopes} onChange={setScopes} />
        <p className="mt-2 text-xs text-muted">Revoke any time from Privacy. Every view is logged in your consent ledger.</p>
        <div className="mt-4">
          <Label htmlFor="apply-msg">Note to the lister (optional)</Label>
          <Textarea id="apply-msg" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="One line on why you'd be a good fit" className="min-h-20" />
        </div>
        {apply.isError && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {(apply.error as Error).message}
          </p>
        )}
        <Button variant="primary" size="lg" className="mt-5 w-full" loading={apply.isPending} onClick={() => apply.mutate()}>
          {o.type === "collective" ? "Opt in and share" : "Apply and share"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function PostCollabDialog({ open, onOpenChange, creatorId }: { open: boolean; onOpenChange: (v: boolean) => void; creatorId: string }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const create = useMutation({
    mutationFn: () => post(`/creators/${creatorId}/collabs`, { title, summary }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["opps"] });
      toast.success("Your collab is live", { description: "Matched creators will see it in their opportunities." });
      setTitle("");
      setSummary("");
      onOpenChange(false);
    },
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent sheet title="Post a creator collab" description="Find another creator to make something with.">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="space-y-4"
        >
          <div>
            <Label htmlFor="cc-title">What are you looking for?</Label>
            <Input id="cc-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="For example, a Hindi voiceover partner" required minLength={4} />
          </div>
          <div>
            <Label htmlFor="cc-sum">Details</Label>
            <Textarea id="cc-sum" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What you'll make together and how you'll share it" required minLength={10} />
          </div>
          <Button type="submit" variant="primary" size="lg" className="w-full" loading={create.isPending}>
            Post collab
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
