import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, Megaphone, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { ChipPicker, countSearch, JoinPrompt, MoreRow, ResultRow, SEARCHES_BEFORE_PROMPT, SearchBox, useCategories, useSettled, useViewerRole } from "@/components/shared/Explore";
import { RowBones } from "@/components/shared/Skeletons";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, Switch } from "@/components/ui/form";
import { useSignedInHome } from "@/lib/session";
import { api } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export interface BrandCard {
  id: string;
  slug: string;
  name: string;
  category: string | null;
  kind: string;
  claimed: boolean;
  source: string | null;
  hue?: number;
  verified?: boolean;
  languages?: string[];
  cities?: string[];
  open_campaigns: number;
  public_handles?: { instagram?: string; youtube?: string };
  note?: string;
  /** Which of the search's words this brand matched, in plain words. */
  matched?: string[];
}

interface Results {
  items: BrandCard[];
  total: number;
  page: number;
  page_size: number;
  search: "all" | "regex" | "atlas";
  note: string | null;
  locked?: boolean;
  niche_hint?: { id: string; label: string } | null;
}

/** Brand search, like a search engine: nothing is listed until someone searches or picks a
 * category, then one ranked list. What a creator makes ("dosa") also finds brands that work
 * with creators like them. */
export default function Brands() {
  useTheme("creator");
  const [urlParams, setUrlParams] = useSearchParams();
  const [q, setQ] = useState(urlParams.get("q") ?? "");
  const category = urlParams.get("category") ?? "";
  const [city, setCity] = useState("");
  const [language, setLanguage] = useState("");
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const settled = useSettled(q.trim(), 350);
  const [now, setNow] = useState<string | null>(null);
  const query = now ?? settled;
  useEffect(() => setNow(null), [settled]);
  const searching = !!query || !!category || !!city || !!language || open;
  const params = new URLSearchParams({ q: query, page: String(page) });
  if (category) params.set("category", category);
  if (city) params.set("city", city);
  if (language) params.set("language", language);
  if (open) params.set("open", "true");
  const role = useViewerRole();
  const home = useSignedInHome().to;
  const facets = useCategories();
  const r = useQuery({
    queryKey: ["directory", params.toString(), role],
    queryFn: () => api<Results>(`/directory/brands?${params}`, { role }),
    placeholderData: keepPreviousData,
    enabled: searching,
  });
  const reset = () => setPage(1);
  const setCategory = (c: string) => {
    const next = new URLSearchParams(urlParams);
    if (c) next.set("category", c);
    else next.delete("category");
    setUrlParams(next, { replace: true });
    reset();
  };
  // Keep the address in step, so a search can be shared or reloaded.
  useEffect(() => {
    const next = new URLSearchParams(urlParams);
    if (query) next.set("q", query);
    else next.delete("q");
    if (next.toString() !== urlParams.toString()) setUrlParams(next, { replace: true });
    setPage(1);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps
  const [prompt, setPrompt] = useState(false);
  // Visitors who keep searching are asked, once, whether they'd like to join.
  const asked = useRef(false);
  useEffect(() => {
    if (role || !query || asked.current) return;
    const t = setTimeout(() => {
      if (countSearch("brands") >= SEARCHES_BEFORE_PROMPT) {
        asked.current = true;
        setPrompt(true);
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [query, role]);
  const d = searching ? r.data : undefined;
  const more = d ? d.total - d.items.length : 0;
  const cats = (facets.data?.categories ?? []).map((c) => ({ id: c, label: c }));
  const box = (big: boolean) => (
    <SearchBox
      value={q}
      onChange={setQ}
      onSubmit={() => setNow(q.trim())}
      placeholder="Search brands: a name, what they make, or what you make"
      label="Search brands"
      big={big}
    />
  );

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
              <Link to="/creators">Creators</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link to={role === "creator" ? "/creator/brands" : (home ?? "/login")}>{role === "creator" ? "Your Dream Brands" : home ? "Your dashboard" : "Sign in"}</Link>
            </Button>
          </div>
        </header>
        <main id="main">
          {!searching ? (
            // No brand is listed until someone searches.
            <section className="mx-auto mt-[12vh] max-w-2xl text-center">
              <h1 className="font-display text-[32px] font-semibold tracking-tight sm:text-[44px]">Search brands</h1>
              <p className="mt-2 text-[15px] text-fg-2">Type what they make, or the kind of content you make, to find brands that work with creators like you.</p>
              <div className="mt-7">{box(true)}</div>
              <p className="mb-2 mt-6 text-xs font-medium text-muted">Or browse a category</p>
              <ChipPicker options={cats} value={category || null} onPick={(c) => setCategory(c ?? "")} noun="category" className="justify-center" />
            </section>
          ) : (
            <>
              <h1 className="sr-only">Brand search</h1>
              <div className="mt-6 max-w-3xl">{box(false)}</div>
              <ChipPicker options={cats} value={category || null} onPick={(c) => setCategory(c ?? "")} noun="category" className="mt-3 max-w-3xl" />
              <div className="mt-3 flex max-w-3xl flex-wrap items-center gap-2">
                <Select aria-label="City" value={city} onChange={(e) => (setCity(e.target.value), reset())} className="h-9 w-auto min-w-[140px] text-[13px]">
                  <option value="">Any city</option>
                  {facets.data?.cities.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </Select>
                <Select aria-label="Language" value={language} onChange={(e) => (setLanguage(e.target.value), reset())} className="h-9 w-auto min-w-[140px] text-[13px]">
                  <option value="">Any language</option>
                  {facets.data?.languages.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </Select>
                <label className="flex items-center gap-2 text-[13px]">
                  <Switch checked={open} onCheckedChange={(v) => (setOpen(v), reset())} aria-label="Only brands with open campaigns" /> Open campaigns
                </label>
              </div>
              {d?.niche_hint && (
                <p className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-fg-2">
                  <Sparkles className="size-3.5 text-accent" aria-hidden /> Including brands that work with {d.niche_hint.label.toLowerCase()} creators
                </p>
              )}
              {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
              {!d && !r.isError && <RowBones rows={4} className="mt-6 max-w-3xl" />}
              {d && (
                <section aria-label="Results" className={cn("mt-5 max-w-3xl transition-opacity", r.isFetching && "opacity-60")}>
                  <p className="px-2 text-sm text-muted sm:px-3" aria-live="polite">
                    {d.total === 0
                      ? "No brands match that yet. Try what they make, or a category."
                      : `${d.total} brand${d.total === 1 ? "" : "s"}${query ? ` for "${query}"` : ""}, best matches first`}
                    {d.note && <span className="block text-xs">{d.note}</span>}
                  </p>
                  <ul className="mt-1 divide-y divide-line">
                    {d.items.map((b) => (
                      <li key={b.id}>
                        <BrandRow b={b} />
                      </li>
                    ))}
                  </ul>
                  {d.locked && <MoreRow text={`${more} more brand${more === 1 ? "" : "s"}`} onClick={() => setPrompt(true)} />}
                  {!d.locked && d.total > d.page_size && (
                    <nav aria-label="Pages" className="mt-4 flex items-center justify-center gap-2">
                      <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                        Previous
                      </Button>
                      <span className="num text-sm text-fg-2">
                        Page {page} of {Math.ceil(d.total / d.page_size)}
                      </span>
                      <Button size="sm" variant="outline" disabled={page * d.page_size >= d.total} onClick={() => setPage((p) => p + 1)}>
                        Next
                      </Button>
                    </nav>
                  )}
                </section>
              )}
            </>
          )}
        </main>
      </div>
      <JoinPrompt kind="brands" open={prompt} onOpenChange={setPrompt} more={d?.locked ? more : undefined} />
    </div>
  );
}

function BrandRow({ b }: { b: BrandCard }) {
  const media = b.claimed ? (
    <Avatar name={b.name} hue={b.hue ?? 260} size={64} className="rounded-2xl" />
  ) : (
    <span className="grid size-16 place-items-center rounded-2xl border border-dashed border-line-strong text-muted" aria-hidden>
      <Building2 className="size-7" />
    </span>
  );
  const meta = [b.category, b.cities?.length ? b.cities.join(", ") : null, b.languages?.length ? b.languages.join(", ") : null].filter(Boolean).join(" · ");
  return (
    <ResultRow
      to={`/brands/${b.slug}`}
      media={media}
      title={
        <>
          <span className="truncate">{b.name}</span>
          {b.verified && <BadgeCheck className="size-4 shrink-0 text-accent" aria-label="Verified" />}
        </>
      }
      meta={meta}
    >
      {b.matched && b.matched.length > 0 && (
        <span className="block">
          <span className="text-muted">Matches: </span>
          {b.matched.join(", ")}
        </span>
      )}
      <span className="flex flex-wrap items-center gap-1.5">
        {b.claimed ? (
          b.open_campaigns > 0 ? (
            <Badge size="sm" variant="success">
              <Megaphone aria-hidden /> {b.open_campaigns} open
            </Badge>
          ) : (
            <Badge size="sm">No open campaigns</Badge>
          )
        ) : (
          <Badge size="sm" variant="outline">
            Unclaimed
          </Badge>
        )}
        <SourceBadge source={b.source} />
      </span>
      {!b.claimed && <span className="block text-[11px] text-muted">{b.note}</span>}
    </ResultRow>
  );
}

export function BrandTile({ b }: { b: BrandCard }) {
  return (
    <Link to={`/brands/${b.slug}`} className="card-surface flex h-full flex-col rounded-xl p-4 transition-colors hover:border-accent/50">
      <span className="flex items-center gap-3">
        {b.claimed ? (
          <Avatar name={b.name} hue={b.hue ?? 260} size={40} className="rounded-xl" />
        ) : (
          <span className="grid size-10 place-items-center rounded-xl border border-dashed border-line-strong text-muted" aria-hidden>
            <Building2 className="size-5" />
          </span>
        )}
        <span className="min-w-0">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="truncate">{b.name}</span> {b.verified && <BadgeCheck className="size-4 shrink-0 text-accent" aria-label="Verified" />}
          </span>
          <span className="block truncate text-xs text-muted">{b.category}</span>
        </span>
      </span>
      <span className="mt-3 flex flex-wrap items-center gap-1.5">
        {b.claimed ? (
          b.open_campaigns > 0 ? (
            <Badge size="sm" variant="success">
              <Megaphone aria-hidden /> {b.open_campaigns} open
            </Badge>
          ) : (
            <Badge size="sm">No open campaigns</Badge>
          )
        ) : (
          <Badge size="sm" variant="outline">
            Unclaimed
          </Badge>
        )}
        <SourceBadge source={b.source} />
      </span>
      {b.matched && b.matched.length > 0 && (
        <span className="mt-2 text-xs text-fg-2">
          <span className="text-muted">Matches: </span>
          {b.matched.join(", ")}
        </span>
      )}
      {!b.claimed && <span className="mt-2 text-[11px] text-muted">{b.note}</span>}
    </Link>
  );
}
