import { useQuery } from "@tanstack/react-query";
import { Bot, CheckCircle2, FileText, GraduationCap, Lightbulb, Repeat, Search, Sparkles, UserRound } from "lucide-react";
import { ErrorState, ReferenceNote, SectionTitle } from "@/components/shared/Bits";
import { WhyPopover } from "@/components/shared/Why";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import type { Roadmap as RoadmapData } from "@/lib/api-types";
import { count } from "@/lib/format";
import { useCreatorId } from "@/lib/session";
import { cn } from "@/lib/utils";
import { StagePill } from "./Home";

const KIND_ICON: Record<string, typeof Lightbulb> = {
  money: FileText,
  growth: Repeat,
  opportunity: Sparkles,
  content: Lightbulb,
  skill: GraduationCap,
  review: Search,
};

export default function Roadmap() {
  const id = useCreatorId();
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["roadmap", id], queryFn: () => api<RoadmapData>(`/creators/${id}/roadmap`) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <RoadmapSkeleton />;
  const r = q.data;

  return (
    <div>
      <StagePill stage={r.stage} />
      <h1 className="mt-3 font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">{t("roadmap.title")}</h1>
      <p className="mt-1 text-[15px] text-fg-2">What to keep, what to add, and how to get there in 30 days.</p>
      {r.creator.is_reference && r.creator.reference_note && <ReferenceNote text={r.creator.reference_note} className="mt-2" />}

      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        <section aria-labelledby="working" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="working" eyebrow="Keep doing" title="What's working" />
          {r.working.length === 0 ? (
            <p className="text-sm text-muted">Connect your account or post a few reels and we'll show what's working.</p>
          ) : (
            <ul className="space-y-2.5">
              {r.working.map((w) => (
                <li key={w.topic} className="flex items-center gap-3 rounded-2xl bg-surface-2 p-3">
                  <CheckCircle2 className="size-5 shrink-0 text-success" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{w.topic}</p>
                    <p className="num text-xs text-muted">
                      {w.count} reels · median {count(w.median_views)} views · {(w.save_rate * 100).toFixed(1)}% save
                    </p>
                  </div>
                  <WhyPopover why={w.why} subject={w.topic} label="" className="no-underline" />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="gaps" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="gaps" eyebrow="Add next" title="Content gaps" />
          {r.gaps.length === 0 ? (
            <p className="text-sm text-muted">No clear gap yet. Keep posting your best format and check back next week.</p>
          ) : (
            <ul className="space-y-3">
              {r.gaps.map((g) => (
                <li key={g.id} className="rounded-2xl border border-line p-3.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-display text-[15px] font-semibold leading-snug">{g.title}</p>
                    <WhyPopover why={g.why} subject={g.title} />
                  </div>
                  <ul className="mt-2 space-y-1">
                    {g.evidence.map((e) => (
                      <li key={e} className="flex gap-2 text-[13px] leading-relaxed text-fg-2">
                        <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-signature" aria-hidden />
                        {e}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="topics" className="mt-8">
        <SectionTitle
          id="topics"
          eyebrow={`In ${r.topics.language}`}
          title="Topic ideas in your language"
          action={
            <Badge size="sm" variant={r.topics.source === "template" ? "neutral" : "accent"}>
              <Bot aria-hidden /> {r.topics.source === "template" ? "Offline suggestions" : "AI suggestions"}
            </Badge>
          }
        />
        <ul className="grid gap-3 md:grid-cols-3">
          {r.topics.ideas.map((idea) => (
            <li key={idea.native} className="card-surface rounded-[var(--radius-card)] p-5">
              <p className="font-display text-xl font-semibold leading-snug" lang={langCode(r.topics.language)}>
                {idea.native}
              </p>
              {idea.english !== idea.native && <p className="mt-1 text-sm text-fg-2">{idea.english}</p>}
              <p className="mt-3 text-[13px] leading-relaxed text-muted">{idea.why}</p>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-8 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        <section aria-labelledby="skills" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="skills" eyebrow="Top 3" title="Skills to build" />
          <ol className="space-y-3">
            {r.skills.map((s) => (
              <li key={s.title} className="flex gap-3">
                <span className="num grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">
                  {s.rank}
                </span>
                <div>
                  <p className="font-medium">{s.title}</p>
                  <p className="mt-0.5 text-[13px] text-fg-2">{s.action}</p>
                  <p className="mt-0.5 text-xs text-muted">{s.reason}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="plan30" className="card-surface rounded-[var(--radius-card)] p-5">
          <SectionTitle id="plan30" eyebrow="Next 30 days" title="Your plan" />
          <ol className="relative ml-3 border-l border-line-strong">
            {r.plan.map((w) => (
              <li key={w.week} className="relative pb-5 pl-6 last:pb-0">
                <span
                  aria-hidden
                  className={cn(
                    "absolute -left-[7px] top-1 size-3.5 rounded-full border-2 border-[var(--bg)]",
                    w.week === 1 ? "bg-signature" : "bg-surface-3",
                  )}
                />
                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">
                  Week {w.week} · {w.title}
                </p>
                <ul className="mt-1.5 space-y-1.5">
                  {w.items.map((it) => {
                    const Icon = KIND_ICON[it.kind] ?? Lightbulb;
                    return (
                      <li key={it.title} className="flex items-start gap-2 text-[14px] leading-snug">
                        <Icon className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
                        {it.title}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section aria-labelledby="twins" className="mt-8">
        <SectionTitle id="twins" eyebrow="One or two stages ahead" title="Reference twins" />
        <ul className="grid gap-3 md:grid-cols-3">
          {r.twins.map((tw) => (
            <li key={tw.id} className="card-surface flex flex-col rounded-[var(--radius-card)] p-5">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-full bg-surface-3 text-fg-2" aria-hidden>
                  <UserRound className="size-5" />
                </span>
                <div className="min-w-0">
                  <p className="truncate font-semibold">{tw.name}</p>
                  <p className="num text-xs text-muted">
                    {count(tw.followers)} followers · {tw.platform}
                  </p>
                </div>
              </div>
              <Badge size="sm" variant="outline" className="mt-3 self-start">
                {tw.label}
              </Badge>
              <p className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-muted">What they did next</p>
              <ol className="mt-1.5 space-y-1">
                {tw.steps.map((s, i) => (
                  <li key={s} className="flex gap-2 text-[13px] leading-snug text-fg-2">
                    <span className="num text-muted">{i + 1}.</span>
                    {s}
                  </li>
                ))}
              </ol>
              <p className="mt-auto pt-3 text-[13px] italic text-fg">{tw.lesson}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function langCode(label: string) {
  return { Tamil: "ta", Telugu: "te", Kannada: "kn", Malayalam: "ml", Bengali: "bn", Marathi: "mr", Hindi: "hi", Gujarati: "gu" }[label] ?? "en";
}

function RoadmapSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="mt-3 h-9 w-64" />
      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        <Skeleton className="h-56 rounded-[var(--radius-card)]" />
        <Skeleton className="h-56 rounded-[var(--radius-card)]" />
      </div>
      <Skeleton className="mt-8 h-40 rounded-[var(--radius-card)]" />
    </div>
  );
}
