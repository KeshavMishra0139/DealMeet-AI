import { useId } from "react";
import { cn } from "@/lib/utils";

/** Two linked rings: a creator and a brand meeting on a fair deal. */
export function LogoMark({ className }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7C3AED" />
          <stop offset="0.55" stopColor="#DB2777" />
          <stop offset="1" stopColor="#F97316" />
        </linearGradient>
      </defs>
      <circle cx="12.25" cy="16" r="7" fill="none" stroke={`url(#${id})`} strokeWidth="3.2" />
      <circle cx="19.75" cy="16" r="7" fill="none" stroke={`url(#${id})`} strokeWidth="3.2" />
    </svg>
  );
}

export function Wordmark({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      {!compact && (
        <span className="font-display text-[17px] font-semibold tracking-tight text-fg">
          DealMeet
          <span className="text-brand ml-1 font-bold">AI</span>
        </span>
      )}
      {compact && <span className="sr-only">DealMeet AI</span>}
    </span>
  );
}
