import { Info, ShieldAlert } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger, Tooltip } from "@/components/ui/overlays";
import type { Confidence, Estimate, Why } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIDENCE_LABEL: Record<Confidence, string> = {
  low: "Low confidence",
  medium: "Medium confidence",
  high: "High confidence",
};

/** Every score, price and recommendation carries one of these. */
export function WhyPopover({
  why,
  label = "Why?",
  className,
  subject,
}: {
  why: Why;
  label?: string;
  className?: string;
  subject?: string;
}) {
  const hasSimulated = (why.simulated_fields?.length ?? 0) > 0;
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-accent underline decoration-dotted underline-offset-4 hover:bg-accent-soft",
          className,
        )}
        aria-label={subject ? `Why: ${subject}` : "Why?"}
      >
        <Info className="size-3.5" aria-hidden />
        {label}
      </PopoverTrigger>
      <PopoverContent className="w-[22rem]">
        <p className="font-display text-[15px] font-semibold">{why.title ?? "Why we suggest this"}</p>
        <ul className="mt-2.5 space-y-2">
          {why.reasons.map((r) => (
            <li key={r} className="flex gap-2 text-[13px] leading-relaxed text-fg-2">
              <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-signature" aria-hidden />
              <span>{r}</span>
            </li>
          ))}
        </ul>
        {why.inputs && why.inputs.length > 0 && (
          <dl className="mt-3 divide-y divide-line rounded-xl border border-line text-[13px]">
            {why.inputs.map((inp) => (
              <div key={inp.label} className="flex items-center justify-between gap-3 px-3 py-2">
                <dt className="text-muted">{inp.label}</dt>
                <dd className="num flex items-center gap-1.5 text-right font-medium text-fg">
                  {inp.value}
                  {inp.provenance === "simulated" && <SimulatedChip />}
                  {inp.provenance === "real" && (
                    <span className="text-[10px] font-semibold uppercase tracking-wide text-success">Real</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        )}
        {hasSimulated && (
          <p className="mt-3 flex gap-2 rounded-xl bg-warn-soft p-2.5 text-xs leading-relaxed text-warn">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>
              Depends on simulated data ({why.simulated_fields!.join(", ")}). These values were not shared by the
              creator and are illustrative for the demo.
            </span>
          </p>
        )}
        {why.source && <p className="mt-2 text-[11px] text-muted">{why.source}</p>}
      </PopoverContent>
    </Popover>
  );
}

export function SimulatedChip({ className }: { className?: string }) {
  return (
    <Tooltip content="Not shared by the creator; illustrative for the demo.">
      <span
        tabIndex={0}
        className={cn(
          "inline-flex h-[18px] items-center rounded-full border border-dashed border-warn/60 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-warn",
          className,
        )}
      >
        Simulated
      </span>
    </Tooltip>
  );
}

/** "Estimate, not a promise" with its assumptions one tap away. */
export function EstimateNote({ estimate, className }: { estimate?: Pick<Estimate, "assumptions" | "confidence">; className?: string }) {
  if (!estimate) {
    return <span className={cn("text-[11px] text-muted", className)}>Estimate, not a promise</span>;
  }
  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex items-center gap-1 text-[11px] text-muted underline decoration-dotted underline-offset-4 hover:text-fg",
          className,
        )}
      >
        Estimate, not a promise
        <span aria-hidden>·</span>
        {CONFIDENCE_LABEL[estimate.confidence]}
      </PopoverTrigger>
      <PopoverContent>
        <p className="font-display text-sm font-semibold">What this estimate assumes</p>
        <ul className="mt-2 space-y-1.5">
          {estimate.assumptions.map((a) => (
            <li key={a} className="flex gap-2 text-[13px] leading-relaxed text-fg-2">
              <span className="mt-[7px] size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
              {a}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          {CONFIDENCE_LABEL[estimate.confidence]}. Ranges reflect real variation between reels and deals; nothing here
          is a promise of income or reach.
        </p>
      </PopoverContent>
    </Popover>
  );
}
