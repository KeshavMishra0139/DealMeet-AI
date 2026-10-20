// Public creator search, like a search engine: nothing is listed until someone searches. Then
// one ranked list: DealMeet creators who keep a public page, matched on their own words (name,
// handle, channel names, tags, niche, city, language), then public YouTube channels that match.
// One or more niches narrow it, and on their own list each niche's top creators. Visitors see
// the best few and are asked to sign in for the rest; the server enforces the limit.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { MapPin, Sparkles, Youtube } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import {
  ChipPicker,
  countSearch,
  JoinPrompt,
  MoreRow,
  ResultRow,
  SEARCHES_BEFORE_PROMPT,
  SearchBox,
  useNiches,
  useSettled,
  useViewerRole,
  type NicheCount,
} from "@/components/shared/Explore";
import { RowBones } from "@/components/shared/Skeletons";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useSignedInHome } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export interface CreatorCard {
  handle: string;
  name: string;
  avatar_hue: number;
  niche: { id: string; label: string } | null;
  languages: string[];
  city: string | null;
  tags: string[];
  followers_band: string | null;
  matched: string[];
  page: string;
}

export interface YouTubeCard {
  channel_id: string;
  title: string;
  handle: string | null;
  thumbnail: string | null;
  description: string;
  subscribers: number | null;
  videos: number;
  url: string;
  on_dealmeet: string | null;
}

interface Results {
  items: CreatorCard[];
  total: number;
  limit: number;
  locked: boolean;
  niche_hint: { id: string; label: string } | null;
  niches: NicheCount[];
  youtube: { items: YouTubeCard[]; note: string | null };
  idle: boolean;
}

/** 950, 45K, 1.8L, 2.2Cr: how subscriber counts read in India. */
function short(n: number): string {
  const one = (x: number) => (x >= 100 ? Math.round(x) : Math.round(x * 10) / 10).toString();
  if (n >= 1e7) return `${one(n / 1e7)}Cr`;
  if (n >= 1e5) return `${one(n / 1e5)}L`;
  if (n >= 1e3) return `${one(n / 1e3)}K`;
  return String(n);
}

