import { memo, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  BookOpenCheck,
  Brain,
  ChartNoAxesCombined,
  CircleCheckBig,
  ClipboardCheck,
  Database,
  FileText,
  Files,
  GitMerge,
  ListFilter,
  MessageCircleQuestion,
  Pause,
  Play,
  ScanSearch,
  Scissors,
  Search,
  ShieldCheck,
  Sparkles,
  Tags,
  UploadCloud,
  UserCheck,
  WholeWord,
  type LucideIcon,
} from "lucide-react";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  NodeToolbar,
  Panel,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type { LessonVisual } from "../types";

type IconName = "question" | "search" | "evidence" | "answer" | "brain" | "database" | "document" | "chunks" | "tags" | "dense" | "keyword" | "candidates" | "fusion" | "rerank" | "context" | "shield" | "check" | "review" | "golden" | "measure" | "release" | "ingest" | "observe";
type HandleMode = "input" | "output" | "single" | "split" | "merge";
type FlowDirection = "horizontal" | "vertical";

type Stage = {
  title: string;
  summary: string;
  receives: string;
  output: string;
  icon: IconName;
};

type RagNodeData = {
  index: number;
  stage: Stage;
  active: boolean;
  handleMode: HandleMode;
  direction: FlowDirection;
};

type RagEdgeData = {
  label: string;
  active: boolean;
  motion: boolean;
};

type RagNode = Node<RagNodeData, "ragStage">;
type RagEdge = Edge<RagEdgeData, "artifact">;

const icons: Record<IconName, LucideIcon> = {
  question: MessageCircleQuestion,
  search: Search,
  evidence: BookOpenCheck,
  answer: Sparkles,
  brain: Brain,
  database: Database,
  document: FileText,
  chunks: Scissors,
  tags: Tags,
  dense: ScanSearch,
  keyword: WholeWord,
  candidates: ListFilter,
  fusion: GitMerge,
  rerank: ArrowDownUp,
  context: Files,
  shield: ShieldCheck,
  check: CircleCheckBig,
  review: UserCheck,
  golden: ClipboardCheck,
  measure: ChartNoAxesCombined,
  release: CircleCheckBig,
  ingest: UploadCloud,
  observe: Activity,
};

