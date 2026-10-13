// One dashboard per connected platform, in that platform's words: videos, subscribers and
// Shorts for YouTube; reels, followers, saves and shares for Instagram. With both connected,
// tabs switch between them and nothing is mixed (GET /creators/{id}/platforms).
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, ExternalLink, Instagram, Lightbulb, Youtube } from "lucide-react";
import { Link } from "react-router-dom";
import { ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/i18n";
import type { Dict } from "@/i18n/en";
import { api } from "@/lib/api";
import type { PlatformDashboard as Dashboard, Platforms, Terms } from "@/lib/api-types";
import { count, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ReachPanel } from "./ReachCard";

const ICON = { youtube: Youtube, instagram: Instagram } as const;
/** Hindi for the words the server sends in English (engines/metrics.py TERMS). */
const HI_TERMS: Record<string, string> = {
  video: "वीडियो",
  videos: "वीडियो",
  reel: "रील",
  reels: "रील्स",
  subscribers: "सब्सक्राइबर्स",
  followers: "फ़ॉलोअर्स",
};

export function usePlatforms(creatorId: string) {
  return useQuery({ queryKey: ["platforms", creatorId], queryFn: () => api<Platforms>(`/creators/${creatorId}/platforms`), enabled: !!creatorId });
}

/** Nothing until a platform is connected; one dashboard for one platform; tabs for two. */
export function PlatformDashboards({ creatorId, className }: { creatorId: string; className?: string }) {
  const { t } = useI18n();
  const q = usePlatforms(creatorId);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <Skeleton className={cn("h-[420px] rounded-[var(--radius-card)]", className)} />;
  const dashboards = q.data.platforms;
  if (!dashboards.length) return null;
  if (dashboards.length === 1) {
    return (
      <section aria-label={t("platform.one", { platform: dashboards[0].terms.label })} className={className}>
        <PlatformView d={dashboards[0]} />
      </section>
    );
  }
  return (
    <section aria-label={t("platform.both")} className={className}>
      <Tabs defaultValue={dashboards[0].platform}>
        <TabsList aria-label={t("platform.both")} className="mb-4">
          {dashboards.map((d) => {
            const Icon = ICON[d.platform];
            return (
              <TabsTrigger key={d.platform} value={d.platform}>
                <Icon aria-hidden /> {d.terms.label}
              </TabsTrigger>
            );
          })}
        </TabsList>
        {dashboards.map((d) => (
          <TabsContent key={d.platform} value={d.platform}>
            <PlatformView d={d} />
          </TabsContent>
        ))}
      </Tabs>
    </section>
  );
}

function useWords(terms: Terms) {
  const { lang } = useI18n();
  const word = (w: string) => (lang === "hi" ? HI_TERMS[w] ?? w : w);
  return { posts: word(terms.posts), post: word(terms.post), audience: word(terms.audience) };
}

function PlatformView({ d }: { d: Dashboard }) {
  const { t } = useI18n();
  const words = useWords(d.terms);
  const Icon = ICON[d.platform];
  const audience = d.chart.audience;
  const median = d.kpis.find((k) => k.key === "median_views")?.value ?? 0;
  return (
    <div className="space-y-3">
      <header className="card-surface flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] p-4 sm:p-5">
        {d.account.picture ? (
          <img src={d.account.picture} alt="" className="size-11 rounded-full border border-line object-cover" referrerPolicy="no-referrer" />
        ) : (
          <span className="grid size-11 place-items-center rounded-full bg-surface-2">
            <Icon className="size-5" aria-hidden />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
            <Icon className="size-5 shrink-0" aria-hidden />
            <span className="truncate">{t(d.platform === "youtube" ? "platform.youtubeTitle" : "platform.instagramTitle")}</span>
          </h2>
          <p className="truncate text-sm text-fg-2">
            {[d.account.name, d.account.handle].filter(Boolean).join(" · ")}
            {d.platform === "youtube" && !d.account.verified && <span className="text-muted"> · {t("platform.unverified")}</span>}
          </p>
        </div>
        <SourceBadge source={d.source} fetchedAt={d.fetched_at} />
      </header>

      <dl className="grid grid-cols-2 gap-2.5 sm:gap-3 lg:grid-cols-4">
        {d.kpis.map((k) => (
          <div key={k.key} className="card-surface rounded-2xl p-3.5 sm:p-4">
            <dt className="text-[11px] font-medium leading-snug text-muted first-letter:uppercase">{t(`platform.kpi.${k.key}` as keyof Dict, { posts: words.posts, audience: words.audience, n: d.chart.recent.length })}</dt>
            <dd className="num mt-1.5 font-display text-2xl font-semibold">
              {k.hidden ? <span className="text-base text-fg-2">{t("platform.hidden")}</span> : k.value == null ? "—" : formatKpi(k.key, k.value)}
            </dd>
            {k.key === "audience" && d.change && <Change change={d.change} since={d.change.since} />}
          </div>
        ))}
      </dl>

      {d.chart.recent.length >= 2 && (
        <ReachPanel posts={d.chart.recent} followers={audience ?? 0} median={median} youtube={d.platform === "youtube"} />
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        {d.insights.length > 0 && (
          <section className="card-surface rounded-[var(--radius-card)] p-5">
            <h3 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
              <Lightbulb className="size-4" aria-hidden /> {t("platform.insights")}
            </h3>
            <ul className="mt-3 space-y-2 text-sm text-fg-2">
              {d.insights.map((line) => (
                <li key={line} className="flex gap-2">
                  <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {(d.formats.length > 0 || d.analytics) && (
          <section className="card-surface rounded-[var(--radius-card)] p-5">
            {d.formats.length > 0 && <Formats formats={d.formats} />}
            {d.analytics && <Audience d={d} className={d.formats.length > 0 ? "mt-5 border-t border-line pt-4" : undefined} />}
          </section>
        )}
      </div>

      {d.posts.length > 0 && <RecentPosts d={d} words={words} />}

      {d.notes.length > 0 && (
        <ul className="space-y-1 px-1 text-xs text-muted">
          {d.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>
            <Link to="/creator/connections" className="font-medium text-accent hover:underline">
              {t("platform.manage")}
            </Link>
          </li>
        </ul>
      )}
    </div>
  );
}

function formatKpi(key: string, value: number) {
  if (key.endsWith("_per_1k") || key === "pace") return value.toLocaleString("en-IN", { maximumFractionDigits: 1 });
  return count(value);
}

function Change({ change, since }: { change: { now: number; before: number }; since: string }) {
  const { t } = useI18n();
  const diff = change.now - change.before;
  const Arrow = diff >= 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <p className={cn("mt-1 inline-flex items-center gap-1 text-xs", diff > 0 ? "text-success" : diff < 0 ? "text-danger" : "text-muted")}>
      {diff !== 0 && <Arrow className="size-3.5" aria-hidden />}
      <span className="num">{t("platform.since", { n: `${diff >= 0 ? "+" : "−"}${count(Math.abs(diff))}`, date: shortDate(since) })}</span>
    </p>
  );
}

function Formats({ formats }: { formats: Dashboard["formats"] }) {
  const { t } = useI18n();
  const max = Math.max(...formats.map((f) => f.median_views), 1);
  return (
    <div>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{t("platform.formats")}</h3>
      <ul className="mt-3 space-y-3">
        {formats.map((f) => (
          <li key={f.key}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium">{t(`platform.format.${f.key}` as keyof Dict)}</span>
              <span className="num text-fg-2">{t("platform.formatLine", { n: count(f.median_views), count: f.count })}</span>
            </div>
            <div className="mt-1.5 h-2 rounded-full bg-surface-2" aria-hidden>
              <div className="h-2 rounded-full bg-[var(--chart-base)]" style={{ width: `${Math.max(4, (f.median_views / max) * 100)}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Audience({ d, className }: { d: Dashboard; className?: string }) {
  const { t } = useI18n();
  const a = d.analytics!;
  const rows: [string, string][] = [];
  if (a.minutes_watched != null) rows.push([t("platform.watchTime"), t("platform.hours", { n: count(Math.round(a.minutes_watched / 60)) })]);
  if (a.average_view_duration_s != null) {
    const s = a.average_view_duration_s;
    rows.push([t("platform.avgView"), `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`]);
  }
  if (a.top_age) rows.push([t("platform.topAge"), `${a.top_age.age} (${a.top_age.percent}%)`]);
  if (a.women_percent != null) rows.push([t("platform.women"), `${a.women_percent}%`]);
  if (a.top_countries?.length) rows.push([t("platform.countries"), a.top_countries.map((c) => `${c.country} ${c.share}%`).join(", ")]);
  if (a.top_cities?.length) rows.push([t("platform.cities"), a.top_cities.map((c) => `${c.city} ${c.share}%`).join(", ")]);
  return (
    <div className={className}>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {d.platform === "youtube" ? t("platform.analytics", { n: a.period_days ?? 28 }) : t("platform.igAudience")}
      </h3>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-muted">{k}</dt>
            <dd className="num font-medium">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function RecentPosts({ d, words }: { d: Dashboard; words: { posts: string } }) {
  const { t } = useI18n();
  const ig = d.platform === "instagram";
  return (
    <section className="card-surface overflow-hidden rounded-[var(--radius-card)]">
      <h3 className="px-5 pt-5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{t("platform.recent", { posts: words.posts })}</h3>
      <ul className="mt-2 divide-y divide-line">
        {d.posts.map((p) => {
          const stats = [
            t("platform.views", { n: count(p.views) }),
            p.likes != null ? t("platform.likes", { n: count(p.likes) }) : null,
            p.comments != null ? t("platform.comments", { n: count(p.comments) }) : null,
            ig && p.saves != null ? t("platform.saves", { n: count(p.saves) }) : null,
            ig && p.shares != null ? t("platform.shares", { n: count(p.shares) }) : null,
          ].filter(Boolean);
          return (
            <li key={p.id} className="flex items-start gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {p.permalink ? (
                    <a href={p.permalink} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-1 hover:underline">
                      <span className="truncate">{p.title || t("platform.untitled")}</span>
                      <ExternalLink className="size-3 shrink-0 text-muted" aria-hidden />
                    </a>
                  ) : (
                    p.title || t("platform.untitled")
                  )}
                </p>
                <p className="num mt-0.5 text-xs text-muted">{stats.join(" · ")}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-xs text-muted">
                <span>{shortDate(p.date)}</span>
                {d.platform === "youtube" && <Badge size="sm">{t(`platform.format.${p.format}` as keyof Dict)}</Badge>}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
