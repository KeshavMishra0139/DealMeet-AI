// Brand Console: matched creators as a 3D value map.
//   x = fair price, y = reach (median views), both on log scales; z = trust.
//   Colour and size follow audience fit. Up and to the left is more reach per
//   rupee. Weak trust shows as a hollow grey sphere, and creators who haven't
//   shared stats sit on the floor as outlines.
// Drag to turn it (mouse), hover for details, click to open the profile.
import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

export interface MapPoint {
  id: string;
  name: string;
  fit: number;
  medianViews: number | null;
  trust: number | null;
  fair: number;
  fairLabel: string;
  viewsLabel: string | null;
}

const LOW = new THREE.Color("#7C3AED");
const MID = new THREE.Color("#DB2777");
const HIGH = new THREE.Color("#F97316");
const BOX = { x: 5.4, y: 3.2, z: 3.2 };

/** Fit is scaled to the range present, so a list of strong matches still spreads out. */
interface Ranges {
  fitMin: number;
  fitMax: number;
  minLog: number;
  maxLog: number;
  minPrice: number;
  maxPrice: number;
}

function colorFor(fit: number, r: Ranges) {
  const t = Math.min(1, Math.max(0, (fit - r.fitMin) / Math.max(1, r.fitMax - r.fitMin)));
  return t < 0.5 ? LOW.clone().lerp(MID, t * 2) : MID.clone().lerp(HIGH, (t - 0.5) * 2);
}

function place(p: MapPoint, r: Ranges) {
  const x = ((Math.log10(Math.max(1, p.fair)) - r.minPrice) / Math.max(0.3, r.maxPrice - r.minPrice) - 0.5) * BOX.x;
  const y = p.medianViews ? ((Math.log10(p.medianViews) - r.minLog) / Math.max(0.5, r.maxLog - r.minLog)) * BOX.y : 0.05;
  const z = ((p.trust ?? 60) / 100 - 0.5) * BOX.z;
  return new THREE.Vector3(x, y, z);
}

function Node({ p, pos, radius, ranges, onOpen, still }: { p: MapPoint; pos: THREE.Vector3; radius: number; ranges: Ranges; onOpen: (id: string) => void; still: boolean }) {
  const mesh = useRef<THREE.Mesh>(null);
  const [hover, setHover] = useState(false);
  const weak = p.trust !== null && p.trust < 50;
  const hidden = p.medianViews === null;
  const color = useMemo(() => (weak ? new THREE.Color("#9CA3AF") : colorFor(p.fit, ranges)), [p.fit, weak, ranges]);
  useFrame((state) => {
    if (!mesh.current) return;
    const s = hover ? 1.35 : 1;
    const bob = still ? 0 : Math.sin(state.clock.elapsedTime * 1.2 + pos.x * 2) * 0.03;
    mesh.current.scale.lerp(new THREE.Vector3(s, s, s), 0.2);
    mesh.current.position.y = pos.y + bob;
  });
  return (
    <group>
      <mesh
        ref={mesh}
        position={pos}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHover(false);
          document.body.style.cursor = "";
        }}
        onClick={(e) => {
          e.stopPropagation();
          onOpen(p.id);
        }}
      >
        <sphereGeometry args={[radius, 32, 32]} />
        {weak || hidden ? (
          <meshBasicMaterial color={color} wireframe transparent opacity={0.7} />
        ) : (
          <meshPhysicalMaterial color={color} roughness={0.25} metalness={0.1} clearcoat={1} emissive={color} emissiveIntensity={hover ? 0.45 : 0.12} />
        )}
      </mesh>
      {/* Drop line to the floor makes height readable */}
      <mesh position={[pos.x, pos.y / 2, pos.z]}>
        <cylinderGeometry args={[0.006, 0.006, Math.max(0.001, pos.y), 6]} />
        <meshBasicMaterial color="#6B6783" transparent opacity={0.35} />
      </mesh>
      {hover && (
        <Html position={[pos.x, pos.y + radius + 0.25, pos.z]} center className="pointer-events-none">
          <div className="w-48 rounded-xl border border-line-strong bg-white/95 p-2.5 text-left text-[12px] text-[#14121F] shadow-xl">
            <p className="font-semibold">{p.name}</p>
            <p className="num mt-0.5 text-[#4A4660]">
              Fit {p.fit} · {p.viewsLabel ? `${p.viewsLabel} median views` : "stats not shared"}
            </p>
            <p className="num text-[#4A4660]">
              Trust {p.trust ?? "n/a"} · fair {p.fairLabel}
            </p>
            <p className="mt-1 text-[11px] text-[#6B6783]">Click to open the profile</p>
          </div>
        </Html>
      )}
    </group>
  );
}

