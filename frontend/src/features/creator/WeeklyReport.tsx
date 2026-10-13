// The Weekly Report at the top of the Creator Studio home: this week against last week,
// aggregated on the server from real records (GET /creators/{id}/weekly-report). A light
// card (.theme-site tokens) so it reads as a report on the dark Studio. Every block keeps
// its data label: sample data, self-reported or live.
import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, BarChart3, Eye, Handshake, IndianRupee, Minus, PlayCircle, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { CountUp } from "@/components/motion/Motion";
import { ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Skeleton } from "@/components/ui/form";
import { useI18n } from "@/i18n";
import { api } from "@/lib/api";
import type { WeeklyReport as Report } from "@/lib/api-types";
import { count, inr, inrShort, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const PLATFORM = { instagram: "Instagram", youtube: "YouTube" } as const;
const TILE_HEIGHT = "min-h-[168px]";

/** `youtube`: the creator's posts are YouTube videos, so it says videos, not reels. */
export function WeeklyReport({ creatorId, youtube = false, className }: { creatorId: string; youtube?: boolean; className?: string }) {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["weekly-report", creatorId], queryFn: () => api<Report>(`/creators/${creatorId}/weekly-report`) });

  return (
    <section
      aria-labelledby="weekly-report"
      className={cn(
        "theme-site overflow-hidden rounded-[28px] border border-slate-200/70 bg-white text-[#0a1b33] shadow-[0_30px_80px_-40px_rgb(0_0_0/0.7)]",
        className,
      )}
    >
      <div className="h-1 bg-signature" aria-hidden />
      <div className="p-4 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="weekly-report" className="flex items-center gap-2 font-display text-lg font-semibold">
            <BarChart3 className="size-5 text-violet-600" aria-hidden /> {t("weekly.title")}
          </h2>
          {q.data ? (
            <p className="text-xs text-slate-600">
              {t("weekly.range", { start: shortDate(q.data.week.start), end: shortDate(q.data.week.end) })}
            </p>
          ) : (
            <Skeleton className="h-4 w-60 max-w-full" />
          )}
        </div>
        {q.isError && (
          <div className="mt-4">
            <ErrorState error={q.error} onRetry={() => q.refetch()} />
          </div>
        )}
        {!q.data && !q.isError && (
          <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-busy="true">
            {/* Same size as the loaded tiles, so nothing below moves when the numbers arrive. */}
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className={cn(TILE_HEIGHT, "rounded-2xl")} />
            ))}
          </div>
        )}
        {q.data && <Body r={q.data} youtube={youtube} />}
      </div>
    </section>
  );
}