const stageSets: Record<LessonVisual, Stage[]> = {
  pipeline: [
    { title: "Question", summary: "The user asks in ordinary language; no search syntax is required.", receives: "A user need", output: "Searchable query", icon: "question" },
    { title: "Retrieve", summary: "The system searches only the approved knowledge base for relevant passages.", receives: "Searchable query", output: "Candidate passages", icon: "search" },
    { title: "Select evidence", summary: "The strongest permitted passages become a small, focused evidence pack.", receives: "Candidate passages", output: "Grounding context", icon: "evidence" },
    { title: "Answer", summary: "The model writes from that evidence and points back to supporting sources.", receives: "Grounding context", output: "Cited response", icon: "answer" },
  ],
  compare: [
    { title: "User question", summary: "The same question can follow a memory-only path or an evidence-backed path.", receives: "A user need", output: "Question text", icon: "question" },
    { title: "Model memory", summary: "General learned patterns may be useful, but can be old and exclude private documents.", receives: "Question text", output: "Unverified recall", icon: "brain" },
    { title: "Trusted sources", summary: "Current policies, manuals, and internal knowledge are searched at question time.", receives: "Question text", output: "Current evidence", icon: "database" },
    { title: "Grounded answer", summary: "The supported path creates a response whose facts can be inspected.", receives: "Current evidence", output: "Verifiable response", icon: "answer" },
  ],
  chunks: [
    { title: "Document", summary: "A parser extracts readable text, structure, tables, and source metadata.", receives: "PDF, HTML, or Markdown", output: "Structured content", icon: "document" },
    { title: "Parent sections", summary: "Large coherent sections retain enough surrounding meaning for the final answer.", receives: "Structured content", output: "Context-rich sections", icon: "evidence" },
    { title: "Child chunks", summary: "Smaller semantic passages improve matching and stay linked to their parent.", receives: "Context-rich sections", output: "Searchable passages", icon: "chunks" },
    { title: "Search index", summary: "Vectors, keywords, permissions, and stable source IDs are stored together.", receives: "Searchable passages", output: "Retrieval-ready index", icon: "tags" },
  ],
  search: [
    { title: "Question", summary: "One query is sent down two complementary retrieval paths.", receives: "User language", output: "Normalized query", icon: "question" },
    { title: "Dense search", summary: "Embedding similarity finds the same meaning even when the wording differs.", receives: "Query embedding", output: "Semantic matches", icon: "dense" },
    { title: "BM25 search", summary: "Lexical ranking finds exact names, error codes, product terms, and rare keywords.", receives: "Query terms", output: "Exact matches", icon: "keyword" },
    { title: "Candidate set", summary: "Both result lists stay broad so the next stage begins with strong recall.", receives: "Two ranked lists", output: "Hybrid candidates", icon: "candidates" },
  ],
  rerank: [
    { title: "Candidates", summary: "Dense and BM25 retrieval contribute a deliberately broad evidence shortlist.", receives: "Search results", output: "Candidate list", icon: "candidates" },
    { title: "RRF fusion", summary: "Rank positions are combined without comparing incompatible raw score scales.", receives: "Dense + BM25 ranks", output: "Fused ranking", icon: "fusion" },
    { title: "Reranker", summary: "A relevance model reads the question with each candidate and sharpens the order.", receives: "Fused ranking", output: "Relevance scores", icon: "rerank" },
    { title: "Final context", summary: "Duplicate parents are removed and the best evidence fits the context budget.", receives: "Relevance scores", output: "Answer evidence", icon: "context" },
  ],
  answer: [
    { title: "Question", summary: "The original question remains the precise task the system must answer.", receives: "User language", output: "Answer instruction", icon: "question" },
    { title: "Source blocks", summary: "Ranked passages enter the prompt with stable IDs and readable source labels.", receives: "Retrieved evidence", output: "Citable context", icon: "evidence" },
    { title: "Answer model", summary: "The model uses supplied evidence and abstains when that evidence is insufficient.", receives: "Instruction + context", output: "Draft response", icon: "brain" },
    { title: "Cited response", summary: "The application checks that cited source IDs exist before returning the answer.", receives: "Draft response", output: "Validated answer", icon: "answer" },
  ],
  shield: [
    { title: "Request", summary: "Scope, permissions, and sensitive intent are checked before retrieval begins.", receives: "User request", output: "Approved request", icon: "question" },
    { title: "Evidence gate", summary: "Weak retrieval scores or missing evidence stop the automatic answer path.", receives: "Retrieved context", output: "Confidence decision", icon: "shield" },
    { title: "Answer check", summary: "Citation and support checks reject output that cannot be tied to context.", receives: "Generated response", output: "Support decision", icon: "check" },
    { title: "Answer or review", summary: "Supported answers continue; uncertain cases abstain or move to a person.", receives: "Support decision", output: "Safe outcome", icon: "review" },
  ],
  quality: [
    { title: "Golden set", summary: "Versioned questions define expected sources, answers, and unanswerable cases.", receives: "Business scenarios", output: "Evaluation cases", icon: "golden" },
    { title: "Retrieve", summary: "Recall, precision, hit rate, and MRR isolate evidence-finding quality.", receives: "Evaluation cases", output: "Retrieval scores", icon: "search" },
    { title: "Generate", summary: "Faithfulness, correctness, completeness, and citations measure evidence use.", receives: "Expected + actual answers", output: "Answer scores", icon: "measure" },
    { title: "Release gate", summary: "A regression blocks release when a business-defined threshold is missed.", receives: "Quality report", output: "Ship or stop", icon: "release" },
  ],
  production: [
    { title: "Ingest", summary: "Versioned, repeatable processing keeps the local index current and recoverable.", receives: "Approved documents", output: "Current knowledge index", icon: "ingest" },
    { title: "Query", summary: "Bounded paths enforce permissions, timeouts, retrieval limits, and evidence budgets.", receives: "User question", output: "Grounded response", icon: "search" },
    { title: "Observe", summary: "Traces connect scores, selected chunks, tokens, latency, errors, and cost.", receives: "Runtime signals", output: "Diagnosable trace", icon: "observe" },
    { title: "Improve", summary: "Golden evaluations and feedback guide safe prompt, model, and index changes.", receives: "Traces + evaluations", output: "Versioned improvement", icon: "measure" },
  ],
};