export default function Creators() {
  useTheme("creator");
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const niches = (params.get("niche") ?? "").split(",").filter(Boolean);
  const niche = niches.join(",");
  // Search once typing settles (or on Enter), so each key press isn't a search: YouTube's quota is small.
  const settled = useSettled(q.trim(), 450);
  const [now, setNow] = useState<string | null>(null);
  const query = now ?? settled;
  useEffect(() => setNow(null), [settled]);
  const role = useViewerRole();
  const home = useSignedInHome().to;
  const [prompt, setPrompt] = useState(false);
  const allNiches = useNiches();
  const searching = !!query || niches.length > 0;

  const search = new URLSearchParams();
  if (query) search.set("q", query);
  if (niche) search.set("niche", niche);
  const r = useQuery({
    queryKey: ["public-creators", search.toString(), role],
    queryFn: () => api<Results>(`/directory/creators?${search}`, { role }),
    placeholderData: keepPreviousData,
    enabled: searching,
  });

  // Keep the address in step, so a search can be shared or reloaded.
  useEffect(() => {
    const next = new URLSearchParams(params);
    if (query) next.set("q", query);
    else next.delete("q");
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  // Visitors who keep searching are asked, once, whether they'd like to join.
  const asked = useRef(false);
  useEffect(() => {
    if (role || !query || asked.current) return;
    const t = setTimeout(() => {
      if (countSearch("creators") >= SEARCHES_BEFORE_PROMPT) {
        asked.current = true;
        setPrompt(true);
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [query, role]);

  const setNiches = (ids: string[]) => {
    const next = new URLSearchParams(params);
    if (ids.length) next.set("niche", ids.join(","));
    else next.delete("niche");
    setParams(next, { replace: true });
  };
  const pickNiche = (id: string | null, on?: boolean) => {
    if (!id) return;
    setNiches(on ? [...niches, id].slice(-5) : niches.filter((n) => n !== id));
  };
  const d = searching ? r.data : undefined;
  const more = d ? d.total - d.items.length : 0;
  const nicheOptions = (allNiches.data ?? []).map((n) => ({ id: n.id, label: n.label }));

  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <div className="relative z-10 mx-auto max-w-5xl px-4 py-6 sm:py-10">
        <header className="flex items-center justify-between gap-3">
          <Link to="/" aria-label="DealMeet AI home" className="rounded-lg">
            <Wordmark />
          </Link>
          <div className="flex items-center gap-1">
            <Button asChild size="sm" variant="ghost">
              <Link to="/brands">Brands</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={home ?? "/login"}>{home ? "Your dashboard" : "Sign in"}</Link>
            </Button>
          </div>
        </header>

        <main id="main">
          {/* One search bar that stays put while the page changes around it, so typing is
              never interrupted when results arrive. Nobody is listed until someone searches. */}
          <section className={cn("mx-auto", searching ? "mt-6 max-w-3xl" : "mt-[12vh] max-w-2xl text-center")}>
            {searching ? (
              <h1 className="sr-only">Creator search</h1>
            ) : (
              <div>
                <h1 className="font-display text-[32px] font-semibold tracking-tight sm:text-[44px]">Search creators</h1>
                <p className="mt-2 text-[15px] text-fg-2">Creators on DealMeet first, then matching channels on YouTube.</p>
              </div>
            )}
            <div className={searching ? "" : "mt-7"}>
              <SearchBox
                value={q}
                onChange={setQ}
                onSubmit={(t) => setNow(t)}
                placeholder="Search creators: a name, @handle, topic, city or language"
                label="Search creators"
                suggestFor="creators"
                big={!searching}
              />
            </div>
            <p className={cn("mb-2 mt-6 text-xs font-medium text-muted", searching && "sr-only")}>Or browse one or more niches</p>
            <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-1", searching ? "mt-3" : "justify-center")}>
              <ChipPicker options={nicheOptions} value={niches} onPick={pickNiche} noun="niche" className={searching ? undefined : "justify-center"} />
              {niches.length > 0 && (
                <button type="button" onClick={() => setNiches([])} className="text-xs font-medium text-muted hover:text-fg">
                  Clear niches
                </button>
              )}
            </div>
          </section>

          {searching && (
            <div className="mx-auto max-w-3xl">
              {d?.niche_hint && !niche && (
                <button
                  type="button"
                  onClick={() => setNiches([d.niche_hint!.id])}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] font-medium text-accent"
                >
                  <Sparkles className="size-3.5" aria-hidden /> Only {d.niche_hint.label.toLowerCase()} creators
                </button>
              )}

              {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
              {!d && !r.isError && <RowBones rows={4} className="mt-6" />}
              {d && (
                <section aria-label="Results" className={cn("mt-5 transition-opacity", r.isFetching && "opacity-60")}>
                  <p className="px-2 text-sm text-muted sm:px-3" aria-live="polite">
                    {summary(d, query, niches.length)}
                  </p>
                  <ul className="mt-1 divide-y divide-line">
                    {d.items.map((c, i) => (
                      <li key={c.handle}>
                        <CreatorRow c={c} best={!!query && i === 0} />
                      </li>
                    ))}
                  </ul>
                  {d.locked && <MoreRow text={`${more} more creator${more === 1 ? "" : "s"} on DealMeet`} onClick={() => setPrompt(true)} />}

                  {(d.youtube.items.length > 0 || d.youtube.note) && (
                    <section aria-labelledby="on-youtube" className="mt-6">
                      <h2 id="on-youtube" className="flex items-center gap-2 px-2 text-sm font-semibold sm:px-3">
                        <Youtube className="size-4 text-[#ff0033]" aria-hidden /> From YouTube
                        <span className="font-normal text-muted">· public channel info, no prices</span>
                      </h2>
                      {d.youtube.note && <p className="mt-1 px-2 text-sm text-fg-2 sm:px-3">{d.youtube.note}</p>}
                      <ul className="mt-1 divide-y divide-line">
                        {d.youtube.items.map((y) => (
                          <li key={y.channel_id}>
                            <ChannelRow y={y} />
                          </li>
                        ))}
                      </ul>
                      {!role && d.youtube.items.length >= 4 && <MoreRow text="More channels" onClick={() => setPrompt(true)} />}
                    </section>
                  )}
                </section>
              )}
            </div>
          )}
        </main>
      </div>
      <JoinPrompt kind="creators" open={prompt} onOpenChange={setPrompt} more={d?.locked ? more : undefined} />
    </div>
  );
}

function summary(d: Results, query: string, niches: number): string {
  const yt = d.youtube.items.length;
  if (d.total === 0) return yt ? `No DealMeet creators match${query ? ` "${query}"` : ""} yet. Here's who matches on YouTube.` : "No creators match that yet. Try a broader word, or a niche.";
  const what = query ? ` for "${query}"` : niches ? ` in ${niches === 1 ? "this niche" : "these niches"}` : "";
  return `${d.total} creator${d.total === 1 ? "" : "s"} on DealMeet${what}${yt ? `, plus ${yt} on YouTube` : ""}`;
}

function CreatorRow({ c, best }: { c: CreatorCard; best?: boolean }) {
  return (
    <ResultRow
      to={c.page}
      media={<Avatar name={c.name} hue={c.avatar_hue} size={64} />}
      title={c.name}
      meta={["@" + c.handle, c.niche?.label, c.followers_band && `${c.followers_band} followers`].filter(Boolean).join(" · ")}
    >
      {(c.city || c.languages.length > 0) && (
        <span className="flex items-center gap-1 text-xs text-muted">
          {c.city && <MapPin className="size-3.5" aria-hidden />}
          {[c.city, c.languages.join(", ")].filter(Boolean).join(" · ")}
        </span>
      )}
      {c.matched.length > 0 ? (
        <span className="block">
          <span className="text-muted">Matches: </span>
          {c.matched.join(", ")}
        </span>
      ) : (
        c.tags.length > 0 && <span className="block truncate">{c.tags.join(" · ")}</span>
      )}
      <span className="flex flex-wrap gap-1.5">
        <Badge size="sm" variant="accent">
          On DealMeet
        </Badge>
        {best && (
          <Badge size="sm" variant="success">
            Best match
          </Badge>
        )}
      </span>
    </ResultRow>
  );
}

function ChannelRow({ y }: { y: YouTubeCard }) {
  const media = y.thumbnail ? (
    <ChannelPicture src={y.thumbnail} />
  ) : (
    <span className="grid size-16 place-items-center rounded-full bg-surface-2" aria-hidden>
      <Youtube className="size-7 text-[#ff0033]" />
    </span>
  );
  const meta = [y.handle, y.subscribers !== null && `${short(y.subscribers)} subscribers`, `${short(y.videos)} videos`].filter(Boolean).join(" · ");
  return (
    <ResultRow
      to={y.on_dealmeet ?? undefined}
      href={y.on_dealmeet ? undefined : y.url}
      label={y.on_dealmeet ? undefined : `${y.title} on YouTube (opens in a new tab)`}
      media={media}
      title={y.title}
      meta={meta}
    >
      {y.description && <span className="line-clamp-2 block">{y.description}</span>}
      <span className="flex flex-wrap gap-1.5">
        {y.on_dealmeet ? (
          <Badge size="sm" variant="accent">
            On DealMeet
          </Badge>
        ) : (
          <Badge size="sm" variant="outline">
            Not on DealMeet yet
          </Badge>
        )}
      </span>
    </ResultRow>
  );
}

/** The channel's picture from YouTube, or the YouTube mark if it can't load. */
function ChannelPicture({ src }: { src: string }) {
  const [failed, setFailed] = useState(false);
  if (failed)
    return (
      <span className="grid size-16 place-items-center rounded-full bg-surface-2" aria-hidden>
        <Youtube className="size-7 text-[#ff0033]" />
      </span>
    );
  return (
    <img
      src={src}
      alt=""
      width={64}
      height={64}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className="size-16 rounded-full bg-surface-2 object-cover"
    />
  );
}
