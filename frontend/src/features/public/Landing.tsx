import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, BadgeIndianRupee, Check, ChevronRight, Lock, Scale, Search, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { siFirebase, siGoogle, siInstagram, siMeta, siMongodb, siRazorpay, siYoutube, type SimpleIcon } from "simple-icons";
import { Reveal, Stagger, StaggerItem, TiltCard } from "@/components/motion/Motion";
import { Wordmark } from "@/components/shared/Wordmark";
import { ExplorePopover } from "@/components/shared/Explore";
import { useSignedInHome } from "@/lib/session";
import { useDemoMode, useSharedDemo } from "@/lib/shared-demo";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { DealMosaic } from "./DealMosaic";

const ease = [0.22, 1, 0.36, 1] as const;

const HERO_VIDEO =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260505_101331_74f9b798-3f00-4e86-8a01-377aa16ffeaa.mp4";

/**
 * The services DealMeet AI actually connects to (see README, "Setup"). Shown as "Works with",
 * never as customers or partners. Logos are Simple Icons (CC0), bundled with the app.
 */
const INTEGRATIONS: { icon: SimpleIcon; label: string }[] = [
  { icon: siInstagram, label: "Instagram" },
  { icon: siYoutube, label: "YouTube" },
  { icon: siGoogle, label: "Google sign-in" },
  { icon: siMeta, label: "Meta" },
  { icon: siFirebase, label: "Firebase" },
  { icon: siMongodb, label: "MongoDB" },
  { icon: siRazorpay, label: "Razorpay" },
];

export default function Landing() {
  const shared = useSharedDemo();
  const demo = useDemoMode();
  const signedIn = !!useDashboard();
  useTheme("site");
  const reduce = useReducedMotion();
  const rise = (delay: number) =>
    reduce
      ? {}
      : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, ease, delay } };

  return (
    <div className="theme-site relative min-h-dvh overflow-x-clip px-4 pt-4 sm:px-6 sm:pt-6">
      <Hero />
      <WorksWith />

      <main id="main" className="relative z-10 mx-auto mt-16 max-w-6xl sm:mt-24">
        {!signedIn && (
          <motion.div {...rise(0.1)} className="mb-5 flex flex-wrap items-end justify-between gap-2 sm:mb-6">
            <div>
              <h2 className="font-display text-2xl font-semibold sm:text-[28px]">Join DealMeet AI</h2>
              <p className="mt-1 text-sm text-fg-2">Free to join. Register as a creator or as a brand.</p>
            </div>
            <p className="text-sm text-muted">
              Already registered?{" "}
              <Link to="/login" className="font-medium text-accent underline-offset-4 hover:underline">
                Sign in
              </Link>
            </p>
          </motion.div>
        )}
        {!signedIn && (
        <section aria-label="Register" className="grid gap-3 sm:gap-4 md:grid-cols-2">
          <motion.div {...rise(0.15)}>
            <TiltCard className="h-full rounded-[28px]" max={5}>
              <CreatorEntry />
            </TiltCard>
          </motion.div>
          <motion.div {...rise(0.22)}>
            <TiltCard className="h-full rounded-[28px]" max={5}>
              <BrandEntry />
            </TiltCard>
          </motion.div>
        </section>
        )}

        <motion.div {...rise(0.3)} className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 sm:mt-7">
          {shared && <p className="w-full text-xs text-muted">Shared live demo: everyone sees the same data, and it resets automatically when idle.</p>}
        </motion.div>

        <section aria-labelledby="principles" className="mt-28 pb-10 sm:mt-36">
          <h2 id="principles" className="sr-only">
            How DealMeet AI works
          </h2>
          <Stagger className="grid gap-px overflow-hidden rounded-3xl border border-line bg-line sm:grid-cols-3">
            {[
              {
                icon: Scale,
                title: "Estimates, never promises",
                body: "Every rupee figure is a range with its assumptions and a confidence level. Prices follow real reach, not follower counts.",
              },
              {
                icon: Lock,
                title: "Your data, your say",
                body: "Creators connect through official logins only and choose exactly what each brand can see. Revoke any time.",
              },
              {
                icon: ShieldCheck,
                title: "Paid through escrow",
                body: "Brands fund escrow before a post goes live and approve the post before the fee is released. Collective deals split one payment by member.",
              },
            ].map((p) => (
              <StaggerItem key={p.title} className="bg-[var(--bg)]/80 p-6">
                <p.icon className="size-5 text-accent" aria-hidden />
                <h3 className="mt-3 text-base font-semibold">{p.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{p.body}</p>
              </StaggerItem>
            ))}
          </Stagger>
          <Reveal as="div" className="mt-10">
          <footer className="flex flex-col gap-2 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
            <p>Built by Team TheVortex for CodeX 3.0, Problem Statement 3.</p>
            <nav aria-label="Legal" className="flex gap-4">
              <Link to="/privacy" className="hover:text-fg">Privacy Policy</Link>
              <Link to="/terms" className="hover:text-fg">Terms of Use</Link>
            </nav>
            {demo && <p>All brands and profiles in the demo are fictional, except one anonymised reference profile.</p>}
          </footer>
          </Reveal>
        </section>
      </main>
    </div>
  );
}

