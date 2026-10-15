// Finding creators and brands from the landing page: a popup with a search box and the busiest
// few niches (or categories), every one a tap away under "more". Plus the prompt visitors see
// when they want more than the first few results.
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, LogIn, Search, UserPlus } from "lucide-react";
import { useState, type ReactNode } from "react";
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
  value?: string | null;
  onPick: (id: string | null) => void;
  noun: string;
  className?: string;
}) {
  const [all, setAll] = useState(false);
  // A picked option stays visible even when it's one of the "more".
  const shown = all ? options : options.filter((o, i) => i < FEW || o.id === value);
  const hidden = options.length - shown.length;
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)} role="group" aria-label={`Pick a ${noun}`}>
      {shown.map((o) => {
        const on = o.id === value;
        return (
          <button
            key={o.id}
            type="button"
            aria-pressed={on}
            onClick={() => onPick(on ? null : o.id)}
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
            if (q.trim()) go({ q: q.trim() });
          }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={c.placeholder} aria-label={`Search ${kind}`} maxLength={80} className="pl-9" autoFocus />
        </form>
        <p className="mb-2 mt-4 text-xs font-medium text-muted">{kind === "creators" ? "Or pick a niche" : "Or pick a category"}</p>
        <ChipPicker options={options} noun={c.noun} onPick={(id) => id && go({ [c.pick]: id })} />
        <button type="button" onClick={() => go({})} className="mt-4 text-[13px] font-medium text-accent hover:underline">
          See all {kind} →
        </button>
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
