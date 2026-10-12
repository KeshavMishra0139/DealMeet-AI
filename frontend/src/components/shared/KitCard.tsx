import { BadgeIndianRupee, History, Sparkles, TrendingUp, Users } from "lucide-react";
import type { Kit } from "@/lib/kit-types";
import { Avatar, ReferenceNote } from "./Bits";
import { SourceBadge } from "./SourceBadge";
import { TrustBadge } from "./TrustBadge";

/** The kit's own words, in its language (a Hindi kit reads in Hindi inside an English app). */
const TEXT = {
  en: {
    best: "What performs best",
    median: "median",
    ratesEstimate: "Rates, priced on reach",
    ratesOwn: "Rates",
    noteEstimate: "Estimated ranges, not promises. Final price depends on deliverables and usage.",
    noteOwn: "Rates set by the creator. Final price depends on deliverables and usage.",
    audience: "Audience",
    safety: "Brand safety",
    version: (n: number, d: string) => `Version ${n}, saved ${d}`,
  },
  hi: {
    best: "सबसे अच्छा क्या चलता है",
    median: "मीडियन",
    ratesEstimate: "रेट, पहुँच के आधार पर",
    ratesOwn: "रेट",
    noteEstimate: "ये अनुमानित रेंज हैं, वादा नहीं। आखिरी कीमत डिलिवरेबल्स और यूसेज पर निर्भर है।",
    noteOwn: "ये रेट क्रिएटर ने तय किए हैं। आखिरी कीमत डिलिवरेबल्स और यूसेज पर निर्भर है।",
    audience: "ऑडियंस",
    safety: "ब्रैंड सेफ़्टी",
    version: (n: number, d: string) => `वर्शन ${n}, ${d} को सेव किया`,
  },
};

/** The media kit as people see it: used in the Studio preview and the public page. */
export function KitCard({ kit, footer, headingLevel = 2 }: { kit: Kit; footer?: React.ReactNode; headingLevel?: 1 | 2 }) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const lang = kit.lang === "hi" ? "hi" : "en";
  const tx = TEXT[lang];
  const own = kit.rates_kind === "your_rate";
  return (
    <article className="card-surface @container overflow-hidden rounded-[28px]" aria-label={`${kit.name} media kit`} lang={lang}>
      <div className="relative p-6">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-signature opacity-20 blur-2xl" />
        <div className="relative flex items-center gap-4">
          <Avatar name={kit.name} hue={kit.avatar_hue} size={64} generic={kit.is_reference} />
          <div className="min-w-0">
            <Heading className="flex flex-wrap items-center gap-2 font-display text-2xl font-semibold">
              {kit.name}
              <TrustBadge trust={kit.trust ? { ...kit.trust, method: "" } : null} />
            </Heading>
            <p className="text-sm text-muted">
              @{kit.handle} · {kit.niche} · {kit.languages.join(", ")}
              {kit.location ? ` · ${kit.location}` : ""}
            </p>
          </div>
        </div>
        {kit.version && (
          <p className="relative mt-3 inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-[11px] text-fg-2">
            <History className="size-3.5" aria-hidden /> {tx.version(kit.version.number, kit.version.saved_on)}
          </p>
        )}
        <p className="relative mt-5 font-display text-lg font-semibold leading-snug">{kit.copy.headline}</p>
        {kit.copy.bio && <p className="relative mt-1.5 text-[15px] leading-relaxed text-fg-2">{kit.copy.bio}</p>}
        {kit.reference_note && <ReferenceNote text={kit.reference_note} className="relative mt-3" />}
      </div>

      {kit.stats && (
        <dl className="grid grid-cols-2 gap-px border-y border-line bg-line @2xl:grid-cols-4">
          {kit.stats.map((s) => (
            <div key={s.label} className="bg-[var(--surface-solid)] px-4 py-3">
              <dt className="text-[11px] text-muted">{s.label}</dt>
              <dd className="num mt-0.5 font-display text-xl font-semibold">{s.value}</dd>
              <dd className="mt-1">
                <SourceBadge source={s.source ?? (s.simulated ? "synthetic" : null)} lang={lang} />
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="grid gap-5 p-6 @2xl:grid-cols-2">
        {kit.formats && kit.formats.length > 0 && (
          <div>
            <p className="flex flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
              <TrendingUp className="size-3.5" aria-hidden /> {tx.best}
              <SourceBadge source={kit.formats[0]?.source ?? (kit.formats[0]?.simulated ? "synthetic" : null)} lang={lang} className="normal-case tracking-normal" />
            </p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {kit.formats.map((f) => (
                <li key={f.topic} className="flex justify-between gap-3">
                  <span className="text-fg-2">{f.topic}</span>
                  <span className="num font-medium">
                    {f.views} {tx.median}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {kit.rates && (
          <div>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
              <BadgeIndianRupee className="size-3.5" aria-hidden /> {own ? tx.ratesOwn : tx.ratesEstimate}
            </p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {kit.rates.map((r) => (
                <li key={r.label} className="flex justify-between gap-3">
                  <span className="text-fg-2">{r.label}</span>
                  <span className="num font-semibold">{r.value}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-muted">{own ? tx.noteOwn : tx.noteEstimate}</p>
          </div>
        )}
        {kit.audience && (
          <div>
            <p className="flex flex-wrap items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
              <Users className="size-3.5" aria-hidden /> {tx.audience}
              <SourceBadge source={kit.audience.source ?? (kit.audience.simulated ? "synthetic" : null)} lang={lang} className="normal-case tracking-normal" />
            </p>
            <p className="mt-2 text-sm text-fg-2">{kit.audience.line}</p>
          </div>
        )}
        {kit.safety_note && (
          <div>
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.1em] text-muted">
              <Sparkles className="size-3.5" aria-hidden /> {tx.safety}
            </p>
            <p className="mt-2 text-sm text-fg-2">{kit.safety_note}</p>
          </div>
        )}
      </div>
      {footer && <div className="border-t border-line p-4">{footer}</div>}
    </article>
  );
}
