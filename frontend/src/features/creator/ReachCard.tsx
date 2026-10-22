import { motion, useInView, useReducedMotion } from "framer-motion";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { EASE } from "@/components/motion/Motion";
import { SimulatedChip } from "@/components/shared/Why";
import { useI18n } from "@/i18n";
import type { Home } from "@/lib/api-types";
import { count, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

type Post = { date: string; views: number };
/** Copy that has a reels-and-followers and a videos-and-subscribers version ("...Yt"). */
type Worded = "reach.title" | "reach.ratio" | "reach.same" | "reach.share" | "reach.viewsOnly" | "reach.caption" | "reach.line" | "reach.pct" | "reach.pctCol";

/** 2.3x under 10, then whole numbers: 12x. */
const times = (r: number) => (r < 10 ? r.toFixed(1).replace(/\.0$/, "") : String(Math.round(r)));
/** Views as a whole percentage of followers; never "0%" for a post someone saw. */
const pctOf = (views: number, followers: number) => (views > 0 ? Math.max(1, Math.round((views / followers) * 100)) : 0);

/** Home's card, from the profile's numbers (reels, or a linked channel's videos). */
export function ReachCard({ context }: { context: Home["context"] }) {
  return (
    <ReachPanel
      posts={context.recent ?? []}
      followers={context.followers}
      median={context.median_views}
      youtube={context.terms.platform === "youtube"}
      simulated={context.recent_provenance?.views === "simulated"}
    />
  );
}

/** The last few reels (or videos) as flat bars against a dashed line at the follower
 * (or subscriber) count. Also used by each platform's dashboard. */
export function ReachPanel({
  posts,
  followers,
  median,
  youtube,
  simulated = false,
  className,
}: {
  posts: Post[];
  followers: number;
  median: number;
  youtube: boolean;
  simulated?: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const id = useId();
  if (posts.length < 2) return null;
  const w = (key: Worded, vars?: Record<string, string | number>) => t(youtube ? (`${key}Yt` as const) : key, vars);
  const r = followers > 0 ? median / followers : null;
  // From the median, so one big post doesn't set the headline.
  const headline =
    r === null
      ? w("reach.viewsOnly", { n: count(median) })
      : r >= 1.5
        ? w("reach.ratio", { n: times(r) })
        : r >= 0.67
          ? w("reach.same")
          : w("reach.share", { pct: pctOf(median, followers) });
  const lineLabel = followers > 0 ? w("reach.line", { n: count(followers) }) : null;
  const caption = w("reach.caption", { n: posts.length });
  return (
    <section aria-labelledby={id} className={cn("card-surface relative overflow-hidden rounded-[var(--radius-card)] p-5 sm:p-6", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={id} className="text-xs font-medium text-muted">
            {w("reach.title")}
          </h2>
          <p className="mt-1.5 font-display text-xl font-semibold leading-snug sm:text-2xl">{headline}</p>
          <p className="mt-1 text-[13px] text-fg-2">{caption}</p>
        </div>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px] bg-[var(--chart-base)]" aria-hidden /> {t("reach.views")}
          </span>
          {lineLabel && (
            <span className="inline-flex items-center gap-1.5">
              <svg width="16" height="4" aria-hidden>
                <line x1="0" y1="2" x2="16" y2="2" stroke="var(--fg-2)" strokeWidth="1.5" strokeDasharray="4 3" />
              </svg>
              <span className="num">{lineLabel}</span>
            </span>
          )}
          {simulated && <SimulatedChip />}
        </p>
      </div>
      <ReachChart
        posts={posts}
        followers={followers}
        lineLabel={lineLabel}
        label={[w("reach.title"), headline, lineLabel].filter(Boolean).join(". ") + "."}
        pctLabel={(v) => w("reach.pct", { pct: pctOf(v, followers) })}
      />
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("reach.date")}</th>
            <th scope="col">{t("reach.views")}</th>
            {followers > 0 && <th scope="col">{w("reach.pctCol")}</th>}
          </tr>
        </thead>
        <tbody>
          {posts.map((p, i) => (
            <tr key={`${p.date}-${i}`}>
              <th scope="row">{shortDate(p.date)}</th>
              <td>{count(p.views)}</td>
              {followers > 0 && <td>{pctOf(p.views, followers)}%</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

const H = 228;
const TOP = 26; // room for the value over the tallest bar
const RIGHT = 4;
const VALUE_FONT = 11;
const AXIS_FONT = 10;
const DATE_FONT = 11;

let measure: CanvasRenderingContext2D | null | undefined;
/** Rendered text width in px, so labels can be placed without overlapping. */
function textWidth(s: string, size: number, weight = 400) {
  if (measure === undefined) measure = document.createElement("canvas").getContext("2d");
  if (!measure) return s.length * size * 0.62;
  measure.font = `${weight} ${size}px "Inter Variable", "Noto Sans Devanagari", ui-sans-serif, system-ui, sans-serif`;
  return measure.measureText(s).width;
}

/** 0 to a round top with 2 or 3 steps, e.g. 0 / 2K / 4K / 6K. */
function scale(max: number) {
  const raw = max / 3;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(1, [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag);
  const steps = Math.max(1, Math.ceil(max / step - 1e-9));
  return { top: steps * step, ticks: Array.from({ length: steps + 1 }, (_, i) => i * step) };
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}
const overlap = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));

/** Bar tops rounded 4px, square at the baseline. */
function barPath(x: number, top: number, w: number, base: number) {
  const r = Math.min(4, w / 2, base - top);
  if (r <= 0) return `M${x},${base}h${w}`;
  return `M${x},${base}V${top + r}Q${x},${top} ${x + r},${top}H${x + w - r}Q${x + w},${top} ${x + w},${top + r}V${base}Z`;
}

function ReachChart({
  posts,
  followers,
  lineLabel,
  label,
  pctLabel,
}: {
  posts: Post[];
  followers: number;
  lineLabel: string | null;
  label: string;
  pctLabel: (views: number) => string;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState<number | null>(null);
  const reduce = !!useReducedMotion();
  const inView = useInView(box, { once: true, amount: 0.4 });
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const { top, ticks } = scale(Math.max(followers, ...posts.map((p) => p.views), 1));
  const left = Math.ceil(Math.max(...ticks.map((v) => textWidth(count(v), AXIS_FONT)))) + 8;
  const right = Math.max(left + 1, width - RIGHT);
  const slot = (right - left) / posts.length;
  const barW = Math.min(28, Math.max(8, slot * 0.5));
  const dates = posts.map((p) => shortDate(p.date));
  // Dates go on two lines ("20" over "Sept") when one line won't fit its slot.
  const stacked = Math.max(...dates.map((d) => textWidth(d, DATE_FONT))) + 8 > slot;
  const base = H - (stacked ? 34 : 22);
  const y = (v: number) => base - (v / top) * (base - TOP);

  const bars = posts.map((p, i) => {
    const cx = left + slot * (i + 1 / 2);
    const barTop = p.views > 0 ? Math.min(y(p.views), base - 2) : base;
    const value = count(p.views);
    const vw = textWidth(value, VALUE_FONT, 600);
    return {
      ...p,
      cx,
      barTop,
      value,
      bar: { x: cx - barW / 2, y: barTop, w: barW, h: base - barTop },
      valueBox: { x: cx - vw / 2 - 2, y: barTop - 17, w: vw + 4, h: 14 },
    };
  });

  // The follower label sits just above (or below) the dashed line, at the right edge if it
  // is clear there, otherwise wherever it covers no value label and the fewest bars.
  const lineY = followers > 0 ? y(followers) : null;
  let tag: (Box & { solid: boolean }) | null = null;
  if (lineY !== null && lineLabel) {
    const w = textWidth(lineLabel, VALUE_FONT, 600) + 8;
    const xs = [right - w, left + 2, ...bars.slice(1).map((b) => b.cx - slot / 2 - w / 2).reverse()];
    let best: { box: Box; cost: number } | null = null;
    for (const x of xs) {
      for (const yTop of [lineY - 18, lineY + 4]) {
        const c: Box = { x, y: yTop, w, h: 14 };
        if (c.y < 0 || c.y + c.h > base - 1 || c.x < left || c.x + c.w > right) continue;
        const cost = bars.reduce((s, b) => s + overlap(c, b.valueBox) * 100 + overlap(c, b.bar), 0);
        if (!best || cost < best.cost) best = { box: c, cost };
        if (cost === 0) break;
      }
      if (best?.cost === 0) break;
    }
    if (best) tag = { ...best.box, solid: best.cost > 0 };
  }

  const hovered = active === null ? null : bars[active];
  return (
    <div ref={box} className="relative mt-4" onPointerLeave={(e) => e.pointerType === "mouse" && setActive(null)}>
      {width > 0 && (
        <svg width={width} height={H} role="img" aria-label={label} className="block overflow-visible">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke={v === 0 ? "var(--line-strong)" : "var(--chart-grid)"} strokeWidth="1" />
              <text x={left - 6} y={y(v)} dy="0.32em" textAnchor="end" fontSize={AXIS_FONT} fill="var(--muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {count(v)}
              </text>
            </g>
          ))}
          {hovered && <rect x={hovered.cx - slot / 2 + 2} y={TOP - 20} width={slot - 4} height={base - TOP + 20} rx="8" fill="var(--surface-2)" />}
          {bars.map((b, i) => (
            <motion.path
              key={`bar-${i}`}
              d={barPath(b.bar.x, b.barTop, barW, base)}
              fill={active === i ? "var(--accent-strong)" : "var(--chart-base)"}
              style={{ originY: 1 }}
              initial={reduce ? false : { scaleY: 0 }}
              animate={{ scaleY: reduce || inView ? 1 : 0 }}
              transition={{ duration: 0.6, ease: EASE, delay: 0.06 * i }}
            />
          ))}
          {lineY !== null && (
            <line x1={left} x2={right} y1={lineY} y2={lineY} stroke="var(--fg-2)" strokeWidth="1.5" strokeDasharray="5 4" />
          )}
          {bars.map((b, i) => (
            <g key={`label-${i}`} fontSize={DATE_FONT} textAnchor="middle">
              <motion.text
                x={b.cx}
                y={b.barTop - 6}
                fontSize={VALUE_FONT}
                fontWeight={600}
                fill="var(--fg)"
                stroke="var(--surface-solid)"
                strokeWidth="3"
                strokeLinejoin="round"
                paintOrder="stroke"
                style={{ fontVariantNumeric: "tabular-nums" }}
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: reduce || inView ? 1 : 0 }}
                transition={{ duration: 0.3, delay: 0.06 * i + 0.35 }}
              >
                {b.value}
              </motion.text>
              <text x={b.cx} y={base + 15} fill="var(--muted)">
                {stacked ? (
                  <>
                    <tspan x={b.cx}>{dates[i].split(" ")[0]}</tspan>
                    <tspan x={b.cx} dy="1.15em">
                      {dates[i].split(" ").slice(1).join(" ")}
                    </tspan>
                  </>
                ) : (
                  dates[i]
                )}
              </text>
            </g>
          ))}
          {tag && lineLabel && (
            <g>
              {tag.solid && <rect x={tag.x} y={tag.y} width={tag.w} height={tag.h} rx="4" fill="var(--surface-solid)" />}
              <text
                x={tag.x + tag.w / 2}
                y={tag.y + 10.5}
                textAnchor="middle"
                fontSize={VALUE_FONT}
                fontWeight={600}
                fill="var(--fg-2)"
                stroke="var(--surface-solid)"
                strokeWidth="3"
                strokeLinejoin="round"
                paintOrder="stroke"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {lineLabel}
              </text>
            </g>
          )}
          {bars.map((b, i) => (
            <rect
              key={`hit-${i}`}
              x={b.cx - slot / 2}
              y={0}
              width={slot}
              height={H}
              fill="transparent"
              onPointerEnter={(e) => e.pointerType === "mouse" && setActive(i)}
              onClick={() => setActive((a) => (a === i ? null : i))}
            />
          ))}
        </svg>
      )}
      {hovered && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xl border border-line-strong bg-[var(--surface-solid)] px-3 py-2 text-xs shadow-lg"
          style={{ left: Math.min(Math.max(hovered.cx, 64), width - 64), top: Math.max(hovered.barTop - 24, 0) }}
          aria-hidden
        >
          <p className="text-muted">{shortDate(hovered.date)}</p>
          <p className="num mt-0.5 font-semibold text-fg">
            {count(hovered.views)} {/* "views" follows the legend's word */}
          </p>
          {followers > 0 && <p className="num mt-0.5 text-fg-2">{pctLabel(hovered.views)}</p>}
        </div>
      )}
    </div>
  );
}
