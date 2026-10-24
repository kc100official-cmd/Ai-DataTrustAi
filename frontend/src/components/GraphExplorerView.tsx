import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Html, Line, Stars, Sparkles as DreiSparkles } from '@react-three/drei';
import * as THREE from 'three';
import {
  Search,
  GitMerge,
  RotateCcw,
  FilePlus2,
  Compass,
  Route,
  Orbit,
  Maximize2,
  Minimize2,
  X,
} from 'lucide-react';
import { api, EvidencePath } from '../api';

interface GraphExplorerViewProps {
  activeSourceId: string;
  initialSelectedEntityId?: string | null;
}

const ENTITY_COLORS: Record<string, string> = {
  Location: '#22D3EE',
  Organization: '#38BDF8',
  Person: '#10B981',
  Product: '#F59E0B',
  Event: '#F43F5E',
  Document: '#A78BFA',
  Concept: '#E879F9',
};

interface Node3DProps {
  node: any;
  basePosition: [number, number, number];
  isSelected: boolean;
  isNeighborOfSelected: boolean;
  isOnHighlightedPath: boolean;
  hasActiveSelection: boolean;
  onSelect: (id: string) => void;
}

const GraphNode3D: React.FC<Node3DProps> = ({
  node,
  basePosition,
  isSelected,
  isNeighborOfSelected,
  isOnHighlightedPath,
  hasActiveSelection,
  onSelect,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const color = ENTITY_COLORS[node.entity_type] || '#22D3EE';
  const isDimmed =
    hasActiveSelection && !isSelected && !isNeighborOfSelected && !isOnHighlightedPath && !hovered;

  // When a node or its neighbor is clicked, smoothly expand outward in 3D space
  const targetPos = useMemo(() => {
    const v = new THREE.Vector3(...basePosition);
    if (isSelected) {
      return v.multiplyScalar(1.12);
    }
    if (isNeighborOfSelected) {
      return v.multiplyScalar(1.22);
    }
    return v;
  }, [basePosition, isSelected, isNeighborOfSelected]);

  useFrame((state, delta) => {
    const dt = Math.min(delta, 0.05);
    const damp = 1 - Math.exp(-8.5 * dt);
    if (groupRef.current) {
      groupRef.current.position.lerp(targetPos, damp);
    }
    if (meshRef.current) {
      meshRef.current.rotation.y += dt * 0.6;
      meshRef.current.rotation.x += dt * 0.25;
      const targetScale = isSelected
        ? 1.85
        : hovered
        ? 1.4
        : isNeighborOfSelected || isOnHighlightedPath
        ? 1.28
        : 0.92;
      meshRef.current.scale.setScalar(
        THREE.MathUtils.lerp(meshRef.current.scale.x, targetScale, damp)
      );
    }
    if (ringRef.current) {
      ringRef.current.rotation.z += dt * (isSelected ? 1.8 : 0.65);
      ringRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 1.1) * 0.45;
      const ringScale = isSelected ? 1.75 : isNeighborOfSelected ? 1.25 : 1.0;
      ringRef.current.scale.setScalar(
        THREE.MathUtils.lerp(ringRef.current.scale.x, ringScale, damp)
      );
    }
  });

  return (
    <group ref={groupRef} position={basePosition}>
      {/* Core 3D Node Sphere */}
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(node.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHovered(true);
        }}
        onPointerOut={() => setHovered(false)}
      >
        <icosahedronGeometry args={[0.42, 2]} />
        <meshStandardMaterial
          color={color}
          emissive={isOnHighlightedPath ? '#10B981' : color}
          emissiveIntensity={isSelected ? 1.8 : hovered ? 1.3 : 0.75}
          roughness={0.18}
          metalness={0.75}
        />
      </mesh>

      {/* Outer Orbital Energy Ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[0.68, 0.02, 12, 42]} />
        <meshBasicMaterial
          color={isSelected ? '#ffffff' : isOnHighlightedPath ? '#10B981' : color}
          transparent
          opacity={isSelected ? 0.95 : hovered || isNeighborOfSelected ? 0.75 : 0.32}
        />
      </mesh>

      {/* Expanded Energy Sphere when Node is Clicked */}
      {isSelected && (
        <mesh>
          <sphereGeometry args={[1.25, 20, 20]} />
          <meshBasicMaterial color={color} wireframe transparent opacity={0.24} />
        </mesh>
      )}

      {/* Compact, Small-Font 3D Label (Expands when Clicked/Hovered, dims when another node is inspected) */}
      <Html distanceFactor={16} position={[0, isSelected ? 1.05 : 0.68, 0]} center zIndexRange={[1, 0]}>
        <div
          onClick={() => onSelect(node.id)}
          className={`rounded-md font-mono whitespace-nowrap select-none transition-all duration-200 ${
            isSelected
              ? 'px-2.5 py-1 text-[10px] bg-cyan-500/35 text-white border border-cyan-300 shadow-[0_0_20px_rgba(34,211,238,0.65)] font-bold opacity-100'
              : hovered || isNeighborOfSelected
              ? 'px-2 py-0.5 text-[9.5px] bg-[#041034]/95 text-cyan-200 border border-cyan-400/50 opacity-100'
              : isDimmed
              ? 'px-1.5 py-0.5 text-[8px] bg-[#01040d]/55 text-slate-400/45 border border-blue-400/10 opacity-35'
              : 'px-1.5 py-0.5 text-[8.5px] bg-[#01040d]/75 text-slate-300/90 border border-blue-400/15 opacity-95'
          }`}
        >
          <span
            className="inline-block w-1.5 h-1.5 rounded-full mr-1"
            style={{ backgroundColor: color }}
          />
          {isSelected || hovered
            ? node.name
            : node.name.length > 18
            ? node.name.slice(0, 16) + '…'
            : node.name}
        </div>
      </Html>
    </group>
  );
};

