import { ShieldCheck, ShieldOff } from "lucide-react";
import { cn } from "@/lib/utils";

export type TeeStatus = "not_configured" | "available" | "failed";

/** Where a protected computation actually ran. Never says "TEE" unless attestation verified. */
export function ProtectedStatus({ processedIn, status, note, className }: { processedIn: "tee" | "server"; status: TeeStatus; note: string; className?: string }) {
  const tee = processedIn === "tee";
  return (
    <p className={cn("flex items-start gap-1.5 text-xs", tee ? "text-success" : "text-muted", className)}>
      {tee ? <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden /> : <ShieldOff className="mt-px size-3.5 shrink-0" aria-hidden />}
      <span>
        <span className="font-medium">{tee ? "Protected computation" : status === "failed" ? "TEE check failed" : "No TEE configured"}:</span> {note}
      </span>
    </p>
  );
}
