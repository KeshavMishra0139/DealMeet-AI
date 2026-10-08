// Money and number formatting in Indian conventions (₹, lakh, crore).

const fullINR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** ₹17,400 */
export function inr(value: number) {
  return `₹${fullINR.format(Math.round(value))}`;
}

/** Compact rupees: ₹950, ₹7K, ₹17.4K, ₹1.2L, ₹2.4Cr */
export function inrShort(value: number, digits = 1) {
  return `₹${shortNumber(value, digits)}`;
}

export function shortNumber(value: number, digits = 1) {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const fmt = (n: number) => {
    const fixed = n.toFixed(digits);
    return fixed.replace(/\.0+$/, "");
  };
  if (abs >= 1e7) return `${sign}${fmt(abs / 1e7)}Cr`;
  if (abs >= 1e5) return `${sign}${fmt(abs / 1e5)}L`;
  if (abs >= 1e3) return `${sign}${fmt(abs / 1e3)}K`;
  return `${sign}${Math.round(abs)}`;
}

/** Social-style counts: 21.3K followers, 1.4L views */
export function count(value: number) {
  return shortNumber(value, 1);
}

/**
 * Rupee ranges that never hide precision: below ₹10K both ends are shown in
 * full (₹600–1,600); above, compact with one decimal (₹5.2K–12K, ₹21K–32.5K).
 */
export function inrRange(low: number, high: number) {
  if (high < 10_000) {
    const a = fullINR.format(Math.round(low));
    const b = fullINR.format(Math.round(high));
    return a === b ? `₹${a}` : `₹${a}–${b}`;
  }
  const a = shortNumber(low, 1);
  const b = shortNumber(high, 1);
  return a === b ? `₹${a}` : `₹${a}–${b}`;
}

export function pct(value: number, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 0) {
  const s = (value * 100).toFixed(digits);
  return value > 0 ? `+${s}%` : `${s}%`;
}

// Always show dates in India time, whatever the viewer's device timezone.
const TZ = "Asia/Kolkata";
const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: TZ });
const dateYearFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: TZ });
const timeFmt = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit", timeZone: TZ });

export function shortDate(iso: string, withYear = false) {
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00+05:30` : iso);
  return (withYear ? dateYearFmt : dateFmt).format(d);
}

export function timeOfDay(iso: string) {
  return timeFmt.format(new Date(iso));
}

const DELIVERABLES: Record<string, [string, string]> = {
  reel: ["reel", "reels"],
  short: ["short", "shorts"],
  story: ["story", "stories"],
  carousel: ["carousel", "carousels"],
  link_in_bio: ["link in bio", "links in bio"],
  live: ["live session", "live sessions"],
};

/** { kind: "story", count: 2 } -> "2 stories" */
export function deliverable(d: { kind: string; count: number }) {
  const [one, many] = DELIVERABLES[d.kind] ?? [d.kind, `${d.kind}s`];
  return `${d.count} ${d.count === 1 ? one : many}`;
}
