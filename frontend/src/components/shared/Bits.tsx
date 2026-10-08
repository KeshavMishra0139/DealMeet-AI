import { AlertTriangle, RotateCw, UserRound } from "lucide-react";
import type * as React from "react";
import { useId } from "react";
import { Button } from "@/components/ui/button";
import { cn, initials } from "@/lib/utils";

export function Avatar({
  name,
  hue = 265,
  size = 40,
  generic = false,
  className,
}: {
  name: string;
  hue?: number;
  size?: number;
  generic?: boolean;
  className?: string;
}) {
  const bg = `linear-gradient(135deg, hsl(${hue} 70% 58%), hsl(${(hue + 40) % 360} 75% 52%))`;
  return (
    <span
      className={cn("inline-grid shrink-0 place-items-center rounded-full font-semibold text-white", className)}
      style={{ width: size, height: size, background: bg, fontSize: size * 0.38 }}
      aria-hidden
    >
      {generic ? <UserRound style={{ width: size * 0.55, height: size * 0.55 }} /> : initials(name)}
    </span>
  );
}

/** A one-line note shown on the reference profile wherever it appears. */
export function ReferenceNote({ text, className }: { text: string; className?: string }) {
  return (
    <p className={cn("flex items-start gap-2 text-xs leading-relaxed text-muted", className)}>
      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warn" aria-hidden />
      {text}
    </p>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 py-10 text-center", className)}>
      {icon && <div className="mb-3 grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent">{icon}</div>}
      <p className="font-display text-base font-semibold">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="card-surface flex flex-col items-center rounded-[var(--radius-card)] px-6 py-10 text-center">
      <div className="mb-3 grid size-12 place-items-center rounded-2xl bg-danger-soft text-danger">
        <AlertTriangle className="size-5" aria-hidden />
      </div>
      <p className="font-display text-base font-semibold">We couldn't load this</p>
      <p className="mt-1 max-w-sm text-sm text-muted">{msg}</p>
      {onRetry && (
        <Button className="mt-4" variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden /> Try again
        </Button>
      )}
    </div>
  );
}

/** Circular 0-100 score with the signature gradient. */
export function ScoreRing({
  value,
  size = 120,
  stroke = 10,
  label,
  sublabel,
}: {
  value: number;
  size?: number;
  stroke?: number;
  label?: React.ReactNode;
  sublabel?: React.ReactNode;
}) {
  const id = useId();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#A78BFA" />
            <stop offset="0.55" stopColor="#F472B6" />
            <stop offset="1" stopColor="#FB923C" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${id})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)}
          style={{ transition: "stroke-dashoffset 900ms var(--ease-soft)" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div className="num font-display text-[28px] font-semibold leading-none">{label ?? Math.round(v)}</div>
          {sublabel && <div className="mt-1 text-[11px] text-muted">{sublabel}</div>}
        </div>
      </div>
    </div>
  );
}

export function SectionTitle({
  eyebrow,
  title,
  action,
  className,
  id,
}: {
  eyebrow?: string;
  title: string;
  action?: React.ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-end justify-between gap-3", className)}>
      <div>
        {eyebrow && <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">{eyebrow}</p>}
        <h2 id={id} className="font-display text-lg font-semibold">
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-grid h-5 min-w-5 place-items-center rounded-md border border-line-strong bg-surface-2 px-1 font-sans text-[11px] font-semibold text-fg-2",
        className,
      )}
    >
      {children}
    </kbd>
  );
}
