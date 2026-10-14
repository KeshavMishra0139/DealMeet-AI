import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Check, Info, Lock, RefreshCw, Send, Star, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { useReducedMotion } from "framer-motion";
import { Stagger, StaggerItem } from "@/components/motion/Motion";
import { hasWebGL, Stage3D } from "@/components/three/Stage3D";
import { MatchMap3D } from "@/components/three/lazy";
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
import type { BrandMatch, Collective, Listing, Matches, RankCriterion } from "@/lib/market-types";
import { useMediaQuery } from "@/lib/hooks";
import { useBrandId } from "@/lib/session";
import { cn } from "@/lib/utils";
import { ApplicationsPanel, CampaignControls, HistoryPanel } from "./CampaignManage";
import { ComparePanel, RankWhy, ShortlistPanel, ShortlistToggle } from "./Shortlist";
import { useLoadWipe, DetailSkeleton } from "@/components/shared/Skeletons";

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

  const ready = useLoadWipe(!!listing.data);
  if (listing.isError) return <ErrorState error={listing.error} onRetry={() => listing.refetch()} />;
  if (!listing.data || !ready) return <DetailSkeleton label="Loading campaign" />;
  const l = listing.data;
  const b = l.budget;

  return (
    <div>
      <Link to="/brand/campaigns" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> Campaigns
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight">{l.title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-2">{l.summary}</p>
          <CampaignControls listing={l} />
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
            {l.exclusivity_days > 0 && <Badge size="sm">{l.exclusivity_days} days exclusivity</Badge>}
            <Badge size="sm">{l.language_labels.join(", ")}</Badge>
            <Badge size="sm">{l.regions.join(", ")}</Badge>
            {l.objective_labels?.map((o) => (
              <Badge key={o} size="sm" variant="accent">
                {o}
              </Badge>
            ))}
            {l.audience && l.audience.ages.length > 0 && <Badge size="sm">Ages {l.audience.ages.join(", ")}</Badge>}
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
          <TabsTrigger value="shortlist">
            <Star aria-hidden /> Shortlist
          </TabsTrigger>
          <TabsTrigger value="compare" disabled={compare.length < 2}>
            Compare{compare.length ? ` (${compare.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="applications">Applications</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* Kept mounted while another tab is open: unmounting the 3D match space mid-update made
            React Three Fiber attach its pointer listeners to a removed element. */}
        <TabsContent value="matches" forceMount className="pt-4 data-[state=inactive]:hidden">
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
              <MatchSpace items={matches.data.items} listingId={l.id} />
              <MatchList items={matches.data.items} criteria={matches.data.criteria} onOffer={setOfferTo} listingId={l.id} />
            </>
          )}
        </TabsContent>

        <TabsContent value="collective" className="pt-4">
          <CollectivePanel listing={l} />
        </TabsContent>

        <TabsContent value="applications" className="pt-4">
          <ApplicationsPanel listing={l} />
        </TabsContent>

        <TabsContent value="history" className="pt-4">
          <HistoryPanel listing={l} />
        </TabsContent>

        <TabsContent value="shortlist" className="pt-4">
          <ShortlistPanel listing={l} criteria={matches.data?.criteria} selected={compare} onSelect={setCompare} onCompare={() => setTab("compare")} />
        </TabsContent>

        <TabsContent value="compare" className="pt-4">
          <ComparePanel listing={l} ids={compare} />
        </TabsContent>
      </Tabs>

      {offerTo && <OfferDialog match={offerTo} brandId={brandId} listing={l} onClose={() => setOfferTo(null)} />}
    </div>
  );
}

/** Matched creators in 3D: fit, reach and trust at a glance. The list below carries the same data. */
function MatchSpace({ items, listingId }: { items: BrandMatch[]; listingId: string }) {
  const navigate = useNavigate();
  const reduce = useReducedMotion();
  const wide = useMediaQuery("(min-width: 768px)");
  const mouse = useMediaQuery("(pointer: fine)");
  const [webgl] = useState(() => hasWebGL());
  if (!wide || !webgl || items.length < 2) return null;
  const points = items.map((m) => ({
    id: m.id,
    name: m.name,
    fit: m.fit,
    medianViews: m.median_views,
    trust: m.trust?.score ?? null,
    fair: m.fair.total,
    fairLabel: inr(m.fair.total),
    viewsLabel: m.median_views !== null ? count(m.median_views) : null,
  }));
  return (
    <section aria-labelledby="space" className="card-surface relative mb-3 overflow-hidden rounded-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 id="space" className="text-sm font-semibold">
          Match space <span className="font-normal text-muted">· price, reach and trust in 3D · up and left is more reach per rupee</span>
        </h2>
        <p className="text-xs text-muted">{mouse ? "Drag to turn · hover for details · click to open a profile" : "Tap a creator in the list to open a profile"}</p>
      </div>
      <div className="relative bg-[radial-gradient(ellipse_at_center,rgb(124_58_237/0.07),transparent_70%)]">
        <Stage3D
          className="h-[380px]"
          label={`3D map of ${items.length} matched creators by fair price, reach and trust, coloured by audience fit. The list below has the same creators and numbers.`}
        >
          {(active, onScreen) => (
            <MatchMap3D
              points={points}
              onOpen={(cid) => navigate(`/brand/creators/${cid}?listing=${listingId}`)}
              active={active}
              onScreen={onScreen}
              still={!!reduce}
              interactive={mouse && !reduce}
            />
          )}
        </Stage3D>
        <ul className="pointer-events-none absolute bottom-3 left-4 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-fg-2">
          <li className="flex items-center gap-1.5">
            <span className="h-2 w-8 rounded-full bg-signature" aria-hidden /> Colour and size: lower to higher fit
          </li>
          <li className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border border-[#9CA3AF]" aria-hidden /> Weak trust or stats not shared
          </li>
        </ul>
      </div>
    </section>
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
  criteria,
  onOffer,
  listingId,
}: {
  items: BrandMatch[];
  criteria?: RankCriterion[];
  onOffer: (m: BrandMatch) => void;
  listingId: string;
}) {
  return (
    <Stagger as="ul" gap={0.04} className="card-surface divide-y divide-line rounded-xl">
      {items.map((m, i) => (
        <StaggerItem
          as="li"
          key={m.id}
          className={cn("grid gap-3 px-4 py-3.5 md:grid-cols-[minmax(0,1fr)_minmax(0,17rem)_auto] md:items-center", m.trust && m.trust.score < 50 && "bg-danger-soft/40")}
        >
          {/* min-w-0 lets long handles and reasons wrap or truncate instead of pushing the columns over. */}
          <div className="flex min-w-0 items-center gap-3">
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
                <RankWhy m={m} criteria={criteria} />
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
            <ShortlistToggle listingId={listingId} creatorId={m.id} name={m.name} on={!!m.shortlisted} />
            <Button asChild size="sm" variant="ghost">
              <Link to={`/brand/creators/${m.id}?listing=${listingId}`}>View</Link>
            </Button>
            <Button size="sm" variant={m.deal_stage ? "outline" : "primary"} disabled={!!m.deal_stage} onClick={() => onOffer(m)}>
              <Send aria-hidden /> {m.deal_stage ? "Sent" : "Offer"}
            </Button>
          </div>
        </StaggerItem>
      ))}
    </Stagger>
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
  // The brand's adjustments before sending: fee and reel/story counts per member, and who's in.
  const [edits, setEdits] = useState<Record<string, { price?: string; reels?: string; stories?: string; out?: boolean }>>({});
  const edit = (id: string, k: "price" | "reels" | "stories" | "out", v: string | boolean) => setEdits((e) => ({ ...e, [id]: { ...e[id], [k]: v } }));
  const num = (v: string | undefined) => (v === undefined ? undefined : Number(v.replace(/[^\d]/g, "")) || 0);
  const c = q.data;
  const chosen = (c?.members ?? []).filter((m) => !edits[m.id]?.out);
  const feeOf = (m: { id: string; price: number }) => num(edits[m.id]?.price) ?? m.price;
  const total = chosen.reduce((a, m) => a + feeOf(m), 0);
  const book = useMutation({
    mutationFn: () => {
      const adjust: Record<string, { price?: number; deliverables?: { kind: string; count: number }[] }> = {};
      for (const m of chosen) {
        const e = edits[m.id];
        if (!e) continue;
        const base = Object.fromEntries(m.deliverables.map((d) => [d.kind, d.count]));
        const reels = num(e.reels) ?? base.reel ?? 0;
        const stories = num(e.stories) ?? base.story ?? 0;
        adjust[m.id] = {
          ...(e.price !== undefined ? { price: feeOf(m) } : {}),
          ...(e.reels !== undefined || e.stories !== undefined
            ? { deliverables: [...(reels ? [{ kind: "reel", count: reels }] : []), ...(stories ? [{ kind: "story", count: stories }] : []), ...m.deliverables.filter((d) => d.kind !== "reel" && d.kind !== "story")] }
            : {}),
        };
      }
      return post<{ id: string; members: number; total: number }>(`/listings/${listing.id}/collective/book`, { member_ids: chosen.map((m) => m.id), combined_reach: c?.combined_reach ?? null, adjust });
    },
    onSuccess: async (r) => {
      await qc.invalidateQueries();
      toast.success(`Sent to ${r.members} creators`, { description: `Each confirms their own terms. You fund ${inr(r.total)} once everyone has.` });
      navigate(`/brand/collectives/${r.id}`);
    },
    onError: (e) => toast.error((e as Error).message),
  });

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
              ["Combined reach", c.combined_reach != null ? count(c.combined_reach) : "—"],
              ["Total price", inr(c.total)],
              ["Saves + shares per view", c.avg_engagement != null ? pct(c.avg_engagement, 1) : "—"],
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

          <details className="card-surface mt-3 rounded-xl px-4 py-3 text-xs text-fg-2">
            <summary className="cursor-pointer text-sm font-medium text-fg">How the builder picks</summary>
            <p className="mt-2">{c.method.objective}</p>
            <p className="mt-1">Effective reach: {c.method.effective_reach}</p>
            <p className="mt-1">Overlap: {c.method.overlap}</p>
            <ul className="mt-1 list-disc pl-5">
              {c.method.thresholds.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
            <p className="mt-1">{c.method.privacy}</p>
          </details>

          <div className="card-surface mt-4 overflow-x-auto rounded-xl">
            <table className="w-full min-w-[760px] text-left text-[13px]">
              <thead className="border-b border-line bg-surface-2 text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Creator</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Reach</th>
                  <th scope="col" className="px-3 py-2 font-medium">Overlap</th>
                  <th scope="col" className="px-3 py-2 font-medium">Deliverables</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Fee</th>
                  <th scope="col" className="w-40 px-4 py-2 font-medium">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {c.members.map((m) => (
                  <tr key={m.id} className={edits[m.id]?.out ? "opacity-50" : undefined}>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-2.5">
                        <Checkbox checked={!edits[m.id]?.out} onCheckedChange={(v) => edit(m.id, "out", !v)} aria-label={`Include ${m.name}`} />
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
                          <Popover>
                            <PopoverTrigger className="text-[11px] text-muted underline decoration-dotted underline-offset-4 hover:text-fg">Why picked</PopoverTrigger>
                            <PopoverContent className="w-80">
                              <ul className="list-disc space-y-1 pl-4 text-xs text-fg-2">
                                {m.why.map((w) => (
                                  <li key={w}>{w}</li>
                                ))}
                              </ul>
                            </PopoverContent>
                          </Popover>
                        </span>
                      </span>
                    </td>
                    <td className="num px-3 py-2 text-right">
                      {m.effective_reach != null && m.reach != null ? (
                        <>
                          {count(m.effective_reach)}
                          {m.effective_reach < m.reach && <span className="block text-[11px] text-muted">of {count(m.reach)}</span>}
                        </>
                      ) : (
                        <span className="text-xs text-muted">
                          Not shared
                          <span className="block text-[11px]">{m.audience_stage}</span>
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">
                      {m.overlap_level === "High" && m.overlap_with
                        ? m.overlap != null
                          ? `${Math.round(m.overlap * 100)}% with ${m.overlap_with}`
                          : `High with ${m.overlap_with}`
                        : "Low"}
                    </td>
                    <td className="px-3 py-2">
                      <span className="flex items-center gap-1 text-xs">
                        <Input
                          value={edits[m.id]?.reels ?? String(m.deliverables.find((d) => d.kind === "reel")?.count ?? 0)}
                          onChange={(e) => edit(m.id, "reels", e.target.value)}
                          inputMode="numeric"
                          aria-label={`Reels from ${m.name}`}
                          className="h-8 w-11 px-2 text-center text-xs"
                        />
                        reels
                        <Input
                          value={edits[m.id]?.stories ?? String(m.deliverables.find((d) => d.kind === "story")?.count ?? 0)}
                          onChange={(e) => edit(m.id, "stories", e.target.value)}
                          inputMode="numeric"
                          aria-label={`Stories from ${m.name}`}
                          className="h-8 w-11 px-2 text-center text-xs"
                        />
                        stories
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Input
                        value={edits[m.id]?.price ?? String(m.price)}
                        onChange={(e) => edit(m.id, "price", e.target.value)}
                        inputMode="numeric"
                        aria-label={`Fee for ${m.name}`}
                        className="num ml-auto h-8 w-24 px-2 text-right text-xs"
                      />
                      {edits[m.id]?.price !== undefined && <span className="block text-[11px] text-muted">fair {inr(m.price)}</span>}
                    </td>
                    <td className="px-4 py-2">
                      {!edits[m.id]?.out && total > 0 && (
                        <span className="flex items-center gap-2">
                          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                            <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.max(2, (feeOf(m) / total) * 100 * 2.5)}%` }} />
                          </span>
                          <span className="num w-11 text-right text-xs">{pct(feeOf(m) / total, 1)}</span>
                        </span>
                      )}
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
              <span className="font-semibold">
                {chosen.length} creators, {inr(total)} in all.
              </span>{" "}
              <span className="text-fg-2">Each confirms their own terms; you fund once, after everyone has.</span>
            </p>
            <Button variant="primary" onClick={() => book.mutate()} loading={book.isPending} disabled={chosen.length < 2}>
              {!book.isPending && <Check aria-hidden />} Send to {chosen.length} creators
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
      toast.success(`Offer sent to ${match.name}`, { description: `${inr(n)} for ${match.fair.deliverables}. Once they accept, sign and fund escrow before they post.` });
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
