import { useEffect, useMemo, useRef, useState } from "react";
import { ClipboardCheck, FileJson2, FlaskConical, LoaderCircle, RotateCcw } from "lucide-react";
import { getEvaluation, startEvaluation } from "../api";
import type { ConnectionConfig, EvaluationStatus, FlowEvent } from "../types";

const terminalStates = new Set(["succeeded", "failed"]);
const metricOrder = [
  "mean_recall",
  "mean_precision",
  "hit_rate",
  "mrr",
  "abstention_accuracy",
  "citation_document_hit_rate",
  "answer_correctness",
  "faithfulness",
  "deepeval_contextual_recall",
  "deepeval_contextual_precision",
  "deepeval_faithfulness",
  "deepeval_answer_relevancy",
];

function pause(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function metricLabel(value: string): string {
  return value.replace(/^deepeval_/, "DeepEval · ").replaceAll("_", " ");
}

export function EvaluationPanel({ config, onEvents }: { config: ConnectionConfig; onEvents: (events: FlowEvent[]) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [endToEnd, setEndToEnd] = useState(true);
  const [deepEval, setDeepEval] = useState(false);
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  const metrics = useMemo(() => metricOrder.flatMap((key) => {
    const value = status?.metrics?.[key];
    return typeof value === "number" ? [[key, value] as const] : [];
  }), [status]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setRunning(true);
    setError(null);
    setStatus(null);
    onEvents([]);
    try {
      const accepted = await startEvaluation(config, { file, endToEnd, deepEval });
      while (mounted.current) {
        const current = await getEvaluation(config, accepted.job_id);
        if (!mounted.current) return;
        setStatus(current);
        onEvents(current.events);
        if (terminalStates.has(current.state)) break;
        await pause(1_000);
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Evaluation failed");
    } finally {
      if (mounted.current) setRunning(false);
    }
  }

  function reset() {
    setFile(null);
    setStatus(null);
    setError(null);
    onEvents([]);
  }

  return (
    <section className="operation-panel evaluation-panel">
      <header className="panel-heading"><div><span>Run evaluation</span><h2>Test a golden dataset</h2><p>Upload the same JSONL labels used by the CLI. The worker runs against the currently indexed local corpus.</p></div>{status && <span className={`job-chip ${status.state}`}>{status.state}</span>}</header>
      <form onSubmit={submit} className="operation-form">
        <label className={`file-drop compact ${file ? "selected" : ""}`}><input type="file" accept=".jsonl" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />{file ? <><FileJson2 size={24} /><strong>{file.name}</strong><small>Golden dataset selected · click to replace</small></> : <><ClipboardCheck size={26} /><strong>Choose golden questions</strong><small>JSONL with expected document IDs and optional expected answers</small></>}</label>
        <div className="evaluation-options"><label><input type="checkbox" checked={endToEnd} onChange={(event) => { setEndToEnd(event.target.checked); if (!event.target.checked) setDeepEval(false); }} /><span><strong>End-to-end quality</strong><small>Run generation, citations, abstention, and the existing quality judge.</small></span></label><label className={!endToEnd ? "disabled" : ""}><input type="checkbox" checked={deepEval} disabled={!endToEnd} onChange={(event) => setDeepEval(event.target.checked)} /><span><strong>DeepEval semantic metrics</strong><small>Add contextual recall, precision, faithfulness, and answer relevancy OCI judge calls.</small></span></label></div>
        <div className="cost-note"><FlaskConical size={16} /><p>Retrieval-only evaluation is cheapest. End-to-end and DeepEval modes make additional OCI model calls for each labelled question.</p></div>
        <div className="form-actions"><button className="primary-button" type="submit" disabled={!file || running}>{running ? <LoaderCircle className="status-spin" size={16} /> : <ClipboardCheck size={16} />}{running ? "Evaluation running" : "Start evaluation"}</button>{(status || error) && <button className="quiet-button" type="button" onClick={reset} disabled={running}><RotateCcw size={15} />New dataset</button>}</div>
      </form>
      {error && <div className="error-card"><strong>Evaluation did not complete</strong><p>{error}</p></div>}
      {status?.state === "failed" && <div className="error-card"><strong>Evaluation worker failed</strong><p>{status.message}</p></div>}
      {metrics.length > 0 && <div className="metric-report"><header><span>Quality report</span><strong>{status?.metrics?.questions ? String(status.metrics.questions) : "—"} questions</strong></header><div>{metrics.map(([key, value]) => <article key={key}><span>{metricLabel(key)}</span><strong>{value.toFixed(3)}</strong><meter min="0" max="1" value={value} /></article>)}</div></div>}
    </section>
  );
}
