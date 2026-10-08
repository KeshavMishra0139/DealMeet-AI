import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  IndianRupee,
  LayoutGrid,
  Play,
  Radio,
  RotateCcw,
  Smartphone,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { PHONE_OUTER, PhoneFrame, useFitScale, useMediaQuery } from "@/components/demo/Frames";
import { useFrameMessages } from "@/components/demo/PhoneMode";
import { Avatar, ErrorState, Kbd, ReferenceNote } from "@/components/shared/Bits";
import { RangeValue } from "@/components/shared/Estimate";
import { TrustBadge } from "@/components/shared/TrustBadge";
import { EstimateNote, WhyPopover } from "@/components/shared/Why";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Segmented, Skeleton } from "@/components/ui/form";
import { FitPill } from "@/features/creator/Opportunities";
import { api, post } from "@/lib/api";
import type { Compare as CompareData, CompareSide, GuideStep, GuideStepId } from "@/lib/demo-types";
import { count, inr, inrRange } from "@/lib/format";
import { framePath, isTypingTarget, postToFrame, setPhoneMode, usePhoneMode } from "@/lib/phone";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const SECTIONS: { id: GuideStepId; title: string; eyebrow: string }[] = [
  { id: "who", eyebrow: "Profiles", title: "Who they are" },
  { id: "stage", eyebrow: "Stage", title: "Where they are now" },
  { id: "price", eyebrow: "Fair-Price AI", title: "What a brand reel is worth" },
  { id: "roadmap", eyebrow: "Growth roadmap", title: "What to post and learn" },
  { id: "money", eyebrow: "Monetisation", title: "Top 3 money paths" },
  { id: "opportunities", eyebrow: "Marketplace", title: "Matched opportunities" },
  { id: "moves", eyebrow: "Next-Step Engine", title: "Their next 3 moves" },
];

const CATEGORY = { money: { label: "Money", icon: IndianRupee }, growth: { label: "Growth", icon: TrendingUp }, opportunity: { label: "Opportunity", icon: Sparkles } };

