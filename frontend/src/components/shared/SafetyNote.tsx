import { ShieldAlert } from "lucide-react";
import { Tooltip } from "@/components/ui/overlays";
import type { Safety } from "@/lib/market-types";
import { cn } from "@/lib/utils";

/** Silent brand-safety note: one small chip, details on hover or focus. Nothing shows when there are no flags. */
export function SafetyNote({ safety, compact = false, className }: { safety: Safety | null | undefined; compact?: boolean; className?: string }) {
  if (!safety?.flags.length) return null;
  const summary = safety.flags.map((f) => f.label).join(". ");
  return (
    <Tooltip
      content={
        <span className="block max-w-64">
          <span className="block font-semibold">Brand-safety note</span>
          {safety.flags.map((f) => (
            <span key={f.id} className="mt-1 block">
              {f.label}
              <span className="block text-muted">Suggested to the creator: {f.fix}</span>
            </span>
          ))}
        </span>
      }
    >
      <span
        tabIndex={0}
        role="img"
        aria-label={`Brand-safety note: ${summary}`}
        className={cn(
          "inline-flex h-5 items-center gap-1 rounded-full bg-warn-soft text-[11px] font-medium text-warn",
          compact ? "w-5 justify-center" : "px-2",
          className,
        )}
      >
        <ShieldAlert className="size-3" aria-hidden />
        {!compact && (safety.flags.length === 1 ? safety.flags[0].label : `${safety.flags.length} safety notes`)}
      </span>
    </Tooltip>
  );
}
