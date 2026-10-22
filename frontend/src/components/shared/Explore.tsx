// Finding creators and brands from the landing page: a popup with a search box and the busiest
// few niches (or categories), every one a tap away under "more". Plus the prompt visitors see
// when they want more than the first few results.
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, ExternalLink, Lock, LogIn, Search, UserPlus } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { Dialog, DialogContent, Popover, PopoverContent, PopoverTrigger } from "@/components/ui/overlays";
import { api } from "@/lib/api";
import { useSession, type Role } from "@/lib/session";
import { cn } from "@/lib/utils";

export type ExploreKind = "creators" | "brands";
export interface NicheCount {
  id: string;
  label: string;
  count: number;
}

/** A value that settles a moment after the last change, so typing doesn't search every key. */
export function useSettled<T>(value: T, ms = 400): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

/** How many niches or categories show before "more". */
export const FEW = 6;

/** The side the viewer is signed in as, so public pages send their session; null for visitors. */
export function useViewerRole(): Role | null {
  const creator = useSession("creator");
  const brand = useSession("brand");
  return creator.data ? "creator" : brand.data ? "brand" : null;
}

export function useNiches() {
  const role = useViewerRole();
  return useQuery({
    queryKey: ["public-niches"],
    queryFn: async () => (await api<{ niches: NicheCount[] }>("/directory/creators", { role })).niches,
    staleTime: 5 * 60_000,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["facets"],
    queryFn: () => api<{ categories: string[]; cities: string[]; languages: { id: string; label: string }[] }>("/directory/facets", { role: null }),
    staleTime: 60_000,
  });
}

/** Chips for the busiest few, and the rest behind "more". */
export function ChipPicker({
  options,
  value,
  onPick,
  noun,
  className,
}: {
  options: { id: string; label: string }[];
  /** The picked option, or several when more than one can be picked. */
  value?: string | string[] | null;
  /** Called with the option tapped and whether it's now picked. */
  onPick: (id: string | null, on?: boolean) => void;
  noun: string;
  className?: string;
}) {
  const [all, setAll] = useState(false);
  const picked = new Set(Array.isArray(value) ? value : value ? [value] : []);
  // Picked options stay visible even when they're among the "more".
  const shown = all ? options : options.filter((o, i) => i < FEW || picked.has(o.id));
  const hidden = options.length - shown.length;
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)} role="group" aria-label={`Pick a ${noun}`}>
      {shown.map((o) => {
        const on = picked.has(o.id);
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={on}
            onClick={() => (Array.isArray(value) ? onPick(o.id, !on) : onPick(on ? null : o.id, !on))}
            className={cn(
              "rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors",
              on ? "border-accent bg-accent text-white" : "border-line-strong bg-surface hover:border-accent/60 hover:text-fg",
            )}
          >
            {o.label}
          </button>
        );
      })}
      {(hidden > 0 || all) && options.length > FEW && (
        <button
          type="button"
          onClick={() => setAll((v) => !v)}
          aria-expanded={all}
          className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[13px] font-medium text-accent hover:underline"
        >
          {all ? "Fewer" : `${hidden} more ${hidden === 1 ? noun : noun.endsWith("y") ? `${noun.slice(0, -1)}ies` : `${noun}s`}`}
          <ChevronDown className={cn("size-3.5 transition-transform", all && "rotate-180")} aria-hidden />
        </button>
      )}
    </div>
  );
}

const COPY = {
  creators: { title: "Find creators", placeholder: "Try 'Tamil breakfast' or '@handle'", noun: "niche", path: "/creators", pick: "niche" },
  brands: { title: "Find brands", placeholder: "Try 'snacks', 'skincare' or 'dosa'", noun: "category", path: "/brands", pick: "category" },
} as const;

