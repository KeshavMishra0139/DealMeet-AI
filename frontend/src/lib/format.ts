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

/** ₹17K–18K. Shares a unit suffix when both ends use the same one. */
export function inrRange(low: number, high: number) {
  const a = shortNumber(low, low >= 1e5 ? 1 : 0);
  const b = shortNumber(high, high >= 1e5 ? 1 : 0);
  if (a === b) return `₹${a}`;
  return `₹${a}–${b}`;
}

export function pct(value: number, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 0) {
  const s = (value * 100).toFixed(digits);
  return value > 0 ? `+${s}%` : `${s}%`;
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
const dateYearFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });

export function shortDate(iso: string, withYear = false) {
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00+05:30` : iso);
  return (withYear ? dateYearFmt : dateFmt).format(d);
}

export function timeOfDay(iso: string) {
  return timeFmt.format(new Date(iso));
}
