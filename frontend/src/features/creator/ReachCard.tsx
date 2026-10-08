import { useReducedMotion } from "framer-motion";
import { useCallback } from "react";
import { Stage3D } from "@/components/three/Stage3D";
import { ReachBars3D } from "@/components/three/lazy";
import { SimulatedChip } from "@/components/shared/Why";
import { useI18n } from "@/i18n";
import type { Home } from "@/lib/api-types";
import { count, shortDate } from "@/lib/format";

/** Last 6 reels against the follower count, in 3D (2D bars without WebGL). */
export function ReachCard({ context }: { context: Home["context"] }) {
  const reduce = useReducedMotion();
  const { t } = useI18n();
  const reels = context.recent ?? [];
  const formatCount = useCallback((n: number) => count(n), []);
  const formatDate = useCallback((d: string) => shortDate(d), []);
  if (reels.length < 2) return null;
  const ratio = context.reach_ratio ?? 1;
  const simulated = context.recent_provenance?.views === "simulated";
  const summary = reels.map((r) => `${shortDate(r.date)}: ${count(r.views)} views`).join("; ");
  return (
    <section aria-labelledby="reach" className="card-surface relative overflow-hidden rounded-[var(--radius-card)] p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="reach" className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
            {t("reach.title")}
          </h2>
          <p className="mt-1.5 font-display text-xl font-semibold leading-snug sm:text-2xl">
            {ratio >= 1.5 ? t("reach.ratio", { n: ratio.toFixed(0) }) : t("reach.same")}
          </p>
          <p className="mt-1 text-[13px] text-fg-2">{t("reach.caption")}</p>
        </div>
        <p className="flex items-center gap-2 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-signature" aria-hidden /> {t("reach.views")}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-3 rounded bg-accent" aria-hidden /> {t("reach.followers")} <span className="num text-fg-2">{count(context.followers)}</span>
          </span>
          {simulated && <SimulatedChip />}
        </p>
      </div>
      <Stage3D
        className="-mx-2 mt-1 h-[270px] sm:h-[290px]"
        label={`${t("reach.title")}. ${summary}. ${t("home.followers", { n: count(context.followers) })}.`}
        fallback={<Bars2D reels={reels} followers={context.followers} />}
      >
        {(active) => (
          <ReachBars3D reels={reels} followers={context.followers} formatCount={formatCount} formatDate={formatDate} active={active} still={!!reduce} />
        )}
      </Stage3D>
    </section>
  );
}

function Bars2D({ reels, followers }: { reels: { date: string; views: number }[]; followers: number }) {
  const max = Math.max(followers, ...reels.map((r) => r.views), 1);
  return (
    <div className="relative flex h-full items-end gap-3 px-4 pb-6 pt-4">
      <div className="absolute inset-x-4 border-t border-dashed border-accent" style={{ bottom: `calc(1.5rem + ${(followers / max) * 100}% * 0.8)` }} />
      {reels.map((r) => (
        <div key={r.date} className="flex flex-1 flex-col items-center gap-1">
          <div className="w-full max-w-10 rounded-t-md bg-signature" style={{ height: `${Math.max(3, (r.views / max) * 180)}px` }} />
          <span className="text-[10px] text-muted">{shortDate(r.date)}</span>
        </div>
      ))}
    </div>
  );
}