interface Edge3DProps {
  edge: any;
  start: [number, number, number];
  end: [number, number, number];
  isHighlighted: boolean;
  isSelected: boolean;
  isConnectedToSelectedNode: boolean;
  hasActiveSelection: boolean;
  onSelectEdge: (edge: any) => void;
}

const GraphEdge3D: React.FC<Edge3DProps> = ({
  edge,
  start,
  end,
  isHighlighted,
  isSelected,
  isConnectedToSelectedNode,
  hasActiveSelection,
  onSelectEdge,
}) => {
  const particleRef = useRef<THREE.Mesh>(null);
  const startVec = useMemo(() => new THREE.Vector3(...start), [start]);
  const endVec = useMemo(() => new THREE.Vector3(...end), [end]);
  const midPoint = useMemo(
    () => [
      (start[0] + end[0]) * 0.5,
      (start[1] + end[1]) * 0.5,
      (start[2] + end[2]) * 0.5,
    ] as [number, number, number],
    [start, end]
  );

  const speedOffset = useMemo(
    () => 0.32 + (edge.id.charCodeAt(edge.id.length - 1) % 7) * 0.07,
    [edge.id]
  );

  useFrame((state) => {
    if (particleRef.current) {
      const t = (state.clock.elapsedTime * speedOffset) % 1;
      particleRef.current.position.lerpVectors(startVec, endVec, t);
    }
  });

  const active = isHighlighted || isSelected || isConnectedToSelectedNode;
  const isDimmed = hasActiveSelection && !active;
  const lineColor = isHighlighted
    ? '#10B981'
    : isSelected
    ? '#FFFFFF'
    : isConnectedToSelectedNode
    ? '#38BDF8'
    : edge.is_inferred
    ? '#A78BFA'
    : '#22D3EE';

  return (
    <group>
      <Line
        points={[start, end]}
        color={lineColor}
        lineWidth={active ? 2.5 : isDimmed ? 0.7 : 1.1}
        dashed={Boolean(edge.is_inferred)}
        dashSize={0.4}
        gapSize={0.25}
        transparent
        opacity={active ? 0.95 : isDimmed ? 0.08 : 0.3}
        onClick={(e) => {
          e.stopPropagation();
          onSelectEdge(edge);
        }}
      />

      {!isDimmed && (
        <mesh ref={particleRef}>
          <sphereGeometry args={[active ? 0.12 : 0.065, 10, 10]} />
          <meshBasicMaterial
            color={isHighlighted ? '#34D399' : edge.is_inferred ? '#C4B5FD' : '#67E8F9'}
          />
        </mesh>
      )}

      {active && (
        <Html distanceFactor={16} position={midPoint} center zIndexRange={[1, 0]}>
          <button
            type="button"
            onClick={() => onSelectEdge(edge)}
            className={`px-1.5 py-0.5 rounded font-mono text-[8px] uppercase tracking-wider border ${
              edge.is_inferred
                ? 'bg-violet-950/90 text-violet-200 border-violet-400/60'
                : 'bg-[#02081c]/90 text-cyan-200 border-cyan-400/60'
            }`}
          >
            {edge.rel_type}
          </button>
        </Html>
      )}
    </group>
  );
};

