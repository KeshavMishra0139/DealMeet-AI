// Landing hero: a glossy "creator" core with brand cards and rupee coins in orbit.
// Follows the pointer and drifts with page scroll. Decorative only.
import { Environment, Float, Lightformer, MeshDistortMaterial, RoundedBox } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

const VIOLET = "#7C3AED";
const MAGENTA = "#DB2777";
const ORANGE = "#F97316";

function Core({ still }: { still: boolean }) {
  const mesh = useRef<THREE.Mesh>(null);
  useFrame((_, dt) => {
    if (still || !mesh.current) return;
    mesh.current.rotation.y += dt * 0.25;
    mesh.current.rotation.x += dt * 0.08;
  });
  return (
    <Float speed={still ? 0 : 1.4} rotationIntensity={0.4} floatIntensity={0.8}>
      <mesh ref={mesh}>
        <sphereGeometry args={[1, 96, 96]} />
        <MeshDistortMaterial
          color={VIOLET}
          distort={still ? 0.25 : 0.32}
          speed={still ? 0 : 1.6}
          roughness={0.12}
          metalness={0.25}
          emissive={MAGENTA}
          emissiveIntensity={0.12}
        />
      </mesh>
    </Float>
  );
}

function OrbitCard({ angle, radius, color, tilt, still }: { angle: number; radius: number; color: string; tilt: number; still: boolean }) {
  const group = useRef<THREE.Group>(null);
  const phase = useRef(angle);
  useFrame((_, dt) => {
    if (!group.current) return;
    if (!still) phase.current += dt * 0.32;
    const a = phase.current;
    group.current.position.set(Math.cos(a) * radius, Math.sin(a * 1.3) * 0.35 + tilt, Math.sin(a) * radius * 0.55);
    group.current.rotation.set(0.15, -a + Math.PI / 2, 0.05);
  });
  return (
    <group ref={group}>
      <RoundedBox args={[0.84, 0.53, 0.05]} radius={0.07} smoothness={4}>
        <meshPhysicalMaterial color={color} roughness={0.25} metalness={0.05} clearcoat={0.8} transparent opacity={0.92} />
      </RoundedBox>
      {/* A "fit bar" printed on the card */}
      <mesh position={[-0.1, -0.1, 0.03]}>
        <boxGeometry args={[0.5, 0.05, 0.01]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.85} />
      </mesh>
      <mesh position={[-0.16, 0.1, 0.03]}>
        <boxGeometry args={[0.37, 0.065, 0.01]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.55} />
      </mesh>
    </group>
  );
}

function Coins({ still }: { still: boolean }) {
  const coins = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => ({
        pos: new THREE.Vector3(Math.cos(i * 0.9) * (2.4 + (i % 3) * 0.35), ((i * 37) % 10) / 10 - 0.5 + (i % 2 ? 0.9 : -0.9), Math.sin(i * 0.9) * 1.2),
        speed: 0.6 + (i % 4) * 0.2,
      })),
    [],
  );
  return (
    <>
      {coins.map((c, i) => (
        <Float key={i} speed={still ? 0 : c.speed * 2} rotationIntensity={still ? 0 : 2} floatIntensity={1.2} position={c.pos}>
          <mesh rotation={[Math.PI / 2.4, 0, i]}>
            <cylinderGeometry args={[0.17, 0.17, 0.045, 40]} />
            <meshStandardMaterial color="#FCD34D" metalness={0.6} roughness={0.28} emissive="#F59E0B" emissiveIntensity={0.25} />
          </mesh>
        </Float>
      ))}
    </>
  );
}

function Rig({ still, children }: { still: boolean; children: React.ReactNode }) {
  const group = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!group.current) return;
    const scroll = Math.min(window.scrollY / 900, 1);
    const tx = still ? 0 : state.pointer.y * 0.18 + scroll * 0.5;
    const ty = still ? 0 : state.pointer.x * 0.35 + scroll * 1.2;
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, tx, 0.06);
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, ty, 0.06);
    group.current.position.y = THREE.MathUtils.lerp(group.current.position.y, scroll * 1.1, 0.08);
  });
  return <group ref={group}>{children}</group>;
}

export default function HeroOrbit({ active, still }: { active: boolean; still: boolean }) {
  return (
    <Canvas
      frameloop={still ? "demand" : active ? "always" : "never"}
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.2, 8.6], fov: 36 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      style={{ background: "transparent" }}
      // Track the pointer over the whole page, not just the canvas.
      eventSource={document.getElementById("root") ?? undefined}
      eventPrefix="client"
    >
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 4, 5]} intensity={1.3} />
      <pointLight position={[-4, -1, 2]} intensity={18} color={MAGENTA} />
      <pointLight position={[4, -2, -1]} intensity={14} color={ORANGE} />
      <Rig still={still}>
        <Core still={still} />
        <mesh rotation={[Math.PI / 2.25, 0, 0.2]}>
          <torusGeometry args={[2.25, 0.012, 16, 160]} />
          <meshBasicMaterial color={MAGENTA} transparent opacity={0.55} />
        </mesh>
        <OrbitCard angle={0} radius={2.25} color={VIOLET} tilt={0.15} still={still} />
        <OrbitCard angle={Math.PI * 0.66} radius={2.25} color={MAGENTA} tilt={-0.1} still={still} />
        <OrbitCard angle={Math.PI * 1.33} radius={2.25} color={ORANGE} tilt={0.05} still={still} />
        <Coins still={still} />
      </Rig>
      {/* Studio reflections built from light panels: no downloaded HDR, works offline. */}
      <Environment resolution={128}>
        <Lightformer form="rect" intensity={2.2} color="#ffffff" position={[0, 3, 4]} scale={[6, 2, 1]} />
        <Lightformer form="ring" intensity={3} color={MAGENTA} position={[-4, 0, 2]} scale={2.5} />
        <Lightformer form="rect" intensity={2} color={ORANGE} position={[4, -2, 1]} scale={[3, 3, 1]} />
      </Environment>
    </Canvas>
  );
}
