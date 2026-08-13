import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, Clock3, MessageSquareText, Play, Search, SlidersHorizontal, Sparkles } from "lucide-react";
import {
  Background,
  Handle,
  Panel,
  Position,
  ReactFlow,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type { PageId } from "../types";

type QueryMode = "meaning" | "exact";
type HeroLayout = "desktop" | "tablet" | "mobile";

type HeroControlData = {
  kind: "query" | "blend" | "context";
  queryMode: QueryMode;
  denseWeight: number;
  contextCount: number;
  onQueryMode: (value: QueryMode) => void;
  onDenseWeight: (value: number) => void;
  onContextCount: (value: number) => void;
};

type HeroOutputData = {
  queryMode: QueryMode;
  denseWeight: number;
  contextCount: number;
};

type HeroControlNode = Node<HeroControlData, "heroControl">;
type HeroOutputNode = Node<HeroOutputData, "heroOutput">;
type HeroSpacerNode = Node<Record<string, never>, "heroSpacer">;
type HeroNode = HeroControlNode | HeroOutputNode | HeroSpacerNode;

function useHeroLayout(): HeroLayout {
  function resolve(): HeroLayout {
    if (window.matchMedia("(max-width: 640px)").matches) return "mobile";
    if (window.matchMedia("(max-width: 980px)").matches) return "tablet";
    return "desktop";
  }

  const [layout, setLayout] = useState<HeroLayout>(resolve);
  useEffect(() => {
    const update = () => setLayout(resolve());
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return layout;
}

function HeroControl({ data }: NodeProps<HeroControlNode>) {
  if (data.kind === "query") {
    return <div className="hero-control-node">
      <header><Search size={14} /><strong>question type</strong></header>
      <div className="hero-radio-list nodrag nowheel">
        <label><input type="radio" name="hero-query" checked={data.queryMode === "meaning"} onChange={() => data.onQueryMode("meaning")} /><span>paraphrased meaning</span></label>
        <label><input type="radio" name="hero-query" checked={data.queryMode === "exact"} onChange={() => data.onQueryMode("exact")} /><span>exact error code</span></label>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>;
  }

  if (data.kind === "blend") {
    return <div className="hero-control-node">
      <header><SlidersHorizontal size={14} /><strong>retrieval blend</strong></header>
      <div className="hero-range-copy"><span>BM25</span><b>{data.denseWeight}% dense</b><span>Vector</span></div>
      <input className="hero-range nodrag nowheel" aria-label="Dense retrieval percentage" type="range" min="0" max="100" step="10" value={data.denseWeight} onChange={(event) => data.onDenseWeight(Number(event.target.value))} />
      <Handle type="source" position={Position.Right} />
    </div>;
  }

  return <div className="hero-control-node">
    <header><BookOpen size={14} /><strong>context size</strong></header>
    <div className="hero-context-value"><strong>{data.contextCount}</strong><span>source blocks</span></div>
    <input className="hero-range nodrag nowheel" aria-label="Final source block count" type="range" min="2" max="8" step="1" value={data.contextCount} onChange={(event) => data.onContextCount(Number(event.target.value))} />
    <Handle type="source" position={Position.Right} />
  </div>;
}

type Particle = { x: number; y: number; seedX: number; seedY: number; phase: number; size: number; rotation: number };

function EvidenceCanvas({ queryMode, denseWeight, contextCount }: HeroOutputData) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number | null>(null);
  const particlesRef = useRef<Particle[]>([]);

  if (particlesRef.current.length === 0) {
    particlesRef.current = Array.from({ length: 44 }, (_, index) => {
      const seedX = ((index * 47 + 13) % 101) / 100;
      const seedY = ((index * 67 + 29) % 103) / 102;
      return { x: seedX, y: seedY, seedX, seedY, phase: index * 0.73, size: 5 + (index % 4) * 1.8, rotation: (index % 7) * 0.23 };
    });
  }

  useEffect(() => {
    const canvasElement = canvasRef.current;
    if (!canvasElement) return;
    const contextElement = canvasElement.getContext("2d");
    if (!contextElement) return;
    const canvas: HTMLCanvasElement = canvasElement;
    const context: CanvasRenderingContext2D = contextElement;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const particles = particlesRef.current;
    let width = 0;
    let height = 0;

    function resize() {
      const bounds = canvas.getBoundingClientRect();
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      width = bounds.width;
      height = bounds.height;
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    }

    function draw(now: number) {
      context.clearRect(0, 0, width, height);
      const time = now / 1000;
      const selected = Math.min(contextCount, particles.length);
      const centreX = width * (queryMode === "meaning" ? 0.54 : 0.58);
      const centreY = height * 0.52;
      const blend = denseWeight / 100;

      context.save();
      context.strokeStyle = "rgba(225, 216, 200, .10)";
      context.lineWidth = 1;
      for (let ring = 1; ring <= 3; ring += 1) {
        context.beginPath();
        context.arc(centreX, centreY, 30 + ring * 36, 0, Math.PI * 2);
        context.stroke();
      }
      context.restore();

      particles.forEach((particle, index) => {
        const isSelected = index < selected;
        const rank = index + 1;
        let targetX: number;
        let targetY: number;

        if (isSelected) {
          const angle = (index / selected) * Math.PI * 2 + time * (reduceMotion ? 0 : 0.08);
          const radius = 26 + (index % 3) * 17 + (1 - blend) * 13;
          targetX = centreX + Math.cos(angle) * radius;
          targetY = centreY + Math.sin(angle) * radius * 0.7;
        } else {
          const semanticPull = queryMode === "meaning" ? blend : 1 - blend;
          targetX = width * (0.08 + particle.seedX * 0.84) * (1 - semanticPull * 0.18) + centreX * semanticPull * 0.18;
          targetY = height * (0.12 + particle.seedY * 0.76);
          if (!reduceMotion) {
            targetX += Math.sin(time * 0.7 + particle.phase) * 7;
            targetY += Math.cos(time * 0.55 + particle.phase) * 5;
          }
        }

        particle.x += ((targetX / width) - particle.x) * 0.035;
        particle.y += ((targetY / height) - particle.y) * 0.035;
        const x = particle.x * width;
        const y = particle.y * height;
        const size = isSelected ? particle.size + 4 : particle.size;

        context.save();
        context.translate(x, y);
        context.rotate(particle.rotation + (reduceMotion ? 0 : time * (isSelected ? 0.12 : 0.025)));
        context.fillStyle = isSelected ? "#eee3cf" : `rgba(139, 127, 110, ${0.14 + ((index % 5) * 0.035)})`;
        context.strokeStyle = isSelected ? "#fffaf0" : "rgba(216, 205, 188, .16)";
        context.lineWidth = isSelected ? 1.2 : 0.6;
        context.beginPath();
        if (queryMode === "meaning") context.roundRect(-size, -size * 0.68, size * 2, size * 1.36, 2.5);
        else context.rect(-size, -size * 0.72, size * 2, size * 1.44);
        context.fill();
        context.stroke();
        if (isSelected) {
          context.fillStyle = "#292824";
          context.font = "6px IBM Plex Mono";
          context.textAlign = "center";
          context.textBaseline = "middle";
          context.fillText(String(rank), 0, 0.5);
        }
        context.restore();
      });

      context.fillStyle = "rgba(238, 227, 207, .62)";
      context.font = "7px IBM Plex Mono";
      context.textAlign = "left";
      context.fillText(`${contextCount} SOURCES SELECTED`, 12, height - 12);

      if (!reduceMotion) frameRef.current = requestAnimationFrame(draw);
    }

    resize();
    const observer = new ResizeObserver(() => { resize(); if (reduceMotion) draw(0); });
    observer.observe(canvas);
    frameRef.current = requestAnimationFrame(draw);
    return () => {
      observer.disconnect();
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, [contextCount, denseWeight, queryMode]);

  return <canvas ref={canvasRef} aria-label={`${contextCount} retrieved evidence blocks animated from the candidate set`} />;
}

function HeroOutput({ data, selected }: NodeProps<HeroOutputNode>) {
  const answer = data.queryMode === "meaning"
    ? "Customers can cancel within 30 days when the notice requirements are met."
    : "ERR_AUTH_17 indicates that the session token has expired.";

  return <div className={selected ? "hero-output-node selected" : "hero-output-node"}>
    <Handle id="query" type="target" position={Position.Left} style={{ top: "24%" }} />
    <Handle id="blend" type="target" position={Position.Left} style={{ top: "49%" }} />
    <Handle id="context" type="target" position={Position.Left} style={{ top: "74%" }} />
    <header><span>RAG output</span><b>Live</b></header>
    <div className="hero-output-canvas"><EvidenceCanvas {...data} /></div>
    <div className="hero-output-answer"><span><Sparkles size={12} />Grounded answer</span><p>{answer} <b>[S1] [S2]</b></p></div>
  </div>;
}

const heroNodeTypes = { heroControl: HeroControl, heroOutput: HeroOutput, heroSpacer: () => null };

function createHeroNodes(layout: HeroLayout, data: HeroControlData & HeroOutputData): HeroNode[] {
  const positions = layout === "desktop"
    ? { spacer: { x: 0, y: 0 }, question: { x: 550, y: 65 }, blend: { x: 530, y: 255 }, context: { x: 565, y: 445 }, output: { x: 820, y: 170 } }
    : layout === "tablet"
      ? { spacer: { x: 0, y: 0 }, question: { x: 80, y: 550 }, blend: { x: 335, y: 550 }, context: { x: 590, y: 550 }, output: { x: 270, y: 745 } }
      : { spacer: { x: 0, y: 0 }, question: { x: 70, y: 480 }, blend: { x: 70, y: 650 }, context: { x: 70, y: 820 }, output: { x: 15, y: 1010 } };

  return [
    { id: "spacer", type: "heroSpacer", position: positions.spacer, data: {}, style: layout === "desktop" ? { width: 410, height: 570, opacity: 0, pointerEvents: "none" } : { width: 1, height: 460, opacity: 0, pointerEvents: "none" }, selectable: false, draggable: false },
    { id: "question", type: "heroControl", position: positions.question, data: { ...data, kind: "query" } },
    { id: "blend", type: "heroControl", position: positions.blend, data: { ...data, kind: "blend" } },
    { id: "context", type: "heroControl", position: positions.context, data: { ...data, kind: "context" } },
    { id: "output", type: "heroOutput", position: positions.output, data },
  ];
}

const heroEdges: Edge[] = [
  { id: "query-output", source: "question", target: "output", targetHandle: "query", type: "smoothstep", animated: true },
  { id: "blend-output", source: "blend", target: "output", targetHandle: "blend", type: "smoothstep", animated: true },
  { id: "context-output", source: "context", target: "output", targetHandle: "context", type: "smoothstep", animated: true },
];

export function HeroRagPlayground({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const layout = useHeroLayout();
  const [queryMode, setQueryMode] = useState<QueryMode>("meaning");
  const [denseWeight, setDenseWeight] = useState(60);
  const [contextCount, setContextCount] = useState(5);

  const controlData = useMemo(() => ({
    kind: "query" as const,
    queryMode,
    denseWeight,
    contextCount,
    onQueryMode: setQueryMode,
    onDenseWeight: setDenseWeight,
    onContextCount: setContextCount,
  }), [contextCount, denseWeight, queryMode]);

  const initialNodes = useMemo(() => createHeroNodes(layout, controlData), [controlData, layout]);
  const [nodes, setNodes, onNodesChange] = useNodesState<HeroNode>(initialNodes);

  useEffect(() => {
    setNodes((current) => {
      const fresh = createHeroNodes(layout, controlData);
      if (layout !== "desktop") return fresh;
      return fresh.map((node) => {
        const existing = current.find((item) => item.id === node.id);
        return existing ? { ...node, position: existing.position } : node;
      });
    });
  }, [controlData, layout, setNodes]);

  const preventDelete = useCallback(async () => false, []);

  return <section className={`hero-rag-playground ${layout}`} aria-label="Interactive RAG playground">
    <ReactFlow
      nodes={nodes}
      edges={heroEdges}
      nodeTypes={heroNodeTypes}
      onNodesChange={onNodesChange}
      fitView
      fitViewOptions={{ padding: layout === "desktop" ? 0.025 : 0.06 }}
      minZoom={0.45}
      maxZoom={1.35}
      nodesConnectable={false}
      elementsSelectable
      deleteKeyCode={null}
      onBeforeDelete={preventDelete}
      panOnScroll={false}
      zoomOnDoubleClick={false}
      proOptions={{ hideAttribution: true }}
    >
      <Background color={layout === "desktop" ? "#8c8376" : "#b7ad9e"} gap={22} size={1} />
      <Panel position="top-left" className="home-hero-copy">
        <span className="lesson-kicker">RAG, explained from the beginning</span>
        <h1>See how AI finds evidence before it answers.</h1>
        <p>Adjust the retrieval controls. Watch candidate passages become a small evidence set, then see how that evidence grounds the final response.</p>
        <div className="hero-actions nodrag"><button className="primary-action" onClick={() => onNavigate("what-is-rag")}><Play size={16} />Start the first lesson</button><button className="secondary-action" onClick={() => onNavigate("interview")}><MessageSquareText size={16} />Practice interviews</button></div>
        <div className="hero-meta"><span><Clock3 size={15} />Nine short lessons</span><span><BookOpen size={15} />No prior knowledge needed</span></div>
      </Panel>
      <Panel position="bottom-right" className="hero-flow-hint">Drag nodes · scroll to zoom</Panel>
    </ReactFlow>
  </section>;
}
