import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Check, Info, Lock, RefreshCw, Send, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { SafetyNote } from "@/components/shared/SafetyNote";
import { TrustBadge } from "@/components/shared/TrustBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox, Input, Label, Skeleton, Slider, Textarea } from "@/components/ui/form";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, post } from "@/lib/api";
import { count, deliverable, inr, inrRange, pct, shortDate } from "@/lib/format";
import type { BrandMatch, Collective, Listing, Matches } from "@/lib/market-types";
import { useBrandId } from "@/lib/session";
import { cn } from "@/lib/utils";

export default function Campaign() {
  const { id = "" } = useParams();
  const brandId = useBrandId();
  const listing = useQuery({ queryKey: ["listing", id], queryFn: () => api<Listing>(`/listings/${id}`) });
  const matches = useQuery({ queryKey: ["matches", id], queryFn: () => api<Matches>(`/listings/${id}/matches`) });
  const [compare, setCompare] = useState<string[]>([]);
  const [offerTo, setOfferTo] = useState<BrandMatch | null>(null);
  const [tab, setTab] = useState<string>("");

  useEffect(() => {
    if (listing.data && !tab) setTab(listing.data.type === "collective" ? "collective" : "matches");
  }, [listing.data, tab]);

  if (listing.isError) return <ErrorState error={listing.error} onRetry={() => listing.refetch()} />;
  if (!listing.data) return <Skeleton className="h-96 rounded-xl" />;
  const l = listing.data;
  const b = l.budget;
  const toggle = (cid: string) =>
    setCompare((cur) => (cur.includes(cid) ? cur.filter((x) => x !== cid) : cur.length >= 3 ? [...cur.slice(1), cid] : [...cur, cid]));

  return (
    <div>
      <Link to="/brand/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Campaigns
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight">{l.title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-2">{l.summary}</p>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <Badge size="sm" variant={l.type === "collective" ? "accent" : "neutral"}>
              {l.type === "collective" ? `Collective · ${l.collective_size} creators` : l.deal_kind === "affiliate" ? "Affiliate" : "Campaign"}
            </Badge>
            {l.deliverables.map((d) => (
              <Badge key={d.kind} size="sm">
                {deliverable(d)}
              </Badge>
            ))}
            {l.usage_rights_days > 0 && <Badge size="sm">{l.usage_rights_days} days usage</Badge>}
            <Badge size="sm">{l.language_labels.join(", ")}</Badge>
            <Badge size="sm">{l.regions.join(", ")}</Badge>
          </div>
        </div>
        <div className="text-right text-sm">
          <p className="text-xs text-muted">Budget</p>
          <p className="num font-display text-lg font-semibold">
            {b.total ? inr(b.total) : b.per_creator_min !== undefined ? `${inrRange(b.per_creator_min, b.per_creator_max)} each` : b.commission_pct ? `${b.commission_pct}% commission` : "—"}
          </p>
          {l.deadline && <p className="text-xs text-muted">Deadline {shortDate(l.deadline)}</p>}
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList>
          <TabsTrigger value="matches">Matches</TabsTrigger>
          <TabsTrigger value="collective">
            <Users aria-hidden /> Ready-made collectives
          </TabsTrigger>
          <TabsTrigger value="compare" disabled={compare.length < 2}>
            Compare{compare.length ? ` (${compare.length})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="matches" className="pt-4">
          {matches.isError && <ErrorState error={matches.error} onRetry={() => matches.refetch()} />}
          {!matches.data && !matches.isError && <Skeleton className="h-80 rounded-xl" />}
          {matches.data && (
            <>
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm">
                  <span className="font-semibold">{matches.data.summary}</span> <span className="text-fg-2">{matches.data.detail}</span>
                </p>
                <p className="text-xs text-muted">Only creators who chose to be discoverable. Fields they haven't shared stay locked.</p>
              </div>
              <MatchList items={matches.data.items} compare={compare} onToggle={toggle} onOffer={setOfferTo} listingId={l.id} />
            </>
          )}
        </TabsContent>

        <TabsContent value="collective" className="pt-4">
          <CollectivePanel listing={l} />
        </TabsContent>

        <TabsContent value="compare" className="pt-4">
          {matches.data && <ComparePanel items={matches.data.items.filter((m) => compare.includes(m.id))} onOffer={setOfferTo} />}
        </TabsContent>
      </Tabs>

      {offerTo && <OfferDialog match={offerTo} brandId={brandId} listing={l} onClose={() => setOfferTo(null)} />}
    </div>
  );
}

function Locked({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted" title={`${label} not shared by the creator`}>
      <Lock className="size-3" aria-hidden /> Not shared
    </span>
  );
}

function FitBar({ fit }: { fit: number }) {
  return (
    <span className="flex items-center gap-2" aria-label={`Fit ${fit} out of 100`}>
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2" aria-hidden>
        <span className="block h-full rounded-full bg-signature" style={{ width: `${fit}%` }} />
      </span>
      <span className="num text-[13px] font-semibold">{fit}</span>
    </span>
  );
}

function StatusBadge({ m }: { m: BrandMatch }) {
  if (m.deal_stage) return <Badge size="sm" variant="success">{m.deal_stage === "offer" ? "Offer sent" : "In a deal"}</Badge>;
  if (m.application) return <Badge size="sm" variant="accent">{m.application === "opted_in" ? "Opted in" : "Applied"}</Badge>;
  return null;
}

function MatchList({
  items,
  compare,
  onToggle,
  onOffer,
  listingId,
}: {
  items: BrandMatch[];
  compare: string[];
  onToggle: (id: string) => void;
  onOffer: (m: BrandMatch) => void;
  listingId: string;
}) {
  return (
    <ul className="card-surface divide-y divide-line rounded-xl">
      {items.map((m, i) => (
        <li key={m.id} className={cn("grid gap-3 px-4 py-3.5 md:grid-cols-[auto_minmax(0,2.2fr)_minmax(0,1.6fr)_auto] md:items-center", m.trust && m.trust.score < 50 && "bg-danger-soft/40")}>
          <div className="flex items-center gap-3 md:contents">
            <Checkbox checked={compare.includes(m.id)} onCheckedChange={() => onToggle(m.id)} aria-label={`Compare ${m.name}`} />
            <div className="flex min-w-0 items-center gap-3">
              <span className="num w-5 text-xs text-muted">{i + 1}</span>
              <Avatar name={m.name} hue={m.avatar_hue} size={36} generic={m.is_reference} />
              <div className="min-w-0">
                <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                  <Link to={`/brand/creators/${m.id}?listing=${listingId}`} className="hover:text-accent">
                    {m.name}
                  </Link>
                  {m.is_reference && <Badge size="sm" variant="warn">Reference profile</Badge>}
                  <TrustBadge trust={m.trust} />
                  {m.trust && m.trust.score < 50 && <Badge size="sm" variant="danger">Weak trust signals</Badge>}
                  <SafetyNote safety={m.safety} compact />
                  <StatusBadge m={m} />
                </p>
                <p className="truncate text-xs text-muted">
                  @{m.handle} · {m.niche_label} · {m.languages.join(", ")} · {m.location}
                </p>
                <p className="mt-1 hidden text-xs text-fg-2 md:block">{m.reasons.slice(0, 2).join(" · ")}</p>
              </div>
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-3 text-[13px] md:gap-4">
            <div>
              <dt className="text-[11px] text-muted">Fit</dt>
              <dd>
                <FitBar fit={m.fit} />
              </dd>
            </div>
            <div>
              <dt className="text-[11px] text-muted">Median views</dt>
              <dd className="num font-medium">{m.median_views !== null ? count(m.median_views) : <Locked label="Stats" />}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-muted">Fair price</dt>
              <dd className="num font-medium">
                {inr(m.fair.total)}
                {!m.within_budget && <span className="block text-[11px] font-normal text-warn">Above your cap</span>}
              </dd>
            </div>
          </dl>
          <div className="flex items-center gap-2 md:justify-end">
            <Button asChild size="sm" variant="ghost">
              <Link to={`/brand/creators/${m.id}?listing=${listingId}`}>View</Link>
            </Button>
            <Button size="sm" variant={m.deal_stage ? "outline" : "primary"} disabled={!!m.deal_stage} onClick={() => onOffer(m)}>
              <Send aria-hidden /> {m.deal_stage ? "Sent" : "Offer"}
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ComparePanel({ items, onOffer }: { items: BrandMatch[]; onOffer: (m: BrandMatch) => void }) {
  if (items.length < 2) return <p className="text-sm text-muted">Tick two or three creators in Matches to compare them here.</p>;
  const rows: { label: string; get: (m: BrandMatch) => React.ReactNode }[] = [
    { label: "Fit", get: (m) => <FitBar fit={m.fit} /> },
    { label: "Fair price", get: (m) => <span className="num font-semibold">{inr(m.fair.total)}</span> },
    { label: "Median views", get: (m) => (m.median_views !== null ? <span className="num">{count(m.median_views)}</span> : <Locked label="Stats" />) },
    { label: "Saves + shares per view", get: (m) => (m.engagement !== null ? <span className="num">{pct(m.engagement, 1)}</span> : <Locked label="Stats" />) },
    { label: "Trust", get: (m) => <TrustBadge trust={m.trust} /> },
    { label: "Audience", get: (m) => m.audience_stage },
    { label: "Languages", get: (m) => m.languages.join(", ") },
    { label: "Location", get: (m) => m.location },
    { label: "Why they fit", get: (m) => <ul className="space-y-1 text-xs text-fg-2">{m.reasons.map((r) => <li key={r}>{r}</li>)}</ul> },
  ];
  return (
    <div className="card-surface overflow-x-auto rounded-xl">
      <table className="w-full min-w-[560px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="w-40 px-4 py-3 text-xs font-medium text-muted">
              <span className="sr-only">Attribute</span>
            </th>
            {items.map((m) => (
              <th key={m.id} scope="col" className="px-4 py-3">
                <span className="flex items-center gap-2">
                  <Avatar name={m.name} hue={m.avatar_hue} size={28} generic={m.is_reference} />
                  <span className="font-semibold">{m.name}</span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="px-4 py-2.5 text-xs font-medium text-muted">
                {r.label}
              </th>
              {items.map((m) => (
                <td key={m.id} className="px-4 py-2.5 align-top">
                  {r.get(m)}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td />
            {items.map((m) => (
              <td key={m.id} className="px-4 py-3">
                <Button size="sm" variant="primary" disabled={!!m.deal_stage} onClick={() => onOffer(m)}>
                  <Send aria-hidden /> Offer {inr(m.fair.total)}
                </Button>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function CollectivePanel({ listing }: { listing: Listing }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [budget, setBudget] = useState(String(listing.budget.total ?? 80_000));
  const [trustMin, setTrustMin] = useState(60);
  const params = { budget: Number(budget.replace(/[^\d]/g, "")) || undefined, trust_min: trustMin };
  const [applied, setApplied] = useState(params);
  const q = useQuery({
    queryKey: ["collective", listing.id, applied],
    queryFn: () => post<Collective>(`/listings/${listing.id}/collective`, applied),
  });
  const book = useMutation({
    mutationFn: () => post<{ members: number; total: number }>(`/listings/${listing.id}/collective/book`, { member_ids: q.data?.members.map((m) => m.id) ?? [] }),
    onSuccess: async (r) => {
      await qc.invalidateQueries();
      toast.success(`Offer sent to ${r.members} creators`, { description: `One escrow payment of ${inr(r.total)}, split automatically by UPI once posts are verified.` });
      navigate("/brand");
    },
  });
  const c = q.data;

  return (
    <div>
      <div className="card-surface flex flex-wrap items-end gap-4 rounded-xl p-4">
        <div className="w-40">
          <Label htmlFor="cb-budget">Total budget (₹)</Label>
          <Input id="cb-budget" inputMode="numeric" value={budget} onChange={(e) => setBudget(e.target.value)} className="h-9 text-sm" />
        </div>
        <div className="w-56">
          <Label htmlFor="cb-trust">Minimum Trust Score: {trustMin}</Label>
          <Slider id="cb-trust" min={30} max={90} step={5} value={[trustMin]} onValueChange={([v]) => setTrustMin(v)} thumbLabel="Minimum Trust Score" />
        </div>
        <Button size="sm" variant="outline" onClick={() => setApplied(params)} loading={q.isFetching}>
          {!q.isFetching && <RefreshCw aria-hidden />} Rebuild
        </Button>
        <p className="ml-auto max-w-xs text-xs text-muted">
          Greedy pack on reach per rupee, with audience overlap removed. Low-trust profiles are left out automatically.
        </p>
      </div>

      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {!c && !q.isError && <Skeleton className="mt-4 h-80 rounded-xl" />}
      {c && (
        <>
          <p className="mt-4 text-sm font-semibold">{c.summary}</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              ["Creators", String(c.size)],
              ["Combined reach", count(c.combined_reach)],
              ["Total price", inr(c.total)],
              ["Saves + shares per view", pct(c.avg_engagement, 1)],
              ["Cost per 1,000 views", c.cost_per_1k ? inr(c.cost_per_1k) : "—"],
            ].map(([k, v]) => (
              <div key={k} className="card-surface rounded-xl px-3.5 py-3">
                <dt className="text-[11px] text-muted">{k}</dt>
                <dd className="num mt-0.5 font-display text-lg font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          {c.notes.length > 0 && (
            <ul className="mt-3 space-y-1">
              {c.notes.map((n) => (
                <li key={n} className="flex items-start gap-1.5 text-xs text-fg-2">
                  <Info className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden /> {n}
                </li>
              ))}
            </ul>
          )}

          <div className="card-surface mt-4 overflow-x-auto rounded-xl">
            <table className="w-full min-w-[640px] text-left text-[13px]">
              <thead className="border-b border-line bg-surface-2 text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Creator</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Reach</th>
                  <th scope="col" className="px-3 py-2 font-medium">Overlap</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Price</th>
                  <th scope="col" className="w-40 px-4 py-2 font-medium">Split</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {c.members.map((m) => (
                  <tr key={m.id}>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-2.5">
                        <Avatar name={m.name} hue={m.avatar_hue} size={26} generic={m.is_reference} />
                        <span className="min-w-0">
                          <span className="flex items-center gap-1.5 font-medium">
                            {m.name}
                            <TrustBadge trust={m.trust} />
                            {m.opted_in && <Badge size="sm" variant="accent">Opted in</Badge>}
                          </span>
                          <span className="block text-xs text-muted">
                            {m.language} · {m.city}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="num px-3 py-2 text-right">
                      {count(m.effective_reach)}
                      {m.effective_reach < m.reach && <span className="block text-[11px] text-muted">of {count(m.reach)}</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">{m.overlap >= 0.15 && m.overlap_with ? `${Math.round(m.overlap * 100)}% with ${m.overlap_with}` : "Low"}</td>
                    <td className="num px-3 py-2 text-right font-medium">{inr(m.price)}</td>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-2">
                        <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                          <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(2, m.split * 100 * 2.5)}%` }} />
                        </span>
                        <span className="num w-11 text-right text-xs">{pct(m.split, 1)}</span>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {c.excluded.length > 0 && (
            <Popover>
              <PopoverTrigger className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted underline decoration-dotted underline-offset-4 hover:text-fg">
                <AlertTriangle className="size-3.5" aria-hidden /> {c.excluded.length} left out and why
              </PopoverTrigger>
              <PopoverContent className="w-96">
                <ul className="max-h-72 space-y-2 overflow-y-auto">
                  {c.excluded.map((e) => (
                    <li key={e.id} className="text-[13px]">
                      <span className="font-medium">{e.name}</span>
                      <span className="block text-xs text-muted">{e.reason}</span>
                    </li>
                  ))}
                </ul>
              </PopoverContent>
            </Popover>
          )}

          <div className="sticky bottom-0 mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface/95 p-3 backdrop-blur">
            <p className="text-sm">
              <span className="font-semibold">One offer, one escrow payment of {inr(c.total)}.</span>{" "}
              <span className="text-fg-2">Payouts split automatically by UPI after each post is verified.</span>
            </p>
            <Button variant="primary" onClick={() => book.mutate()} loading={book.isPending} disabled={c.size < 2}>
              {!book.isPending && <Check aria-hidden />} Book this collective
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

export function OfferDialog({
  match,
  brandId,
  listing,
  onClose,
}: {
  match: Pick<BrandMatch, "id" | "name" | "fair">;
  brandId: string;
  listing?: { id: string; title: string } | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState(String(match.fair.total));
  const [message, setMessage] = useState("");
  const n = Number(amount.replace(/[^\d]/g, "")) || 0;
  const below = 1 - n / match.fair.total;
  const send = useMutation({
    mutationFn: () => post("/offers", { brand_id: brandId, creator_id: match.id, listing_id: listing?.id ?? null, amount: n, message: message || null }),
    onSuccess: async () => {
      await qc.invalidateQueries();
      toast.success(`Offer sent to ${match.name}`, { description: `${inr(n)} for ${match.fair.deliverables}. Funds go to escrow once they accept.` });
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent title={`Offer to ${match.name}`} description={listing ? listing.title : "Direct offer"}>
        <div className="rounded-xl bg-surface-2 p-3 text-sm">
          Fair price for {match.fair.deliverables}: <span className="num font-semibold">{inr(match.fair.total)}</span>
          <span className="block text-xs text-muted">Range {inrRange(match.fair.range.low, match.fair.range.high)}, priced on their reach and fit with your brand.</span>
        </div>
        <div className="mt-4">
          <Label htmlFor="offer-amt">Your offer (₹)</Label>
          <Input id="offer-amt" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
          {below >= 0.3 && (
            <p className="mt-2 flex items-start gap-1.5 text-xs text-warn">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              This is {Math.round(below * 100)}% below their fair price. The creator will see that, and low offers are usually countered.
            </p>
          )}
        </div>
        <div className="mt-4">
          <Label htmlFor="offer-msg">Message (optional)</Label>
          <Textarea id="offer-msg" value={message} onChange={(e) => setMessage(e.target.value)} className="min-h-20" placeholder="What you'd love them to make" />
        </div>
        <Button variant="primary" className="mt-5 w-full" onClick={() => send.mutate()} loading={send.isPending} disabled={n < 500}>
          {!send.isPending && <Send aria-hidden />} Send offer
        </Button>
      </DialogContent>
    </Dialog>
  );
}
