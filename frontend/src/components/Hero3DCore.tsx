import React, { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Line, Sphere, Float, Sparkles as DreiSparkles } from '@react-three/drei';
import * as THREE from 'three';
import { Sparkles, Zap } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
}

class WebGLErrorBoundary extends Component<
  { children: React.ReactNode; fallback: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode; fallback: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

interface Node3DData {
  id: string;
  label: string;
  position: [number, number, number];
  color: string;
  size: number;
}

const HERO_NODES: Node3DData[] = [
  { id: 'core', label: 'DataTrust Nexus Core', position: [0, 0, 0], color: '#FDE68A', size: 0.36 },
  { id: 'n1', label: 'Gwalior · Larsen & Toubro', position: [-2.15, 1.05, 0.55], color: '#818CF8', size: 0.22 },
  { id: 'n2', label: 'Morena · Adani Green', position: [2.15, 1.15, -0.45], color: '#38BDF8', size: 0.24 },
  { id: 'n3', label: 'Mumbai · Reliance', position: [-1.85, -1.35, -0.65], color: '#34D399', size: 0.20 },
  { id: 'n4', label: 'Gandhinagar · TCS', position: [1.9, -1.25, 0.75], color: '#C084FC', size: 0.22 },
  { id: 'n5', label: 'Jaipur · Mahindra & Infosys', position: [0.25, 2.05, -0.85], color: '#FB7185', size: 0.19 },
  { id: 'n6', label: 'Bhopal · Biocon & Bharat Forge', position: [-0.35, -1.95, 0.95], color: '#FBBF24', size: 0.20 },
];

const HERO_EDGES: { from: number; to: number; inferred?: boolean }[] = [
  { from: 0, to: 1 },
  { from: 0, to: 2 },
  { from: 0, to: 3 },
  { from: 0, to: 4, inferred: true },
  { from: 0, to: 5 },
  { from: 0, to: 6 },
  { from: 1, to: 5 },
  { from: 2, to: 5 },
  { from: 2, to: 4, inferred: true },
  { from: 3, to: 6 },
];

const NEXUS_RANDOM_ACTS = [
  {
    type: 'ARC_DISCHARGE',
    badge: 'Neural Arc Pulse',
    detail: 'Gwalior Hub ↔ Larsen & Toubro ($6.4M verified)',
    color: '#FDE68A',
    pair: [1, 5] as [number, number],
  },
  {
    type: 'SHOCKWAVE',
    badge: 'Gravity Ripple',
    detail: 'Morena Grid → Adani Green 2-hop link confirmed',
    color: '#38BDF8',
    pair: [0, 2] as [number, number],
  },
  {
    type: 'SUPERNOVA',
    badge: 'Alias Sync',
    detail: 'Merged duplicate: L&T India → Larsen & Toubro',
    color: '#A78BFA',
    pair: [1, 0] as [number, number],
  },
  {
    type: 'ORBIT_SHIFT',
    badge: 'SQL Guard Check',
    detail: 'Mumbai Reliance & Gandhinagar TCS read-only check',
    color: '#34D399',
    pair: [3, 4] as [number, number],
  },
  {
    type: 'STAR_FLARE',
    badge: 'Path Replay',
    detail: 'Bhopal Biocon ↔ Katni Bharat Forge linked',
    color: '#FB7185',
    pair: [3, 6] as [number, number],
  },
];

function CrystalNexusScene({
  onHoverNode,
  pulseTrigger,
  activeActIndex,
}: {
  onHoverNode: (label: string | null) => void;
  pulseTrigger: number;
  activeActIndex: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const innerShellRef = useRef<THREE.Mesh>(null);
  const outerShellRef = useRef<THREE.Mesh>(null);
  const shockwaveRef = useRef<THREE.Mesh>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);
  const travelerRef = useRef<THREE.Mesh>(null);
  const expansionRef = useRef<number>(0);
  const shockwaveScaleRef = useRef<number>(0.5);

  useEffect(() => {
    expansionRef.current = 1.15;
    shockwaveScaleRef.current = 0.6;
  }, [pulseTrigger, activeActIndex]);

  const currentAct = NEXUS_RANDOM_ACTS[activeActIndex % NEXUS_RANDOM_ACTS.length];
  const nodeVecs = useMemo(
    () => HERO_NODES.map((n) => new THREE.Vector3(...n.position)),
    []
  );

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05);
    const t = state.clock.elapsedTime;
    const dampFast = 1 - Math.exp(-4.5 * dt);
    expansionRef.current = THREE.MathUtils.lerp(expansionRef.current, 0, dampFast);
    shockwaveScaleRef.current = THREE.MathUtils.lerp(shockwaveScaleRef.current, 3.6, 1 - Math.exp(-3.2 * dt));
    const expScale = 1 + expansionRef.current * 0.45;

    if (groupRef.current) {
      const targetRotY = t * 0.24 + state.pointer.x * 0.55;
      const targetRotX = Math.sin(t * 0.32) * 0.1 - state.pointer.y * 0.32;
      const rotDamp = 1 - Math.exp(-4.0 * dt);
      groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, targetRotY, rotDamp);
      groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, targetRotX, rotDamp);
    }

    if (innerShellRef.current) {
      innerShellRef.current.rotation.x -= dt * 0.45;
      innerShellRef.current.rotation.z += dt * 0.3;
      innerShellRef.current.scale.setScalar(expScale);
    }
    if (outerShellRef.current) {
      outerShellRef.current.rotation.y += dt * 0.32;
      outerShellRef.current.scale.setScalar(1 + expansionRef.current * 0.7);
    }
    if (shockwaveRef.current) {
      shockwaveRef.current.scale.setScalar(shockwaveScaleRef.current);
      const mat = shockwaveRef.current.material as THREE.MeshBasicMaterial;
      if (mat) {
        mat.opacity = Math.max(0, (3.6 - shockwaveScaleRef.current) * 0.22);
      }
    }
    if (ring1Ref.current) {
      ring1Ref.current.rotation.z += dt * 0.28;
      ring1Ref.current.rotation.x = 0.45 + Math.sin(t * 0.45) * 0.14;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.z -= dt * 0.22;
      ring2Ref.current.rotation.y = 0.65 + Math.cos(t * 0.38) * 0.14;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.x += dt * 0.18;
    }

    // Autonomous energy traveler shooting between the active random act pair (zero per-frame allocations)
    if (travelerRef.current) {
      const [fromIdx, toIdx] = currentAct.pair;
      const alpha = (t * 1.35) % 1;
      travelerRef.current.position.lerpVectors(nodeVecs[fromIdx], nodeVecs[toIdx], alpha);
    }
  });

  const edgeLines = useMemo(() => {
    return HERO_EDGES.map((e, idx) => {
      const start = HERO_NODES[e.from].position;
      const end = HERO_NODES[e.to].position;
      return {
        key: `edge-${idx}`,
        from: e.from,
        to: e.to,
        points: [start, end] as [number, number, number][],
        color: e.inferred ? '#C084FC' : '#7DD3FC',
        dashed: Boolean(e.inferred),
      };
    });
  }, []);

  return (
    <group ref={groupRef}>
      <DreiSparkles count={65} scale={6.2} size={2.1} speed={0.5} color={currentAct.color} />

      {/* Autonomous Expanding Shockwave Ring */}
      <mesh ref={shockwaveRef} rotation={[Math.PI / 3, 0.2, 0]}>
        <ringGeometry args={[0.92, 1.0, 64]} />
        <meshBasicMaterial color={currentAct.color} side={THREE.DoubleSide} transparent opacity={0.4} />
      </mesh>

      <mesh ref={ring1Ref}>
        <torusGeometry args={[2.45, 0.01, 12, 120]} />
        <meshBasicMaterial color="#A78BFA" transparent opacity={0.65} />
      </mesh>
      <mesh ref={ring2Ref}>
        <torusGeometry args={[2.95, 0.008, 12, 120]} />
        <meshBasicMaterial color="#FDE68A" transparent opacity={0.5} />
      </mesh>
      <mesh ref={ring3Ref} rotation={[1.1, 0.4, 0]}>
        <torusGeometry args={[1.85, 0.008, 12, 100]} />
        <meshBasicMaterial color="#7DD3FC" transparent opacity={0.55} />
      </mesh>

      <mesh ref={innerShellRef}>
        <icosahedronGeometry args={[0.78, 1]} />
        <meshStandardMaterial
          color={currentAct.color}
          emissive={currentAct.color}
          emissiveIntensity={0.45}
          transparent
          opacity={0.62}
          roughness={0.18}
          metalness={0.75}
        />
      </mesh>
      <mesh ref={outerShellRef}>
        <icosahedronGeometry args={[1.22, 1]} />
        <meshStandardMaterial color="#E0E7FF" wireframe transparent opacity={0.48} />
      </mesh>

      {/* Traveling Autonomous Lightning Orb */}
      <mesh ref={travelerRef}>
        <sphereGeometry args={[0.14, 16, 16]} />
        <meshBasicMaterial color="#FFFFFF" />
      </mesh>

      {edgeLines.map((edge) => {
        const isActivelyFiring =
          (edge.from === currentAct.pair[0] && edge.to === currentAct.pair[1]) ||
          (edge.from === currentAct.pair[1] && edge.to === currentAct.pair[0]);
        return (
          <Line
            key={edge.key}
            points={edge.points}
            color={isActivelyFiring ? '#FDE68A' : edge.color}
            lineWidth={isActivelyFiring ? 3.2 : 1.7}
            transparent
            opacity={isActivelyFiring ? 1.0 : edge.dashed ? 0.55 : 0.78}
          />
        );
      })}

      {HERO_NODES.map((node, idx) => {
        const isFiringNode = currentAct.pair.includes(idx);
        return (
          <Float key={node.id} speed={2.0} rotationIntensity={0.3} floatIntensity={0.5}>
            <Sphere
              args={[isFiringNode ? node.size * 1.25 : node.size, 24, 24]}
              position={node.position}
              onPointerOver={(e) => {
                e.stopPropagation();
                onHoverNode(node.label);
              }}
              onPointerOut={() => onHoverNode(null)}
            >
              <meshStandardMaterial
                color={node.color}
                emissive={node.color}
                emissiveIntensity={node.id === 'core' || isFiringNode ? 1.15 : 0.5}
                roughness={0.15}
                metalness={0.75}
              />
            </Sphere>
          </Float>
        );
      })}
    </group>
  );
}

