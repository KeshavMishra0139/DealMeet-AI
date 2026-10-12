import { Check } from "lucide-react";
import type { Deal } from "@/lib/deal-types";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Offer -> Contract -> Escrow -> Post submitted -> Approved -> Paid out, as a tracker. */
export function Rail({ steps, declined = false }: { steps: Deal["steps"]; declined?: boolean }) {
  return (
    <ol aria-label="Deal progress" className="grid grid-cols-1 gap-0 sm:grid-cols-6">
      {steps.map((s, i) => (
        <li key={s.key} className="relative flex items-start gap-3 pb-4 sm:flex-col sm:items-center sm:gap-2 sm:pb-0 sm:text-center">
          {i < steps.length - 1 && (
            <span
              aria-hidden
              className={cn(
                "absolute left-[13px] top-7 h-[calc(100%-20px)] w-0.5 sm:left-1/2 sm:top-[13px] sm:h-0.5 sm:w-full",
                s.status === "done" ? "bg-signature" : "bg-line-strong",
              )}
            />
          )}
          <span
            className={cn(
              "relative z-10 grid size-7 shrink-0 place-items-center rounded-full border-2 text-xs font-semibold",
              s.status === "done" && "border-transparent bg-signature-strong text-white",
              s.status === "current" && !declined && "border-accent bg-[var(--surface-solid)] text-accent ring-4 ring-accent-soft",
              (s.status === "upcoming" || (declined && s.status === "current")) && "border-line-strong bg-[var(--surface-solid)] text-muted",
            )}
            aria-hidden
          >
            {s.status === "done" ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
          </span>
          <span className="min-w-0">
            <span className={cn("block text-[13px] font-medium", s.status === "upcoming" ? "text-muted" : "text-fg")}>
              {s.label}
              <span className="sr-only">: {s.status === "done" ? "done" : s.status === "current" ? "current step" : "not yet"}</span>
            </span>
            {s.at && <span className="num block text-[11px] text-muted">{shortDate(s.at)}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