function useCompactFlow() {
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 760px)").matches);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 760px)");
    const update = () => setCompact(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return compact;
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

function nodePositions(variant: LessonVisual, compact: boolean) {
  const branched = variant === "search" || variant === "compare";
  if (compact && branched) return [{ x: 150, y: 0 }, { x: 0, y: 210 }, { x: 300, y: 210 }, { x: 150, y: 420 }];
  if (compact) return [{ x: 40, y: 0 }, { x: 40, y: 190 }, { x: 40, y: 380 }, { x: 40, y: 570 }];
  if (branched) return [{ x: 0, y: 150 }, { x: 300, y: 15 }, { x: 300, y: 285 }, { x: 650, y: 150 }];
  return [{ x: 0, y: 150 }, { x: 270, y: 150 }, { x: 540, y: 150 }, { x: 810, y: 150 }];
}

function RagStageNode({ data }: NodeProps<RagNode>) {
  const Icon = icons[data.stage.icon];
  const vertical = data.direction === "vertical";
  const targetPosition = vertical ? Position.Top : Position.Left;
  const sourcePosition = vertical ? Position.Bottom : Position.Right;
  const splitStyleA = vertical ? { left: "34%" } : { top: "34%" };
  const splitStyleB = vertical ? { left: "66%" } : { top: "66%" };

  return (
    <div className={data.active ? "rag-stage-node active" : "rag-stage-node"}>
      <NodeToolbar isVisible={data.active} position={Position.Top} offset={10} className="rag-node-toolbar">
        Now explaining · step {data.index + 1}
      </NodeToolbar>

      {data.handleMode === "merge" ? <>
        <Handle id="branch-a" type="target" position={targetPosition} style={splitStyleA} />
        <Handle id="branch-b" type="target" position={targetPosition} style={splitStyleB} />
      </> : data.handleMode !== "input" && data.handleMode !== "split" && <Handle type="target" position={targetPosition} />}

      <div className="rag-node-header"><span><Icon size={16} strokeWidth={1.7} /></span><small>Stage {String(data.index + 1).padStart(2, "0")}</small></div>
      <strong>{data.stage.title}</strong>
      <p>{data.stage.summary}</p>
      <div className="rag-node-output"><span>Produces</span>{data.stage.output}</div>

      {data.handleMode === "split" ? <>
        <Handle id="branch-a" type="source" position={sourcePosition} style={splitStyleA} />
        <Handle id="branch-b" type="source" position={sourcePosition} style={splitStyleB} />
      </> : data.handleMode !== "output" && data.handleMode !== "merge" && <Handle type="source" position={sourcePosition} />}
    </div>
  );
}

function ArtifactEdge({ id, data, markerEnd, ...props }: EdgeProps<RagEdge>) {
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    borderRadius: 22,
  });

  return <>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} className={data?.active ? "artifact-edge active" : "artifact-edge"} />
    {data?.active && data.motion && <circle className="edge-packet" r="5"><animateMotion dur="1.65s" repeatCount="indefinite" path={path} /></circle>}
    <EdgeLabelRenderer>
      <span className={data?.active ? "edge-artifact-label active" : "edge-artifact-label"} style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>{data?.label}</span>
    </EdgeLabelRenderer>
  </>;
}

const nodeTypes = { ragStage: memo(RagStageNode) };
const edgeTypes = { artifact: ArtifactEdge };

