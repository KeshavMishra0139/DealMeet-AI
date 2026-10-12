import { CircleDot, FilePen, Lock, Pause } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { CampaignStatus } from "@/lib/market-types";

const LOOK: Record<CampaignStatus, { label: string; variant: "success" | "neutral" | "warn" | "outline"; Icon: typeof CircleDot }> = {
  draft: { label: "Draft", variant: "outline", Icon: FilePen },
  live: { label: "Live", variant: "success", Icon: CircleDot },
  paused: { label: "Paused", variant: "warn", Icon: Pause },
  closed: { label: "Closed", variant: "neutral", Icon: Lock },
};

/** A campaign's state, with an icon and a word so it never rests on colour alone. */
export function CampaignStatusBadge({ status, className }: { status: string; className?: string }) {
  const look = LOOK[(status === "open" ? "live" : status) as CampaignStatus] ?? LOOK.live;
  return (
    <Badge size="sm" variant={look.variant} className={className}>
      <look.Icon aria-hidden /> {look.label}
    </Badge>
  );
}
