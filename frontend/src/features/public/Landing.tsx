import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, BadgeIndianRupee, Lock, Play, Scale, ShieldCheck, Youtube } from "lucide-react";
import { Link } from "react-router-dom";
import { ParallaxAurora, Reveal, Stagger, StaggerItem, TiltCard } from "@/components/motion/Motion";
import { Stage3D } from "@/components/three/Stage3D";
import { useDemoMode, useSharedDemo } from "@/lib/shared-demo";
import { HeroOrbit } from "@/components/three/lazy";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

const ease = [0.22, 1, 0.36, 1] as const;

export default function Landing() {
  const shared = useSharedDemo();
  const demo = useDemoMode();
  useTheme("creator");
  const reduce = useReducedMotion();
  const rise = (delay: number) =>
    reduce
      ? {}
      : { initial: { opacity: 0, y: 16 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.7, ease, delay } };

  return (
    <div className="theme-creator grain relative min-h-dvh overflow-x-clip">
      <ParallaxAurora />

      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 sm:py-5">
        <Link to="/" aria-label="DealMeet AI home" className="rounded-lg">
          <Wordmark />
        </Link>
        <nav aria-label="Primary" className="flex items-center gap-1 sm:gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/worth">What am I worth?</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link to="/brands">Brands</Link>
          </Button>
          {demo && (
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
              <Link to="/demo/compare">Demo</Link>
            </Button>
          )}
          <Button asChild variant="outline" size="sm">
            <Link to="/login">Sign in</Link>
          </Button>
        </nav>
      </header>

      <main id="main" className="relative z-10 mx-auto max-w-6xl px-4 sm:px-6">
        {/* 3D hero: creator core with brand cards and coins in orbit. Desktop only; follows the pointer and the scroll. */}
        <Stage3D media="(min-width: 1280px)" className="pointer-events-none absolute -right-36 -top-12 hidden h-[560px] w-[680px] xl:block">
          {(active, onScreen) => <HeroOrbit active={active} onScreen={onScreen} still={!!reduce} />}
        </Stage3D>
        <section aria-labelledby="pitch" className="relative pt-4 sm:pt-12 lg:pt-16">
          <motion.p
            {...rise(0)}
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-2"
          >
            <span className="size-1.5 rounded-full bg-signature" aria-hidden />
            Creator monetisation and brand opportunity engine
          </motion.p>
          <motion.h1
            {...rise(0.05)}
            id="pitch"
            className="max-w-[18ch] font-display text-[29px] font-semibold leading-[1.12] tracking-[-0.03em] sm:max-w-[22ch] sm:text-5xl sm:leading-[1.06] lg:max-w-[24ch] lg:text-[60px] xl:max-w-[17ch]"
          >
            <span className="text-muted">Other dashboards tell creators how they're doing. </span>
            DealMeet AI tells them <span className="text-gradient">what to do next</span>, prices it fairly, and makes
            sure they get paid.
          </motion.h1>
        </section>

        <section aria-label="Choose your side" className="mt-7 grid gap-3 sm:mt-10 sm:gap-4 md:grid-cols-2">
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

        <motion.div {...rise(0.3)} className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2 sm:mt-7">
          {demo && (
            <>
              <Button asChild variant="outline" size="lg" className="h-11 sm:h-12">
                <Link to="/demo/compare?guide=1">
                  <Play className="fill-current" aria-hidden /> Watch the demo
                </Link>
              </Button>
              <span className="text-sm text-muted">Two creators, two different plans, side by side.</span>
            </>
          )}
          <Button asChild variant={demo ? "ghost" : "outline"} size="lg" className="h-11 sm:h-12">
            <Link to="/worth">
              <Youtube aria-hidden /> What am I worth? Check your YouTube channel
            </Link>
          </Button>
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
            <p>All brands and profiles are fictional, except one anonymised reference profile.</p>
          </footer>
          </Reveal>
        </section>
      </main>
    </div>
  );
}

function CreatorEntry() {
  const moves = [
    { t: "Raise your reel rate", v: "₹17K–18K" },
    { t: "Post 2 more beat-sync edits", v: "+2.8L–3.5L views" },
    { t: "Apply to 2 matched offers", v: "₹21K–33K" },
  ];
  return (
    <Link
      to="/login?role=creator"
      className="group relative block h-full overflow-hidden rounded-[28px] border border-line-strong bg-surface p-5 transition-[transform,border-color] duration-300 ease-[var(--ease-soft)] hover:-translate-y-1 hover:border-accent/50 sm:p-7"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full bg-[radial-gradient(circle,rgb(219_39_119/0.35),transparent_65%)] blur-2xl transition-opacity duration-500 group-hover:opacity-100 sm:opacity-80"
      />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Creator Studio</p>
          <h2 className="mt-1.5 font-display text-2xl font-semibold sm:text-[28px]">I'm a creator</h2>
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
            <span className="num font-medium text-fg">{m.v}</span>
          </li>
        ))}
      </ol>
    </Link>
  );
}

function BrandEntry() {
  const rows = [
    { n: "Anime edits · Hindi", fit: 92 },
    { n: "Gaming · Hinglish", fit: 86 },
    { n: "Anime edits · Marathi", fit: 79 },
  ];
  return (
    <Link
      to="/login?role=brand"
      className="theme-brand group relative block h-full overflow-hidden rounded-[28px] border border-white/20 bg-[#F8F7FC] p-5 text-fg shadow-[0_30px_80px_-30px_rgb(124_58_237/0.55)] transition-transform duration-300 ease-[var(--ease-soft)] hover:-translate-y-1 sm:p-7"
    >
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Brand Console</p>
          <h2 className="mt-1.5 font-display text-2xl font-semibold sm:text-[28px]">I'm a brand</h2>
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
          <span>12 creators fit · 3 strong</span>
          <span className="flex items-center gap-1">
            <BadgeIndianRupee className="size-3.5" /> Fair price
          </span>
        </div>
        {rows.map((r) => (
          <div key={r.n} className="flex items-center gap-3 rounded-lg px-1 py-1.5 text-[13px]">
            <span className="w-40 shrink-0 truncate text-fg-2">{r.n}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
              <span className="block h-full rounded-full bg-signature" style={{ width: `${r.fit}%` }} />
            </span>
            <span className="num w-8 text-right font-semibold">{r.fit}</span>
          </div>
        ))}
      </div>
    </Link>
  );
}
