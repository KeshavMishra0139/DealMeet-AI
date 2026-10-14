// Loading skeletons shaped like each tab, so the page keeps its layout while it loads, and a
// wipe from skeleton to content when the data lands. The bones shimmer (the `skeleton` utility);
// the wipe uses the browser's View Transitions: the skeleton's snapshot is masked away left to
// right over the real page (see `::view-transition-old(dm-load)` in index.css). Browsers without
// View Transitions, and anyone who asked for reduced motion, just get the page.
import { useEffect, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { Skeleton as Bone } from "@/components/ui/form";
import { cn } from "@/lib/utils";

type Doc = Document & { startViewTransition?: (cb: () => void) => unknown };

/**
 * True once the page may show its content. When `ready` turns true after a skeleton was on
 * screen, the swap runs inside a view transition so the skeleton wipes away. Data that was
 * already cached shows at once, with no wipe.
 */
export function useLoadWipe(ready: boolean) {
  const [shown, setShown] = useState(ready);
  useEffect(() => {
    if (!ready || shown) return;
    const doc = document as Doc;
    const still = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (
      still ||
      !doc.startViewTransition ||
      document.visibilityState !== "visible"
    ) {
      setShown(true);
      return;
    }
    try {
      doc.startViewTransition(() => flushSync(() => setShown(true)));
    } catch {
      setShown(true);
    }
  }, [ready, shown]);
  return ready && shown;
}

function Shell({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      className={className}
    >
      {children}
    </div>
  );
}

/** The heading block every tab opens with: an optional eyebrow, the title and a line under it. */
export function HeaderBones({
  eyebrow = false,
  action = false,
  small = false,
}: {
  eyebrow?: boolean;
  action?: boolean;
  small?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0 flex-1">
        {eyebrow && <Bone className="mb-3 h-4 w-40 rounded-full" />}
        <Bone
          className={cn(
            "w-56 max-w-full rounded-lg sm:w-72",
            small ? "h-7" : "h-9",
          )}
        />
        <Bone className="mt-2.5 h-4 w-[min(420px,90%)] rounded-full" />
      </div>
      {action && <Bone className="h-10 w-32 rounded-full" />}
    </div>
  );
}

/** A card with a title line, a few lines of text and, if asked, a big number or a button. */
export function CardBones({
  lines = 3,
  figure = false,
  button = false,
  className,
}: {
  lines?: number;
  figure?: boolean;
  button?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn("card-surface rounded-[var(--radius-card)] p-5", className)}
    >
      <div className="flex items-center gap-2">
        <Bone className="size-5 rounded-md" />
        <Bone className="h-4 w-32 rounded-full" />
      </div>
      {figure && <Bone className="mt-4 h-8 w-36 rounded-lg" />}
      <div className="mt-4 space-y-2.5">
        {Array.from({ length: lines }, (_, i) => (
          <Bone
            key={i}
            className={cn(
              "h-3.5 rounded-full",
              i === lines - 1 ? "w-3/5" : "w-full",
            )}
          />
        ))}
      </div>
      {button && <Bone className="mt-5 h-10 w-36 rounded-full" />}
    </div>
  );
}

/** Rows like the deal, pitch and brand lists: an icon, two lines and a chip. */
export function RowBones({
  rows = 4,
  className,
  tinted = false,
}: {
  rows?: number;
  className?: string;
  tinted?: boolean;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className={cn(
            "flex items-center gap-3 rounded-2xl p-4",
            tinted ? "border border-line" : "card-surface",
          )}
        >
          <Bone className="size-10 shrink-0 rounded-xl" />
          <div className="min-w-0 flex-1 space-y-2">
            <Bone className="h-4 w-1/2 max-w-[240px] rounded-full" />
            <Bone className="h-3 w-3/4 max-w-[360px] rounded-full" />
          </div>
          <Bone className="hidden h-7 w-20 rounded-full sm:block" />
        </div>
      ))}
    </div>
  );
}

