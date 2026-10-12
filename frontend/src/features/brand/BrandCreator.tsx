import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, BarChart3, Heart, IndianRupee, Lock, Send, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Waterfall } from "@/components/charts/Waterfall";
import { Avatar, ErrorState, ReferenceNote } from "@/components/shared/Bits";
import { SafetyNote } from "@/components/shared/SafetyNote";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { TrustBadge } from "@/components/shared/TrustBadge";
import { SimulatedChip } from "@/components/shared/Why";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import type { FairPrice, PriceStep } from "@/lib/api-types";
import { count, inr, inrRange, pct, shortDate } from "@/lib/format";
import type { Safety, Scopes } from "@/lib/market-types";
import { useBrandId } from "@/lib/session";
import type { Provenance } from "@/lib/types";
import { OfferDialog } from "./Campaign";

interface CreatorView {
  id: string;
  name: string;
  handle: string;
  avatar_hue: number;
  is_reference: boolean;
  reference_note: string | null;
  bio: string;
  niche_label: string;
  languages: string[];
  location: string | null;
  audience_stage: string;
  trust: { score: number; level: "high" | "medium" | "low"; reasons: string[]; method: string } | null;
  safety?: Safety;
  scopes: Scopes;
  scope_source: string;
  scope_labels: Record<keyof Scopes, string>;
  fit: { score: number; reasons: string[]; cautions: string[] } | null;
  fair: { range: { low: number; high: number }; total: number; deliverables: string; steps: PriceStep[] | null; follower_price: number | null; model_check?: FairPrice["model_check"] };
  stats: {
    followers: number;
    median_views: number;
    reach_ratio: number;
    saves_shares_per_view: number;
    posts_per_week: number;
    recent: { date: string; views: number; topic: string | null }[];
    provenance: { views: Provenance; saves: Provenance; topic: Provenance };
  } | null;
  demographics: { age: Record<string, number>; gender: Record<string, number>; cities: { name: string; share: number }[]; languages: Record<string, number>; provenance: Provenance } | null;
  rate_card: { typical: number | null; provenance: Provenance } | null;
  listing: { id: string; title: string } | null;
  fan_proof: { label: string; links: string[]; platforms: string[] } | null;
  deal: { stage: string } | null;
}

