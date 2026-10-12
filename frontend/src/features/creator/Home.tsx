import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CalendarClock, Clock, FileWarning, Handshake, IndianRupee, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { ErrorState, ReferenceNote, ScoreRing } from "@/components/shared/Bits";
import { RangeValue } from "@/components/shared/Estimate";
import { TrustBadge } from "@/components/shared/TrustBadge";
import { WhyPopover } from "@/components/shared/Why";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { useI18n, useTr } from "@/i18n";
import { api, post } from "@/lib/api";
import type { Durable, Home as HomeData, Pipeline, Plan, RateGap, Stage } from "@/lib/api-types";
import { count, inr, inrRange, inrShort, shortDate } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import { Goals } from "./Goals";
import { cn } from "@/lib/utils";
import { CountUp, Reveal, Stagger, StaggerItem, TiltCard } from "@/components/motion/Motion";
import { MoveCard } from "./MoveCard";
import { ReachCard } from "./ReachCard";

export function useHome(id: string) {
  return useQuery({ queryKey: ["home", id], queryFn: () => api<HomeData>(`/creators/${id}/home`) });
}

export default function Home() {
  const id = useCreatorId();
  const { t } = useI18n();
  const tr = useTr();
  const home = useHome(id);
  const qc = useQueryClient();
  const next = useMutation({
    mutationFn: () => post<Plan>(`/creators/${id}/plan/next`),
    onSuccess: async (plan) => {
      await qc.invalidateQueries({ queryKey: ["home", id] });
      toast.success(t("home.planned", { n: plan.week }), { description: plan.changes[0] });
    },
  });

  if (home.isError) return <ErrorState error={home.error} onRetry={() => home.refetch()} />;
  if (!home.data) return <HomeSkeleton />;
  const { creator, stage, plan, durable, rate_gap, pipeline, context } = home.data;

  return (
    <div>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted">
        <span className="inline-flex items-center gap-1.5">
          <CalendarClock className="size-4" aria-hidden /> {t("home.weekOf", { date: shortDate(plan.week_start) })}
          {plan.week > 1 && <span className="text-fg-2">· {t("home.planN", { n: plan.week })}</span>}
        </span>
        <StagePill stage={stage} />
      </header>
      <h1 className="mt-3 font-display text-[28px] font-semibold leading-tight tracking-tight sm:text-[34px]">
        {t("home.greeting")}
      </h1>
      {creator.reference_note && <ReferenceNote text={tr(creator.reference_note)} className="mt-2" />}

      {plan.changes.length > 0 && plan.week > 1 && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 rounded-2xl border border-line bg-surface p-3.5 text-sm text-fg-2"
        >
          <p className="font-medium text-fg">{t("home.changed")}</p>
          <ul className="mt-1 space-y-0.5">
            {plan.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </motion.div>
      )}

      <section aria-labelledby="moves" className="mt-6">
        <div className="mb-3 flex items-end justify-between gap-3">
          <h2 id="moves" className="font-display text-lg font-semibold">
            {t("home.moves")}
          </h2>
          <Button
            variant={plan.done_count > 0 ? "secondary" : "ghost"}
            size="sm"
            onClick={() => next.mutate()}
            loading={next.isPending}
          >
            {!next.isPending && <Wand2 aria-hidden />} {t("home.nextWeek")}
          </Button>
        </div>
        <MovesCarousel label={t("home.carousel")}>
          {plan.moves.map((m, i) => (
            <TiltCard key={m.id} className="h-full rounded-[26px]" max={5}>
              <MoveCard move={m} creatorId={id} index={i} />
            </TiltCard>
          ))}
        </MovesCarousel>
      </section>

      <Goals creatorId={id} />

      {context.has_reels && (
        <Reveal className="mt-8">
          <ReachCard context={context} />
        </Reveal>
      )}

      <section aria-label={t("home.glance")} className={context.has_reels ? "mt-3" : "mt-8"}>
        <Stagger className="grid items-start gap-3 md:grid-cols-3">
          <StaggerItem>
            <DurableCard durable={durable} label={t("home.durable")} />
          </StaggerItem>
          <StaggerItem>
            <RateGapCard gap={rate_gap} label={t("home.rateGap")} />
          </StaggerItem>
          <StaggerItem>
            <PipelineCard pipeline={pipeline} label={t("home.pipeline")} />
          </StaggerItem>
        </Stagger>
      </section>

      <p className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span>{t("home.context")}:</span>
        <span className="num">{t("home.followers", { n: count(context.followers) })}</span>
        {context.has_reels && (
          <>
            <span aria-hidden>·</span>
            <span className="num">{t("home.medianViews", { n: count(context.median_views) })}</span>
          </>
        )}
        {context.trust && (
          <>
            <span aria-hidden>·</span>
            <TrustBadge trust={context.trust} />
          </>
        )}
      </p>
    </div>
  );
}