/** Small number tiles, like the weekly report and the brand overview. */
export function TileBones({
  tiles = 3,
  className,
}: {
  tiles?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid gap-3",
        tiles >= 4 ? "grid-cols-2 md:grid-cols-4" : "md:grid-cols-3",
        className,
      )}
    >
      {Array.from({ length: tiles }, (_, i) => (
        <div key={i} className="card-surface rounded-xl p-4">
          <Bone className="h-3 w-24 rounded-full" />
          <Bone className="mt-3 h-7 w-28 rounded-lg" />
          <Bone className="mt-3 h-3 w-4/5 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/** Form fields: a label and an input each. */
function FieldBones({ fields = 4 }: { fields?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: fields }, (_, i) => (
        <div key={i}>
          <Bone className="h-3 w-24 rounded-full" />
          <Bone className="mt-2 h-11 w-full rounded-xl" />
        </div>
      ))}
    </div>
  );
}

/* ---------- creator tabs ---------- */

/** Home: the week's report, three move cards and the pipeline. */
export function HomeSkeleton() {
  return (
    <Shell label="Loading your plan">
      <Bone className="h-4 w-52 rounded-full" />
      <Bone className="mt-3 h-9 w-72 max-w-full rounded-lg" />
      <TileBones tiles={4} className="mt-6" />
      <div className="mt-6 flex gap-3 overflow-hidden lg:grid lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="card-surface flex h-[360px] w-[86%] shrink-0 flex-col rounded-[26px] p-5 lg:w-auto"
          >
            <Bone className="h-6 w-24 rounded-full" />
            <Bone className="mt-5 h-6 w-4/5 rounded-lg" />
            <Bone className="mt-2 h-6 w-3/5 rounded-lg" />
            <div className="mt-5 space-y-2.5">
              <Bone className="h-3.5 w-full rounded-full" />
              <Bone className="h-3.5 w-full rounded-full" />
              <Bone className="h-3.5 w-2/3 rounded-full" />
            </div>
            <Bone className="mt-auto h-11 w-full rounded-full" />
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-3 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <CardBones key={i} lines={3} figure={i === 0} />
        ))}
      </div>
    </Shell>
  );
}

/** Money: the earnings strip, then the price cards per format. */
export function MoneySkeleton() {
  return (
    <Shell label="Loading your money">
      <Bone className="h-7 w-44 rounded-full" />
      <Bone className="mt-3 h-9 w-64 max-w-full rounded-lg" />
      <Bone className="mt-2.5 h-4 w-[min(420px,90%)] rounded-full" />
      <div className="card-surface mt-8 flex flex-col gap-3 rounded-[var(--radius-card)] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Bone className="h-3 w-28 rounded-full" />
          <Bone className="mt-2 h-8 w-40 rounded-lg" />
        </div>
        <Bone className="h-10 w-40 rounded-full" />
      </div>
      <Bone className="mb-3 mt-8 h-6 w-48 rounded-lg" />
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <CardBones key={i} lines={2} figure />
        ))}
      </div>
    </Shell>
  );
}

/** Roadmap: two progress cards, then the milestone list. */
export function RoadmapSkeleton() {
  return (
    <Shell label="Loading your roadmap">
      <HeaderBones eyebrow />
      <div className="mt-6 grid gap-3 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="card-surface rounded-[var(--radius-card)] p-5"
          >
            <Bone className="h-4 w-36 rounded-full" />
            <RowBones rows={3} tinted className="mt-4" />
          </div>
        ))}
      </div>
      <CardBones lines={3} className="mt-8" />
    </Shell>
  );
}

/** A list tab (Deals, Pitches, Dream brands, brand Deals and Campaigns). */
export function ListSkeleton({
  label = "Loading",
  rows = 4,
  action = false,
  small = false,
}: {
  label?: string;
  rows?: number;
  action?: boolean;
  small?: boolean;
}) {
  return (
    <Shell label={label}>
      <HeaderBones action={action} small={small} />
      <Bone className="mb-3 mt-8 h-5 w-40 rounded-lg" />
      <RowBones rows={rows} />
    </Shell>
  );
}