export default function BrandCreator() {
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const listingId = params.get("listing");
  const brandId = useBrandId();
  const [offer, setOffer] = useState(false);
  const q = useQuery({
    queryKey: ["brand-creator", brandId, id, listingId],
    queryFn: () => api<CreatorView>(`/brands/${brandId}/creators/${id}${listingId ? `?listing_id=${listingId}` : ""}`),
  });
  const ask = useMutation({
    mutationFn: (scopes: string[]) => post(`/brands/${brandId}/creators/${id}/request-access`, { scopes }),
    onSuccess: () => toast.success("Request sent", { description: "The creator decides. You'll see the data here if they allow it." }),
  });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className="h-96 rounded-xl" />;
  const c = q.data;
  const fp = { steps: c.fair.steps ?? [], total: c.fair.total, base: c.fair.steps?.[0]?.amount ?? 0 };

  const LockedCard = ({ scope, icon: Icon }: { scope: keyof Scopes; icon: typeof Lock }) => (
    <div className="card-surface flex flex-col items-start gap-2 rounded-xl p-4">
      <p className="flex items-center gap-1.5 text-sm font-semibold">
        <Icon className="size-4 text-muted" aria-hidden /> {c.scope_labels[scope]}
      </p>
      <p className="flex items-center gap-1.5 text-xs text-muted">
        <Lock className="size-3.5" aria-hidden /> {c.name} hasn't shared this with you.
      </p>
      <Button size="sm" variant="outline" onClick={() => ask.mutate([scope])} loading={ask.isPending && ask.variables?.[0] === scope}>
        Request access
      </Button>
    </div>
  );

  return (
    <div>
      <Link to={listingId ? `/brand/campaigns/${listingId}` : "/brand"} className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
        <ArrowLeft className="size-3.5" aria-hidden /> {c.listing ? c.listing.title : "Overview"}
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <Avatar name={c.name} hue={c.avatar_hue} size={52} generic={c.is_reference} />
          <div>
            <h1 className="flex flex-wrap items-center gap-2 font-display text-2xl font-semibold tracking-tight">
              {c.name} <TrustBadge trust={c.trust} />
              <SafetyNote safety={c.safety} />
            </h1>
            <p className="text-sm text-muted">
              @{c.handle} · {c.niche_label} · {c.languages.join(", ")} · {c.location} · {c.audience_stage} followers
            </p>
            {c.fan_proof && (
              <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-fg-2">
                <Heart className="size-3.5 text-accent" aria-hidden /> {c.fan_proof.label} of your brand
                <SourceBadge source={`${c.fan_proof.platforms[0]}_api`} />
              </p>
            )}
          </div>
        </div>
        <Button variant="primary" onClick={() => setOffer(true)} disabled={!!c.deal}>
          <Send aria-hidden /> {c.deal ? "Offer sent" : "Send offer"}
        </Button>
      </div>
      {c.reference_note && <ReferenceNote text={c.reference_note} className="mt-3" />}

      <div className="mt-4 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-muted">You can see:</span>
        {(Object.keys(c.scope_labels) as (keyof Scopes)[]).map((k) => (
          <Badge key={k} size="sm" variant={c.scopes[k] ? "success" : "outline"}>
            {!c.scopes[k] && <Lock aria-hidden />} {c.scope_labels[k]}
          </Badge>
        ))}
        <span className="text-muted">· {c.scope_source === "grant" ? "Chosen for your brand" : "Creator's defaults"}</span>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="fp" className="card-surface rounded-xl p-5">
          <h2 id="fp" className="text-xs font-medium text-muted">
            Fair price for your brand · {c.fair.deliverables}
          </h2>
          <p className="num mt-1 font-display text-3xl font-semibold">{inrRange(c.fair.range.low, c.fair.range.high)}</p>
          <p className="mt-1 text-xs text-muted">
            Priced on reach and fit with your audience.
            {c.fair.follower_price != null && ` Follower-count pricing would say ${inr(c.fair.follower_price)}.`}
          </p>
          {c.fair.steps ? (
            <div className="mt-4">
              <Waterfall fp={fp} />
            </div>
          ) : (
            <p className="mt-4 flex items-center gap-1.5 text-xs text-muted">
              <Lock className="size-3.5" aria-hidden /> The breakdown uses stats this creator hasn't shared with you.
            </p>
          )}
          {c.fit && (
            <div className="mt-4 border-t border-line pt-3">
              <p className="text-xs font-medium text-muted">Fit {c.fit.score}/100 for this campaign</p>
              <ul className="mt-1.5 space-y-1 text-[13px] text-fg-2">
                {c.fit.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
                {c.fit.cautions.map((r) => (
                  <li key={r} className="text-warn">
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <div className="space-y-3">
          {c.stats ? (
            <section aria-labelledby="st" className="card-surface rounded-xl p-4">
              <h2 id="st" className="flex items-center gap-1.5 text-sm font-semibold">
                <BarChart3 className="size-4 text-muted" aria-hidden /> Reach and engagement
              </h2>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-[13px]">
                {[
                  ["Followers", count(c.stats.followers), null],
                  ["Median views, last 6", count(c.stats.median_views), c.stats.provenance.views],
                  ["Reach vs followers", `${c.stats.reach_ratio}x`, c.stats.provenance.views],
                  ["Saves + shares per view", pct(c.stats.saves_shares_per_view, 1), c.stats.provenance.saves],
                ].map(([k, v, p]) => (
                  <div key={k as string}>
                    <dt className="text-[11px] text-muted">{k}</dt>
                    <dd className="num flex items-center gap-1.5 font-semibold">
                      {v} {p === "simulated" && <SimulatedChip />}
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 flex items-center gap-1.5 border-t border-line pt-3 text-[11px] text-muted">
                Last 6 reels {c.stats.provenance.topic === "simulated" && <>· format labels <SimulatedChip /></>}
              </p>
              <ul className="mt-1.5 space-y-1 text-xs">
                {c.stats.recent.map((r) => (
                  <li key={r.date} className="flex justify-between gap-2">
                    <span className="text-muted">
                      {shortDate(r.date)} · {r.topic}
                    </span>
                    <span className="num font-medium">{count(r.views)}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <LockedCard scope="stats" icon={BarChart3} />
          )}

          {c.demographics ? (
            <section aria-labelledby="dm" className="card-surface rounded-xl p-4">
              <h2 id="dm" className="flex items-center gap-1.5 text-sm font-semibold">
                <Users className="size-4 text-muted" aria-hidden /> Audience {c.demographics.provenance === "simulated" && <SimulatedChip />}
              </h2>
              <ul className="mt-3 space-y-1.5 text-[13px]">
                {Object.entries(c.demographics.age).map(([k, v]) => (
                  <li key={k} className="grid grid-cols-[52px_1fr_40px] items-center gap-2">
                    <span className="text-muted">{k}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface-2" aria-hidden>
                      <span className="block h-full rounded-full bg-accent" style={{ width: `${v * 100}%` }} />
                    </span>
                    <span className="num text-right">{pct(v)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">Top cities: {c.demographics.cities.slice(0, 4).map((x) => `${x.name} ${pct(x.share)}`).join(", ")}</p>
            </section>
          ) : (
            <LockedCard scope="demographics" icon={Users} />
          )}

          {c.rate_card ? (
            <section className="card-surface rounded-xl p-4">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold">
                <IndianRupee className="size-4 text-muted" aria-hidden /> Rate card {c.rate_card.provenance === "simulated" && <SimulatedChip />}
              </h2>
              <p className="num mt-2 text-lg font-semibold">{c.rate_card.typical ? `${inr(c.rate_card.typical)} a reel` : "No rate set yet"}</p>
              <p className="text-xs text-muted">What they usually quote. The fair price above is our independent estimate.</p>
            </section>
          ) : (
            <LockedCard scope="rate_card" icon={IndianRupee} />
          )}
        </div>
      </div>

      {offer && <OfferDialog match={{ id: c.id, name: c.name, fair: { ...c.fair, per_reel: c.fair.total } }} brandId={brandId} listing={c.listing} onClose={() => setOffer(false)} />}
    </div>
  );
}
