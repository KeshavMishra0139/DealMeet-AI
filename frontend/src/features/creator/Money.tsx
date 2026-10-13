import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Briefcase,
  Gift,
  Handshake,
  IndianRupee,
  Link2,
  Megaphone,
  Newspaper,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Waterfall } from "@/components/charts/Waterfall";
import { ErrorState, ReferenceNote } from "@/components/shared/Bits";
import { Reveal } from "@/components/motion/Motion";
import { RangeValue } from "@/components/shared/Estimate";
import { EstimateNote, SimulatedChip, WhyPopover } from "@/components/shared/Why";
import { Badge } from "@/components/ui/badge";
import { Segmented, Skeleton } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import { AiReviewNote } from "@/components/shared/AiReview";
import type { FairPrice, Money as MoneyData, MoneyPath } from "@/lib/api-types";
import { inr, inrRange, signedPct } from "@/lib/format";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";
import { StagePill } from "./Home";
import { RateCards } from "./RateCards";
import { useTerms } from "./terms";

const ICONS: Record<string, typeof IndianRupee> = {
  brand: Megaphone,
  affiliate: Link2,
  collective: Users,
  digital: Gift,
  services: Briefcase,
  pr: Newspaper,
  page: Handshake,
};
const EFFORT = { S: "Small effort", M: "Medium effort", L: "Large effort" };

export default function Money() {
  const id = useCreatorId();
  const { t } = useI18n();
  const money = useQuery({ queryKey: ["money", id], queryFn: () => api<MoneyData>(`/creators/${id}/money`) });

  if (money.isError) return <ErrorState error={money.error} onRetry={() => money.refetch()} />;
  if (!money.data) return <PageSkeleton />;
  const m = money.data;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <StagePill stage={m.stage} />
      </div>
      <h1 className="mt-3 font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("money.title")}</h1>
      <p className="mt-1 text-[15px] text-fg-2">Ranked for you. Every range is an estimate, not a promise.</p>
      {m.creator.is_reference && m.creator.reference_note && <ReferenceNote text={m.creator.reference_note} className="mt-2" />}

      <FairPriceCard creatorId={id} initial={m.fair} options={m.brand_options} />

      <RateCards creatorId={id} />

      <Reveal as="section" aria-labelledby="goal" className="mt-8">
        <div className="card-surface flex flex-col gap-3 rounded-[var(--radius-card)] p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 id="goal" className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
              Your goal
            </h2>
            <p className="num mt-1 font-display text-2xl font-semibold">{inr(m.goal.goal)} a month</p>
          </div>
          <div className="sm:text-right">
            <p className="text-xs text-muted">Your top 3 paths together</p>
            <RangeValue estimate={m.goal.top3} className="block" />
            <EstimateNote estimate={m.goal.top3} />
          </div>
        </div>
      </Reveal>

      <Reveal as="section" aria-labelledby="paths" className="mt-8">
        <h2 id="paths" className="mb-3 font-display text-lg font-semibold">
          Ranked paths
        </h2>
        <ol className="space-y-3">
          {m.paths.map((p) => (
            <PathCard key={p.type} path={p} />
          ))}
        </ol>
      </Reveal>
    </div>
  );
}