function Axes() {
  const half = { x: BOX.x / 2, z: BOX.z / 2 };
  const grid = useMemo(() => {
    const g = new THREE.GridHelper(BOX.x, 6, "#C9C3DD", "#E4E0EF");
    g.scale.set(1, 1, BOX.z / BOX.x);
    return g;
  }, []);
  return (
    <group>
      <primitive object={grid} />
      <mesh position={[-half.x, BOX.y / 2, -half.z]}>
        <cylinderGeometry args={[0.008, 0.008, BOX.y, 6]} />
        <meshBasicMaterial color="#8A86A0" />
      </mesh>
      <Html position={[half.x, 0, half.z + 0.35]} center className="pointer-events-none">
        <span className="whitespace-nowrap text-[11px] font-medium text-[#4A4660]">Fair price →</span>
      </Html>
      <Html position={[-half.x, BOX.y + 0.25, -half.z]} center className="pointer-events-none">
        <span className="whitespace-nowrap text-[11px] font-medium text-[#4A4660]">↑ Reach</span>
      </Html>
      <Html position={[half.x + 0.3, 0, -half.z]} center className="pointer-events-none">
        <span className="whitespace-nowrap text-[11px] font-medium text-[#4A4660]">Trust ↗</span>
      </Html>
    </group>
  );
}

export default function MatchMap3D({
  points,
  onOpen,
  active,
  still,
  interactive,
}: {
  points: MapPoint[];
  onOpen: (id: string) => void;
  active: boolean;
  still: boolean;
  interactive: boolean;
}) {
  const ranges = useMemo<Ranges>(() => {
    const logs = points.filter((p) => p.medianViews).map((p) => Math.log10(p.medianViews!));
    const fits = points.map((p) => p.fit);
    const prices = points.map((p) => Math.log10(Math.max(1, p.fair)));
    return {
      minPrice: Math.min(...prices) - 0.05,
      maxPrice: Math.max(...prices) + 0.05,
      fitMin: Math.max(0, Math.min(...fits) - 3),
      fitMax: Math.min(100, Math.max(...fits) + 1),
      minLog: logs.length ? Math.min(...logs) - 0.15 : 3,
      maxLog: logs.length ? Math.max(...logs) : 5,
    };
  }, [points]);
  return (
    <Canvas
      frameloop={still ? "demand" : active ? "always" : "never"}
      dpr={[1, 1.75]}
      camera={{ position: [3.4, 3.1, 5.6], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent", touchAction: "pan-y" }}
    >
      <ambientLight intensity={0.75} />
      <directionalLight position={[3, 6, 4]} intensity={1.5} />
      <pointLight position={[-4, 3, 3]} intensity={12} color="#DB2777" />
      <group position={[0, -1.25, 0]}>
        <Axes />
        {points.map((p) => (
          <Node
            key={p.id}
            p={p}
            pos={place(p, ranges)}
            radius={0.09 + 0.13 * Math.min(1, Math.max(0, (p.fit - ranges.fitMin) / Math.max(1, ranges.fitMax - ranges.fitMin)))}
            ranges={ranges}
            onOpen={onOpen}
            still={still}
          />
        ))}
      </group>
      <OrbitControls
        enabled={interactive}
        enableZoom={false}
        enablePan={false}
        autoRotate={!still}
        autoRotateSpeed={0.45}
        minPolarAngle={Math.PI / 5}
        maxPolarAngle={Math.PI / 2.1}
        target={[0, 0.1, 0]}
      />
    </Canvas>
  );
}
