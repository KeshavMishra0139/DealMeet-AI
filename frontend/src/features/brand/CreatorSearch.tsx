// "Find creators" at the top of the Brand Console: a search box and filters for niche,
// followers and reach, answered by GET /brands/{id}/creators (a MongoDB query).
//
// Filters live in the address (?q=&niche=&followers=&reach=&sort=&page=), so a search can
// be shared and the back button works. Results show once something is searched, filtered
// or "Browse all" is pressed; before that the card says how many creators can be reached.
// Followers and reach appear only for creators who share stats with this brand.
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, EyeOff, Search, SlidersHorizontal, X } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, ErrorState } from "@/components/shared/Bits";
import { SourceBadge } from "@/components/shared/SourceBadge";
import { Skeleton } from "@/components/ui/form";
import { api } from "@/lib/api";
import { count } from "@/lib/format";
import type { CreatorSearch as SearchData, CreatorSearchOption, CreatorSearchResult } from "@/lib/market-types";
import { cn } from "@/lib/utils";

const FILTERS = ["q", "niche", "followers", "reach", "sort", "page", "browse"] as const;
const DEBOUNCE_MS = 300;

export function CreatorSearch({ brandId }: { brandId: string }) {
  const [params, setParams] = useSearchParams();
  const get = (k: (typeof FILTERS)[number]) => params.get(k) ?? "";
  const q = get("q");
  const [text, setText] = useState(q);

  // Typing updates the address (and the query) once the person pauses.
  useEffect(() => setText(q), [q]);
  useEffect(() => {
    if (text.trim() === q) return;
    const t = window.setTimeout(() => set({ q: text.trim() }), DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [text]);

  /** Change filters; any change except paging goes back to page 1. */
  function set(next: Partial<Record<(typeof FILTERS)[number], string>>) {
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(next)) v ? p.set(k, v) : p.delete(k);
        if (!("page" in next)) p.delete("page");
        return p;
      },
      { replace: true },
    );
  }

  const query = new URLSearchParams();
  for (const k of ["q", "niche", "followers", "reach", "sort", "page"] as const) if (get(k)) query.set(k, get(k));
  const search = useQuery({
    queryKey: ["creator-search", brandId, query.toString()],
    queryFn: () => api<SearchData>(`/brands/${brandId}/creators?${query}`),
    placeholderData: keepPreviousData,
  });
  const filtered = Boolean(q || get("niche") || get("followers") || get("reach"));
  const showing = filtered || get("browse") === "1";
  const d = search.data;
  const ids = { input: useId(), niche: useId(), sort: useId(), followers: useId(), reach: useId() };

  return (
    <section
      aria-labelledby="find-creators"
      className="rounded-[28px] border border-slate-200/70 bg-white p-4 shadow-[0_24px_60px_-40px_rgb(10_27_51/0.35)] sm:p-6"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="find-creators" className="font-display text-lg font-semibold text-[#0a1b33]">
            Find creators
          </h2>
          <p className="mt-0.5 text-[13px] text-slate-600">Everyone who's discoverable to you, with only what they chose to share.</p>
        </div>
        {d && !showing && (
          <button
            type="button"
            onClick={() => set({ browse: "1" })}
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[13px] font-medium text-[#0a1b33] hover:bg-slate-100"
          >
            Browse all {d.total} <ChevronRight className="size-4" aria-hidden />
          </button>
        )}
      </div>

      <form role="search" className="mt-4" onSubmit={(e) => (e.preventDefault(), set({ q: text.trim() }))}>
        <label htmlFor={ids.input} className="sr-only">
          Search creators by name, handle, city or niche
        </label>
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-[18px] -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            id={ids.input}
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={80}
            placeholder="Name, handle, city or niche"
            autoComplete="off"
            className="h-12 w-full rounded-full border border-slate-200 bg-[#f9fafb] pl-11 pr-11 text-[15px] text-[#0a1b33] transition-colors placeholder:text-slate-500 focus:border-violet-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-violet-500/10"
          />
          {text && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => (setText(""), set({ q: "" }))}
              className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-[#0a1b33]"
            >
              <X className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </form>

      {d && (
        <div className="mt-4 grid gap-x-6 gap-y-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <Pills id={ids.followers} label="Followers" options={d.options.followers} value={get("followers")} onChange={(v) => set({ followers: v })} />
          <Pills id={ids.reach} label="Reach per reel" options={d.options.reach} value={get("reach")} onChange={(v) => set({ reach: v })} />
          <div className="flex flex-wrap items-end gap-2">
            <SelectField id={ids.niche} label="Niche" value={get("niche")} onChange={(v) => set({ niche: v })} options={[{ id: "", label: "All niches" }, ...d.options.niches]} />
            <SelectField id={ids.sort} label="Sort" value={get("sort") || "reach"} onChange={(v) => set({ sort: v === "reach" ? "" : v })} options={d.options.sorts} />
          </div>
        </div>
      )}

      {search.isError && (
        <div className="mt-4">
          <ErrorState error={search.error} onRetry={() => search.refetch()} />
        </div>
      )}
      {!d && !search.isError && <Skeleton className="mt-4 h-24 rounded-2xl" />}
      {d && showing && <Results data={d} filtered={filtered} busy={search.isFetching} onPage={(p) => set({ page: p > 1 ? String(p) : "" })} onClear={() => (setText(""), set({ q: "", niche: "", followers: "", reach: "", sort: "", browse: "" }))} />}
      {d && !showing && (
        <p className="mt-4 flex items-center gap-2 text-[13px] text-slate-600">
          <SlidersHorizontal className="size-4 text-slate-400" aria-hidden />
          {d.total === 0 ? "No creators are discoverable to you yet." : `${d.total} creator${d.total === 1 ? " is" : "s are"} discoverable to you. Search or pick a filter to see them.`}
        </p>
      )}
    </section>
  );
}

function Results({ data, filtered, busy, onPage, onClear }: { data: SearchData; filtered: boolean; busy: boolean; onPage: (p: number) => void; onClear: () => void }) {
  return (
    <div className={cn("mt-5 transition-opacity", busy && "opacity-60")} aria-busy={busy}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4">
        <p className="text-[13px] text-slate-600" aria-live="polite">
          <span className="num font-semibold text-[#0a1b33]">{data.total}</span> creator{data.total === 1 ? "" : "s"}
          {data.pages > 1 && ` · page ${data.page} of ${data.pages}`}
        </p>
        <button type="button" onClick={onClear} className="rounded-full px-3 py-1 text-[13px] font-medium text-slate-600 hover:bg-slate-100 hover:text-[#0a1b33]">
          {filtered ? "Clear filters" : "Close"}
        </button>
      </div>
      {data.hidden_by_reach > 0 && (
        <p className="mt-2 flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-[13px] text-slate-600">
          <EyeOff className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden />
          {data.hidden_by_reach} more creator{data.hidden_by_reach === 1 ? "" : "s"} match the other filters but don't share their reach with you, so the reach filter leaves them out.
        </p>
      )}
      {data.results.length === 0 ? (
        <p className="py-10 text-center text-sm text-slate-600">No creators match. Try fewer filters or a shorter search.</p>
      ) : (
        <ul className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {data.results.map((c) => (
            <li key={c.id}>
              <CreatorCard c={c} />
            </li>
          ))}
        </ul>
      )}
      {data.pages > 1 && (
        <nav aria-label="Search results pages" className="mt-4 flex items-center justify-center gap-2">
          <PageButton disabled={data.page <= 1} onClick={() => onPage(data.page - 1)} label="Previous page">
            <ChevronLeft className="size-4" aria-hidden /> Previous
          </PageButton>
          <PageButton disabled={data.page >= data.pages} onClick={() => onPage(data.page + 1)} label="Next page">
            Next <ChevronRight className="size-4" aria-hidden />
          </PageButton>
        </nav>
      )}
    </div>
  );
}

function CreatorCard({ c }: { c: CreatorSearchResult }) {
  return (
    <Link
      to={`/brand/creators/${c.id}`}
      className="group flex h-full min-w-0 gap-3 rounded-2xl border border-slate-200/70 bg-white p-3.5 transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-[0_16px_40px_-24px_rgb(10_27_51/0.35)]"
    >
      <Avatar name={c.name} hue={c.avatar_hue} size={44} generic={c.is_reference} />
      <div className="min-w-0 flex-1">
        <p className="flex min-w-0 items-baseline gap-1.5">
          <span className="min-w-0 truncate font-semibold text-[#0a1b33] group-hover:text-violet-700">{c.name}</span>
          {c.handle && <span className="min-w-0 truncate text-xs text-slate-500">@{c.handle}</span>}
        </p>
        <p className="truncate text-[13px] text-slate-600">
          {c.niche_label}
          {c.city && ` · ${c.city}`}
        </p>
        {c.languages.length > 0 && <p className="truncate text-xs text-slate-500">{c.languages.join(", ")}</p>}
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <Chip>{c.audience_stage}</Chip>
          {c.shares_stats ? (
            <>
              {c.followers != null && <Chip strong>{count(c.followers)} followers</Chip>}
              {c.reach_views != null ? <Chip strong>{count(c.reach_views)} views per reel</Chip> : <Chip>No reach yet</Chip>}
              <SourceBadge source={c.reach_source ?? c.followers_source} />
            </>
          ) : (
            <Chip>
              <EyeOff className="size-3" aria-hidden /> Stats not shared
            </Chip>
          )}
          {c.sample && c.shares_stats === false && <SourceBadge source="synthetic" />}
        </div>
      </div>
    </Link>
  );
}

function Chip({ children, strong = false }: { children: ReactNode; strong?: boolean }) {
  return (
    <span className={cn("num inline-flex items-center gap-1 rounded-full px-2 py-0.5", strong ? "bg-[#0a1b33]/[0.06] font-medium text-[#0a1b33]" : "bg-slate-100 text-slate-600")}>
      {children}
    </span>
  );
}

/** Single-choice pill toggles; "Any" clears the filter. */
function Pills({ id, label, options, value, onChange }: { id: string; label: string; options: CreatorSearchOption[]; value: string; onChange: (v: string) => void }) {
  return (
    <div role="group" aria-labelledby={id}>
      <p id={id} className="mb-1.5 text-xs font-medium text-slate-600">
        {label}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {[{ id: "", label: "Any" }, ...options].map((o) => {
          const on = value === o.id;
          return (
            <button
              key={o.id || "any"}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? "" : o.id)}
              className={cn(
                "num whitespace-nowrap rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors",
                on ? "border-[#0a1b33] bg-[#0a1b33] text-white" : "border-slate-200 bg-[#f9fafb] text-slate-600 hover:border-slate-300 hover:text-[#0a1b33]",
              )}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SelectField({ id, label, value, onChange, options }: { id: string; label: string; value: string; onChange: (v: string) => void; options: CreatorSearchOption[] }) {
  return (
    <div className="min-w-[150px] flex-1">
      <label htmlFor={id} className="mb-1.5 block text-xs font-medium text-slate-600">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-full border border-slate-200 bg-[#f9fafb] px-3 text-[13px] font-medium text-[#0a1b33] focus:border-violet-400 focus:outline-none focus:ring-4 focus:ring-violet-500/10"
      >
        {options.map((o) => (
          <option key={o.id} value={o.id}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function PageButton({ disabled, onClick, label, children }: { disabled: boolean; onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-[13px] font-medium text-[#0a1b33] hover:bg-slate-50 disabled:opacity-40"
    >
      {children}
    </button>
  );
}