function Body({ r, youtube }: { r: Report; youtube: boolean }) {
  const { t } = useI18n();
  const yt = youtube || r.reach?.source === "youtube_api";
  const w = (key: "weekly.reach" | "weekly.reelsOne" | "weekly.reels" | "weekly.reelsNone" | "weekly.quiet", vars?: Record<string, string | number>) =>
    t(yt ? (`${key}Yt` as const) : key, vars);
  const { profile_views: views, offers, paid, reach } = r;
  return (
    <>
      <div className="mt-4 grid grid-cols-2 gap-2.5 sm:gap-3 lg:grid-cols-4">
        <Metric
          icon={<Eye />}
          label={t("weekly.views")}
          value={views.this}
          format={String}
          last={views.last}
          sub={views.this ? (views.brands === 1 ? t("weekly.viewsFromOne") : t("weekly.viewsFrom", { n: views.brands })) : null}
          source={views.source}
        />
        <Metric
          icon={<Handshake />}
          label={t("weekly.offers")}
          value={offers.this}
          format={String}
          last={offers.last}
          sub={offers.value ? t("weekly.offersValue", { amount: inrShort(offers.value) }) : null}
          source={offers.source}
        />
        <Metric
          icon={<IndianRupee />}
          label={paid.simulated ? t("weekly.paidSimulated") : t("weekly.paid")}
          value={paid.this}
          format={inr}
          last={paid.last}
          lastFormat={inrShort}
          sub={paid.deals ? (paid.deals === 1 ? t("weekly.paidDealsOne") : t("weekly.paidDeals", { n: paid.deals })) : null}
          source={paid.source}
        />
        {reach ? (
          <Metric
            icon={<PlayCircle />}
            label={w("weekly.reach")}
            value={reach.this}
            format={count}
            last={reach.last}
            lastFormat={count}
            sub={reach.reels === 0 ? w("weekly.reelsNone") : reach.reels === 1 ? w("weekly.reelsOne") : w("weekly.reels", { n: reach.reels })}
            source={reach.source}
          />
        ) : (
          <div className={cn(TILE_HEIGHT, "flex flex-col justify-between rounded-2xl bg-[#f9fafb] p-3.5 ring-1 ring-slate-200/70 sm:p-4")}>
            <p className="flex items-center gap-1.5 text-xs font-medium text-slate-600">
              <PlayCircle className="size-3.5" aria-hidden /> {w("weekly.reach")}
            </p>
            <p className="mt-2 text-[13px] leading-snug text-slate-600">{t("weekly.noReach")}</p>
            <Link to="/creator/connections" className="mt-2 self-start rounded-full bg-[#0a1b33] px-3 py-1 text-xs font-medium text-white hover:bg-[#16305a]">
              {t("weekly.connect")}
            </Link>
          </div>
        )}
        {r.followers.map((f) => (
          <Metric
            key={f.platform}
            icon={<Users />}
            label={t(f.platform === "youtube" ? "weekly.followersYt" : "weekly.followers", { platform: PLATFORM[f.platform] })}
            value={f.now}
            format={count}
            last={f.before}
            lastFormat={count}
            source={f.source}
          />
        ))}
      </div>
      {r.quiet && <p className="mt-3 text-[13px] text-slate-600">{w("weekly.quiet")}</p>}
    </>
  );
}

function Metric({
  icon,
  label,
  value,
  format,
  last,
  lastFormat,
  sub,
  source,
}: {
  icon: ReactNode;
  label: string;
  value: number;
  format: (n: number) => string;
  last: number;
  lastFormat?: (n: number) => string;
  sub?: string | null;
  source: string;
}) {
  return (
    <div className={cn(TILE_HEIGHT, "flex min-w-0 flex-col rounded-2xl bg-[#f9fafb] p-3.5 ring-1 ring-slate-200/70 sm:p-4")}>
      <p className="flex items-start gap-1.5 text-xs font-medium leading-snug text-slate-600 [&_svg]:mt-px [&_svg]:size-3.5 [&_svg]:shrink-0">
        {icon}
        <span className="line-clamp-2">{label}</span>
      </p>
      <p className="num mt-2 truncate font-display text-[26px] font-semibold leading-none sm:text-[30px]">
        <CountUp value={value} format={format} />
      </p>
      {sub && <p className="mt-1 truncate text-xs text-slate-600">{sub}</p>}
      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-2.5">
        <Delta now={value} before={last} format={lastFormat ?? format} />
        {source !== "dealmeet" && <SourceBadge source={source} />}
      </div>
    </div>
  );
}

/** This week against last: up, down or the same, with last week's figure. */
function Delta({ now, before, format }: { now: number; before: number; format: (n: number) => string }) {
  const { t } = useI18n();
  const diff = now - before;
  if (diff === 0)
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
        <Minus className="size-3" aria-hidden /> {t("weekly.same")}
      </span>
    );
  const up = diff > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn("num inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-[11px] font-medium", up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700")}
      title={t(up ? "weekly.up" : "weekly.down", { n: format(Math.abs(diff)) })}
    >
      <Icon className="size-3" aria-hidden />
      <span className="sr-only">{t(up ? "weekly.up" : "weekly.down", { n: format(Math.abs(diff)) })}. </span>
      <span aria-hidden>{t("weekly.lastWeek", { n: format(before) })}</span>
    </span>
  );
}
