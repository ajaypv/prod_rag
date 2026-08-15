import { CheckCircle2, CircleOff, LoaderCircle, PlugZap, ServerCog } from "lucide-react";
import type { BackendHealth, ConnectionConfig } from "../types";

interface Props {
  config: ConnectionConfig;
  onChange: (config: ConnectionConfig) => void;
  health: BackendHealth | null;
  checking: boolean;
  error: string | null;
  onCheck: () => void;
}

export function ConnectionSettings({ config, onChange, health, checking, error, onCheck }: Props) {
  const connected = health?.status === "ready" || health?.status === "ok";
  function update(field: keyof ConnectionConfig, value: string) {
    onChange({ ...config, [field]: value });
  }

  return (
    <section className="connection-settings">
      <header><div><span>Runtime connection</span><strong>Backend and tenant</strong></div><span className={`connection-state ${connected ? "connected" : error ? "failed" : "idle"}`}>{checking ? <LoaderCircle className="status-spin" size={14} /> : connected ? <CheckCircle2 size={14} /> : <CircleOff size={14} />}{checking ? "Checking" : connected ? "Connected" : error ? "Unavailable" : "Not checked"}</span></header>
      <div className="connection-grid">
        <label className="wide"><span>API base URL</span><div><ServerCog size={15} /><input value={config.apiBaseUrl} onChange={(event) => update("apiBaseUrl", event.target.value)} placeholder="http://127.0.0.1:8000" /></div></label>
        <label><span>Tenant</span><input value={config.tenantId} onChange={(event) => update("tenantId", event.target.value)} /></label>
        <label><span>Query key</span><input type="password" value={config.queryKey} onChange={(event) => update("queryKey", event.target.value)} placeholder="Optional in development" autoComplete="off" /></label>
        <label><span>Admin key</span><input type="password" value={config.adminKey} onChange={(event) => update("adminKey", event.target.value)} placeholder="Required when configured" autoComplete="off" /></label>
        <button onClick={onCheck} disabled={checking}><PlugZap size={15} />Test services</button>
      </div>
      {error && <p className="connection-error">{error}</p>}
      {health?.checks && <div className="service-checks">{Object.entries(health.checks).map(([service, state]) => <span key={service}><i />{service}<b>{state}</b></span>)}</div>}
      <small>Keys remain in memory for this browser tab and are never saved to local storage.</small>
    </section>
  );
}
