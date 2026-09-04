import { useEffect, useRef, useState } from "react";
import { FileText, LoaderCircle, RotateCcw, UploadCloud } from "lucide-react";
import { getIngestion, uploadDocument } from "../api";
import type { ConnectionConfig, FlowEvent, IngestionStatus } from "../types";

const terminalStates = new Set(["succeeded", "failed"]);

function pause(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function IngestionPanel({ config, onEvents }: { config: ConnectionConfig; onEvents: (events: FlowEvent[]) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [product, setProduct] = useState("");
  const [version, setVersion] = useState("");
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setRunning(true);
    setError(null);
    setStatus(null);
    onEvents([]);
    try {
      const accepted = await uploadDocument(config, { file, documentId, product, version });
      while (mounted.current) {
        const current = await getIngestion(config, accepted.job_id);
        if (!mounted.current) return;
        setStatus(current);
        onEvents(current.events);
        if (terminalStates.has(current.state)) break;
        await pause(800);
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Ingestion failed");
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
    <section className="operation-panel">
      <header className="panel-heading"><div><span>Run ingestion</span><h2>Add knowledge</h2><p>Upload one supported document and watch the actual worker stage history appear on the canvas.</p></div>{status && <span className={`job-chip ${status.state}`}>{status.state}</span>}</header>
      <form onSubmit={submit} className="operation-form">
        <label className={`file-drop ${file ? "selected" : ""}`}>
          <input type="file" accept=".pdf,.html,.htm,.md,.markdown,.docx,.pptx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          {file ? <><FileText size={25} /><strong>{file.name}</strong><small>{formatBytes(file.size)} · click to replace</small></> : <><UploadCloud size={27} /><strong>Choose a source document</strong><small>PDF, HTML, Markdown, Word, or PowerPoint · maximum 200 PDF pages</small></>}
        </label>
        <div className="field-grid">
          <label><span>Document ID</span><input value={documentId} onChange={(event) => setDocumentId(event.target.value)} placeholder="Generated when blank" /></label>
          <label><span>Product filter</span><input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="Optional" /></label>
          <label><span>Version</span><input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="Optional" /></label>
        </div>
        <div className="form-actions"><button className="primary-button" type="submit" disabled={!file || running}>{running ? <LoaderCircle className="status-spin" size={16} /> : <UploadCloud size={16} />}{running ? "Ingestion running" : "Start ingestion"}</button>{(status || error) && <button className="quiet-button" type="button" onClick={reset} disabled={running}><RotateCcw size={15} />New document</button>}</div>
      </form>
      {error && <div className="error-card"><strong>Ingestion did not complete</strong><p>{error}</p></div>}
      {status?.result && <div className="result-summary"><div><span>Document</span><strong>{status.result.document_id}</strong></div><div><span>Parent sections</span><strong>{status.result.parents_indexed}</strong></div><div><span>Child chunks</span><strong>{status.result.chunks_indexed}</strong></div><div><span>Checksum</span><strong>{status.result.checksum.slice(0, 12)}</strong></div></div>}
    </section>
  );
}