/** Two cards side by side: Profile and Privacy. */
export function SettingsSkeleton({
  label = "Loading",
  form = false,
}: {
  label?: string;
  form?: boolean;
}) {
  return (
    <Shell label={label}>
      <HeaderBones small={form} />
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="card-surface rounded-[var(--radius-card)] p-5"
          >
            <div className="flex items-center gap-4">
              <Bone className="size-12 shrink-0 rounded-2xl" />
              <div className="flex-1 space-y-2">
                <Bone className="h-5 w-40 rounded-lg" />
                <Bone className="h-3 w-24 rounded-full" />
              </div>
            </div>
            <div className="mt-5">
              {form ? (
                <FieldBones fields={i === 0 ? 3 : 4} />
              ) : (
                <RowBones rows={3} tinted />
              )}
            </div>
          </div>
        ))}
      </div>
    </Shell>
  );
}

/** Connections: one row per app. */
export function ConnectionsSkeleton() {
  return (
    <Shell label="Loading your connections">
      <HeaderBones small />
      <div className="mt-6 divide-y divide-line overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
        {[0, 1].map((i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-4 sm:px-5">
            <Bone className="size-10 shrink-0 rounded-xl" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex items-center gap-3">
                <Bone className="h-4 w-20 rounded-full" />
                <Bone className="h-3 w-12 rounded-full" />
              </div>
              <Bone className="h-3 w-3/5 rounded-full" />
            </div>
            <Bone className="h-8 w-24 rounded-full" />
          </div>
        ))}
      </div>
    </Shell>
  );
}

/** Media kit: the kit preview beside its settings. */
export function KitSkeleton() {
  return (
    <Shell label="Loading your media kit">
      <HeaderBones />
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <div className="card-surface rounded-[28px] p-6">
          <div className="flex items-center gap-4">
            <Bone className="size-16 shrink-0 rounded-full" />
            <div className="flex-1 space-y-2">
              <Bone className="h-6 w-48 rounded-lg" />
              <Bone className="h-3.5 w-32 rounded-full" />
            </div>
          </div>
          <TileBones tiles={3} className="mt-6" />
          <div className="mt-6 space-y-2.5">
            <Bone className="h-3.5 w-full rounded-full" />
            <Bone className="h-3.5 w-full rounded-full" />
            <Bone className="h-3.5 w-1/2 rounded-full" />
          </div>
        </div>
        <div className="space-y-4">
          <CardBones lines={2} button />
          <CardBones lines={3} />
        </div>
      </div>
    </Shell>
  );
}

/** A single item: a deal, a creator, a campaign. */
export function DetailSkeleton({ label = "Loading" }: { label?: string }) {
  return (
    <Shell label={label}>
      <Bone className="h-4 w-24 rounded-full" />
      <div className="mt-4">
        <HeaderBones action small />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="space-y-4">
          <CardBones lines={4} figure />
          <CardBones lines={3} />
        </div>
        <div className="space-y-4">
          <CardBones lines={2} button />
          <CardBones lines={3} />
        </div>
      </div>
    </Shell>
  );
}

/* ---------- brand tabs ---------- */

/** Brand overview: the three number cards and the campaign list. */
export function ConsoleSkeleton() {
  return (
    <Shell label="Loading your overview">
      <HeaderBones eyebrow action small />
      <TileBones tiles={3} className="mt-6" />
      <div className="card-surface mt-6 rounded-xl p-5">
        <Bone className="h-5 w-40 rounded-lg" />
        <RowBones rows={3} tinted className="mt-4" />
      </div>
    </Shell>
  );
}

/** A brand form tab: Brand profile, New campaign. */
export function FormSkeleton({
  label = "Loading",
  fields = 5,
}: {
  label?: string;
  fields?: number;
}) {
  return (
    <Shell label={label}>
      <HeaderBones small />
      <div className="card-surface mt-6 max-w-2xl rounded-xl p-5">
        <FieldBones fields={fields} />
        <Bone className="mt-6 h-11 w-40 rounded-full" />
      </div>
    </Shell>
  );
}