export default function Compare() {
  useTheme("creator");
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const phones = usePhoneMode();
  const reduce = useReducedMotion();
  const q = useQuery({ queryKey: ["compare"], queryFn: () => api<CompareData>("/demo/compare") });
  const initialStep = params.get("guide") === "1" ? Math.max(0, Number(params.get("step") ?? 1) - 1) : null;
  const [step, setStep] = useState<number | null>(initialStep);
  const [resetting, setResetting] = useState(false);
  const frameA = useRef<HTMLIFrameElement>(null);
  const frameB = useRef<HTMLIFrameElement>(null);
  const guide = q.data?.guide ?? [];
  // P pressed inside one of the phones comes back here.
  useFrameMessages((msg) => msg.type === "jd:toggle-phone" && setPhoneMode(false));
  const active = step !== null ? guide[step] : undefined;

  const go = useCallback(
    (next: number | null) => {
      setStep(next);
      const p = new URLSearchParams(params);
      if (next === null) {
        p.delete("guide");
        p.delete("step");
      } else {
        p.set("guide", "1");
        p.set("step", String(next + 1));
      }
      setParams(p, { replace: true });
    },
    [params, setParams],
  );

  // Move focus of attention: scroll the section in, and steer both phones to the matching screen.
  useEffect(() => {
    if (!active) return;
    if (phones) {
      postToFrame(frameA.current, { type: "jd:navigate", to: active.route });
      postToFrame(frameB.current, { type: "jd:navigate", to: active.route });
    } else {
      document.getElementById(`sec-${active.id}`)?.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    }
  }, [active, phones, reduce]);

  useEffect(() => {
    if (step === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e) || e.defaultPrevented) return;
      if (e.key === "ArrowRight") go(Math.min(guide.length - 1, step + 1));
      else if (e.key === "ArrowLeft") go(Math.max(0, step - 1));
      else if (e.key === "Escape") go(null);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, guide.length, go]);

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <a href="#main" className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to content
      </a>
      <header className="relative z-10 border-b border-line">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link to="/" className="rounded-lg" aria-label="JodiDar AI home">
            <Wordmark />
          </Link>
          <nav aria-label="Demo" className="flex flex-wrap items-center gap-1.5">
            <Button asChild variant="ghost" size="sm">
              <Link to="/demo/live">
                <Radio aria-hidden /> Live deal demo
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              loading={resetting}
              onClick={async () => {
                setResetting(true);
                await post("/demo/reset");
                await qc.invalidateQueries();
                setResetting(false);
              }}
            >
              {!resetting && <RotateCcw aria-hidden />} Reset demo
            </Button>
          </nav>
        </div>
      </header>

      <main id="main" className={cn("relative z-10 mx-auto max-w-[1240px] px-4 pt-6 sm:px-6 sm:pt-10", step !== null ? "pb-72 sm:pb-56" : "pb-16")}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Demo · same engine, two creators</p>
            <h1 className="mt-2 font-display text-[30px] font-semibold leading-tight tracking-tight sm:text-[40px]">
              Creator A <span className="text-muted">vs</span> Creator B
            </h1>
            <p className={cn("mt-2 text-[15px] leading-relaxed text-fg-2", phones && "hidden")}>
              An anime-edit creator who already earns, and a Tamil home cook just starting out. Every number has a reason behind it, and every
              range is an estimate, not a promise.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              label="Layout"
              size="sm"
              value={phones ? "phones" : "cards"}
              onChange={(v) => setPhoneMode(v === "phones")}
              options={[
                { value: "cards", label: <span className="inline-flex items-center gap-1.5"><LayoutGrid className="size-3.5" aria-hidden /> Side by side</span> },
                { value: "phones", label: <span className="inline-flex items-center gap-1.5"><Smartphone className="size-3.5" aria-hidden /> Two phones</span> },
              ]}
            />
            <Button variant="primary" onClick={() => go(step === null ? 0 : null)} disabled={!q.data}>
              {step === null ? <Play aria-hidden /> : <X aria-hidden />} {step === null ? "Guided demo" : "End guided demo"}
            </Button>
          </div>
        </div>
        <p className={cn("mt-3 hidden text-xs text-muted", !phones && "lg:block")}>
          <Kbd>P</Kbd> switches to two phones · in the guided demo, <Kbd>←</Kbd> <Kbd>→</Kbd> move between steps and <Kbd>Esc</Kbd> ends it.
        </p>
        {q.data?.a.creator.reference_note && <ReferenceNote text={`Creator A: ${q.data.a.creator.reference_note}`} className="mt-4 max-w-3xl" />}

        {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
        {!q.data && !q.isError && <CompareSkeleton />}
        {q.data && (phones ? <TwoPhones data={q.data} frameA={frameA} frameB={frameB} /> : <Sections data={q.data} activeId={active?.id} />)}
      </main>

      <AnimatePresence>{active && step !== null && <GuideBar steps={guide} step={step} onGo={go} />}</AnimatePresence>
    </div>
  );
}

// ------------------------------------------------------------------ side by side
function Sections({ data, activeId }: { data: CompareData; activeId?: GuideStepId }) {
  return (
    <div className="mt-8 space-y-10">
      {SECTIONS.map((s) => (
        <section
          key={s.id}
          id={`sec-${s.id}`}
          aria-labelledby={`h-${s.id}`}
          data-active={activeId === s.id || undefined}
          className={cn(
            "scroll-mt-6 rounded-[30px] transition-[opacity,box-shadow] duration-300 motion-reduce:transition-none",
            activeId === s.id && "bg-[var(--bg)]/40 shadow-[0_0_0_2px_var(--accent),0_0_70px_-10px_var(--accent)]",
            activeId && "p-3 sm:p-4",
          )}
        >
          <div className="mb-3 flex items-baseline gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{s.eyebrow}</p>
            <h2 id={`h-${s.id}`} className="font-display text-lg font-semibold">
              {s.title}
            </h2>
            {activeId === s.id && (
              <Badge size="sm" variant="accent" className="ml-auto">
                Now showing
              </Badge>
            )}
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <Panel side={data.a} tag="A">
              <SectionBody id={s.id} side={data.a} />
            </Panel>
            <Panel side={data.b} tag="B">
              <SectionBody id={s.id} side={data.b} />
            </Panel>
          </div>
        </section>
      ))}
    </div>
  );
}

function Panel({ side, tag, children }: { side: CompareSide; tag: "A" | "B"; children: React.ReactNode }) {
  return (
    <article className="card-surface flex flex-col rounded-[24px] p-5" aria-label={side.creator.name}>
      <p className="mb-3 flex items-center gap-2 text-xs font-medium text-muted">
        <span className={cn("grid size-5 place-items-center rounded-full text-[11px] font-bold text-white", tag === "A" ? "bg-[#7C3AED]" : "bg-[#DB2777]")} aria-hidden>
          {tag}
        </span>
        {side.creator.name}
      </p>
      {children}
    </article>
  );
}

