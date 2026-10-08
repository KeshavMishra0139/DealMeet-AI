import type { Estimate } from "@/lib/types";
import { count, inrRange } from "@/lib/format";
import { cn } from "@/lib/utils";

const PERIOD: Record<string, string> = { month: "/ month", reel: "/ reel", week: "this week", deal: "per deal" };

/** Formats an estimate range by its unit: ₹14K–19K / month, +2.8L–3.5L views. */
export function rangeText(e: Estimate) {
  if (e.unit === "inr") return inrRange(e.low, e.high);
  const a = count(e.low);
  const b = count(e.high);
  const r = a === b ? a : `${a}–${b}`;
  return `+${r} ${e.unit === "views" ? "views" : e.unit === "followers" ? "followers" : "reach"}`;
}

export function periodText(e: Estimate) {
  if (e.unit !== "inr") return e.period === "week" ? "this week" : e.period === "month" ? "a month" : "";
  return e.period ? PERIOD[e.period] ?? "" : "";
}

export function RangeValue({ estimate, className, size = "lg" }: { estimate: Estimate; className?: string; size?: "md" | "lg" | "xl" }) {
  const sizes = { md: "text-lg", lg: "text-2xl", xl: "text-[34px] leading-none" };
  return (
    <span className={cn("num font-display font-semibold tracking-tight", sizes[size], className)}>
      {rangeText(estimate)}
      {periodText(estimate) && (
        <span className="ml-1.5 font-sans text-[13px] font-normal tracking-normal text-muted">{periodText(estimate)}</span>
      )}
    </span>
  );
}