/** The landing bar's Creators and Brands: a popup to search, or start from a niche or category. */
export function ExplorePopover({ kind, children }: { kind: ExploreKind; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const navigate = useNavigate();
  const niches = useNiches();
  const cats = useCategories();
  const c = COPY[kind];
  const options =
    kind === "creators"
      ? (niches.data ?? []).map((n) => ({ id: n.id, label: n.label }))
      : (cats.data?.categories ?? []).map((x) => ({ id: x, label: x }));
  const go = (params: Record<string, string>) => {
    setOpen(false);
    navigate(`${c.path}?${new URLSearchParams(params)}`);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent side="top" align="center" sideOffset={14} className="w-[min(380px,calc(100vw-24px))] p-4">
        <p className="font-display text-base font-semibold">{c.title}</p>
        <form
          role="search"
          className="relative mt-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim() || picked.length) go({ ...(q.trim() ? { q: q.trim() } : {}), ...(picked.length ? { niche: picked.join(",") } : {}) });
          }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={c.placeholder} aria-label={`Search ${kind}`} maxLength={80} className="pl-9" autoFocus />
        </form>
        <p className="mb-2 mt-4 text-xs font-medium text-muted">{kind === "creators" ? "Or pick one or more niches" : "Or pick a category"}</p>
        {kind === "creators" ? (
          <ChipPicker options={options} noun={c.noun} value={picked} onPick={(id, on) => id && setPicked((p) => (on ? [...p, id] : p.filter((x) => x !== id)))} />
        ) : (
          <ChipPicker options={options} noun={c.noun} onPick={(id) => id && go({ [c.pick]: id })} />
        )}
        <div className="mt-4 flex items-center justify-between gap-3">
          <button type="button" onClick={() => go({})} className="text-[13px] font-medium text-accent hover:underline">
            See all {kind} →
          </button>
          {kind === "creators" && (q.trim() || picked.length > 0) && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => go({ ...(q.trim() ? { q: q.trim() } : {}), ...(picked.length ? { niche: picked.join(",") } : {}) })}
            >
              <Search aria-hidden /> Search
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** "Want to know more?": visitors who want more than the first few results. */
export function JoinPrompt({ kind, open, onOpenChange, more }: { kind: ExploreKind; open: boolean; onOpenChange: (v: boolean) => void; more?: number }) {
  // People looking for creators are usually brands, and the other way round.
  const role: Role = kind === "creators" ? "brand" : "creator";
  const other: Role = role === "brand" ? "creator" : "brand";
  const next = encodeURIComponent(kind === "creators" ? "/creators" : "/brands");
  const body =
    kind === "creators"
      ? `${more ? `${more} more creators match. ` : ""}Sign in to see every match, and the reach, rates and audience each creator chooses to share with brands.`
      : `${more ? `${more} more brands match. ` : ""}Sign in to see every brand, save the ones you'd love to work with, and hear when they open a campaign.`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Want to know more?" description={body}>
        <div className="grid gap-2 sm:grid-cols-2">
          <Button asChild variant="primary" size="lg">
            <Link to={`/login?role=${role}&mode=signup&next=${next}`}>
              <UserPlus aria-hidden /> Sign up as a {role}
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to={`/login?role=${role}&next=${next}`}>
              <LogIn aria-hidden /> Log in
            </Link>
          </Button>
        </div>
        <p className="mt-4 text-center text-sm text-muted">
          Are you a {other}?{" "}
          <Link to={`/login?role=${other}&mode=signup`} className="font-medium text-accent underline-offset-4 hover:underline">
            Sign up as a {other}
          </Link>
        </p>
      </DialogContent>
    </Dialog>
  );
}

/** Counts a visitor's searches this session; after a few, it's time to ask them to join. */
export function countSearch(kind: ExploreKind): number {
  try {
    const key = `dm.searches.${kind}`;
    const n = Number(window.sessionStorage.getItem(key) ?? 0) + 1;
    window.sessionStorage.setItem(key, String(n));
    return n;
  } catch {
    return 0;
  }
}
export const SEARCHES_BEFORE_PROMPT = 4;

/* ---------- search-engine pieces shared by /creators and /brands ---------- */

export interface Suggestion {
  text: string;
  /** "channel": a YouTube channel a creator search found; the rest are on DealMeet. */
  kind: "creator" | "channel" | "tag" | "niche" | "city" | "language" | "brand" | "category";
  query: string;
}

const KIND_LABEL: Record<Suggestion["kind"], string> = {
  creator: "On DealMeet",
  channel: "YouTube",
  tag: "Topic",
  niche: "Niche",
  city: "City",
  language: "Language",
  brand: "Brand",
  category: "Category",
};

/**
 * A wide, rounded search bar with its button attached, like a web search engine's, that
 * suggests matching words as you type (arrow keys to move, Enter to pick). Typing is never
 * interrupted: results refresh beside it while you keep typing.
 */
export function SearchBox({
  value,
  onChange,
  onSubmit,
  placeholder,
  label,
  suggestFor,
  big = false,
}: {
  value: string;
  onChange: (v: string) => void;
  /** Search now, with this text (a picked suggestion, or what's typed). */
  onSubmit: (text: string) => void;
  placeholder: string;
  label: string;
  suggestFor: ExploreKind;
  big?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const typed = useSettled(value.trim(), 120);
  const s = useQuery({
    queryKey: ["suggest", suggestFor, typed],
    queryFn: () => api<{ items: Suggestion[] }>(`/directory/suggest?${new URLSearchParams({ q: typed, kind: suggestFor })}`, { role: null }),
    enabled: typed.length >= 1,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
  const items = value.trim() ? (s.data?.items ?? []).filter((x) => x.text.toLowerCase() !== value.trim().toLowerCase() || x.query !== x.text) : [];
  const show = open && items.length > 0;
  useEffect(() => setActive(-1), [typed]);
  const pick = (x: Suggestion) => {
    onChange(x.query);
    setOpen(false);
    onSubmit(x.query);
  };
  const listId = `suggest-${suggestFor}`;
  return (
    <form
      role="search"
      className="relative flex w-full items-stretch"
      onSubmit={(e) => {
        e.preventDefault();
        if (show && active >= 0) pick(items[active]);
        else {
          setOpen(false);
          onSubmit(value.trim());
        }
      }}
    >
      <input
        type="search"
        role="combobox"
        aria-expanded={show}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={show && active >= 0 ? `${listId}-${active}` : undefined}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            // Closes the list (even before its suggestions arrive) and keeps the text:
            // a search box's own Escape would clear it.
            e.preventDefault();
            setOpen(false);
            return;
          }
          if (!show) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => (i + 1) % items.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => (i <= 0 ? items.length - 1 : i - 1));
          }
        }}
        placeholder={placeholder}
        aria-label={label}
        maxLength={80}
        autoFocus={big}
        autoComplete="off"
        className={cn(
          "min-w-0 flex-1 rounded-l-full border border-r-0 border-line-strong bg-[var(--surface-solid)] px-5 text-fg outline-none transition-colors placeholder:text-muted focus:border-accent",
          big ? "h-14 text-base" : "h-11 text-[15px]",
        )}
      />
      <button
        type="submit"
        aria-label="Search"
        className={cn(
          "grid shrink-0 place-items-center rounded-r-full border border-line-strong bg-surface-2 text-fg transition-colors hover:bg-surface-3",
          big ? "h-14 w-16" : "h-11 w-14",
        )}
      >
        <Search className="size-5" aria-hidden />
      </button>
      {show && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Suggestions"
          className="absolute inset-x-0 top-full z-40 mt-1.5 overflow-hidden rounded-2xl border border-line-strong bg-[var(--surface-solid)] py-1.5 text-left shadow-[0_18px_50px_-12px_rgb(0_0_0/0.45)]"
        >
          {items.map((x, i) => (
            <li
              key={`${x.kind}:${x.text}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // mousedown, not click: it runs before the input's blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(x);
              }}
              onMouseEnter={() => setActive(i)}
              className={cn("flex cursor-pointer items-center gap-3 px-5 py-2 text-[15px]", i === active && "bg-surface-2")}
            >
              <Search className="size-4 shrink-0 text-muted" aria-hidden />
              <span className="min-w-0 flex-1 truncate">
                <Highlight text={x.text} q={value.trim().replace(/^@/, "")} />
                {(x.kind === "creator" || x.kind === "channel") && x.query !== x.text && <span className="ml-2 text-xs text-muted">{x.query}</span>}
              </span>
              <span className="shrink-0 text-[11px] text-muted">{KIND_LABEL[x.kind]}</span>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

/** The typed part in normal weight, the rest bold, as search engines show suggestions. */
function Highlight({ text, q }: { text: string; q: string }) {
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return <span className="font-medium">{text}</span>;
  return (
    <span>
      <span className="font-semibold">{text.slice(0, i)}</span>
      <span className="text-fg-2">{text.slice(i, i + q.length)}</span>
      <span className="font-semibold">{text.slice(i + q.length)}</span>
    </span>
  );
}

/** One search result: a picture on the left, then title, a meta line and details. */
export function ResultRow({
  to,
  href,
  media,
  title,
  meta,
  children,
  label,
}: {
  to?: string;
  href?: string;
  media: ReactNode;
  title: ReactNode;
  meta: ReactNode;
  children?: ReactNode;
  label?: string;
}) {
  const body = (
    <>
      <span className="shrink-0">{media}</span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5 text-[17px] font-medium leading-snug group-hover:text-accent">{title}</span>
        <span className="mt-0.5 block text-xs text-muted">{meta}</span>
        {children && <span className="mt-2 block space-y-1.5 text-[13px] text-fg-2">{children}</span>}
      </span>
      {href ? <ExternalLink className="mt-1 size-4 shrink-0 text-muted" aria-hidden /> : <ArrowRight className="mt-1 size-4 shrink-0 text-muted" aria-hidden />}
    </>
  );
  const cls = "group flex items-start gap-4 rounded-2xl px-2 py-4 transition-colors hover:bg-surface-2/60 sm:px-3";
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className={cls} aria-label={label}>
      {body}
    </a>
  ) : (
    <Link to={to ?? "#"} className={cls}>
      {body}
    </Link>
  );
}

/** The row at the end of a visitor's results: more is there for members. */
export function MoreRow({ text, onClick }: { text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-2 flex w-full items-center gap-4 rounded-2xl border border-dashed border-line-strong px-4 py-4 text-left transition-colors hover:border-accent/60"
    >
      <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent-soft">
        <Lock className="size-5 text-accent" aria-hidden />
      </span>
      <span>
        <span className="block font-medium">{text}</span>
        <span className="block text-xs text-muted">Want to know more? Log in or sign up</span>
      </span>
    </button>
  );
}