function SectionBody({ id, side }: { id: GuideStepId; side: CompareSide }) {
  switch (id) {
    case "who":
      return <Who side={side} />;
    case "stage":
      return <StageBody side={side} />;
    case "price":
      return <Price side={side} />;
    case "roadmap":
      return <RoadmapBody side={side} />;
    case "money":
      return <MoneyBody side={side} />;
    case "opportunities":
      return <Opps side={side} />;
    case "moves":
      return <Moves side={side} />;
  }
}

function Who({ side }: { side: CompareSide }) {
  const c = side.creator;
  const goal = c.income_goal?.monthly;
  return (
    <div>
      <div className="flex items-center gap-3.5">
        <Avatar name={c.name} hue={c.avatar_hue} size={52} generic={c.is_reference} />
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-display text-xl font-semibold">
            {c.name}
            <Badge size="sm" variant={c.is_reference ? "warn" : "neutral"}>
              {c.is_reference ? "Reference profile" : "Fictional"}
            </Badge>
          </p>
          <p className="text-sm text-muted">
            @{c.handle} · {c.niche_label} · {c.language_labels.join(", ")}
            {c.city ? ` · ${c.city}` : ""}
          </p>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-2 text-[13px]">
        <Stat label="Monthly goal" value={goal ? inr(goal) : "Not set"} />
        <Stat label="Median views" value={side.context.has_reels ? count(side.context.median_views) : "None yet"} />
        <Stat label="For context: followers" value={count(c.followers)} muted />
      </dl>
      <p className="mt-3 flex items-center gap-2 text-xs text-muted">
        Trust <TrustBadge trust={side.context.trust} />
        {side.context.reach_ratio !== null && <span>· reels reach about {side.context.reach_ratio.toFixed(0)}x followers</span>}
      </p>
    </div>
  );
}

function Stat({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="rounded-xl bg-surface-2 px-3 py-2">
      <dt className="text-[11px] leading-tight text-muted">{label}</dt>
      <dd className={cn("num mt-0.5 font-display text-base font-semibold", muted && "text-fg-2")}>{value}</dd>
    </div>
  );
}

function StageBody({ side }: { side: CompareSide }) {
  return (
    <div>
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-display text-2xl font-semibold text-gradient">{side.stage.label}</span>
        <WhyPopover why={side.stage.why} subject={`${side.creator.name}'s stage`} />
      </p>
      <p className="mt-1.5 text-[15px] text-fg-2">{side.stage.line}</p>
      <p className="mt-3 text-xs text-muted">Audience size: {side.stage.audience_stage.label}</p>
    </div>
  );
}

