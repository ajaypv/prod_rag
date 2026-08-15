import { memo, useEffect, useMemo, useState } from "react";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Check, Circle, LoaderCircle, Minus, TriangleAlert } from "lucide-react";
import type { FlowEvent, FlowStatus, WorkflowId } from "../types";
import { workflowStages, type WorkflowStage } from "../workflow";

type VisualStatus = FlowStatus | "waiting";
type HandleDirection = "forward" | "down" | "backward";

type StageNodeData = {
  stage: WorkflowStage;
  index: number;
  event?: FlowEvent;
  status: VisualStatus;
  targetDirection: HandleDirection;
  sourceDirection: HandleDirection;
};

type StageNode = Node<StageNodeData, "liveStage">;
type StageEdge = Edge<{ active: boolean; label: string }, "liveEdge">;

function useCompactCanvas(): boolean {
  const [compact, setCompact] = useState(() => window.matchMedia("(max-width: 760px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const update = () => setCompact(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return compact;
}

function handlePosition(direction: HandleDirection, target: boolean): Position {
  if (direction === "down") return target ? Position.Top : Position.Bottom;
  if (direction === "backward") return target ? Position.Right : Position.Left;
  return target ? Position.Left : Position.Right;
}

function StatusGlyph({ status }: { status: VisualStatus }) {
  if (status === "running") return <LoaderCircle className="status-spin" size={14} />;
  if (status === "completed") return <Check size={14} />;
  if (status === "failed") return <TriangleAlert size={14} />;
  if (status === "skipped") return <Minus size={14} />;
  return <Circle size={10} />;
}

function LiveStageNode({ data }: NodeProps<StageNode>) {
  const Icon = data.stage.icon;
  const details = Object.entries(data.event?.data ?? {}).slice(0, 2);
  return (
    <article className={`live-stage-node ${data.status}`}>
      <Handle type="target" position={handlePosition(data.targetDirection, true)} />
      <header>
        <span className="stage-icon"><Icon size={17} strokeWidth={1.7} /></span>
        <span className="stage-index">{String(data.index + 1).padStart(2, "0")}</span>
        <span className="stage-status"><StatusGlyph status={data.status} />{data.status}</span>
      </header>
      <h3>{data.stage.title}</h3>
      <p>{data.event?.message ?? data.stage.description}</p>
      {details.length > 0 ? (
        <dl>{details.map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl>
      ) : <div className="stage-artifact"><span>Produces</span>{data.stage.artifact}</div>}
      {data.event?.duration_ms != null && <time>{data.event.duration_ms.toFixed(0)} ms</time>}
      <Handle type="source" position={handlePosition(data.sourceDirection, false)} />
    </article>
  );
}

function LiveEdge({ id, data, markerEnd, ...props }: EdgeProps<StageEdge>) {
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
    borderRadius: 18,
  });
  return <>
    <BaseEdge id={id} path={path} markerEnd={markerEnd} className={data?.active ? "live-edge active" : "live-edge"} />
    {data?.active && <circle r="4" className="flow-packet"><animateMotion dur="1.25s" repeatCount="indefinite" path={path} /></circle>}
    <EdgeLabelRenderer><span className="live-edge-label" style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}>{data?.label}</span></EdgeLabelRenderer>
  </>;
}

const nodeTypes = { liveStage: memo(LiveStageNode) };
const edgeTypes = { liveEdge: LiveEdge };

function latestEvents(events: FlowEvent[]): Map<string, FlowEvent> {
  const result = new Map<string, FlowEvent>();
  for (const event of events) result.set(event.stage, event);
  return result;
}

export function WorkflowCanvas({ workflow, events }: { workflow: WorkflowId; events: FlowEvent[] }) {
  const compact = useCompactCanvas();
  const stages = workflowStages[workflow];
  const byStage = useMemo(() => latestEvents(events), [events]);
  const columns = stages.length <= 6 ? 3 : 4;

  const nodes = useMemo<StageNode[]>(() => stages.map((stage, index) => {
    const secondRow = index >= columns;
    const rowIndex = secondRow ? index - columns : index;
    const column = secondRow ? columns - 1 - rowIndex : rowIndex;
    const position = compact
      ? { x: 30, y: index * 218 }
      : { x: column * 275, y: secondRow ? 280 : 20 };
    const isTurn = !compact && index === columns - 1 && index < stages.length - 1;
    const isFirstSecondRow = !compact && index === columns;
    return {
      id: stage.id,
      type: "liveStage",
      position,
      data: {
        stage,
        index,
        event: byStage.get(stage.id),
        status: byStage.get(stage.id)?.status ?? "waiting",
        targetDirection: compact || isFirstSecondRow ? "down" : secondRow ? "backward" : "forward",
        sourceDirection: compact || isTurn ? "down" : secondRow ? "backward" : "forward",
      },
      draggable: false,
      selectable: true,
    };
  }), [byStage, columns, compact, stages]);

  const edges = useMemo<StageEdge[]>(() => stages.slice(0, -1).map((stage, index) => {
    const targetEvent = byStage.get(stages[index + 1].id);
    return {
      id: `${stage.id}-${stages[index + 1].id}`,
      type: "liveEdge",
      source: stage.id,
      target: stages[index + 1].id,
      data: { active: targetEvent?.status === "running", label: stage.artifact },
      markerEnd: { type: MarkerType.ArrowClosed, color: targetEvent ? "#2c2b28" : "#b7afa2", width: 15, height: 15 },
    };
  }), [byStage, stages]);

  const current = [...events].reverse().find((event) => event.status === "running") ?? events.at(-1);
  const height = compact ? Math.max(620, stages.length * 218 + 70) : 580;

  return (
    <section className="workflow-canvas" style={{ height }} aria-label={`${workflow} runtime flow`}>
      <ReactFlow
        key={`${workflow}-${compact}`}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: compact ? 0.08 : 0.12 }}
        minZoom={0.35}
        maxZoom={1.35}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={!compact}
        zoomOnScroll={!compact}
        zoomOnPinch={!compact}
        zoomOnDoubleClick={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#c8c0b4" gap={24} size={1} />
        <Panel position="top-left" className="canvas-caption"><span>Runtime trace</span><strong>{current?.message ?? "Ready for a real operation"}</strong></Panel>
        {!compact && <Controls showInteractive={false} position="bottom-right" />}
      </ReactFlow>
    </section>
  );
}