export function ConceptVisual({ variant, caption }: { variant: LessonVisual; caption: string }) {
  const stages = stageSets[variant];
  const compact = useCompactFlow();
  const reducedMotion = useReducedMotion();
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(!reducedMotion);
  const branched = variant === "search" || variant === "compare";

  useEffect(() => {
    setActive(0);
    setPlaying(!reducedMotion);
  }, [reducedMotion, variant]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setActive((current) => (current + 1) % stages.length), 3200);
    return () => window.clearInterval(timer);
  }, [playing, stages.length]);

  const nodes = useMemo<RagNode[]>(() => {
    const layout = nodePositions(variant, compact);
    return stages.map((stage, index) => ({
      id: String(index),
      type: "ragStage",
      position: layout[index],
      data: {
        index,
        stage,
        active: index === active,
        handleMode: index === 0 ? (branched ? "split" : "input") : index === stages.length - 1 ? (branched ? "merge" : "output") : "single",
        direction: compact ? "vertical" : "horizontal",
      },
      draggable: false,
      selectable: true,
    }));
  }, [active, branched, compact, stages, variant]);

  const edges = useMemo<RagEdge[]>(() => {
    const links = branched ? [[0, 1, "branch-a", undefined], [0, 2, "branch-b", undefined], [1, 3, undefined, "branch-a"], [2, 3, undefined, "branch-b"]] : stages.slice(1).map((_, index) => [index, index + 1, undefined, undefined]);
    return links.map(([source, target, sourceHandle, targetHandle], index) => ({
      id: `edge-${index}`,
      type: "artifact",
      source: String(source),
      target: String(target),
      sourceHandle: sourceHandle as string | undefined,
      targetHandle: targetHandle as string | undefined,
      data: { label: stages[Number(source)].output, active: Number(source) === active, motion: !reducedMotion },
      markerEnd: { type: MarkerType.ArrowClosed, color: Number(source) === active ? "#282724" : "#a9a094", width: 15, height: 15 },
      zIndex: Number(source) === active ? 2 : 1,
    }));
  }, [active, branched, reducedMotion, stages]);

  function selectStage(index: number) {
    setActive(index);
    setPlaying(false);
  }

  return (
    <figure className="concept-visual">
      <div className={compact ? "react-flow-frame compact" : "react-flow-frame"} role="img" aria-label={caption}>
        <ReactFlow
          key={`${variant}-${compact}`}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: compact ? 0.1 : 0.16 }}
          minZoom={0.35}
          maxZoom={1.45}
          nodesConnectable={false}
          nodesDraggable={false}
          zoomOnDoubleClick={false}
          onNodeClick={(_, node) => selectStage(Number(node.id))}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#b9b0a2" gap={22} size={1} />
          <Panel position="top-left" className="flow-canvas-title"><span>Interactive pipeline</span><strong>{branched ? "Split and merge flow" : "Guided data flow"}</strong></Panel>
          <Panel position="top-right" className="flow-playback"><button onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause walkthrough" : "Play walkthrough"}>{playing ? <Pause size={13} /> : <Play size={13} />}{playing ? "Pause" : "Play"}</button></Panel>
          <Panel position="bottom-center" className="flow-step-selector">{stages.map((stage, index) => <button key={stage.title} className={index === active ? "active" : ""} onClick={() => selectStage(index)} aria-label={`Explain stage ${index + 1}: ${stage.title}`}>{index + 1}</button>)}</Panel>
          <Controls showInteractive={false} position="bottom-right" />
        </ReactFlow>
      </div>

      <div className="flow-explanation">
        <div className="flow-explanation-index"><span>{String(active + 1).padStart(2, "0")}</span><small>of {stages.length}</small></div>
        <div className="flow-explanation-copy"><span>Currently explaining</span><strong>{stages[active].title}</strong><p>{stages[active].summary}</p></div>
        <dl><div><dt>Receives</dt><dd>{stages[active].receives}</dd></div><div><dt>Passes forward</dt><dd>{stages[active].output}</dd></div></dl>
      </div>
      <figcaption>{caption} Select a node or numbered step to pause and inspect it.</figcaption>
    </figure>
  );
}
