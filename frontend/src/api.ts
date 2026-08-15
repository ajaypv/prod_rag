import type {
  BackendHealth,
  ConnectionConfig,
  EvaluationAccepted,
  EvaluationStatus,
  IngestionAccepted,
  IngestionStatus,
  QueryStreamMessage,
} from "./types";

function endpoint(config: ConnectionConfig, path: string): string {
  return `${config.apiBaseUrl.replace(/\/$/, "")}${path}`;
}

async function apiError(response: Response): Promise<Error> {
  try {
    const body = await response.json() as { detail?: unknown };
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    return new Error(detail || `Request failed with status ${response.status}`);
  } catch {
    return new Error(`Request failed with status ${response.status}`);
  }
}

function headers(keyName: "X-Admin-Key" | "X-API-Key", key: string): HeadersInit {
  return key ? { [keyName]: key } : {};
}

export async function checkBackend(config: ConnectionConfig): Promise<BackendHealth> {
  const response = await fetch(endpoint(config, "/healthz"));
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<BackendHealth>;
}

export async function checkReadiness(config: ConnectionConfig): Promise<BackendHealth> {
  const response = await fetch(endpoint(config, "/readyz"));
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<BackendHealth>;
}

export async function uploadDocument(
  config: ConnectionConfig,
  input: {
    file: File;
    documentId: string;
    product: string;
    version: string;
  },
): Promise<IngestionAccepted> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("tenant_id", config.tenantId);
  if (input.documentId) form.append("document_id", input.documentId);
  if (input.product) form.append("product", input.product);
  if (input.version) form.append("version", input.version);
  const response = await fetch(endpoint(config, "/v1/documents"), {
    method: "POST",
    headers: headers("X-Admin-Key", config.adminKey),
    body: form,
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<IngestionAccepted>;
}

export async function getIngestion(
  config: ConnectionConfig,
  jobId: string,
): Promise<IngestionStatus> {
  const response = await fetch(endpoint(config, `/v1/ingestions/${jobId}`), {
    headers: headers("X-Admin-Key", config.adminKey),
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<IngestionStatus>;
}

export async function streamQuery(
  config: ConnectionConfig,
  input: { question: string; product: string; version: string },
  onMessage: (message: QueryStreamMessage) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(endpoint(config, "/v1/query/stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers("X-API-Key", config.queryKey),
    },
    body: JSON.stringify({
      question: input.question,
      tenant_id: config.tenantId,
      product: input.product || null,
      version: input.version || null,
    }),
    signal,
  });
  if (!response.ok) throw await apiError(response);
  if (!response.body) throw new Error("The browser did not expose the response stream");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame.split("\n").find((line) => line.startsWith("data: "));
      if (data) onMessage(JSON.parse(data.slice(6)) as QueryStreamMessage);
    }
    if (done) break;
  }
}

export async function startEvaluation(
  config: ConnectionConfig,
  input: { file: File; endToEnd: boolean; deepEval: boolean },
): Promise<EvaluationAccepted> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("tenant_id", config.tenantId);
  form.append("end_to_end", String(input.endToEnd));
  form.append("deep_eval", String(input.deepEval));
  const response = await fetch(endpoint(config, "/v1/evaluations"), {
    method: "POST",
    headers: headers("X-Admin-Key", config.adminKey),
    body: form,
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<EvaluationAccepted>;
}

export async function getEvaluation(
  config: ConnectionConfig,
  jobId: string,
): Promise<EvaluationStatus> {
  const response = await fetch(endpoint(config, `/v1/evaluations/${jobId}`), {
    headers: headers("X-Admin-Key", config.adminKey),
  });
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<EvaluationStatus>;
}
