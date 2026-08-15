# prodRAG Flow Console

The frontend is a React/Vite operations console connected to the real prodRAG backend. React Flow
nodes are driven by backend stage events rather than simulated playback.

It provides three workflows:

- **Ingest** uploads a supported document, polls the durable Redis job, and shows checksum,
  Docling parsing, parent sectioning, semantic chunking/embedding, and local Qdrant indexing.
- **Query** consumes the streaming query endpoint and shows triage, dense + BM25 retrieval with RRF,
  reranking, parent-context assembly, confidence gating, generation, citations, and evidence excerpts.
- **Evaluate** uploads golden JSONL, polls the evaluation worker, and displays retrieval, answer,
  abstention, citation, and optional DeepEval metrics.

API and tenant values are saved locally for convenience. Query and admin keys remain only in React
memory for the current browser tab.

## Prerequisites

Start Qdrant and Redis, the FastAPI process, and the Dramatiq worker from the repository root. Use
the development dependency group when the DeepEval UI option is required:

```powershell
docker compose up -d
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv sync --group dev
uv run uvicorn prodrag.api:app --host 0.0.0.0 --port 8000
```

In a second root terminal:

```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv run dramatiq prodrag.worker --processes 1 --threads 2
```

## Run the frontend

```powershell
Set-Location .\frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open `http://127.0.0.1:4173`. The default backend is `http://127.0.0.1:8000`; change it in the
connection panel or provide `VITE_API_BASE_URL` at build time.

```powershell
$env:VITE_API_BASE_URL = 'https://rag-api.example.com'
pnpm build
```

The backend must allow the frontend origin through `RAG_CORS_ORIGINS`. The project-local `.npmrc`
points pnpm to the official npm registry.

For GitHub Pages, create a repository Actions variable named `VITE_API_BASE_URL` whose value is the
public HTTPS URL of the running prodRAG API. The Pages workflow passes that value into the Vite
build. Add the Pages origin to the backend's `RAG_CORS_ORIGINS` value as well.
