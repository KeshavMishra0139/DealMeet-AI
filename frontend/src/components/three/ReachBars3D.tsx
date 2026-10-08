// Creator Studio: the last 6 reels as 3D bars against a glass plane at the
// follower count, so "reach is about 7x followers" is something you can see.
// Bars grow in when the card comes into view and lean toward the pointer.
import { Html, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useAdaptiveQuality } from "./perf";

export interface ReachBarsProps {
  reels: { date: string; views: number }[];
  followers: number;
  formatCount: (n: number) => string;
  formatDate: (iso: string) => string;
  active: boolean;
  still: boolean;
}

const COLORS = ["#7C3AED", "#9333EA", "#C026D3", "#DB2777", "#F43F5E", "#F97316"];
const HEIGHT = 2.6;
const GAP = 0.78;

function Bar({ x, h, color, label, value, still, index }: { x: number; h: number; color: string; label: string; value: string; still: boolean; index: number }) {
  const mesh = useRef<THREE.Group>(null);
  const start = useRef<number | null>(null);
  const [hover, setHover] = useState(false);
  // Staggered grow-in (ease-out cubic) from the first frame the card is on screen.
  useFrame((state) => {
    if (!mesh.current) return;
    if (still) {
      mesh.current.scale.y = 1;
      return;
    }
    if (start.current === null) start.current = state.clock.elapsedTime;
    const p = Math.min(1, Math.max(0, (state.clock.elapsedTime - start.current - index * 0.12) / 0.9));
    mesh.current.scale.y = Math.max(0.001, 1 - Math.pow(1 - p, 3));
  });
  return (
    <group position={[x, 0, 0]}>
      <group ref={mesh} scale={[1, still ? 1 : 0.001, 1]}>
        <RoundedBox
          args={[0.5, h, 0.5]}
          radius={0.06}
          smoothness={3}
          position={[0, h / 2, 0]}
          onPointerOver={(e) => {
            e.stopPropagation();
            setHover(true);
          }}
          onPointerOut={() => setHover(false)}
        >
          <meshStandardMaterial color={color} roughness={0.3} metalness={0.1} emissive={color} emissiveIntensity={hover ? 0.5 : 0.18} />
        </RoundedBox>
      </group>
      <Html position={[0, -0.32, 0.3]} center className="pointer-events-none select-none">
        <span className="whitespace-nowrap text-[10px] font-medium text-muted">{label}</span>
      </Html>
      {hover && (
        <Html position={[0, h + 0.35, 0]} center className="pointer-events-none">
          <span className="num whitespace-nowrap rounded-lg border border-line-strong bg-[var(--surface-solid)] px-2 py-1 text-[11px] font-semibold text-fg shadow-lg">
            {value} views
          </span>
        </Html>
      )}
    </group>
  );
}

function Scene({ reels, followers, formatCount, formatDate, still }: Omit<ReachBarsProps, "active">) {
  const rig = useRef<THREE.Group>(null);
  // Narrow canvases (phones) get day-only labels and leave the follower count to the card's legend.
  const compact = useThree((s) => s.size.width) < 560;
  const max = Math.max(followers, ...reels.map((r) => r.views), 1);
  const planeY = (followers / max) * HEIGHT;
  const width = (reels.length - 1) * GAP + 1.2;
  const bars = useMemo(
    () =>
      reels.map((r, i) => ({
        x: (i - (reels.length - 1) / 2) * GAP,
        h: Math.max(0.04, (r.views / max) * HEIGHT),
        color: COLORS[Math.round((i / Math.max(1, reels.length - 1)) * (COLORS.length - 1))],
        label: compact && i > 0 && r.date.slice(0, 7) === reels[i - 1].date.slice(0, 7) ? String(Number(r.date.slice(8, 10))) : formatDate(r.date),
        value: formatCount(r.views),
      })),
    [reels, max, formatCount, formatDate, compact],
  );
  useFrame((state) => {
    if (!rig.current) return;
    const t = state.clock.elapsedTime;
    const ty = still ? -0.45 : -0.45 + state.pointer.x * 0.35 + Math.sin(t * 0.35) * 0.06;
    const tx = still ? 0.16 : 0.16 - state.pointer.y * 0.08;
    rig.current.rotation.y = THREE.MathUtils.lerp(rig.current.rotation.y, ty, 0.06);
    rig.current.rotation.x = THREE.MathUtils.lerp(rig.current.rotation.x, tx, 0.06);
  });
  return (
    <group ref={rig} position={[0, -1.15, 0]}>
      {bars.map((b, i) => (
        <Bar key={i} index={i} {...b} still={still} />
      ))}
      {/* Follower level: a glass plane the bars rise through */}
      <mesh position={[0, planeY, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width + 0.5, 1.3]} />
        <meshStandardMaterial color="#c4b5fd" emissive="#a78bfa" emissiveIntensity={0.35} transparent opacity={0.3} roughness={0.1} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <lineSegments position={[0, planeY, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(width + 0.5, 0.001, 1.3)]} />
        <lineBasicMaterial color="#ddd6fe" transparent opacity={0.9} />
      </lineSegments>
      {!compact && (
        <Html position={[width / 2 + 0.25, planeY + 0.05, 0.65]} className="pointer-events-none">
          <span className="num whitespace-nowrap rounded-full border border-accent/40 bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent">
            {formatCount(followers)} followers
          </span>
        </Html>
      )}
    </group>
  );
}

/** Pulls the camera back on narrow canvases so the whole chart, labels included, stays in frame. */
function FitCamera({ halfWidth }: { halfWidth: number }) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const aspect = size.width / Math.max(1, size.height);
    const z = Math.max(5.3, halfWidth / (Math.tan((camera.fov * Math.PI) / 360) * aspect));
    camera.position.set(0, 1.25 * (z / 5.3), z);
    camera.lookAt(0, 0.1, 0);
    camera.updateProjectionMatrix();
    invalidate();
  }, [camera, size, halfWidth, invalidate]);
  return null;
}

export default function ReachBars3D({ active, still: reduced, ...props }: ReachBarsProps) {
  const { degraded, monitor } = useAdaptiveQuality();
  const still = reduced || degraded;
  return (
    <Canvas
      frameloop={still ? "demand" : active ? "always" : "never"}
      dpr={degraded ? 1 : [1, 1.25]}
      camera={{ position: [0, 1.25, 5.3], fov: 38 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent", touchAction: "pan-y" }}
    >
      {!reduced && monitor([30, 60])}
      <ambientLight intensity={0.55} />
      <directionalLight position={[2, 5, 4]} intensity={1.4} />
      <pointLight position={[-3, 2, 3]} intensity={10} color="#DB2777" />
      <FitCamera halfWidth={((props.reels.length - 1) * GAP) / 2 + 1.35} />
      <Scene {...props} still={still} />
    </Canvas>
  );
}
