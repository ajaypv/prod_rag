import { useEffect, useRef, useState } from "react";
import { BookOpenCheck, CircleStop, LoaderCircle, MessageSquareText, Search, ShieldAlert } from "lucide-react";
import { streamQuery } from "../api";
import type { ConnectionConfig, EvidencePreview, FlowEvent, QueryResponse } from "../types";

export function QueryPanel({ config, onEvents }: { config: ConnectionConfig; onEvents: (events: FlowEvent[]) => void }) {
  const [question, setQuestion] = useState("How long are events retained?");
  const [product, setProduct] = useState("");
  const [version, setVersion] = useState("");
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [evidence, setEvidence] = useState<EvidencePreview[]>([]);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const trace = useRef<FlowEvent[]>([]);

  useEffect(() => () => controller.current?.abort(), []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    controller.current?.abort();
    controller.current = new AbortController();
    trace.current = [];
    onEvents([]);
    setResponse(null);
    setEvidence([]);
    setError(null);
    setRunning(true);
    try {
      await streamQuery(
        config,
        { question, product, version },
        (message) => {
          if (message.type === "stage") {
            trace.current = [...trace.current, message.event];
            onEvents(trace.current);
          } else if (message.type === "result") {
            setResponse(message.response);
            setEvidence(message.evidence);
          } else {
            setError(message.detail);
          }
        },
        controller.current.signal,
      );
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") return;
      setError(cause instanceof Error ? cause.message : "Query failed");
    } finally {
      setRunning(false);
    }
  }

  function cancel() {
    controller.current?.abort();
    setRunning(false);
  }

  return (
    <section className="operation-panel query-panel">
      <header className="panel-heading"><div><span>Run a query</span><h2>Inspect one answer</h2><p>The streamed canvas reflects the real backend path, including skipped safety and answer stages.</p></div>{response && <span className={`job-chip ${response.answered ? "succeeded" : "review"}`}>{response.answered ? "answered" : "human review"}</span>}</header>
      <form onSubmit={submit} className="operation-form">
        <label><span>Question</span><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} minLength={2} maxLength={4000} /></label>
        <div className="field-grid two"><label><span>Product filter</span><input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="Optional" /></label><label><span>Version</span><input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="Optional" /></label></div>
        <div className="form-actions"><button className="primary-button" type="submit" disabled={running || question.trim().length < 2}>{running ? <LoaderCircle className="status-spin" size={16} /> : <Search size={16} />}{running ? "Query running" : "Run grounded query"}</button>{running && <button className="quiet-button" type="button" onClick={cancel}><CircleStop size={15} />Cancel</button>}</div>
      </form>
      {error && <div className="error-card"><strong>Query did not complete</strong><p>{error}</p></div>}
      {response && <div className="query-result">
        <div className="answer-meta"><span><MessageSquareText size={14} />{response.category.replaceAll("_", " ")}</span><span className={`confidence ${response.confidence}`}>{response.confidence} confidence</span><span>{response.citations.length} citations</span></div>
        <div className={response.answered ? "answer-copy" : "answer-copy abstained"}>{!response.answered && <ShieldAlert size={20} />}<p>{response.answer}</p></div>
        {response.escalation_reasons.length > 0 && <div className="reason-row">Reasons: {response.escalation_reasons.map((reason) => reason.replaceAll("_", " ")).join(", ")}</div>}
        {response.citations.length > 0 && <div className="citation-list"><h3>Validated citations</h3>{response.citations.map((citation) => <article key={citation.source_id}><span>{citation.source_id}</span><div><strong>{citation.title}</strong><p>{citation.section} · {citation.source_name}</p></div><b>{citation.relevance_score.toFixed(3)}</b></article>)}</div>}
      </div>}
      {evidence.length > 0 && <div className="evidence-list"><h3><BookOpenCheck size={16} />Evidence passed to the answer</h3>{evidence.map((item, index) => <details key={`${item.document_id}-${item.section}-${index}`}><summary><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{item.title}</strong><small>{item.section}</small></div><b>{item.score.toFixed(3)}</b></summary><p>{item.excerpt}</p></details>)}</div>}
    </section>
  );
}
