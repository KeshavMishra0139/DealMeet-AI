// Public creator search: creators who keep a public page, matched on their own words (name,
// handle, tags, niche, city, language). Visitors see the best few and are asked to sign in
// for the rest; the server enforces the limit.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowRight, Lock, MapPin, Search, Sparkles } from "lucide-react";
import { useDeferredValue, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { ChipPicker, countSearch, JoinPrompt, SEARCHES_BEFORE_PROMPT, useViewerRole, type NicheCount } from "@/components/shared/Explore";
import { RowBones } from "@/components/shared/Skeletons";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
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

interface Results {
  items: CreatorCard[];
  total: number;
  limit: number;
  locked: boolean;
  niche_hint: { id: string; label: string } | null;
  niches: NicheCount[];
}

export default function Creators() {
  useTheme("creator");
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const niche = params.get("niche");
  const query = useDeferredValue(q.trim());
  const role = useViewerRole();
  const home = useSignedInHome().to;
  const [prompt, setPrompt] = useState(false);

  const search = new URLSearchParams();
  if (query) search.set("q", query);
  if (niche) search.set("niche", niche);
  const r = useQuery({
    queryKey: ["public-creators", search.toString(), role],
    queryFn: () => api<Results>(`/directory/creators?${search}`, { role }),
    placeholderData: keepPreviousData,
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

  const pickNiche = (id: string | null) => {
    const next = new URLSearchParams(params);
    if (id) next.set("niche", id);
    else next.delete("niche");
    setParams(next, { replace: true });
  };
  const d = r.data;
  const more = d ? d.total - d.items.length : 0;

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

        <main id="main" className="mt-8">
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">Creators</h1>
          <p className="mt-1 max-w-2xl text-[15px] text-fg-2">
            Search by what they make, a topic, a city or a language. Each card opens the page the creator shares publicly.
          </p>

          <form role="search" className="card-surface mt-6 rounded-[var(--radius-card)] p-4" onSubmit={(e) => e.preventDefault()}>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Try 'Tamil breakfast', 'Bengali', 'yoga' or '@handle'"
                aria-label="Search creators"
                maxLength={80}
                className="pl-9"
              />
            </div>
            <ChipPicker options={(d?.niches ?? []).map((n) => ({ id: n.id, label: n.label }))} value={niche} onPick={pickNiche} noun="niche" className="mt-3" />
          </form>

          {d?.niche_hint && !niche && (
            <button
              type="button"
              onClick={() => pickNiche(d.niche_hint!.id)}
              className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent-soft px-3 py-1.5 text-[13px] font-medium text-accent"
            >
              <Sparkles className="size-3.5" aria-hidden /> Only {d.niche_hint.label.toLowerCase()} creators
            </button>
          )}

          {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
          {!d && !r.isError && <RowBones rows={4} className="mt-6" />}
          {d && (
            <section aria-label="Results" className={cn("mt-6 transition-opacity", r.isFetching && "opacity-60")}>
              <p className="mb-3 text-sm text-fg-2" aria-live="polite">
                {d.total === 0
                  ? "No creators match that yet. Try a broader word, or a niche."
                  : query
                    ? `${d.total} creator${d.total === 1 ? "" : "s"} for "${query}", best matches first`
                    : `${d.total} creator${d.total === 1 ? "" : "s"}`}
              </p>
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {d.items.map((c, i) => (
                  <li key={c.handle}>
                    <CreatorTile c={c} best={!!query && i === 0} />
                  </li>
                ))}
                {d.locked && (
                  <li>
                    <button
                      type="button"
                      onClick={() => setPrompt(true)}
                      className="flex h-full min-h-[148px] w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-line-strong p-4 text-center transition-colors hover:border-accent/60"
                    >
                      <Lock className="size-5 text-accent" aria-hidden />
                      <span className="font-medium">
                        {more} more creator{more === 1 ? "" : "s"}
                      </span>
                      <span className="text-xs text-muted">Want to know more? Log in or sign up</span>
                    </button>
                  </li>
                )}
              </ul>
            </section>
          )}
        </main>
      </div>
      <JoinPrompt kind="creators" open={prompt} onOpenChange={setPrompt} more={d?.locked ? more : undefined} />
    </div>
  );
}

export function CreatorTile({ c, best }: { c: CreatorCard; best?: boolean }) {
  return (
    <Link to={c.page} className="card-surface group flex h-full flex-col rounded-xl p-4 transition-colors hover:border-accent/50">
      <span className="flex items-center gap-3">
        <Avatar name={c.name} hue={c.avatar_hue} size={40} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{c.name}</span>
          <span className="block truncate text-xs text-muted">@{c.handle}</span>
        </span>
        <ArrowRight className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
      </span>
      <span className="mt-3 flex flex-wrap items-center gap-1.5">
        {best && (
          <Badge size="sm" variant="success">
            Best match
          </Badge>
        )}
        {c.niche && <Badge size="sm">{c.niche.label}</Badge>}
        {c.followers_band && (
          <Badge size="sm" variant="outline">
            {c.followers_band} followers
          </Badge>
        )}
      </span>
      {(c.city || c.languages.length > 0) && (
        <span className="mt-2 flex items-center gap-1 text-xs text-muted">
          {c.city && <MapPin className="size-3.5" aria-hidden />}
          {[c.city, c.languages.join(", ")].filter(Boolean).join(" · ")}
        </span>
      )}
      {c.matched.length > 0 ? (
        <span className="mt-2 text-xs text-fg-2">
          <span className="text-muted">Matches: </span>
          {c.matched.join(", ")}
        </span>
      ) : (
        c.tags.length > 0 && <span className="mt-2 truncate text-xs text-fg-2">{c.tags.join(" · ")}</span>
      )}
    </Link>
  );
}