/** Video hero card with the tile mosaic, the headline and the floating navigation. */
function Hero() {
  const reduce = useReducedMotion();
  return (
    <section
      aria-labelledby="hero-title"
      className="relative isolate mx-auto flex h-[600px] w-full max-w-[1400px] flex-col overflow-hidden rounded-[48px] border border-slate-200/50 bg-white shadow-[0_40px_100px_-20px_rgba(0,0,0,0.03)]"
    >
      {/* Decorative. With reduced motion it stays on its first frame. */}
      <video
        aria-hidden
        tabIndex={-1}
        src={HERO_VIDEO}
        autoPlay={!reduce}
        loop
        muted
        playsInline
        className="pointer-events-none absolute inset-0 z-0 h-full w-full scale-105 object-cover transition-transform duration-1000"
      />
      {/* Right of the headline on large screens; a band under it, fading in, on smaller ones. */}
      <DealMosaic className="absolute inset-x-4 top-[62%] bottom-0 z-10 [mask-image:linear-gradient(to_bottom,transparent,black_45%)] md:inset-x-8 lg:inset-y-0 lg:right-12 lg:left-auto lg:w-[40%] lg:[mask-image:linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)] xl:w-[44%]" />
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.9, ease }}
        className="relative z-20 flex flex-1 flex-col items-start px-8 pt-12 md:px-16 md:pt-16"
      >
        <Link to="/" aria-label="DealMeet AI home" className="mb-8 rounded-lg">
          <Wordmark />
        </Link>
        <h1 id="hero-title" className="font-display text-[42px] leading-[1.08] text-[#0a1b33] md:text-[56px]">
          Foundation of the
          {/* The break only from md: at 42px on a phone it would leave "the" alone on a line. */}
          <br className="hidden md:block" /> new digital epoch
        </h1>
        <p className="mt-5 max-w-md font-sans text-[14px] leading-relaxed text-[#64748b] md:text-[15px]">
          Other dashboards tell creators how they're doing. DealMeet AI tells them what to do next, prices it fairly,
          and makes sure they get paid.
        </p>
      </motion.div>
      <FloatingNav />
    </section>
  );
}

function NavItem({ to, className, children }: { to: string; className?: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full px-3.5 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-[#0a1b33]",
        className,
      )}
    >
      {children}
    </Link>
  );
}

/** Where a signed-in visitor's dashboard is, or null when nobody is signed in. */
function useDashboard(): string | null {
  return useSignedInHome().to;
}

