// The AI market review on a price: what it changed and why, or that one is on its way.
// The review never sets a price alone: it's one capped step (-30% to +40%) on the formula.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { post } from "@/lib/api";
import type { AiPriceReview } from "@/lib/api-types";
import { cn } from "@/lib/utils";

function pct(n: number) {
  return `${n > 0 ? "+" : ""}${n}%`;
}

export function AiReviewNote({ review, creatorId, className }: { review?: AiPriceReview | null; creatorId?: string; className?: string }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: () => post<AiPriceReview>(`/creators/${creatorId}/price-review`),
    onSuccess: () => {
      void qc.invalidateQueries({ predicate: (q) => ["fair", "money", "home", "rates", "kit"].includes(String(q.queryKey[0])) });
      toast.success("AI review added to your price");
    },
    onError: (e) => toast.error((e as Error).message),
  });
  if (!review || review.status === "off") return null;
  if (review.status === "pending") {
    return (
      <div className={cn("flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface-2/60 px-4 py-3 text-sm text-fg-2", className)}>
        <Sparkles className="size-4 shrink-0 text-muted" aria-hidden />
        <p className="min-w-0 flex-1">An AI review of this price is being prepared from your latest numbers. Until then, it's the formula's price.</p>
        {creatorId && (
          <Button size="sm" variant="outline" loading={run.isPending} onClick={() => run.mutate()}>
            Review now
          </Button>
        )}
      </div>
    );
  }
  return (
    <div className={cn("rounded-2xl border border-line bg-surface-2/60 px-4 py-3 text-sm", className)}>
      <p className="flex flex-wrap items-center gap-2 font-medium">
        <Sparkles className="size-4 shrink-0 text-[var(--chart-up)]" aria-hidden />
        AI market review: <span className="num">{pct(review.adjust_pct)}</span>
        <span className="text-xs font-normal text-muted">confidence {review.confidence} · capped at -30% to +40%</span>
      </p>
      <ul className="mt-1.5 space-y-1 text-[13px] leading-relaxed text-fg-2">
        {review.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      {review.suggested_niche_label && (
        <p className="mt-1.5 text-xs text-muted">From your titles, your content also reads as {review.suggested_niche_label.toLowerCase()}. You can change your niche in Profile.</p>
      )}
    </div>
  );
}