export const Hero3DCore: React.FC = () => {
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);
  const [pulseCount, setPulseCount] = useState<number>(0);
  const [actIndex, setActIndex] = useState<number>(0);

  // Autonomous random acts timer (every 2.8 seconds)
  useEffect(() => {
    const timer = setInterval(() => {
      setActIndex((prev) => (prev + 1) % NEXUS_RANDOM_ACTS.length);
    }, 2800);
    return () => clearInterval(timer);
  }, []);

  const currentAct = NEXUS_RANDOM_ACTS[actIndex % NEXUS_RANDOM_ACTS.length];

  const triggerRandomAct = () => {
    setPulseCount((c) => c + 1);
    setActIndex((prev) => (prev + 1) % NEXUS_RANDOM_ACTS.length);
  };

  return (
    <div className="relative w-full h-[460px] sm:h-[500px] rounded-3xl glass-panel-elevated spotlight-card overflow-hidden flex flex-col justify-between">
      {/* Top Bar */}
      <div className="z-10 flex items-center justify-between px-6 py-4 border-b border-white/15 bg-white/[0.04]">
        <div className="flex items-center gap-2.5">
          <Sparkles className="w-4 h-4 text-amber-300 animate-spin" style={{ animationDuration: '6s' }} />
          <span className="text-xs font-semibold tracking-wider text-indigo-100">
            Live Autonomous Nexus
          </span>
        </div>
        <button
          type="button"
          onClick={triggerRandomAct}
          className="text-xs font-semibold px-3.5 py-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white border border-white/25 transition flex items-center gap-1.5"
        >
          <Zap className="w-3.5 h-3.5 text-amber-300" />
          Trigger Nexus Act
        </button>
      </div>

      {/* 3D Autonomous Nexus Stage (Locked 60 FPS High-Performance WebGL) */}
      <div onClick={triggerRandomAct} className="relative flex-1 w-full">
        <WebGLErrorBoundary fallback={<div className="p-8 text-center text-xs text-indigo-200">3D Nexus Active</div>}>
          <Suspense fallback={<div className="p-8 text-center text-xs text-indigo-200">Loading 3D Nexus...</div>}>
            <Canvas
              dpr={[1, 1.5]}
              gl={{ powerPreference: 'high-performance', antialias: true }}
              camera={{ position: [0, 0, 5.1], fov: 46 }}
            >
              <ambientLight intensity={1.15} />
              <pointLight position={[5, 5, 5]} intensity={2.3} color="#FDE68A" />
              <pointLight position={[-5, -4, -3]} intensity={1.7} color="#A78BFA" />
              <CrystalNexusScene
                onHoverNode={setHoveredLabel}
                pulseTrigger={pulseCount}
                activeActIndex={actIndex}
              />
              <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.75} />
            </Canvas>
          </Suspense>
        </WebGLErrorBoundary>

        {/* Live Autonomous Act Toast Pill inside the Nexus */}
        <div className="pointer-events-none absolute bottom-3 left-4 right-4 flex items-center justify-between gap-2 px-4 py-2.5 rounded-2xl bg-[#141b3d]/85 backdrop-blur-xl border border-white/20 shadow-lg">
          <div className="flex items-center gap-2.5 truncate">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0 animate-ping"
              style={{ backgroundColor: currentAct.color }}
            />
            <span className="text-xs font-bold text-amber-200 shrink-0">{currentAct.badge}:</span>
            <span className="text-xs text-white/95 truncate">
              {hoveredLabel || currentAct.detail}
            </span>
          </div>
          <span className="text-[11px] text-indigo-200/80 shrink-0 hidden sm:inline">
            Click to pulse
          </span>
        </div>
      </div>
    </div>
  );
};
