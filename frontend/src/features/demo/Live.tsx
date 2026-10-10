import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Columns2, Monitor, RotateCcw, Smartphone } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useFrameMessages } from "@/components/demo/PhoneMode";
import { BrowserFrame, PHONE_OUTER, PhoneFrame, useFitScale, useMediaQuery } from "@/components/demo/Frames";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/form";
import { post } from "@/lib/api";
import { framePath, publicPath } from "@/lib/phone";
import { onSync, syncAvailable } from "@/lib/sync";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

type Who = "phone" | "console";

const SCENARIOS = {
  deal: {
    label: "Deal rail",
    title: "Creator A and Senpai Supply Co.",
    creator: { path: "/creator/deals/dl_a_senpai", as: "cr_a", name: "Creator A" },
    brand: { path: "/brand/deals/dl_a_senpai", as: "br_senpai", name: "Senpai Supply Co." },
    steps: [
      { who: "phone", text: "The offer is flagged as below fair price. Tap Counter: the fair price and its reasons are filled in." },
      { who: "console", text: "The counter arrives at the creator's fair price. Accept it; both e-signatures land on the contract." },
      { who: "console", text: "Fund escrow. Test mode is simulated; no real money moves." },
      { who: "phone", text: "Escrow is funded, so it's safe to post. Paste the reel link once it's live." },
      { who: "console", text: "Confirm the post. The payout goes out by UPI and the invoice is marked paid." },
    ] as { who: Who; text: string }[],
  },
  collective: {
    label: "Collective",
    title: "Creator B and Thalam Foods",
    creator: { path: "/creator/opportunities", as: "cr_b", name: "Creator B" },
    brand: { path: "/brand/campaigns/lst_thalam_collective", as: "br_thalam", name: "Thalam Foods" },
    steps: [
      { who: "phone", text: "Open the Thalam Foods collective and opt in, choosing exactly what the brand can see." },
      { who: "console", text: "Creator B appears as opted in inside the 20-creator pack, with overlap already removed." },
      { who: "console", text: "Book the pack: one escrow payment, split to each creator by UPI once their post is verified." },
    ] as { who: Who; text: string }[],
  },
} as const;

type ScenarioId = keyof typeof SCENARIOS;

const SYNC_LABEL: [RegExp, string][] = [
  [/\/pay/, "Escrow funded"],
  [/\/action/, "Deal updated"],
  [/\/apply/, "Opt-in received"],
  [/\/withdraw/, "Opt-in withdrawn"],
  [/\/collective/, "Collective updated"],
  [/\/demo\/reset/, "Demo reset"],
];

