import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, ExternalLink, Search, Youtube } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChannelAvatar } from "@/components/shared/ChannelAvatar";
import { FormatPriceCard } from "@/components/shared/FormatPriceCard";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/form";
import { api, post } from "@/lib/api";
import { count, shortDate } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { WorthReport } from "@/lib/youtube-types";

interface Meta {
  niches: { id: string; label: string }[];
}

/** Public, no sign-in: a creator types their YouTube handle and sees real numbers and a price estimate. */
export default function Worth() {
  useTheme("creator");
  const [params, setParams] = useSearchParams();
  const [handle, setHandle] = useState(params.get("handle") ?? "");
  const [niche, setNiche] = useState("");
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta") });
  const lookup = useMutation({
    mutationFn: (v: { handle: string; niche: string }) => post<WorthReport>("/youtube/preview", { handle: v.handle, niche: v.niche || null }),
  });
  const r = lookup.data;

  const run = (h = handle, n = niche) => {
    if (h.trim().length < 2) return;
    setParams({ handle: h.trim() }, { replace: true });
    lookup.mutate({ handle: h.trim(), niche: n });
  };

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto flex min-h-dvh max-w-4xl flex-col px-4 py-5 sm:px-6 sm:py-8">
        <header className="flex items-center justify-between">
          <Link to="/" className="rounded-lg" aria-label="JodiDar AI home">
            <Wordmark />
          </Link>
          <Button asChild variant="outline" size="sm">
            <Link to="/login?role=creator">Sign in</Link>
          </Button>
        </header>

        <main id="main" className="mt-10 flex-1 sm:mt-14">
          <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-2">
            <Youtube className="size-3.5 text-accent" aria-hidden /> Free, no sign-in, official YouTube data
          </p>
          <h1 className="mt-4 font-display text-[32px] font-semibold leading-tight tracking-tight sm:text-5xl">What am I worth?</h1>
          <p className="mt-3 max-w-2xl text-[15px] text-fg-2 sm:text-base">
            Type your YouTube handle. We read your channel's public numbers and estimate a fair fee for a brand video from the views your recent videos
            get, not your subscriber count. Shorts and long videos are priced separately.
          </p>

          <form
            className="card-surface mt-6 grid gap-3 rounded-[var(--radius-card)] p-4 sm:grid-cols-[1fr_220px_auto] sm:items-end sm:p-5"
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            <div>
              <Label htmlFor="worth-handle">YouTube handle or channel link</Label>
              <Input id="worth-handle" value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@yourchannel" required autoComplete="off" />
            </div>
            <div>
              <Label htmlFor="worth-niche">Niche</Label>
              <Select
                id="worth-niche"
                value={niche}
                onChange={(e) => {
                  setNiche(e.target.value);
                  if (r) run(handle, e.target.value);
                }}
              >
                <option value="">Detect from my channel</option>
                {meta.data?.niches.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" variant="primary" loading={lookup.isPending}>
              {!lookup.isPending && <Search aria-hidden />} Check my price
            </Button>
          </form>

          {lookup.isError && (
            <p role="alert" className="mt-4 rounded-2xl border border-danger/40 bg-danger-soft p-4 text-sm">
              {(lookup.error as Error).message}
            </p>
          )}

          {r && (
            <div className="mt-8 space-y-5" aria-live="polite">
              <section aria-labelledby="channel" className="card-surface flex flex-wrap items-center gap-4 rounded-[var(--radius-card)] p-5">
                <ChannelAvatar src={r.channel.thumbnail} name={r.channel.title} size={56} />
                <div className="min-w-0 flex-1">
                  <h2 id="channel" className="flex flex-wrap items-center gap-2 font-display text-xl font-semibold">
                    {r.channel.title} <SourceBadge source={r.source} fetchedAt={r.fetched_at} />
                  </h2>
                  <p className="text-sm text-muted">{r.channel.handle}</p>
                </div>
                <dl className="grid w-full grid-cols-3 gap-3 text-center sm:w-auto">
                  <Stat k="Subscribers" v={r.channel.subscribers == null ? "Hidden" : count(r.channel.subscribers)} />
                  <Stat k="Total views" v={count(r.channel.total_views)} />
                  <Stat k="Videos" v={count(r.channel.video_count)} />
                </dl>
              </section>

              <p className="text-sm text-fg-2">
                Niche: <span className="font-medium text-fg">{r.niche_label}</span>
                {r.niche_guessed ? " (guessed from your channel's YouTube topics; change it above)" : ""}.
              </p>

              <div className="grid gap-4 md:grid-cols-2">
                <FormatPriceCard price={r.prices.shorts} title="One brand Short" />
                <FormatPriceCard price={r.prices.long} title="One brand integration in a long video" />
              </div>
              <p className="text-xs text-muted">Estimates, not promises. Brands and creators agree the actual fee.</p>

              {r.notes.length > 0 && (
                <ul className="space-y-1.5 text-sm text-fg-2">
                  {r.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}

              {r.videos.length > 0 && (
                <section aria-labelledby="recent" className="card-surface rounded-[var(--radius-card)] p-5">
                  <h2 id="recent" className="text-sm font-semibold">
                    Recent videos
                  </h2>
                  <ul className="mt-3 divide-y divide-line">
                    {r.videos.map((v) => (
                      <li key={v.post_id} className="flex items-center gap-3 py-2.5 text-[13px]">
                        <Badge size="sm" variant="outline">
                          {v.format === "shorts" ? "Short" : "Long"}
                        </Badge>
                        <a href={v.permalink} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate hover:text-accent">
                          {v.title} <ExternalLink className="inline size-3" aria-hidden />
                        </a>
                        <span className="num shrink-0 text-muted">{shortDate(v.published_at)}</span>
                        <span className="num w-16 shrink-0 text-right font-medium">{count(v.views)}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border border-line bg-surface-2 p-5">
                <p className="flex-1 text-sm text-fg-2">
                  Create a creator account to link this channel, keep these numbers current and get matched with brands.
                </p>
                <Button asChild variant="primary">
                  <Link to="/login?role=creator">
                    Get started <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-[11px] text-muted">{k}</dt>
      <dd className="num font-display text-lg font-semibold">{v}</dd>
    </div>
  );
}
