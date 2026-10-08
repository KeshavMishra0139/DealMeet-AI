// Keeps 3D scenes light on modest hardware.
import { PerformanceMonitor } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import { useEffect, useState } from "react";

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
 * Watches the frame rate; if the device can't keep up, the scene settles into a
 * still, lower-resolution frame instead of stuttering. One-way: it never flips back.
 */
export function useAdaptiveQuality() {
  const [degraded, setDegraded] = useState(false);
  const monitor = (bounds: [number, number]) => (
    <PerformanceMonitor bounds={() => bounds} flipflops={1} onDecline={() => setDegraded(true)} onFallback={() => setDegraded(true)} />
  );
  return { degraded, monitor };
}
