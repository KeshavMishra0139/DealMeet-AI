import { Info } from "lucide-react";
import { RangeValue } from "@/components/shared/Estimate";
import { Badge } from "@/components/ui/badge";
import { count } from "@/lib/format";
import type { FormatPrice } from "@/lib/youtube-types";

/** An estimate for one video format (Shorts or long videos), or why there isn't one. */
export function FormatPriceCard({ price, title }: { price: FormatPrice; title: string }) {
  return (
    <article className="card-surface rounded-[var(--radius-card)] p-5">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="flex gap-1.5">
          {price.ai && (
            <Badge size="sm" variant="outline">
              AI-reviewed
            </Badge>
          )}
          <Badge size="sm" variant="outline">
            Estimate
          </Badge>
        </span>
      </div>
      {price.enough_data && price.estimate ? (
        <>
          <p className="mt-3">
            <RangeValue estimate={price.estimate} size="xl" className="text-[26px] sm:text-[34px]" />
          </p>
          <p className="mt-1 text-xs text-muted">
            Median {count(price.median_views ?? 0)} views across your last {price.videos} {price.format === "shorts" ? "Shorts" : "long videos"} · confidence{" "}
            {price.estimate.confidence}
          </p>
          <ul className="mt-4 space-y-1.5 text-[13px] leading-relaxed text-fg-2">
            {price.why?.map((w) => (
              <li key={w} className="flex gap-2">
                <Info className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />
                {w}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-3 text-sm text-fg-2">{price.reason}</p>
      )}
    </article>
  );
}
