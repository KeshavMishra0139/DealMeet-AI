// "Check your worth" (/worth): the tool creators come for, emphasised in the landing's
// navigation for visitors who haven't signed in (signed-in creators see their price in the Studio). A soft signature-gradient glow breathes behind it (opacity only, so it stays
// cheap; still with reduced motion), and the sparkle turns on hover.
import { motion, useReducedMotion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

const VARIANTS = {
  /** Landing's floating nav, on white. */
  pill: "rounded-full px-3.5 py-2 text-[13px] text-[#0a1b33] bg-linear-to-r from-violet-500/10 via-pink-500/10 to-orange-400/10 ring-1 ring-violet-500/25 ring-inset hover:ring-violet-500/50",
} as const;

const ICON = { pill: "size-3.5 text-violet-600" } as const;

export function WorthLink({
  variant,
  label = "Check your worth",
  onClick,
  className,
}: {
  variant: keyof typeof VARIANTS;
  label?: string;
  onClick?: () => void;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <Link
      to="/worth"
      onClick={onClick}
      className={cn("group relative isolate inline-flex items-center gap-1.5 whitespace-nowrap font-semibold transition-shadow", VARIANTS[variant], className)}
    >
      <motion.span
        aria-hidden
        className="absolute -inset-px -z-10 rounded-[inherit] bg-signature opacity-15 blur-md"
        animate={reduce ? undefined : { opacity: [0.1, 0.32, 0.1] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      />
      <Sparkles className={cn("shrink-0 transition-transform duration-300 ease-[var(--ease-soft)] group-hover:rotate-12 group-hover:scale-110", ICON[variant])} aria-hidden />
      {label}
    </Link>
  );
}
