import { useEffect, useMemo, useState } from "react";
import { Activity, ChevronRight, DatabaseZap, FileCheck2, SearchCheck, SlidersHorizontal } from "lucide-react";
import { checkBackend, checkReadiness } from "./api";
import { ConnectionSettings } from "./components/ConnectionSettings";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { IngestionPanel } from "./components/IngestionPanel";
import { QueryPanel } from "./components/QueryPanel";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import type { BackendHealth, ConnectionConfig, FlowEvent, WorkflowId } from "./types";
import { workflowCopy, workflowStages } from "./workflow";

const navigation: Array<{ id: WorkflowId; label: string; caption: string; icon: typeof DatabaseZap }> = [
  { id: "ingestion", label: "Ingest", caption: "Document to local index", icon: DatabaseZap },
  { id: "query", label: "Query", caption: "Question to cited answer", icon: SearchCheck },
  { id: "evaluation", label: "Evaluate", caption: "Golden set to quality report", icon: FileCheck2 },
];

function initialConfig(): ConnectionConfig {
  return {
    apiBaseUrl: localStorage.getItem("prodrag-api-base") || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
    tenantId: localStorage.getItem("prodrag-tenant") || "default",
    adminKey: "",
    queryKey: "",
  };
}

function updateWorkflowEvents(
  current: Record<WorkflowId, FlowEvent[]>,
  workflow: WorkflowId,
  events: FlowEvent[],
): Record<WorkflowId, FlowEvent[]> {
  return { ...current, [workflow]: events };
}

export function App() {
  const [workflow, setWorkflow] = useState<WorkflowId>("ingestion");
  const [config, setConfig] = useState<ConnectionConfig>(initialConfig);
  const [events, setEvents] = useState<Record<WorkflowId, FlowEvent[]>>({ ingestion: [], query: [], evaluation: [] });
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [checking, setChecking] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const copy = workflowCopy[workflow];

  useEffect(() => {
    localStorage.setItem("prodrag-api-base", config.apiBaseUrl);
    localStorage.setItem("prodrag-tenant", config.tenantId);
  }, [config.apiBaseUrl, config.tenantId]);

  async function checkConnection() {
    setChecking(true);
    setConnectionError(null);
    try {
      await checkBackend(config);
      const ready = await checkReadiness(config);
      setHealth(ready);
    } catch (cause) {
      setHealth(null);
      setConnectionError(cause instanceof Error ? cause.message : "Backend is unavailable");
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => { void checkConnection(); }, []);

  const progress = useMemo(() => {
    const latest = new Map(events[workflow].map((event) => [event.stage, event]));
    const completed = workflowStages[workflow].filter((stage) => {
      const status = latest.get(stage.id)?.status;
      return status === "completed" || status === "skipped";
    }).length;
    return { completed, total: workflowStages[workflow].length };
  }, [events, workflow]);

  return (
    <div className="flow-console">
      <aside className="console-sidebar">
        <div className="console-brand"><span>PR</span><div><strong>prodRAG</strong><small>Flow console</small></div></div>
        <nav aria-label="Runtime workflows">
          <span className="nav-label">Workflows</span>
          {navigation.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={workflow === item.id ? "active" : ""} onClick={() => setWorkflow(item.id)}><Icon size={18} /><span><strong>{item.label}</strong><small>{item.caption}</small></span><ChevronRight size={15} /></button>;
          })}
        </nav>
        <div className="sidebar-note"><Activity size={17} /><div><strong>Runtime-backed</strong><p>Nodes change only when the backend records a real stage event.</p></div></div>
      </aside>

      <div className="console-main">
        <header className="console-topbar"><div><span className="topbar-mark">prodRAG / {workflow}</span><strong>Local RAG operations</strong></div><div className="topbar-status"><span>{progress.completed}/{progress.total} stages</span><i /><b>{health?.status === "ready" ? "services ready" : "check services"}</b></div></header>
        <main>
          <section className="workflow-intro"><div><span>{copy.eyebrow}</span><h1>{copy.title}</h1><p>{copy.summary}</p></div><div className="intro-fact"><SlidersHorizontal size={18} /><span>Active tenant</span><strong>{config.tenantId}</strong><small>Qdrant stays local; OCI handles configured model operations.</small></div></section>

          <ConnectionSettings config={config} onChange={setConfig} health={health} checking={checking} error={connectionError} onCheck={() => void checkConnection()} />

          <WorkflowCanvas workflow={workflow} events={events[workflow]} />

          <div className="operation-panels">
            <div hidden={workflow !== "ingestion"}><IngestionPanel config={config} onEvents={(next) => setEvents((current) => updateWorkflowEvents(current, "ingestion", next))} /></div>
            <div hidden={workflow !== "query"}><QueryPanel config={config} onEvents={(next) => setEvents((current) => updateWorkflowEvents(current, "query", next))} /></div>
            <div hidden={workflow !== "evaluation"}><EvaluationPanel config={config} onEvents={(next) => setEvents((current) => updateWorkflowEvents(current, "evaluation", next))} /></div>
          </div>
        </main>
      </div>
    </div>
  );
}