export default function Live() {
  useTheme("creator");
  const qc = useQueryClient();
  const [scenario, setScenario] = useState<ScenarioId>("deal");
  const [nonce, setNonce] = useState(0);
  const [resetting, setResetting] = useState(false);
  const [sync, setSync] = useState<{ label: string; at: number } | null>(null);
  const [consoleUrl, setConsoleUrl] = useState("");
  const phone = useRef<HTMLIFrameElement>(null);
  const browser = useRef<HTMLIFrameElement>(null);
  const row = useRef<HTMLDivElement>(null);
  const wide = useMediaQuery("(min-width: 1024px)");
  const scale = useFitScale(row, PHONE_OUTER.width, PHONE_OUTER.height, 24, wide);
  const s = SCENARIOS[scenario];
  const src = useMemo(
    () => ({ phone: framePath(s.creator.path, s.creator.as), console: framePath(s.brand.path, s.brand.as) }),
    [s],
  );

  useEffect(
    () =>
      onSync((e) => {
        const label = SYNC_LABEL.find(([rx]) => rx.test(e.path))?.[1] ?? "Update received";
        setSync({ label, at: e.at });
      }),
    [],
  );
  useEffect(() => {
    if (!sync) return;
    const t = setTimeout(() => setSync(null), 4500);
    return () => clearTimeout(t);
  }, [sync]);

  // The console's address bar follows navigation inside its frame.
  useFrameMessages((msg, source) => {
    if (msg.type === "jd:route" && source === browser.current?.contentWindow) setConsoleUrl(publicPath(msg.path));
  });

  const height = PHONE_OUTER.height * scale;
  return (
    <div className="theme-creator grain relative min-h-dvh">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <a href="#main" className="sr-only z-50 rounded-lg bg-accent px-3 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to content
      </a>
      <header className="relative z-10 border-b border-line">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link to="/" className="rounded-lg" aria-label="JodiDar AI home">
            <Wordmark />
          </Link>
          <nav aria-label="Demo" className="flex flex-wrap items-center gap-1.5">
            <Button asChild variant="ghost" size="sm">
              <Link to="/demo/compare">
                <Columns2 aria-hidden /> Compare A and B
              </Link>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              loading={resetting}
              onClick={async () => {
                setResetting(true);
                await post("/demo/reset");
                await qc.invalidateQueries();
                setNonce((n) => n + 1);
                setResetting(false);
              }}
            >
              {!resetting && <RotateCcw aria-hidden />} Reset demo
            </Button>
          </nav>
        </div>
      </header>

      <main id="main" className="relative z-10 mx-auto max-w-[1440px] px-4 pb-12 pt-6 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">Live demo · {s.title}</p>
            <h1 className="mt-1.5 font-display text-[28px] font-semibold leading-tight tracking-tight sm:text-[34px]">Creator phone, brand console, one deal</h1>
            <p className="mt-1.5 max-w-2xl text-[15px] text-fg-2">
              Act on either side; the other updates within a second. Both run the real app on demo data.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <SyncPill sync={sync} />
            <Segmented
              label="Scenario"
              value={scenario}
              onChange={(v) => {
                setConsoleUrl("");
                setScenario(v);
              }}
              options={(Object.keys(SCENARIOS) as ScenarioId[]).map((id) => ({ value: id, label: SCENARIOS[id].label }))}
            />
          </div>
        </div>

        <ol className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-5" aria-label="Demo script">
          {s.steps.map((st, i) => (
            <li key={st.text} className="flex gap-2.5 rounded-2xl border border-line bg-surface p-3 text-[13px] leading-snug text-fg-2">
              <span className="num grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">{i + 1}</span>
              <span>
                <span className="mb-0.5 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">
                  {st.who === "phone" ? <Smartphone className="size-3" aria-hidden /> : <Monitor className="size-3" aria-hidden />}
                  {st.who === "phone" ? s.creator.name : s.brand.name}
                </span>
                {st.text}
              </span>
            </li>
          ))}
        </ol>

        <div ref={row} className="mt-6 flex flex-col items-center gap-6 lg:flex-row lg:items-start">
          <PhoneFrame
            key={`p-${scenario}-${nonce}`}
            src={src.phone}
            frameRef={phone}
            scale={scale}
            tone="dark"
            title={`${s.creator.name}'s Creator Studio`}
            label={
              <span className="inline-flex items-center gap-1.5">
                <Smartphone className="size-4 text-accent" aria-hidden /> {s.creator.name} · Creator Studio
              </span>
            }
          />
          <figure className="w-full min-w-0 flex-1">
            <BrowserFrame
              key={`b-${scenario}-${nonce}`}
              src={src.console}
              frameRef={browser}
              url={consoleUrl || publicPath(src.console)}
              height={Math.max(480, height)}
              title={`${s.brand.name} Brand Console`}
            />
            <figcaption className="mt-3 flex items-center justify-center gap-1.5 text-sm text-fg-2">
              <Monitor className="size-4 text-accent" aria-hidden /> {s.brand.name} · Brand Console
            </figcaption>
          </figure>
        </div>
        <p className="mt-4 text-center text-xs text-muted lg:hidden">Best on a laptop or projector: the console renders at desktop width.</p>
      </main>
    </div>
  );
}

function SyncPill({ sync }: { sync: { label: string; at: number } | null }) {
  return (
    <p
      role="status"
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-medium transition-colors motion-reduce:transition-none",
        sync ? "border-success/40 bg-success-soft text-success" : "border-line bg-surface text-fg-2",
      )}
    >
      <span className="relative flex size-2">
        {syncAvailable && <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-60 motion-reduce:animate-none" />}
        <span className="relative inline-flex size-2 rounded-full bg-success" />
      </span>
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={sync?.at ?? "idle"} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
          {sync ? `Synced · ${sync.label}` : syncAvailable ? "Live sync on" : "Live sync: refresh to update"}
        </motion.span>
      </AnimatePresence>
    </p>
  );
}
