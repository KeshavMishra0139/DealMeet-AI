// Loads a 3D scene only when the browser can draw it. three.js lives in its own
// lazily loaded chunks, so screens without 3D never download it. Without WebGL,
// or if a scene fails, the 2D fallback renders instead.
import { Component, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

let webgl: boolean | null = null;
export function hasWebGL() {
  if (webgl !== null) return webgl;
  try {
    const c = document.createElement("canvas");
    webgl = !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    webgl = false;
  }
  return webgl;
}

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

// Scenes animate while the viewer is doing something (moving the pointer,
// scrolling, typing) and hold their last frame after a few idle seconds, so a
// page left open doesn't keep the graphics chip busy. A held scene still
// redraws when something changes, such as a window resize or new data.
const IDLE_MS = 6000;
let busy = true;
let idleTimer: ReturnType<typeof setTimeout> | undefined;
const activityListeners = new Set<() => void>();
function setBusy(v: boolean) {
  if (busy === v) return;
  busy = v;
  activityListeners.forEach((l) => l());
}
function poke() {
  setBusy(true);
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => setBusy(false), IDLE_MS);
}
if (typeof window !== "undefined") {
  for (const ev of ["pointermove", "pointerdown", "wheel", "scroll", "keydown", "touchstart"]) {
    window.addEventListener(ev, poke, { passive: true, capture: true });
  }
  poke();
}
function useViewerBusy() {
  const [v, setV] = useState(busy);
  useEffect(() => {
    const on = () => setV(busy);
    activityListeners.add(on);
    on();
    return () => {
      activityListeners.delete(on);
    };
  }, []);
  return v;
}

/** True while the element is on screen; scenes stop rendering frames when it's false. */
export function useOnScreen<T extends Element>(margin = "120px") {
  const ref = useRef<T>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { rootMargin: margin });
    io.observe(el);
    return () => io.disconnect();
  }, [margin]);
  return [ref, on] as const;
}

export function Stage3D({
  children,
  fallback = null,
  className,
  label,
  media,
}: {
  /** Receives whether the scene should animate (on screen, viewer active) and whether it's on screen. */
  children: (active: boolean, onScreen: boolean) => ReactNode;
  fallback?: ReactNode;
  className?: string;
  /** Describes the scene for screen readers; omit for decorative scenes. */
  label?: string;
  /** Only load the scene when this media query matches (e.g. wide screens). */
  media?: string;
}) {
  const [ref, onScreen] = useOnScreen<HTMLDivElement>();
  const viewerBusy = useViewerBusy();
  const active = onScreen && viewerBusy;
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const mq = media ? window.matchMedia(media) : null;
    const update = () => setReady(hasWebGL() && (!mq || mq.matches));
    update();
    mq?.addEventListener("change", update);
    return () => mq?.removeEventListener("change", update);
  }, [media]);
  return (
    <div
      ref={ref}
      className={cn("relative", className)}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      {ready ? (
        <SceneBoundary fallback={fallback}>
          <Suspense fallback={fallback}>{children(active, onScreen)}</Suspense>
        </SceneBoundary>
      ) : (
        fallback
      )}
    </div>
  );
}
