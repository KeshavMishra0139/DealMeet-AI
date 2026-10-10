import { ShieldAlert, ShieldCheck, ShieldHalf } from "lucide-react";
import { Tooltip } from "@/components/ui/overlays";
import type { TrustInfo } from "@/lib/api-types";
import { cn } from "@/lib/utils";

/** Silent Trust Score: a small shield with the top two reasons on hover. */
export function TrustBadge({ trust, className }: { trust: TrustInfo | null | undefined; className?: string }) {
  if (!trust) return null;
  const Icon = trust.level === "high" ? ShieldCheck : trust.level === "medium" ? ShieldHalf : ShieldAlert;
  const tone = trust.level === "high" ? "text-success" : trust.level === "medium" ? "text-warn" : "text-danger";
  return (
    <Tooltip
      content={
        <span className="block">
          <span className="block font-semibold">Trust {trust.score}/100</span>
          {trust.reasons.map((r) => (
            <span key={r} className="block text-muted">
              {r}
            </span>
          ))}
          <span className="mt-1 block text-[10px] text-muted">
            {trust.simulated?.length
              ? `Partly from sample data (${trust.simulated.join(", ")}), marked simulated.`
              : "From insights connected via the official API."}
          </span>
        </span>
      }
    >
      <span
        tabIndex={0}
        aria-label={`Trust score ${trust.score} out of 100. ${trust.reasons.join(". ")}`}
        className={cn("num inline-flex items-center gap-1 rounded-full text-xs font-semibold", tone, className)}
      >
        <Icon className="size-3.5" aria-hidden />
        {trust.score}
      </span>
    </Tooltip>
  );
}