function Price({ side }: { side: CompareSide }) {
  const g = side.rate_gap;
  const rows = [
    { label: "Fair, priced on reach", value: g.per_reel, tone: "bg-signature" },
    { label: "Priced on followers alone", value: g.follower_price, tone: "bg-[var(--chart-muted)]" },
    ...(g.current ? [{ label: "Their typical quote", value: g.current, tone: "bg-[var(--chart-muted)]" }] : []),
  ];
  const max = Math.max(...rows.map((r) => r.value));
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted">Fair rate per reel{g.brand ? ` · for ${g.brand}` : ""}</p>
          <p className="num font-display text-[30px] font-semibold leading-tight tracking-tight">{inrRange(g.fair.low, g.fair.high)}</p>
        </div>
        <WhyPopover why={side.fair.why} subject={`${side.creator.name}'s fair price`} />
      </div>
      <dl className="mt-3 space-y-2.5 text-[13px]">
        {rows.map((r) => (
          <div key={r.label} className="grid grid-cols-[1fr_auto] gap-y-1">
            <dt className="text-fg-2">{r.label}</dt>
            <dd className="num font-medium">{inr(r.value)}</dd>
            <dd className="col-span-2 h-1.5 rounded-full bg-surface-3" aria-hidden>
              <div className={cn("h-full rounded-full", r.tone)} style={{ width: `${Math.max(4, (r.value / max) * 100)}%` }} />
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[13px] text-fg-2">{g.line}</p>
      <EstimateNote estimate={side.fair.estimate} className="mt-1 block" />
    </div>
  );
}

function RoadmapBody({ side }: { side: CompareSide }) {
  const { working, gaps, skills } = side.roadmap;
  return (
    <div className="space-y-3 text-[14px]">
      <Row label="Keep">
        {working[0] ? (
          <span className="flex flex-wrap items-center gap-x-2">
            {working[0].topic}
            <span className="num text-xs text-muted">{count(working[0].median_views)} median views</span>
            <WhyPopover why={working[0].why} label="" subject={`Keep ${working[0].topic}`} className="px-1 no-underline" />
          </span>
        ) : (
          <span className="text-fg-2">No proven format yet; the plan tests two.</span>
        )}
      </Row>
      <Row label="Add">
        {gaps[0] ? (
          <span>
            <span className="flex flex-wrap items-center gap-x-2">
              {gaps[0].title}
              <WhyPopover why={gaps[0].why} label="" subject={gaps[0].title} className="px-1 no-underline" />
            </span>
            <span className="mt-0.5 block text-[13px] text-muted">{gaps[0].evidence[0]}</span>
          </span>
        ) : (
          <span className="text-fg-2">No clear gap this week.</span>
        )}
      </Row>
      <Row label="Learn">
        <ol className="space-y-1">
          {skills.map((s) => (
            <li key={s.rank} className="flex gap-2">
              <span className="num text-muted">{s.rank}.</span>
              <span>{s.title}</span>
            </li>
          ))}
        </ol>
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[56px_1fr] gap-3">
      <p className="pt-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">{label}</p>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function MoneyBody({ side }: { side: CompareSide }) {
  return (
    <div>
      <ol className="space-y-2.5">
        {side.paths.map((p, i) => (
          <li key={p.type} className="rounded-2xl border border-line bg-surface p-3">
            <div className="flex items-start justify-between gap-2">
              <p className="flex gap-2 text-[14px] font-semibold leading-snug">
                <span className="num text-accent">{i + 1}</span>
                {p.title}
              </p>
              <WhyPopover why={p.why} label="" subject={p.title} className="px-1 no-underline" />
            </div>
            <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
              <RangeValue estimate={p.estimate} size="md" />
              <span className="flex gap-1.5">
                <Badge size="sm" variant="outline">
                  Fit {p.fit_score}
                </Badge>
                <Badge size="sm" variant="outline">
                  Effort {p.effort}
                </Badge>
              </span>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[13px] text-fg-2">
        Together: <span className="num font-medium text-fg">{inrRange(side.goal.top3.low, side.goal.top3.high)}</span> a month
        {side.goal.goal ? <> against a goal of <span className="num">{inr(side.goal.goal)}</span></> : null}.
      </p>
    </div>
  );
}

function Opps({ side }: { side: CompareSide }) {
  return (
    <ul className="space-y-2.5">
      {side.opportunities.map((o) => (
        <li key={o.id} className="rounded-2xl border border-line bg-surface p-3">
          <div className="flex items-center justify-between gap-2">
            <Badge size="sm" variant={o.type === "collective" ? "accent" : "neutral"}>
              {o.type_label}
            </Badge>
            <FitPill fit={o.fit} />
          </div>
          <p className="mt-2 text-[14px] font-semibold leading-snug">{o.title}</p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted">
            {o.lister.name}
            {o.lister.verified && <BadgeCheck className="size-3.5 text-success" aria-label="Verified" />}
          </p>
          {o.value.estimate && <RangeValue estimate={o.value.estimate} size="md" className="mt-1.5 block" />}
        </li>
      ))}
    </ul>
  );
}

function Moves({ side }: { side: CompareSide }) {
  return (
    <ol className="space-y-2.5">
      {side.moves.map((m, i) => {
        const cat = CATEGORY[m.category];
        return (
          <li key={m.id} className="rounded-2xl border border-line bg-surface p-3.5">
            <div className="flex items-center justify-between gap-2">
              <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
                <span className="num grid size-5 place-items-center rounded-full bg-accent-soft text-[11px] text-accent">{i + 1}</span>
                <cat.icon className="size-3.5" aria-hidden /> {cat.label}
              </span>
              <span className="flex items-center gap-1">
                <Badge size="sm" variant="outline" title={m.effort_hint}>
                  Effort {m.effort}
                </Badge>
                <WhyPopover why={m.why} label="" subject={m.title} className="px-1 no-underline" />
              </span>
            </div>
            <p className="mt-2 font-display text-[16px] font-semibold leading-snug">{m.title}</p>
            <p className="mt-1 text-[13px] leading-relaxed text-fg-2">{m.reason}</p>
            <RangeValue estimate={m.impact} size="md" className="mt-2 block" />
          </li>
        );
      })}
    </ol>
  );
}

// ------------------------------------------------------------------ two phones
function TwoPhones({
  data,
  frameA,
  frameB,
}: {
  data: CompareData;
  frameA: React.RefObject<HTMLIFrameElement | null>;
  frameB: React.RefObject<HTMLIFrameElement | null>;
}) {
  const wide = useMediaQuery("(min-width: 768px)");
  const box = useRef<HTMLDivElement>(null);
  const gap = 56;
  const scale = useFitScale(box, wide ? PHONE_OUTER.width * 2 + gap : PHONE_OUTER.width, PHONE_OUTER.height + 56, 24, wide);
  const srcA = useRef(framePath("/creator", data.a.creator.id));
  const srcB = useRef(framePath("/creator", data.b.creator.id));
  return (
    <div ref={box} className="mt-6 flex flex-col items-center gap-8 md:flex-row md:items-start md:justify-center" style={{ gap: wide ? gap * scale : 32 }}>
      {[
        { side: data.a, src: srcA.current, ref: frameA, tag: "A" },
        { side: data.b, src: srcB.current, ref: frameB, tag: "B" },
      ].map(({ side, src, ref, tag }) => (
        <PhoneFrame
          key={tag}
          src={src}
          frameRef={ref}
          scale={scale}
          title={`${side.creator.name}'s Creator Studio`}
          label={
            <span className="inline-flex items-center gap-2">
              <span className={cn("grid size-5 place-items-center rounded-full text-[11px] font-bold text-white", tag === "A" ? "bg-[#7C3AED]" : "bg-[#DB2777]")} aria-hidden>
                {tag}
              </span>
              {side.creator.name} · <span className="text-gradient font-semibold">{side.stage.label}</span>
            </span>
          }
        />
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ guided demo
function GuideBar({ steps, step, onGo }: { steps: GuideStep[]; step: number; onGo: (n: number | null) => void }) {
  const s = steps[step];
  const last = step === steps.length - 1;
  return (
    <motion.div
      role="region"
      aria-label="Guided demo"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 24 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-3xl rounded-[26px] border border-line-strong bg-[var(--surface-solid)] p-4 shadow-[0_30px_80px_-20px_rgb(0_0_0/0.7)] sm:bottom-5 sm:p-5"
    >
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px rounded-t-[26px] bg-signature" />
      <div className="flex items-start justify-between gap-3">
        <div aria-live="polite" className="min-w-0">
          <p className="num text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            Step {step + 1} of {steps.length}
          </p>
          <p className="mt-1 font-display text-lg font-semibold leading-snug sm:text-xl">{s.title}</p>
          <p className="mt-1.5 text-[14px] leading-relaxed text-fg-2 sm:text-[15px]">{s.caption}</p>
        </div>
        <Button variant="ghost" size="icon-sm" aria-label="End guided demo" onClick={() => onGo(null)}>
          <X />
        </Button>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="flex gap-1.5">
          {steps.map((x, i) => (
            <button
              key={x.id}
              type="button"
              aria-label={`Step ${i + 1}: ${x.title}`}
              aria-current={i === step ? "step" : undefined}
              onClick={() => onGo(i)}
              className="grid h-6 place-items-center rounded-full px-0.5"
            >
              <span className={cn("block h-1.5 rounded-full transition-all motion-reduce:transition-none", i === step ? "w-6 bg-accent" : "w-1.5 bg-surface-3")} />
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => onGo(step - 1)} disabled={step === 0}>
            <ArrowLeft aria-hidden /> Back
          </Button>
          <Button variant="primary" size="sm" onClick={() => onGo(last ? null : step + 1)}>
            {last ? "Finish" : "Next"} {!last && <ArrowRight aria-hidden />}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

function CompareSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the comparison" className="mt-8 space-y-6">
      {[0, 1, 2].map((i) => (
        <div key={i} className="grid gap-3 lg:grid-cols-2">
          <Skeleton className="h-48 rounded-[24px]" />
          <Skeleton className="h-48 rounded-[24px]" />
        </div>
      ))}
    </div>
  );
}