export function StagePill({ stage }: { stage: Stage }) {
  const { pick } = useI18n();
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line bg-surface py-0.5 pl-2.5 pr-1 text-xs font-medium text-fg-2">
      {pick(stage.label, stage.hi?.label)}
      <WhyPopover why={stage.why} label="" subject={`Stage: ${stage.label}`} className="px-1 no-underline" />
    </span>
  );
}

function MovesCarousel({ children, label }: { children: React.ReactNode[]; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => {
      const w = el.firstElementChild?.getBoundingClientRect().width ?? 1;
      setActive(Math.round(el.scrollLeft / (w + 12)));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <div>
      <div
        ref={ref}
        role="region"
        aria-label={label}
        tabIndex={0}
        className="-mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 scrollbar-none sm:-mx-6 sm:px-6 lg:mx-0 lg:grid lg:grid-cols-3 lg:overflow-visible lg:px-0"
      >
        {children.map((child, i) => (
          <div key={i} className="w-[86%] shrink-0 snap-center sm:w-[60%] lg:w-auto">
            {child}
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-center gap-1.5 lg:hidden" aria-hidden>
        {children.map((_, i) => (
          <span key={i} className={cn("h-1.5 rounded-full transition-all", i === active ? "w-5 bg-accent" : "w-1.5 bg-surface-3")} />
        ))}
      </div>
    </div>
  );
}

function CardShell({ title, why, children, className }: { title: string; why?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("card-surface flex flex-col rounded-[var(--radius-card)] p-5", className)}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{title}</h2>
        {why}
      </div>
      {children}
    </section>
  );
}

function DurableCard({ durable, label }: { durable: Durable; label: string }) {
  const { t, pick } = useI18n();
  const tr = useTr();
  return (
    <CardShell title={label} why={<WhyPopover why={durable.why} subject={label} />}>
      <div className="mt-3 flex items-center gap-4">
        {durable.score !== null ? (
          <ScoreRing value={durable.score} size={96} stroke={9} sublabel={t("durable.of100")} />
        ) : (
          <div className="grid size-24 shrink-0 place-items-center rounded-full border-[9px] border-surface-3 text-center text-[11px] leading-tight text-muted">
            {t("durable.notScored")}
          </div>
        )}
        <div className="min-w-0">
          <p className="font-display text-base font-semibold">{tr(durable.headline)}</p>
          {durable.warning ? (
            <p className="mt-1 flex gap-1.5 text-[13px] leading-snug text-warn">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {pick(durable.warning, durable.warning_hi)}
            </p>
          ) : (
            <p className="mt-1 text-[13px] leading-snug text-fg-2">
              {durable.state === "no_income" ? t("durable.firstSets") : t("durable.spread")}
            </p>
          )}
        </div>
      </div>
      {durable.next_stream && (
        <div className="mt-4 rounded-2xl bg-surface-2 p-3">
          <p className="text-xs text-muted">{durable.state === "no_income" ? t("durable.firstStream") : t("durable.nextStream")}</p>
          <p className="mt-0.5 text-sm font-semibold">{durable.next_stream.title}</p>
          <RangeValue estimate={durable.next_stream.estimate} size="md" className="mt-0.5 block" />
        </div>
      )}
    </CardShell>
  );
}

function RateGapCard({ gap, label }: { gap: RateGap; label: string }) {
  const { t, pick } = useI18n();
  const max = Math.max(gap.fair.high, gap.current ?? 0, gap.follower_price);
  const bar = (v: number) => `${Math.max(4, (v / max) * 100)}%`;
  return (
    <CardShell title={label} why={<WhyPopover why={gap.why} subject={label} />}>
      <p className="mt-3 text-xs text-muted">
        {t("rate.fairPerReel")}
        {gap.brand ? ` · ${t("rate.forBrand", { brand: gap.brand })}` : ""}
      </p>
      <p className="num font-display text-[28px] font-semibold leading-tight tracking-tight">{inrRange(gap.fair.low, gap.fair.high)}</p>
      <dl className="mt-3 space-y-2.5 text-[13px]">
        <div className="grid grid-cols-[1fr_auto] gap-y-1">
          <dt className="text-fg-2">{t("rate.typical")}</dt>
          <dd className="num font-medium">{gap.current ? inr(gap.current) : t("rate.notSet")}</dd>
          <dd className="col-span-2 h-1.5 rounded-full bg-surface-3" aria-hidden>
            {gap.current && <div className="h-full rounded-full bg-[var(--chart-muted)]" style={{ width: bar(gap.current) }} />}
          </dd>
        </div>
        <div className="grid grid-cols-[1fr_auto] gap-y-1">
          <dt className="text-fg-2">{t("rate.fairOnReach")}</dt>
          <dd className="num font-medium">
            <CountUp value={gap.per_reel} format={inr} />
          </dd>
          <dd className="col-span-2 h-1.5 rounded-full bg-surface-3" aria-hidden>
            <div className="h-full rounded-full bg-signature" style={{ width: bar(gap.per_reel) }} />
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-[13px] text-fg-2">{pick(gap.line, gap.line_hi)}</p>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mt-auto self-start pt-2">
        <Link to="/creator/money">
          {t("rate.breakdown")} <ArrowRight aria-hidden />
        </Link>
      </Button>
    </CardShell>
  );
}

const ALERT_ICON = { low_offer: IndianRupee, verify_late: Clock, invoice_late: FileWarning };

function PipelineCard({ pipeline, label }: { pipeline: Pipeline; label: string }) {
  const { t, pick } = useI18n();
  const stats = [
    { label: t("pipe.offers"), value: String(pipeline.offers.length) },
    { label: t("pipe.active"), value: String(pipeline.active.length) },
    { label: t("pipe.awaiting"), value: pipeline.awaiting_total ? inrShort(pipeline.awaiting_total) : "₹0" },
  ];
  return (
    <CardShell title={label}>
      <dl className="mt-3 grid grid-cols-3 gap-2">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl bg-surface-2 px-2.5 py-2">
            <dt className="text-[11px] text-muted">{s.label}</dt>
            <dd className="num mt-0.5 font-display text-lg font-semibold">{s.value}</dd>
          </div>
        ))}
      </dl>
      {pipeline.alerts.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {pipeline.alerts.map((a) => {
            const Icon = ALERT_ICON[a.kind];
            return (
              <li key={a.text} className="flex gap-2.5 rounded-xl border border-line p-2.5">
                <Icon className={cn("mt-0.5 size-4 shrink-0", a.kind === "low_offer" ? "text-warn" : "text-muted")} aria-hidden />
                <div className="min-w-0">
                  <p className="text-[13px] font-medium leading-snug">{pick(a.text, a.hi?.text)}</p>
                  <p className="mt-0.5 text-xs leading-snug text-muted">{pick(a.detail, a.hi?.detail)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : pipeline.offers.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {pipeline.offers.map((o) => (
            <li key={o.id} className="flex items-center gap-2.5 rounded-xl border border-line p-2.5">
              <Handshake className="size-4 shrink-0 text-success" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium leading-snug">
                  {t("pipe.offered", { brand: o.brand, amount: inr(o.amount) })}
                </p>
                {o.fair_total !== undefined && (
                  <p className="mt-0.5 text-xs text-muted">
                    {o.amount >= o.fair_total ? t("pipe.atFair") : t("pipe.fairIs", { amount: inr(o.fair_total) })}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 flex items-center gap-2 text-[13px] text-muted">
          <Handshake className="size-4" aria-hidden /> {t("pipe.none")}
        </p>
      )}
      <Button asChild variant="ghost" size="sm" className="-ml-2 mt-auto self-start pt-2">
        <Link to={pipeline.alerts.length || pipeline.offers.length ? "/creator/deals" : "/creator/opportunities"}>
          {pipeline.alerts.length || pipeline.offers.length ? t("pipe.openDeals") : t("pipe.seeOpps")} <ArrowRight aria-hidden />
        </Link>
      </Button>
    </CardShell>
  );
}

function HomeSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading your plan">
      <Skeleton className="h-5 w-48" />
      <Skeleton className="mt-3 h-9 w-72" />
      <div className="mt-6 flex gap-3 overflow-hidden lg:grid lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-[360px] w-[86%] shrink-0 rounded-[26px] lg:w-auto" />
        ))}
      </div>
      <div className="mt-8 grid gap-3 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-56 rounded-[var(--radius-card)]" />
        ))}
      </div>
    </div>
  );
}