/** Pill navigation floating at the bottom of the hero. Every item goes to a real page. */
function FloatingNav() {
  const reduce = useReducedMotion();
  const dashboard = useDashboard();
  return (
    <motion.nav
      aria-label="Primary"
      initial={reduce ? false : { opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease, delay: 0.25 }}
      className="absolute bottom-10 left-1/2 z-30 flex -translate-x-1/2 items-center rounded-full border border-slate-200/40 bg-white/90 px-1.5 py-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.08)] backdrop-blur-2xl"
    >
      <Link
        to="/"
        aria-label="DealMeet AI home"
        className="mr-1 grid size-9 shrink-0 place-items-center rounded-full bg-[#0a1b33] text-[15px] leading-none text-white"
      >
        <span aria-hidden>✦</span>
      </Link>
      {/* Finding people: each opens a search with the busiest niches or categories. */}
      <ExplorePopover kind="creators">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-linear-to-r from-violet-500/10 via-pink-500/10 to-orange-400/10 px-3.5 py-2 text-[13px] font-medium text-[#0a1b33] ring-1 ring-violet-500/25 ring-inset transition-shadow hover:ring-violet-500/50"
        >
          <Search className="size-3.5 text-violet-600" aria-hidden /> Creators
        </button>
      </ExplorePopover>
      <ExplorePopover kind="brands">
        <button
          type="button"
          className="inline-flex items-center whitespace-nowrap rounded-full px-3.5 py-2 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-[#0a1b33]"
        >
          Brands
        </button>
      </ExplorePopover>
      {!dashboard && (
        <NavItem to="/login" className="hidden sm:inline-flex">
          Sign in
        </NavItem>
      )}
      <Link
        to={dashboard ?? "/login?mode=signup"}
        className="ml-1 inline-flex items-center gap-0.5 whitespace-nowrap rounded-full bg-[#0a1b33] py-2 pl-4 pr-2.5 text-[13px] font-medium text-white transition-colors hover:bg-[#16305a]"
      >
        {dashboard ? "Your dashboard" : "Get started"}
        <ChevronRight className="size-4" aria-hidden />
      </Link>
    </motion.nav>
  );
}

/**
 * Seamless logo scroller, pure CSS: the track holds the list twice and slides by half its
 * width (--animate-marquee). Pauses on hover; with reduced motion it's a still, wrapped list.
 */
function WorksWith() {
  return (
    <section aria-labelledby="works-with" className="mx-auto mt-10 w-full max-w-[1400px]">
      <h2 id="works-with" className="text-center font-sans text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
        Works with
      </h2>
      <div className="group/marquee mt-4 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)] motion-reduce:[mask-image:none]">
        <div className="flex w-max animate-marquee py-2 group-hover/marquee:[animation-play-state:paused] motion-reduce:w-full motion-reduce:animate-none">
          {[0, 1].map((copy) => (
            <ul
              key={copy}
              aria-hidden={copy === 1 || undefined}
              // pr-3 matches gap-3, so each copy is exactly half the track and the loop has no seam.
              className={cn(
                "flex shrink-0 gap-3 pr-3 motion-reduce:w-full motion-reduce:flex-wrap motion-reduce:justify-center motion-reduce:pr-0",
                copy === 1 && "motion-reduce:hidden",
              )}
            >
              {INTEGRATIONS.map(({ icon, label }) => (
                <li
                  key={label}
                  className="group/logo relative flex shrink-0 items-center gap-2.5 overflow-hidden whitespace-nowrap rounded-full border border-slate-200/40 bg-white py-2.5 pl-4 pr-5 shadow-[0_12px_40px_rgba(0,0,0,0.04)]"
                >
                  <span
                    aria-hidden
                    className="absolute inset-0 scale-125 rounded-full bg-linear-to-r from-violet-100 via-pink-100 to-orange-100 opacity-0 transition-[opacity,scale] duration-500 ease-[var(--ease-soft)] group-hover/logo:scale-100 group-hover/logo:opacity-100"
                  />
                  <svg viewBox="0 0 24 24" aria-hidden className="relative size-5 transition-[filter] duration-300 group-hover/logo:brightness-0">
                    <path d={icon.path} fill={`#${icon.hex}`} />
                  </svg>
                  <span className="relative font-sans text-[13px] font-medium text-slate-600 transition-colors group-hover/logo:text-[#0a1b33]">
                    {label}
                  </span>
                </li>
              ))}
            </ul>
          ))}
        </div>
      </div>
    </section>
  );
}

function CreatorEntry() {
  // What the Studio gives you each week. Features, not figures: real numbers come from your own accounts.
  const moves = [
    { t: "Your fair rate for a reel", v: "A range, with reasons" },
    { t: "What to post next", v: "From your own numbers" },
    { t: "Offers that fit your audience", v: "You choose who sees what" },
  ];
  return (
    <Link
      to="/login?role=creator&mode=signup"
      className="group relative block h-full overflow-hidden rounded-[28px] border border-line-strong bg-surface p-5 transition-[transform,border-color] duration-300 ease-[var(--ease-soft)] hover:-translate-y-1 hover:border-accent/50 sm:p-7"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-[radial-gradient(circle,rgb(219_39_119/0.35),transparent_65%)] blur-2xl transition-opacity duration-500 group-hover:opacity-100 sm:opacity-80"
      />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Creator Studio</p>
          <h3 className="mt-1.5 font-display text-2xl font-semibold sm:text-[28px]">Register as a creator</h3>
          <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-fg-2">
            Your next 3 moves, your fair rate, and deals that pay on time.
          </p>
        </div>
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-signature-strong text-white transition-transform duration-300 group-hover:translate-x-1">
          <ArrowRight className="size-4" aria-hidden />
        </span>
      </div>
      <ol aria-hidden className="relative mt-5 hidden space-y-2 sm:block">
        {moves.map((m, i) => (
          <li
            key={m.t}
            className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface-2 px-3.5 py-2.5 text-[13px]"
            style={{ marginLeft: i * 10 }}
          >
            <span className="flex items-center gap-2.5">
              <span className="num grid size-5 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">
                {i + 1}
              </span>
              {m.t}
            </span>
            <span className="hidden text-right text-xs text-muted md:block">{m.v}</span>
          </li>
        ))}
      </ol>
    </Link>
  );
}

function BrandEntry() {
  // What the Console does for each campaign. Features, not figures.
  const rows = [
    { n: "Creators ranked by audience fit", d: "With the reasons" },
    { n: "A fair price for each creator", d: "From their real reach" },
    { n: "One creator or a whole collective", d: "Paid through escrow" },
  ];
  return (
    <Link
      to="/login?role=brand&mode=signup"
      className="theme-brand group relative block h-full overflow-hidden rounded-[28px] border border-white/20 bg-[#F8F7FC] p-5 text-fg shadow-[0_30px_80px_-30px_rgb(124_58_237/0.55)] transition-transform duration-300 ease-[var(--ease-soft)] hover:-translate-y-1 sm:p-7"
    >
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Brand Console</p>
          <h3 className="mt-1.5 font-display text-2xl font-semibold sm:text-[28px]">Register as a brand</h3>
          <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-fg-2">
            Find creators who fit, see a fair price with reasons, and book one creator or a whole collective.
          </p>
        </div>
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-fg text-white transition-transform duration-300 group-hover:translate-x-1">
          <ArrowRight className="size-4" aria-hidden />
        </span>
      </div>
      <div aria-hidden className="relative mt-5 hidden rounded-2xl border border-line bg-white p-3 sm:block">
        <div className="mb-2 flex items-center justify-between px-1 text-[11px] font-medium uppercase tracking-wide text-muted">
          <span>For every campaign</span>
          <span className="flex items-center gap-1">
            <BadgeIndianRupee className="size-3.5" /> Fair price
          </span>
        </div>
        {rows.map((r) => (
          <div key={r.n} className="flex items-center gap-3 rounded-lg px-1 py-1.5 text-[13px]">
            <Check className="size-4 shrink-0 text-accent" />
            <span className="min-w-0 flex-1 truncate text-fg-2">{r.n}</span>
            <span className="hidden shrink-0 text-xs text-muted md:block">{r.d}</span>
          </div>
        ))}
      </div>
    </Link>
  );
}
