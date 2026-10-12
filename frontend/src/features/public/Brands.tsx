import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, Megaphone, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Wordmark } from "@/components/shared/Wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label, Select, Skeleton, Switch } from "@/components/ui/form";
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
}

interface Results {
  items: BrandCard[];
  total: number;
  page: number;
  page_size: number;
  search: "all" | "regex" | "atlas";
  note: string | null;
}

interface Facets {
  categories: string[];
  cities: string[];
  languages: { id: string; label: string }[];
}

/** The public brand directory. */
export default function Brands() {
  useTheme("creator");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [city, setCity] = useState("");
  const [language, setLanguage] = useState("");
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const query = useDeferredValue(q);
  const params = new URLSearchParams({ q: query, page: String(page) });
  if (category) params.set("category", category);
  if (city) params.set("city", city);
  if (language) params.set("language", language);
  if (open) params.set("open", "true");
  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/directory/facets", { role: null }), staleTime: 60_000 });
  const r = useQuery({
    queryKey: ["directory", params.toString()],
    queryFn: () => api<Results>(`/directory/brands?${params}`, { role: null }),
    placeholderData: keepPreviousData,
  });
  const reset = () => setPage(1);

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
          <Button asChild size="sm" variant="ghost">
            <Link to="/creator/brands">Your Dream Brands</Link>
          </Button>
        </header>
        <main id="main" className="mt-8">
          <h1 className="font-display text-[28px] font-semibold tracking-tight sm:text-[34px]">Brands</h1>
          <p className="mt-1 text-[15px] text-fg-2">Find brands to work with. Save the ones you'd love to work with, and hear when they open a campaign.</p>

          <form role="search" className="card-surface mt-6 grid gap-3 rounded-[var(--radius-card)] p-4 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_auto]" onSubmit={(e) => e.preventDefault()}>
            <div className="sm:col-span-2 lg:col-span-1">
              <Label htmlFor="bd-q">Search</Label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
                <Input id="bd-q" value={q} onChange={(e) => (setQ(e.target.value), reset())} placeholder="Name, category or what they make" maxLength={80} className="pl-9" />
              </div>
            </div>
            <div>
              <Label htmlFor="bd-cat">Category</Label>
              <Select id="bd-cat" value={category} onChange={(e) => (setCategory(e.target.value), reset())}>
                <option value="">Any</option>
                {facets.data?.categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="bd-city">City</Label>
              <Select id="bd-city" value={city} onChange={(e) => (setCity(e.target.value), reset())}>
                <option value="">Any</option>
                {facets.data?.cities.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="bd-lang">Language</Label>
              <Select id="bd-lang" value={language} onChange={(e) => (setLanguage(e.target.value), reset())}>
                <option value="">Any</option>
                {facets.data?.languages.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.label}
                  </option>
                ))}
              </Select>
            </div>
            <label className="flex items-center gap-2 self-end pb-2.5 text-sm">
              <Switch checked={open} onCheckedChange={(v) => (setOpen(v), reset())} aria-label="Only brands with open campaigns" /> Open campaigns
            </label>
          </form>

          {r.isError && <ErrorState error={r.error} onRetry={() => r.refetch()} />}
          {!r.data && !r.isError && <Skeleton className="mt-6 h-96 rounded-xl" />}
          {r.data && (
            <section aria-label="Results" className={cn("mt-6 transition-opacity", r.isFetching && "opacity-60")}>
              <p className="mb-3 text-sm text-fg-2" aria-live="polite">
                {r.data.total} brand{r.data.total === 1 ? "" : "s"}
                {r.data.search === "atlas" && " · ranked by Atlas Search"}
                {r.data.note && <span className="block text-xs text-muted">{r.data.note}</span>}
              </p>
              <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {r.data.items.map((b) => (
                  <li key={b.id}>
                    <BrandTile b={b} />
                  </li>
                ))}
              </ul>
              {r.data.total > r.data.page_size && (
                <nav aria-label="Pages" className="mt-4 flex items-center justify-center gap-2">
                  <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <span className="num text-sm text-fg-2">
                    Page {page} of {Math.ceil(r.data.total / r.data.page_size)}
                  </span>
                  <Button size="sm" variant="outline" disabled={page * r.data.page_size >= r.data.total} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </nav>
              )}
            </section>
          )}
        </main>
      </div>
    </div>
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
      {!b.claimed && <span className="mt-2 text-[11px] text-muted">{b.note}</span>}
    </Link>
  );
}
