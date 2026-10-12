import { Award, BadgeIndianRupee, BarChart3, CheckCircle2, Clock, Heart, Link2, Play, Radio, Star, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Badge } from "@/components/ui/badge";
import { inrRange, shortDate } from "@/lib/format";
import type { PageBadge, PublicPage } from "@/lib/kit-types";

const BADGE_ICON: Record<PageBadge["key"], typeof Award> = {
  connected: Radio,
  on_time: Clock,
  completed: CheckCircle2,
  rating: Star,
  collective: Users,
};

/** Badges, niche tags and the positioning line, above the kit. */
export function PageIntro({ page }: { page: PublicPage }) {
  return (
    <div className="mb-4 space-y-3">
      {page.positioning && <p className="font-display text-lg font-semibold leading-snug">{page.positioning}</p>}
      <ul className="flex flex-wrap gap-1.5" aria-label="Niche">
        {page.niche_tags.map((t) => (
          <li key={t}>
            <Badge size="sm">{t}</Badge>
          </li>
        ))}
      </ul>
      {page.badges.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Badges">
          {page.badges.map((b) => {
            const Icon = BADGE_ICON[b.key] ?? Award;
            return (
              <li key={b.key} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-xs" title={b.detail}>
                <Icon className="size-3.5 text-accent" aria-hidden /> <span className="font-medium">{b.label}</span>
                <span className="sr-only">: {b.detail}</span>
                {b.sample && <SourceBadge source="synthetic" />}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** Below the kit: the estimate, top posts, Fan Proof, collaborations and case studies. */
export function PageSections({ page }: { page: PublicPage }) {
  return (
    <div className="mt-4 space-y-4">
      {/* The kit already shows estimated ranges unless the creator set their own rates. */}
      {page.estimate && page.rates_kind === "your_rate" && (
        <section aria-labelledby="pg-est" className="card-surface rounded-[var(--radius-card)] p-5">
          <h2 id="pg-est" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <BadgeIndianRupee className="size-3.5" aria-hidden /> {page.estimate.label} · {page.estimate.deliverables}
          </h2>
          <p className="num mt-1 font-display text-2xl font-semibold">{inrRange(page.estimate.range.low, page.estimate.range.high)}</p>
          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-fg-2">
            An estimate, not a quote. {page.estimate.data_label.replace("your ", "their ")} <SourceBadge source={page.estimate.data_source} />
          </p>
        </section>
      )}

      {page.top_posts && page.top_posts.length > 0 && (
        <section aria-labelledby="pg-posts" className="card-surface rounded-[var(--radius-card)] p-5">
          <h2 id="pg-posts" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <Play className="size-3.5" aria-hidden /> Top posts
          </h2>
          <ul className="mt-2 divide-y divide-line">
            {page.top_posts.map((p, i) => (
              <li key={p.url ?? i} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noreferrer nofollow" className="hover:text-accent">
                      {p.text || `${p.platform} post`}
                    </a>
                  ) : (
                    p.text
                  )}
                </span>
                <span className="num text-xs text-fg-2">{p.views_label} views</span>
                <SourceBadge source={p.source} fetchedAt={null} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {page.fan_badges.length > 0 && (
        <section aria-labelledby="pg-fan" className="card-surface rounded-[var(--radius-card)] p-5">
          <h2 id="pg-fan" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <Heart className="size-3.5" aria-hidden /> Fan Proof
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {page.fan_badges.map((f) => (
              <li key={f.brand} className="rounded-full border border-line px-3 py-1 text-xs">
                {f.slug ? (
                  <Link to={`/brands/${f.slug}`} className="font-medium hover:text-accent">
                    {f.brand}
                  </Link>
                ) : (
                  <span className="font-medium">{f.brand}</span>
                )}{" "}
                · {f.label}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">Unpaid mentions in posts from their connected accounts.</p>
        </section>
      )}

      {page.collaborations && page.collaborations.length > 0 && (
        <section aria-labelledby="pg-collabs" className="card-surface rounded-[var(--radius-card)] p-5">
          <h2 id="pg-collabs" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <Link2 className="size-3.5" aria-hidden /> Completed on JodiDar
          </h2>
          <ul className="mt-2 space-y-1.5 text-sm">
            {page.collaborations.map((c, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.brand}</span>
                <span className="text-xs text-muted">
                  {c.deliverables}
                  {c.month && ` · ${c.month}`}
                </span>
                {c.sample && <SourceBadge source="synthetic" />}
              </li>
            ))}
          </ul>
        </section>
      )}

      {page.case_studies && page.case_studies.length > 0 && (
        <section aria-labelledby="pg-cases" className="card-surface rounded-[var(--radius-card)] p-5">
          <h2 id="pg-cases" className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
            <BarChart3 className="size-3.5" aria-hidden /> Case studies
          </h2>
          <ul className="mt-2 divide-y divide-line">
            {page.case_studies.map((c, i) => (
              <li key={i} className="py-2.5 text-sm">
                <p className="font-medium">{c.brand}</p>
                <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-fg-2">
                  Predicted <span className="num font-medium text-fg">{c.predicted_label}</span> views <SourceBadge source={c.predicted_source} />
                  {c.actual_label ? (
                    <>
                      · actual <span className="num font-medium text-fg">{c.actual_label}</span> <SourceBadge source={c.actual_source} />
                    </>
                  ) : (
                    " · actual views not available yet"
                  )}
                  {c.paid_in_days != null && ` · paid in ${c.paid_in_days} days`}
                  {c.sample && <SourceBadge source="synthetic" />}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function lastUpdated(iso: string | null | undefined) {
  return iso ? shortDate(iso, true) : null;
}
