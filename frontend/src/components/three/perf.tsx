// Keeps 3D scenes light on modest hardware.
import { PerformanceMonitor } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";

/**
 * How often a scene draws: every frame while it plays, only when something
 * changes (a resize, new data) while the viewer is idle or motion is off, and
 * not at all off screen.
 */
export function frameloopFor({ active, onScreen, still }: { active: boolean; onScreen: boolean; still: boolean }) {
  if (active && !still) return "always" as const;
  return onScreen || still ? ("demand" as const) : ("never" as const);
}

/** Renders at most `fps` frames a second (use with frameloop="demand"). */
export function FrameCap({ fps, on }: { fps: number; on: boolean }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    if (!on) return;
    const id = setInterval(() => invalidate(), 1000 / fps);
    return () => clearInterval(id);
  }, [on, fps, invalidate]);
  return null;
}

/**
 * Keeps scene time continuous across pauses. The renderer restarts its clock
 * from zero whenever the frameloop changes, and the first frame after an idle
 * spell would otherwise jump ahead by the whole pause, so here the clock only
 * moves while frames are drawn, at most 0.1 s a frame.
 */
export function SteadyClock() {
  const played = useRef(0);
  useFrame((state, dt) => {
    played.current += Math.min(dt, 0.1);
    state.clock.elapsedTime = played.current;
  }, -2);
  return null;
}

/**
 * Watches the frame rate; if the device can't keep up, the scene settles into a
 * still, lower-resolution frame instead of stuttering. One-way: it never flips back.
 * Only a falling frame rate counts: a device at or above the upper bound is fine.
 * Mount the monitor only while the scene plays, so paused stretches aren't
 * mistaken for slow frames.
 */
export function useAdaptiveQuality() {
  const [degraded, setDegraded] = useState(false);
  const monitor = (bounds: [number, number]) => <PerformanceMonitor bounds={() => bounds} onDecline={() => setDegraded(true)} />;
  return { degraded, monitor };
}
