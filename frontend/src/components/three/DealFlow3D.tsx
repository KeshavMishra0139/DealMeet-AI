// Brand Console: the deal rail as a 3D track. Each stage is a ring on a glowing
// rail; coin stacks show how many deals sit at that stage, and small glowing
// tokens flow from Offer to Paid, the way money moves through escrow.
import { Html } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

export interface FlowStage {
  label: string;
  count: number;
  amountLabel: string | null;
}

const STOPS = ["#7C3AED", "#9333EA", "#C026D3", "#DB2777", "#F43F5E", "#F97316"];
const SPAN = 9;

function colorAt(t: number) {
  const f = Math.min(0.999, Math.max(0, t)) * (STOPS.length - 1);
  const i = Math.floor(f);
  return new THREE.Color(STOPS[i]).lerp(new THREE.Color(STOPS[i + 1]), f - i);
}

function Rail() {
  const geo = useMemo(() => {
    const g = new THREE.BoxGeometry(SPAN + 0.6, 0.06, 0.06, 64, 1, 1);
    const colors: number[] = [];
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const c = colorAt((pos.getX(i) + SPAN / 2) / SPAN);
      colors.push(c.r, c.g, c.b);
    }
    g.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return g;
  }, []);
  return (
    <mesh geometry={geo}>
      <meshStandardMaterial vertexColors emissive="#ffffff" emissiveIntensity={0.08} roughness={0.4} />
    </mesh>
  );
}

function Tokens({ still }: { still: boolean }) {
  const group = useRef<THREE.Group>(null);
  const tokens = useMemo(() => Array.from({ length: 14 }, (_, i) => ({ offset: i / 14, speed: 0.05 + (i % 4) * 0.012, lift: ((i * 7) % 5) * 0.03 })), []);
  useFrame((state) => {
    if (!group.current) return;
    const t = state.clock.elapsedTime;
    group.current.children.forEach((child, i) => {
      const k = tokens[i];
      const p = still ? k.offset : (k.offset + t * k.speed) % 1;
      child.position.set(p * SPAN - SPAN / 2, 0.14 + k.lift + Math.sin(t * 2 + i) * 0.02, 0);
      const m = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
      m.color.copy(colorAt(p));
      m.emissive.copy(m.color);
      const s = 0.6 + Math.sin(p * Math.PI) * 0.6;
      child.scale.setScalar(s);
    });
  });
  return (
    <group ref={group}>
      {tokens.map((_, i) => (
        <mesh key={i}>
          <sphereGeometry args={[0.07, 16, 16]} />
          <meshStandardMaterial emissiveIntensity={0.9} roughness={0.3} />
        </mesh>
      ))}
    </group>
  );
}

function StageStop({ x, stage, color, still, index }: { x: number; stage: FlowStage; color: string; still: boolean; index: number }) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ring.current || still) return;
    ring.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.8 + index) * 0.25;
  });
  const coins = Math.min(stage.count, 5);
  return (
    <group position={[x, 0, 0]}>
      <mesh ref={ring} rotation={[0, Math.PI / 2, 0]}>
        <torusGeometry args={[0.34, 0.035, 16, 64]} />
        <meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={stage.count ? 0.35 : 0.05} roughness={0.25} clearcoat={1} transparent opacity={stage.count ? 1 : 0.45} />
      </mesh>
      {/* Coin stack: one coin per deal at this stage */}
      {Array.from({ length: coins }, (_, i) => (
        <mesh key={i} position={[0, -0.62 + i * 0.075, 0.55]}>
          <cylinderGeometry args={[0.2, 0.2, 0.06, 40]} />
          <meshStandardMaterial color="#FCD34D" metalness={0.55} roughness={0.3} emissive="#F59E0B" emissiveIntensity={0.3} />
        </mesh>
      ))}
      <Html position={[0, -1.05, 0.55]} center className="pointer-events-none select-none">
        <div className="w-24 text-center leading-tight">
          <p className="text-[11px] font-semibold text-[#14121F]">{stage.label}</p>
          <p className="num text-[11px] text-[#4A4660]">
            {stage.count} {stage.count === 1 ? "deal" : "deals"}
            {stage.amountLabel ? ` · ${stage.amountLabel}` : ""}
          </p>
        </div>
      </Html>
    </group>
  );
}

function Rig({ still, children }: { still: boolean; children: React.ReactNode }) {
  const group = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!group.current) return;
    const ty = still ? -0.18 : -0.18 + state.pointer.x * 0.12;
    const tx = still ? 0.32 : 0.32 - state.pointer.y * 0.06;
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, ty, 0.05);
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, tx, 0.05);
  });
  return <group ref={group}>{children}</group>;
}

function FitCamera() {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const aspect = size.width / Math.max(1, size.height);
    const z = Math.max(6.2, (SPAN / 2 + 0.9) / (Math.tan((camera.fov * Math.PI) / 360) * aspect));
    camera.position.set(0, 0.4, z);
    camera.lookAt(0, -0.25, 0);
    camera.updateProjectionMatrix();
    invalidate();
  }, [camera, size, invalidate]);
  return null;
}

export default function DealFlow3D({ stages, active, still }: { stages: FlowStage[]; active: boolean; still: boolean }) {
  return (
    <Canvas
      frameloop={still ? "demand" : active ? "always" : "never"}
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.4, 7], fov: 34 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent", touchAction: "pan-y" }}
    >
      <FitCamera />
      <ambientLight intensity={0.8} />
      <directionalLight position={[2, 4, 5]} intensity={1.4} />
      <pointLight position={[-4, 1, 3]} intensity={8} color="#DB2777" />
      <Rig still={still}>
        <Rail />
        <Tokens still={still} />
        {stages.map((s, i) => (
          <StageStop key={s.label} x={(i / Math.max(1, stages.length - 1)) * SPAN - SPAN / 2} stage={s} color={STOPS[Math.min(i, STOPS.length - 1)]} still={still} index={i} />
        ))}
      </Rig>
    </Canvas>
  );
}
