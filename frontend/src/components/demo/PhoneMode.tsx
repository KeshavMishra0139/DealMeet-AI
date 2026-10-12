import { motion } from "framer-motion";
import { MonitorSmartphone, Smartphone, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Kbd } from "@/components/shared/Bits";
import { Wordmark } from "@/components/shared/Wordmark";
import { Button } from "@/components/ui/button";
import {
  framePath,
  isTypingTarget,
  postToFrame,
  postToParent,
  publicPath,
  setPhoneMode,
  togglePhoneMode,
  usePhoneMode,
  type FrameMessage,
} from "@/lib/phone";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";
import { PHONE_OUTER, PhoneFrame, useFitScale } from "./Frames";

/** Listens for DealMeet messages from same-origin frames; the handler gets the sending window to tell frames apart. */
export function useFrameMessages(handler: (msg: FrameMessage, source: MessageEventSource | null) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || typeof e.data?.type !== "string" || !e.data.type.startsWith("jd:")) return;
      ref.current(e.data as FrameMessage, e.source);
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
}

/** P toggles phone view. Inside a frame the key is forwarded to the page that owns the frame. */
export function usePhoneShortcut(embedded: boolean, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "p" && e.key !== "P") return;
      if (isTypingTarget(e) || e.defaultPrevented) return;
      if (embedded) postToParent({ type: "jd:toggle-phone" });
      else togglePhoneMode();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [embedded, enabled]);
}

/** Runs inside framed copies of the app: follows navigation requests and reports the route. */
export function EmbedBridge() {
  const location = useLocation();
  const navigate = useNavigate();
  useFrameMessages((msg, source) => {
    if (source !== window.parent) return;
    if (msg.type === "jd:navigate") navigate(msg.to);
  });
  useEffect(() => {
    postToParent({ type: "jd:route", path: `${location.pathname}${location.search}${location.hash}` });
  }, [location]);
  return null;
}

/** Floating switch for phone view, shown on desktop-sized screens. */
export function PhoneToggle() {
  const on = usePhoneMode();
  return (
    <aside aria-label="Presentation" className="fixed bottom-4 right-4 z-[45] hidden lg:block">
      <button
        type="button"
        aria-pressed={on}
        onClick={() => setPhoneMode(!on)}
        title="Phone view (P)"
        className={cn(
          "group flex h-10 items-center gap-2 rounded-full border px-3 text-xs font-medium shadow-lg transition-colors",
          on ? "border-transparent bg-accent text-accent-fg" : "border-line-strong bg-[var(--surface-solid)] text-fg-2 hover:text-fg",
        )}
      >
        <Smartphone className="size-4" aria-hidden />
        <span className="sr-only">Phone view</span>
        <span className="max-w-0 overflow-hidden whitespace-nowrap transition-[max-width] duration-200 group-hover:max-w-24 group-focus-visible:max-w-24 motion-reduce:transition-none" aria-hidden>
          Phone view
        </span>
        <Kbd className={cn(on && "border-white/40 bg-white/15 text-white")}>P</Kbd>
      </button>
    </aside>
  );
}

/** The whole app inside a 390 x 844 phone, for presenting on a laptop or projector. */
export function PhoneStage() {
  useTheme("creator");
  const location = useLocation();
  const navigate = useNavigate();
  const current = `${location.pathname}${location.search}${location.hash}`;
  const src = useRef(framePath(current));
  const reported = useRef(current);
  const frame = useRef<HTMLIFrameElement>(null);
  const area = useRef<HTMLDivElement>(null);
  const scale = useFitScale(area, PHONE_OUTER.width, PHONE_OUTER.height + 8, 24);

  useFrameMessages((msg, source) => {
    if (source !== frame.current?.contentWindow) return;
    if (msg.type === "jd:route") {
      reported.current = publicPath(msg.path);
      if (reported.current !== current) navigate(reported.current, { replace: true });
    }
    if (msg.type === "jd:toggle-phone") setPhoneMode(false);
  });

  // Back and forward in the outer window move the phone too.
  useEffect(() => {
    if (current !== reported.current) {
      reported.current = current;
      postToFrame(frame.current, { type: "jd:navigate", to: current });
    }
  }, [current]);

  const tone = location.pathname.startsWith("/brand") ? "light" : "dark";
  return (
    <div className="theme-creator grain relative min-h-dvh overflow-hidden">
      <div className="aurora" aria-hidden>
        <span />
      </div>
      <header className="relative z-10 flex items-center justify-between gap-4 px-6 py-4">
        <Link to="/" className="rounded-lg" aria-label="DealMeet AI home">
          <Wordmark />
        </Link>
        <p className="hidden text-sm text-muted md:block">
          Phone view · 390 × 844 · press <Kbd>P</Kbd> to switch back
        </p>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm">
            <Link to="/demo/compare">
              <MonitorSmartphone aria-hidden /> Compare A and B
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={() => setPhoneMode(false)}>
            <X aria-hidden /> Exit phone view
          </Button>
        </div>
      </header>
      <main id="main" ref={area} className="relative z-10 flex justify-center px-4">
        <h1 className="sr-only">DealMeet AI in phone view</h1>
        <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 220, damping: 26 }}>
          <PhoneFrame src={src.current} title="DealMeet AI on a phone" tone={tone} scale={scale} frameRef={frame} />
        </motion.div>
      </main>
    </div>
  );
}
