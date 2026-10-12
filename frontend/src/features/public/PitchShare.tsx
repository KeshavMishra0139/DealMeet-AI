import { useQuery } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import { inrRange, shortDate } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import NotFound from "./NotFound";

interface Shared {
  subject: string;
  pitch: string;
  content_ideas: string[];
  lang: "en" | "hi";
  brand_name: string;
  sent_at: string;
  fan_proof: { label: string; links: string[] } | null;
  suggested_price_range: { range: { low: number; high: number }; deliverables: string } | null;
  creator: { name: string; handle: string; niche: string; languages: string[]; avatar_hue: number; page: string | null };
}

/** A pitch a creator shared with a brand that isn't on DealMeet AI. */
export default function PitchShare() {
  useTheme("creator");
  const { slug = "" } = useParams();
  const q = useQuery({ queryKey: ["shared-pitch", slug], queryFn: () => api<Shared>(`/p/${slug}`, { role: null }), retry: false });
  if (q.isError && (q.error as { status?: number }).status === 404) return <NotFound />;
  const p = q.data;
  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto max-w-2xl px-4 py-6 sm:py-10">
        <main id="main">
          {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
          {!p && !q.isError && <Skeleton className="h-96 rounded-[28px]" />}
          {p && (
            <article className="card-surface rounded-[28px] p-6" lang={p.lang}>
              <p className="text-xs text-muted">
                A pitch for {p.brand_name} · {shortDate(p.sent_at, true)}
              </p>
              <div className="mt-4 flex items-center gap-3">
                <Avatar name={p.creator.name} hue={p.creator.avatar_hue} size={48} />
                <div>
                  <h1 className="font-display text-xl font-semibold">{p.creator.name}</h1>
                  <p className="text-sm text-muted">
                    @{p.creator.handle} · {p.creator.niche} · {p.creator.languages.join(", ")}
                  </p>
                </div>
              </div>
              <h2 className="mt-6 font-display text-lg font-semibold">{p.subject}</h2>
              <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed text-fg-2">{p.pitch}</p>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-fg-2">
                {p.content_ideas.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
              {p.fan_proof && (
                <p className="mt-4 flex items-center gap-1.5 text-sm">
                  <Heart className="size-4 text-accent" aria-hidden /> {p.fan_proof.label}, from posts on their connected accounts.
                </p>
              )}
              {p.suggested_price_range && (
                <p className="mt-3 text-sm text-fg-2">
                  Estimated rate for {p.suggested_price_range.deliverables}: <span className="num font-medium">{inrRange(p.suggested_price_range.range.low, p.suggested_price_range.range.high)}</span>. An estimate, not a quote.
                </p>
              )}
              {p.creator.page && (
                <Button asChild variant="primary" className="mt-5">
                  <Link to={p.creator.page}>See {p.creator.name.split(" ")[0]}'s media kit</Link>
                </Button>
              )}
            </article>
          )}
        </main>
        <footer className="mt-8 flex items-center justify-center gap-2 text-xs text-muted">
          <Link to="/" aria-label="DealMeet AI home" className="rounded-lg">
            <Wordmark />
          </Link>
          <span>· Fair prices and escrow</span>
        </footer>
      </div>
    </div>
  );
}