export const GraphExplorerView: React.FC<GraphExplorerViewProps> = ({
  activeSourceId,
  initialSelectedEntityId,
}) => {
  const [sourceFilter, setSourceFilter] = useState<string>(activeSourceId);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [relTypeFilter, setRelTypeFilter] = useState<string>('ALL');
  const [includeInferred, setIncludeInferred] = useState<boolean>(true);
  const [linkDensity, setLinkDensity] = useState<'clean' | 'balanced' | 'all'>('clean');

  const [graphData, setGraphData] = useState<any>({ nodes: [], edges: [], relationship_types: [] });
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(initialSelectedEntityId || null);
  const [selectedEntityDetail, setSelectedEntityDetail] = useState<any>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);

  // Fullscreen / Expanded Graph state
  const [isGraphExpanded, setIsGraphExpanded] = useState<boolean>(false);
  const [autoRotate3D, setAutoRotate3D] = useState<boolean>(true);

  // Path finder state
  const [pathSourceId, setPathSourceId] = useState<string>('');
  const [pathTargetId, setPathTargetId] = useState<string>('');
  const [discoveredPaths, setDiscoveredPaths] = useState<EvidencePath[]>([]);
  const [pathSearchDone, setPathSearchDone] = useState<boolean>(false);

  // Entity resolution & Document ingestion modals
  const [resolutions, setResolutions] = useState<any[]>([]);
  const [showResolutionPanel, setShowResolutionPanel] = useState<boolean>(false);
  const [showIngestModal, setShowIngestModal] = useState<boolean>(false);
  const [ingestTitle, setIngestTitle] = useState<string>('Gwalior & Morena Grid Audit Note');
  const [ingestText, setIngestText] = useState<string>(
    'Director Ananya Sharma verified that Gwalior Heavy Engineering Hub operates in Region North and supplies Project Mercury under contract CNT-901 with Larsen & Toubro (L&T).'
  );
  const [ingestResult, setIngestResult] = useState<any>(null);

  useEffect(() => {
    setSourceFilter(activeSourceId);
  }, [activeSourceId]);

  const loadGraph = async () => {
    setLoading(true);
    try {
      const maxEdgesParam = linkDensity === 'clean' ? 25 : linkDensity === 'balanced' ? 50 : 0;
      const data = await api.getGraph({
        source_id: sourceFilter === 'ALL' ? undefined : sourceFilter,
        rel_type: relTypeFilter === 'ALL' ? undefined : relTypeFilter,
        include_inferred: includeInferred,
        include_merged_aliases: false,
        search: searchQuery || undefined,
        max_edges: maxEdgesParam,
      });
      setGraphData(data);
      if (data.nodes.length >= 2 && !pathSourceId && !pathTargetId) {
        setPathSourceId(data.nodes[0].id);
        setPathTargetId(data.nodes[Math.min(2, data.nodes.length - 1)].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadResolutions = async () => {
    try {
      const res = await api.resolveEntities({ action: 'detect' });
      setResolutions(res.resolutions || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadGraph();
    loadResolutions();
  }, [sourceFilter, relTypeFilter, includeInferred, linkDensity]);

  useEffect(() => {
    if (initialSelectedEntityId) {
      setSelectedNodeId(initialSelectedEntityId);
    }
  }, [initialSelectedEntityId]);

  useEffect(() => {
    if (!selectedNodeId) {
      setSelectedEntityDetail(null);
      return;
    }
    api
      .getEntityDetail(selectedNodeId)
      .then((detail) => setSelectedEntityDetail(detail))
      .catch(() => setSelectedEntityDetail(null));
  }, [selectedNodeId, graphData]);

  // Wide, Spacious 3D Fibonacci Constellation Coordinates so nodes never crowd
  const positions3D = useMemo(() => {
    const pos: Record<string, [number, number, number]> = {};
    const nodes = graphData.nodes || [];
    const total = nodes.length;
    if (total === 0) return pos;

    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    nodes.forEach((n: any, idx: number) => {
      if (idx === 0) {
        pos[n.id] = [0, 0, 0];
        return;
      }
      const y = 1 - (idx / Math.max(1, total - 1)) * 2;
      const radiusAtY = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = goldenAngle * idx;
      const shellRadius = idx % 2 === 0 ? 9.2 : 6.4;
      const x = Math.cos(theta) * radiusAtY * shellRadius;
      const z = Math.sin(theta) * radiusAtY * shellRadius;
      pos[n.id] = [
        Number(x.toFixed(2)),
        Number((y * 6.2).toFixed(2)),
        Number(z.toFixed(2)),
      ];
    });
    return pos;
  }, [graphData.nodes]);

  // Neighbors of currently clicked node (for 3D expansion effect)
  const neighborNodeIds = useMemo(() => {
    const set = new Set<string>();
    if (!selectedNodeId) return set;
    (graphData.edges || []).forEach((e: any) => {
      if (e.source === selectedNodeId) set.add(e.target);
      if (e.target === selectedNodeId) set.add(e.source);
    });
    return set;
  }, [selectedNodeId, graphData.edges]);

  // Set of node/edge pairs highlighted by active path search
  const { highlightedEdgePairs, highlightedNodeIds } = useMemo(() => {
    const edgeSet = new Set<string>();
    const nodeSet = new Set<string>();
    if (discoveredPaths.length > 0) {
      const p0 = discoveredPaths[0];
      p0.hops.forEach((h) => {
        edgeSet.add(`${h.from_entity_id}->${h.to_entity_id}`);
        edgeSet.add(`${h.to_entity_id}->${h.from_entity_id}`);
        nodeSet.add(h.from_entity_id);
        nodeSet.add(h.to_entity_id);
      });
    }
    return { highlightedEdgePairs: edgeSet, highlightedNodeIds: nodeSet };
  }, [discoveredPaths]);

  const handleExpandNeighbors = async (depth: number) => {
    if (!selectedNodeId) return;
    setLoading(true);
    try {
      const data = await api.getNeighbors(selectedNodeId, depth, includeInferred);
      setGraphData((prev: any) => ({
        ...prev,
        nodes: data.nodes,
        edges: data.edges,
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleRunPathSearch = async () => {
    if (!pathSourceId || !pathTargetId) return;
    const res = await api.findPaths(pathSourceId, pathTargetId, 4, includeInferred);
    setDiscoveredPaths(res.paths || []);
    setPathSearchDone(true);
  };

  const handleMergeToggle = async (resolutionId: string, currentStatus: string) => {
    const action = currentStatus === 'MERGED' ? 'unmerge' : 'merge';
    const res = await api.resolveEntities({ action, resolution_id: resolutionId });
    setResolutions(res.resolutions || []);
    await loadGraph();
  };

  const handleIngestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await api.ingestDocument(
      sourceFilter === 'ALL' ? 'enterprise_supply_ops' : sourceFilter,
      ingestTitle,
      'audit_memo',
      ingestText
    );
    setIngestResult(res);
    await loadGraph();
  };

  return (
    <div className="space-y-8">
      {/* Clean, Straight-to-the-Point Header & Filter Bar */}
      <div className="rounded-3xl glass-panel p-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="eye-label block">3D KNOWLEDGE CONSTELLATION</span>
          <h2 className="text-2xl font-display font-bold text-white mt-1">
            Interactive 3D Entity & Provenance Graph
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadGraph()}
              placeholder="Search company or city..."
              className="pl-10 pr-4 py-2 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs text-white focus:border-cyan-300 outline-none w-52"
            />
          </div>

          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3.5 py-2 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs text-slate-200"
          >
            <option value="enterprise_supply_ops">Indian Corporate Supply DB</option>
            <option value="california_schools_bird_demo">Regional STEM Schools</option>
            <option value="ALL">All Sources</option>
          </select>

          <select
            value={relTypeFilter}
            onChange={(e) => setRelTypeFilter(e.target.value)}
            className="px-3.5 py-2 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs text-slate-200 font-mono"
          >
            <option value="ALL">All Relationships</option>
            {['LOCATED_IN', 'SUPPLIES_TO', 'MANAGES', 'OWNS', 'CAUSED_BY', 'PART_OF', 'WORKS_FOR'].map(
              (rt) => (
                <option key={rt} value={rt}>
                  {rt}
                </option>
              )
            )}
          </select>

          <select
            value={linkDensity}
            onChange={(e) => setLinkDensity(e.target.value as any)}
            className="px-3.5 py-2 rounded-xl bg-[#030d2b] border border-cyan-400/40 text-xs text-cyan-200 font-mono shadow-[0_0_10px_rgba(34,211,238,0.15)] outline-none"
            title="Adjust number of links to keep a clean graph look"
          >
            <option value="clean">✦ Clean Look (25 Links)</option>
            <option value="balanced">Balanced (50 Links)</option>
            <option value="all">Full Graph (All Links)</option>
          </select>

          <button
            type="button"
            onClick={() => setShowResolutionPanel((prev) => !prev)}
            className="px-3.5 py-2 rounded-xl bg-violet-500/20 hover:bg-violet-500/30 text-violet-200 border border-violet-400/40 text-xs font-mono flex items-center gap-1.5 transition"
          >
            <GitMerge className="w-3.5 h-3.5" />
            Duplicates ({resolutions.length})
          </button>

          <button
            type="button"
            onClick={() => setShowIngestModal((prev) => !prev)}
            className="px-3.5 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 border border-emerald-400/40 text-xs font-mono flex items-center gap-1.5 transition"
          >
            <FilePlus2 className="w-3.5 h-3.5" />
            Add Text Note
          </button>
        </div>
      </div>

      {/* Reversible Entity Resolution Modal */}
      {showResolutionPanel && (
        <div className="rounded-3xl glass-panel-elevated p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-blue-400/20 pb-3">
            <h3 className="text-base font-display font-bold text-white flex items-center gap-2">
              <GitMerge className="w-4 h-4 text-violet-400" />
              Duplicate Company Alias Resolution (100% Reversible)
            </h3>
            <button
              type="button"
              onClick={() => setShowResolutionPanel(false)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {resolutions.map((res) => (
              <div
                key={res.resolution_id}
                className="p-5 rounded-2xl bg-[#030d2b] border border-blue-400/25 flex flex-col justify-between gap-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-violet-300">
                      Similarity: {Math.round(res.similarity_score * 100)}%
                    </span>
                    <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-blue-500/20 text-cyan-200">
                      {res.status}
                    </span>
                  </div>
                  <div className="text-base font-semibold text-white">
                    {res.duplicate_name} <span className="text-cyan-400 font-mono text-xs">→</span>{' '}
                    {res.canonical_name}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{res.reason}</p>
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-blue-400/15">
                  <span className="text-xs font-mono text-slate-400">
                    {res.duplicate_source_record} & {res.canonical_source_record}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleMergeToggle(res.resolution_id, res.status)}
                    className="px-4 py-1.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-[#01040d] text-xs font-semibold transition"
                  >
                    {res.status === 'MERGED' ? 'Unmerge' : 'Merge Alias'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document Extraction Modal */}
      {showIngestModal && (
        <form onSubmit={handleIngestSubmit} className="rounded-3xl glass-panel-elevated p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-display font-bold text-white">
              Extract Entities & Relationships from Text
            </h3>
            <button
              type="button"
              onClick={() => setShowIngestModal(false)}
              className="text-xs text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              value={ingestTitle}
              onChange={(e) => setIngestTitle(e.target.value)}
              placeholder="Document Title"
              className="px-4 py-2.5 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs text-white"
              required
            />
            <input
              type="text"
              value={ingestText}
              onChange={(e) => setIngestText(e.target.value)}
              placeholder="Paste text mentioning Indian companies & facilities..."
              className="md:col-span-2 px-4 py-2.5 rounded-xl bg-[#030d2b] border border-blue-400/30 text-xs text-white"
              required
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-[#01040d] text-xs font-semibold transition"
            >
              Extract & Add to 3D Graph
            </button>
          </div>
          {ingestResult && (
            <div className="p-3 rounded-xl bg-[#030d2b] border border-emerald-500/40 text-xs font-mono text-emerald-300">
              Extracted {ingestResult.relationships_extracted?.length || 0} relationship(s) into the 3D Graph.
            </div>
          )}
        </form>
      )}

      {/* FULL-WIDTH, EXPANDABLE 3D SPACE KNOWLEDGE GRAPH */}
      <div
        className={`rounded-3xl glass-panel overflow-hidden flex flex-col transition-all duration-300 ${
          isGraphExpanded
            ? 'fixed inset-4 right-24 lg:right-68 z-50 shadow-[0_0_90px_rgba(0,0,0,0.95)]'
            : 'relative w-full h-[680px]'
        }`}
      >
        {/* Top Graph Toolbar */}
        <div className="px-6 py-4 border-b border-blue-400/20 bg-[#02081c]/90 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            <span className="text-white font-semibold">
              {graphData.nodes?.length || 0} Entities
            </span>
            <span className="text-cyan-300">
              {graphData.confirmed_edge_count || 0} Confirmed Links
            </span>
            <span className="text-violet-300">
              {graphData.inferred_edge_count || 0} Inferred Links
            </span>

            {/* Inline Path Highlight Finder */}
            <div className="hidden xl:flex items-center gap-2 pl-4 border-l border-blue-400/20">
              <Route className="w-3.5 h-3.5 text-cyan-300" />
              <select
                value={pathSourceId}
                onChange={(e) => setPathSourceId(e.target.value)}
                className="px-2.5 py-1 rounded-lg bg-[#030d2b] border border-blue-400/30 text-[11px] text-white"
              >
                {(graphData.nodes || []).map((n: any) => (
                  <option key={`src-${n.id}`} value={n.id}>
                    {n.name}
                  </option>
                ))}
              </select>
              <span className="text-slate-400">→</span>
              <select
                value={pathTargetId}
                onChange={(e) => setPathTargetId(e.target.value)}
                className="px-2.5 py-1 rounded-lg bg-[#030d2b] border border-blue-400/30 text-[11px] text-white"
              >
                {(graphData.nodes || []).map((n: any) => (
                  <option key={`tgt-${n.id}`} value={n.id}>
                    {n.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleRunPathSearch}
                className="px-3 py-1 rounded-lg bg-cyan-500/25 hover:bg-cyan-500/40 text-cyan-200 border border-cyan-400/40 text-[11px]"
              >
                Trace Path
              </button>
              {discoveredPaths.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setDiscoveredPaths([]);
                    setPathSearchDone(false);
                  }}
                  className="px-2 py-1 rounded-lg bg-slate-800 text-slate-300 text-[11px]"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <label className="flex items-center gap-1.5 text-xs font-mono text-slate-300 mr-2">
              <input
                type="checkbox"
                checked={includeInferred}
                onChange={(e) => setIncludeInferred(e.target.checked)}
                className="accent-violet-400"
              />
              <span>Inferred</span>
            </label>

            <button
              type="button"
              onClick={() => setAutoRotate3D((prev) => !prev)}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono flex items-center gap-1.5 border transition ${
                autoRotate3D
                  ? 'bg-cyan-500/20 text-cyan-200 border-cyan-400/50'
                  : 'bg-[#030d2b] text-slate-400 border-slate-700'
              }`}
            >
              <Orbit className="w-3.5 h-3.5" />
              <span>{autoRotate3D ? 'Orbit ON' : 'Orbit OFF'}</span>
            </button>

            <button
              type="button"
              onClick={() => setIsGraphExpanded((prev) => !prev)}
              className="px-3 py-1.5 rounded-xl bg-blue-500/25 hover:bg-blue-500/40 text-white border border-cyan-300/50 text-xs font-mono flex items-center gap-1.5 transition"
            >
              {isGraphExpanded ? (
                <>
                  <Minimize2 className="w-3.5 h-3.5" />
                  <span>Collapse</span>
                </>
              ) : (
                <>
                  <Maximize2 className="w-3.5 h-3.5" />
                  <span>Expand Space</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => {
                setSelectedNodeId(null);
                setSelectedEdge(null);
                loadGraph();
              }}
              className="p-2 rounded-xl bg-[#030d2b] hover:bg-blue-950 text-slate-300 border border-blue-400/25"
              title="Reset Graph"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 3D Canvas Viewport (Luminous Dark-Bright Starlit Studio) */}
        <div
          className="relative flex-1 w-full overflow-hidden"
          style={{
            background:
              'radial-gradient(circle at 50% 42%, rgba(99, 102, 241, 0.35), rgba(18, 24, 52, 0.96) 76%), #121834',
          }}
        >
          {loading ? (
            <div className="h-full flex items-center justify-center text-xs font-mono text-amber-200 animate-pulse">
              Initializing 3D Knowledge Space...
            </div>
          ) : (
            <div className="absolute inset-0 z-0 isolate">
              <Canvas
                dpr={[1, 1.5]}
                gl={{ powerPreference: 'high-performance', antialias: true }}
                camera={{ position: [0, 3.2, 16.5], fov: 46 }}
              >
                <ambientLight intensity={1.15} />
                <pointLight position={[14, 14, 14]} intensity={2.2} color="#fde68a" />
                <pointLight position={[-14, -10, -14]} intensity={1.7} color="#a78bfa" />

                <Stars radius={55} depth={40} count={1400} factor={3.2} saturation={0.7} fade speed={1.1} />
                <DreiSparkles count={75} scale={18} size={2.2} speed={0.4} color="#fde68a" />

                <group position={[selectedEntityDetail?.entity || selectedEdge ? -2.1 : 0, 0, 0]}>
                  {/* 3D Edges with Animated Energy Pulses */}
                  {(graphData.edges || []).map((e: any) => {
                    const p1 = positions3D[e.source];
                    const p2 = positions3D[e.target];
                    if (!p1 || !p2) return null;
                    const isHighlighted = highlightedEdgePairs.has(`${e.source}->${e.target}`);
                    const isSelectedEdge = selectedEdge?.id === e.id;
                    const isConnectedToSelectedNode =
                      Boolean(selectedNodeId) &&
                      (e.source === selectedNodeId || e.target === selectedNodeId);
                    return (
                      <GraphEdge3D
                        key={e.id}
                        edge={e}
                        start={p1}
                        end={p2}
                        isHighlighted={isHighlighted}
                        isSelected={isSelectedEdge}
                        isConnectedToSelectedNode={isConnectedToSelectedNode}
                        hasActiveSelection={Boolean(selectedNodeId || selectedEdge)}
                        onSelectEdge={(edgeObj) => setSelectedEdge(edgeObj)}
                      />
                    );
                  })}

                  {/* 3D Interactive Entity Nodes */}
                  {(graphData.nodes || []).map((n: any) => {
                    const pos = positions3D[n.id];
                    if (!pos) return null;
                    return (
                      <GraphNode3D
                        key={n.id}
                        node={n}
                        basePosition={pos}
                        isSelected={selectedNodeId === n.id}
                        isNeighborOfSelected={neighborNodeIds.has(n.id)}
                        isOnHighlightedPath={highlightedNodeIds.has(n.id)}
                        hasActiveSelection={Boolean(selectedNodeId || selectedEdge)}
                        onSelect={(nid) => {
                          setSelectedNodeId((prev) => (prev === nid ? null : nid));
                          setSelectedEdge(null);
                        }}
                      />
                    );
                  })}
                </group>

                <OrbitControls
                  enablePan
                  enableZoom
                  enableRotate
                  autoRotate={autoRotate3D && !selectedNodeId}
                  autoRotateSpeed={0.65}
                  minDistance={5}
                  maxDistance={28}
                />
              </Canvas>
            </div>
          )}

          {/* Active Path Banner Inside 3D Space */}
          {pathSearchDone && discoveredPaths.length > 0 && (
            <div className="absolute top-4 left-4 right-4 md:right-auto md:max-w-xl z-30 p-3.5 rounded-2xl bg-[#02081c]/95 backdrop-blur-xl border border-emerald-400/50 text-xs font-mono text-emerald-300 shadow-lg">
              Path Verified: {discoveredPaths[0].summary_chain}
            </div>
          )}

          {/* EXPANDING FLOATING PROVENANCE DRAWER WHEN NODE OR EDGE IS CLICKED */}
          {(selectedEntityDetail?.entity || selectedEdge) && (
            <div className="absolute top-4 right-4 bottom-14 z-40 w-80 sm:w-96 rounded-2xl bg-[#02081c]/96 backdrop-blur-2xl border border-cyan-300/50 p-5 overflow-y-auto shadow-[0_0_60px_rgba(0,0,0,0.95)] space-y-4 transition-all duration-300">
              <div className="flex items-center justify-between border-b border-blue-400/20 pb-3">
                <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-cyan-300">
                  <Compass className="w-4 h-4" />
                  <span>Expanded Node Provenance</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedNodeId(null);
                    setSelectedEdge(null);
                  }}
                  className="p-1 rounded-lg bg-blue-950/60 hover:bg-blue-900 text-slate-300"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {selectedEdge && (
                <div className="p-3.5 rounded-xl bg-[#030d2b] border border-cyan-400/40 space-y-2 text-xs">
                  <div className="font-mono text-cyan-300 font-semibold">
                    {selectedEdge.source_name} → {selectedEdge.rel_type} → {selectedEdge.target_name}
                  </div>
                  <div className="font-mono text-[11px] text-slate-400">
                    Source: {selectedEdge.provenance?.source_record}
                  </div>
                  <div className="text-slate-200 font-light">“{selectedEdge.provenance?.excerpt}”</div>
                </div>
              )}

              {selectedEntityDetail?.entity && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-blue-500/20 text-cyan-200 border border-blue-400/30">
                      {selectedEntityDetail.entity.entity_type} · {selectedEntityDetail.entity.id}
                    </span>
                    <h4 className="text-lg font-display font-bold text-white pt-1">
                      {selectedEntityDetail.entity.name}
                    </h4>
                    <p className="text-xs font-mono text-cyan-300">
                      Source: {selectedEntityDetail.entity.provenance.source_record}
                    </p>
                    <div className="p-3 rounded-xl bg-[#030d2b] border border-blue-400/20 text-xs text-slate-200 leading-relaxed">
                      “{selectedEntityDetail.entity.provenance.excerpt}”
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleExpandNeighbors(1)}
                      className="flex-1 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-200 border border-cyan-400/40 text-xs font-mono transition"
                    >
                      Focus 1-Hop Neighborhood
                    </button>
                    <button
                      type="button"
                      onClick={loadGraph}
                      className="px-3 py-2 rounded-xl bg-[#030d2b] text-slate-300 border border-blue-400/25 text-xs font-mono"
                    >
                      Show All
                    </button>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-blue-400/15">
                    <div className="text-[11px] font-mono uppercase text-slate-400">
                      Connected Links ({selectedEntityDetail.relationships?.length || 0})
                    </div>
                    <div className="space-y-2">
                      {(selectedEntityDetail.relationships || []).map((rel: any) => (
                        <div
                          key={rel.id}
                          onClick={() => setSelectedEdge(rel)}
                          className="p-2.5 rounded-xl bg-[#030d2b] border border-blue-400/20 hover:border-cyan-400/50 text-xs space-y-1 transition"
                        >
                          <div className="font-mono text-slate-200 text-[11px]">
                            {rel.source_name}{' '}
                            <span className="text-cyan-300 font-bold">→ {rel.rel_type} →</span>{' '}
                            {rel.target_name}
                          </div>
                          <div className="text-[10px] font-mono text-slate-400 truncate">
                            {rel.provenance.source_record}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Minimal Bottom Legend */}
          <div className="absolute bottom-3 left-4 right-4 z-30 flex flex-wrap items-center justify-between gap-2 pointer-events-none text-[10px] font-mono text-slate-300/80">
            <div className="flex flex-wrap items-center gap-3 bg-[#01040d]/80 px-3 py-1.5 rounded-xl border border-blue-400/20">
              {Object.entries(ENTITY_COLORS).map(([etype, col]) => (
                <span key={etype} className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: col }} />
                  {etype}
                </span>
              ))}
            </div>
            <div className="bg-[#01040d]/80 px-3 py-1.5 rounded-xl border border-blue-400/20 text-cyan-200/80">
              Click any node to expand its 3D neighborhood & provenance
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