function FairPriceCard({
  creatorId,
  initial,
  options,
}: {
  creatorId: string;
  initial: FairPrice;
  options: MoneyData["brand_options"];
}) {
  const [lister, setLister] = useState(initial.lister_id ?? options[0]?.id ?? "");
  const words = useTerms();
  const fp = useQuery({
    queryKey: ["fair", creatorId, lister],
    queryFn: () => api<FairPrice>(`/creators/${creatorId}/fair-price?lister_id=${lister}`),
    initialData: lister === initial.lister_id ? initial : undefined,
  });
  const data = fp.data ?? initial;
  const choices = options.slice(0, 2);

  return (
    <Reveal as="section" aria-labelledby="fair" className="card-surface mt-6 overflow-hidden rounded-[28px]">
      <div className="relative p-5 sm:p-7">
        <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-[radial-gradient(circle,rgb(124_58_237/0.28),transparent_65%)] blur-2xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 id="fair" className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
              Your fair rate · per {words.post}
            </h2>
            <p className="num mt-1 font-display text-[40px] font-semibold leading-none tracking-tight sm:text-5xl">
              <span className="text-gradient">{inrRange(data.range.low, data.range.high)}</span>
            </p>
            <p className="mt-2 text-sm text-fg-2">
              For <span className="font-medium text-fg">{data.lister_name ?? "a typical brand in your niche"}</span>. Priced on {words.audience} alone:{" "}
              <span className="num font-medium text-fg">{inr(data.follower_price)}</span>
              {data.uplift_vs_followers && data.uplift_vs_followers > 1.2 && (
                <span className="num"> ({data.uplift_vs_followers.toFixed(1)}x less)</span>
              )}
              .
            </p>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {data.data_label && (
                <span className="inline-flex items-center gap-1.5 text-xs text-fg-2">
                  {data.data_label} <SourceBadge source={data.data_source} />
                </span>
              )}
              <EstimateNote estimate={data.estimate} />
              <WhyPopover why={data.why} subject="Fair rate" />
            </div>
          </div>
          {choices.length > 1 && (
            <div>
              <p className="mb-1.5 text-xs text-muted">Price for a specific brand</p>
              <Segmented
                label="Brand to price for"
                value={lister}
                onChange={setLister}
                size="sm"
                options={choices.map((o) => ({ value: o.id, label: `${o.name} · fit ${o.fit}` }))}
              />
            </div>
          )}
        </div>

        <div className={cn("relative mt-6 transition-opacity", fp.isFetching && "opacity-60")}>
          <Waterfall fp={data} />
        </div>
        <AiReviewNote review={data.ai_review} creatorId={creatorId} className="relative mt-4" />

        {data.model_check && (
          <p className="relative mt-4 text-xs text-muted">
            Cross-check: a gradient-boosted model trained on {data.model_check.trained_on.toLocaleString("en-IN")} synthetic deals
            agrees within {data.model_check.agrees_within_pct}%
            {data.model_check.checked_before_floor ? " (before the production floor)" : ""}. It checks consistency, not
            what the market will pay.
          </p>
        )}
      </div>

      <div className="border-t border-line">
        <h3 className="sr-only">Every step of the price</h3>
        <table className="w-full text-left text-[13px]">
          <thead className="sr-only">
            <tr>
              <th>Step</th>
              <th>Change</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.steps.map((s) => (
              <tr key={s.key} className="align-top">
                <th scope="row" className="w-[34%] px-5 py-3 font-medium text-fg sm:w-[26%] sm:px-7">
                  <span className="flex flex-wrap items-center gap-1.5">
                    {s.label}
                    {s.simulated && <SimulatedChip />}
                    {s.capped && <Badge size="sm" variant="outline">Capped</Badge>}
                  </span>
                </th>
                <td className="num w-[22%] whitespace-nowrap px-2 py-3 font-semibold sm:w-[14%]">
                  {s.key === "base" ? inr(s.amount) : `${s.amount >= 0 ? "+" : "−"}${inr(Math.abs(s.amount))}`}
                  {s.pct !== null && s.key !== "deliverables" && (
                    <span className="block text-[11px] font-normal text-muted">{signedPct(s.pct)}</span>
                  )}
                </td>
                <td className="px-5 py-3 leading-relaxed text-fg-2 sm:px-7">{s.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Reveal>
  );
}

function PathCard({ path }: { path: MoneyPath }) {
  const Icon = ICONS[path.type] ?? IndianRupee;
  const top = path.rank <= 3;
  return (
    <li className={cn("card-surface rounded-[var(--radius-card)] p-4 sm:p-5", top && "ring-1 ring-accent/30")}>
      <div className="flex gap-3.5">
        <span className="num grid size-9 shrink-0 place-items-center rounded-xl bg-surface-2 font-display text-sm font-semibold text-fg-2">
          {path.rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            <div className="min-w-0">
              <h3 className="flex items-center gap-2 font-display text-base font-semibold">
                <Icon className="size-4 shrink-0 text-accent" aria-hidden />
                {path.title}
              </h3>
              <p className="mt-1 text-[13px] leading-relaxed text-fg-2">{path.reasons[0]}</p>
            </div>
            <div className="text-left sm:text-right">
              <RangeValue estimate={path.estimate} size="md" />
              <div>
                <EstimateNote estimate={path.estimate} />
              </div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
            <span className="flex items-center gap-2">
              Fit
              <span className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-3" aria-hidden>
                <span className="block h-full rounded-full bg-signature" style={{ width: `${path.fit_score}%` }} />
              </span>
              <span className="num font-medium text-fg-2">{path.fit_score}</span>
            </span>
            <span>{EFFORT[path.effort]}</span>
            {path.active && <Badge size="sm" variant="success">Earning from this</Badge>}
            <WhyPopover why={path.why} subject={path.title} className="ml-auto" />
          </div>
          <p className="mt-3 flex items-center gap-1.5 text-[13px] text-fg">
            <ArrowRight className="size-3.5 text-accent" aria-hidden /> {path.first_step}
          </p>
        </div>
      </div>
    </li>
  );
}

function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="mt-3 h-9 w-64" />
      <Skeleton className="mt-6 h-[520px] rounded-[28px]" />
    </div>
  );
}

