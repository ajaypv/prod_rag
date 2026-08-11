# prodRAG

Lightweight production RAG for roughly 10–30 technical documents or FAQ files. Document
contents are parsed locally and stored in a local Qdrant server. OCI Generative AI is used
for safety triage, embedding, reranking, and grounded answer generation through LangChain.

## B2B SaaS support demo

The repository includes nine fictional NimbusFlow support documents (eight Markdown and one HTML FAQ), labeled retrieval cases,
and a PowerShell demo for billing, API limits, authentication, and integration failures. The
query response now includes ticket category, confidence, human-review routing, and sensitive-data
types. An OCI LLM performs structured safety triage before retrieval. Sensitive tickets stop
after triage and are routed to the secure customer-support queue without embedding, reranking,
or automatic answer generation.

See [B2B SaaS support demo](docs/b2b-saas-demo.md) for the test flow,
[OCI cost estimate](docs/cost-estimate.md) for the per-1,000-query calculation, and
[production readiness status](docs/production-readiness.md) for completed checks and deployment
blockers.

## Architecture

```mermaid
flowchart LR
    U["Upload API"] --> R["Redis / Dramatiq queue"]
    R --> D["Local parser: native PDF text or Docling"]
    D --> S["Heading-aware parent sections"]
    S --> C["Chonkie semantic child chunks"]
    C --> E["OCI Embed 4 via LangChain"]
    E --> Q["Local Qdrant: dense + BM25 RRF"]
    X["Customer query"] --> T["OCI LLM safety triage"]
    T -->|"safe with medium or high confidence"| Q
    T -->|"sensitive, low-confidence, or invalid"| H["Customer-support review"]
    Q --> RR["OCI Rerank 4"]
    RR --> P["Expand top children to parent sections"]
    P --> L["OCI chat model via LangChain"]
    L --> A["Grounded answer + source citations"]
```

The ingestion worker writes a new checksum-based revision before deleting stale vectors.
If parsing or embedding fails, the previous good revision stays searchable. Point IDs are
deterministic, making retries idempotent.

## Code layout

Each module has one main responsibility:

- `ingestion/parsing.py` extracts Markdown and structure-aware parent sections.
- `ingestion/chunking.py` creates semantic child chunks inside each parent.
- `ingestion/service.py` builds deterministic metadata and upserts document revisions.
- `retrieval/hybrid_search.py` defines the dense-and-sparse search contract.
- `retrieval/sparse.py` configures local FastEmbed `Qdrant/bm25` sparse embeddings.
- `retrieval/reranking.py` contains the OCI reranker adapter.
- `retrieval/context.py` deduplicates children and expands winning parent sections.
- `retrieval/confidence.py` grades retrieval confidence independently from the LLM.
- `retrieval/service.py` orchestrates search, reranking, filtering, and context assembly.
- `vector_store.py` owns Qdrant collection, HNSW/exact settings, upserts, and RRF fusion.
- `prompts.py`, `triage.py`, `answering.py`, and `querying.py` own the LLM-facing flow.

## Why these libraries

- [Docling](https://docling-project.github.io/docling/) parses PDF, DOCX, PPTX, HTML,
  Markdown, and text locally while retaining document structure.
- [Chonkie SemanticChunker](https://docs.chonkie.ai/oss/chunkers/semantic-chunker) creates
  bounded semantic chunks with a custom OCI embedding adapter.
- [LangChain OCI](https://docs.langchain.com/oss/python/integrations/providers/oci) provides
  reusable OCI chat and embedding clients. They are singletons in this service.
- [Qdrant + LangChain](https://qdrant.tech/documentation/frameworks/langchain/) provides
  local dense, BM25 sparse, and hybrid retrieval with explicit RRF fusion. FastEmbed runs BM25
  locally using the packaged English stopword asset, without a runtime model download.
- [Dramatiq](https://dramatiq.io/guide.html) gives the ingestion path durable Redis queues,
  automatic retries, exponential backoff, and a dead-letter queue.

## Exact search versus HNSW

When `.env` sets `QDRANT_PATH`, the service uses Qdrant's embedded Python mode. That mode performs
exact in-process search and does not build a real HNSW graph. Exact search is the better choice for
the current demo corpus because all candidates can be scored with no approximate-recall loss.

For a self-hosted local Qdrant server with HNSW, keep Qdrant on `localhost` and configure:

```dotenv
QDRANT_URL=http://localhost:6333
QDRANT_PATH=
QDRANT_COLLECTION=technical_support_v2
QDRANT_HNSW_ENABLED=true
QDRANT_HNSW_M=16
QDRANT_HNSW_EF_CONSTRUCT=128
QDRANT_HNSW_EF_SEARCH=128
RAG_BM25_MODEL=Qdrant/bm25
RAG_BM25_LANGUAGE=english
```

Qdrant builds and maintains the dense HNSW graph as ingestion upserts points. At query time,
`QDRANT_HNSW_ENABLED=true` selects approximate HNSW search with `hnsw_ef`; the sparse BM25
results use Qdrant's sparse index and are fused with dense results using RRF. The application rejects HNSW plus
`QDRANT_PATH` so embedded exact search cannot be mistaken for HNSW.

Changing the BM25 model, language, tokenizer behavior, or sparse-vector implementation requires a
new collection and full reingestion. Do not mix the former term-frequency vectors from
`technical_support_v1` with FastEmbed BM25 vectors in `technical_support_v2`.

## Accuracy target

No library can honestly guarantee 95–100% retrieval accuracy. This project provides the
controls needed to reach and verify that target on your data:

1. Structure-aware parsing and heading parents prevent unrelated sections from being mixed.
2. Semantic children improve recall for natural-language questions.
3. Hybrid dense + BM25 retrieval covers both intent and exact technical terms/error codes.
4. The default OCI Rerank 4 configuration reorders the best 10 of 20 retrieved candidates
   before answer generation, then retains up to 5 parent contexts.
5. When reranking is enabled, low rerank scores cause an abstention instead of an unsupported
   answer.
6. `prodrag-eval` reports document-level recall and precision, and fails CI when configured
   recall, precision, hit-rate, or abstention thresholds are missed.

Build an evaluation set from real support questions. Include answerable questions, exact
error codes, acronyms, version-specific questions, and unanswerable questions. Start with at
least 50–100 labeled questions even when the document corpus is small.

## Local setup (PowerShell)

Requirements: Python 3.13, `uv`, and OCI credentials and policies for Generative AI. Docker
Desktop is required only for the API and asynchronous-worker setup.

Choose one of these local setups after copying `.env.example` to `.env` and filling in the OCI
configuration. Keep API keys secret. Development can use the legacy global keys. Production
requires tenant-bound admin and query key maps whose values contain at least 32 characters:

```dotenv
RAG_TENANT_ADMIN_API_KEYS={"default":"replace-with-a-32-character-admin-key"}
RAG_TENANT_QUERY_API_KEYS={"default":"replace-with-a-32-character-query-key"}
```

Each key authorizes only its mapped tenant, even if a request supplies a different `tenant_id`.
Use different values for the admin and query roles. Put the maps in a secret manager rather than
committing them to source control.

### Option A: embedded index for synchronous CLI testing

This option does not require Docker or Redis. Set `QDRANT_PATH=./data/qdrant` in `.env`; it takes
precedence over `QDRANT_URL` and uses exact in-process search.

```powershell
Set-Location C:\Users\AJay\Documents\ogent\refernce\ocigeniworkshop\prodrag
Copy-Item .env.example .env
# Edit .env: OCI IDs, region, profile, API keys, and QDRANT_PATH=./data/qdrant.
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv sync
```

### Option B: API and asynchronous ingestion worker

This option requires Redis and a Qdrant server. Leave `QDRANT_PATH=` empty in `.env`, then start
the local dependencies with Docker Compose. Production deployments should use a managed or
self-hosted Qdrant server configured through `QDRANT_URL`.

```powershell
Set-Location C:\Users\AJay\Documents\ogent\refernce\ocigeniworkshop\prodrag
Copy-Item .env.example .env
# Edit .env with OCI IDs, region, profile, and strong API keys. Keep QDRANT_PATH empty.
docker compose up -d
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv sync
```

The Markdown and HTML demo corpus needs no local model download. PDF ingestion defaults to native
text extraction with OCR and table reconstruction disabled; this is faster and more reliable for
digitally generated technical manuals. For scanned PDFs, set `RAG_PDF_OCR_ENABLED=true` and
`RAG_PDF_FORCE_BACKEND_TEXT=false`. Enable `RAG_PDF_TABLE_STRUCTURE_ENABLED=true` only when table
layout is important to retrieval. OCR, table reconstruction, DOCX, and PPTX processing may download
model assets. Bake or prefetch those assets in the production image so workers do not need internet
access at startup.

`RAG_MAX_PDF_PAGES=200` limits each PDF ingestion job to 200 pages. Documents above the limit are
rejected; split them into smaller, versioned documents before ingestion.

Production also requires upload scanning. Configure a command as a JSON argument list; `{path}` is
replaced with the temporary upload path. For example, with ClamAV installed:

```dotenv
RAG_UPLOAD_SCAN_COMMAND=["clamscan","--no-summary","{path}"]
```

If an upstream gateway already scans every upload, set `RAG_UPLOADS_PREVALIDATED=true` instead.
Successful uploads and files whose retries are exhausted are removed from the temporary upload
directory.

Start the API and worker in separate terminals:

```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv run uvicorn prodrag.api:app --host 0.0.0.0 --port 8000
```

```powershell
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv run dramatiq prodrag.worker --processes 1 --threads 2
```

The import paths in those two commands are lowercase: `prodrag.api:app` and
`prodrag.worker`. On a case-sensitive host, use the lowercase spelling exactly.

For an initial 10–30 document bootstrap, synchronous CLI ingestion is simpler:

```powershell
uv run prodrag ingest C:\path\to\technical-docs --tenant default --product router --version 1.0
uv run prodrag query "How do I rotate the API token?" --product router --version 1.0
```

The command name is lowercase `prodrag` on case-sensitive hosts.

## Prompt engineering and safety controls

The service uses separate prompts for triage and answer generation. The triage prompt treats the
customer question as untrusted data, asks for one schema-checked JSON decision, and instructs the
model never to repeat sensitive values. It classifies category, sensitive-data types, policy-review
status, and confidence. Invalid output, low triage confidence, and detected sensitive data fail
closed to `customer_support` before retrieval.

The answer prompt accepts facts only from the supplied retrieved sections. It labels those sections
as untrusted data, requires source markers such as `[S1]`, and requires `NOT_FOUND` when the
evidence is insufficient. The application rejects answers without a valid source marker. Retrieval
confidence is evaluated before the answer prompt runs, so a low-confidence result is routed to
human review instead of asking the model to decide whether its own evidence is adequate.

Policy-review tickets, including refunds, charge disputes, permanent or contract-specific capacity
changes, account-specific actions, and high-impact integration failures, may receive a grounded
draft but remain marked for human review.

## OCI cost estimate for 1,000 queries

Under the documented fully answered-query assumptions, OCI model usage is estimated at **USD 3.40
per 1,000 queries**. This includes safety triage, one query embedding, one rerank search unit, and
grounded answer generation. It excludes ingestion, Qdrant and Redis infrastructure, storage,
retries, taxes, networking, and support plans.

Sensitive tickets skip embedding, reranking, and answer generation; low-confidence tickets skip
answer generation. Actual blended cost can therefore be lower or higher than this estimate,
depending on traffic and document size. Oracle pricing, region, taxes, and contract discounts can
change; validate the current SKUs before budgeting. See [OCI cost estimate](docs/cost-estimate.md)
for rates and formulas.

## HTTP API

Upload returns `202 Accepted`; poll the returned job ID until it succeeds.

```powershell
$headers = @{ 'X-Admin-Key' = '<tenant-admin-key>' }
$form = @{
  file = Get-Item 'C:\path\to\guide.pdf'
  document_id = 'authentication-guide'
  tenant_id = 'default'
  product = 'router'
  version = '1.0'
}
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/documents -Headers $headers -Form $form
```

Save the upload response and poll until its `state` is `succeeded` or `failed`:

```powershell
$upload = Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/documents -Headers $headers -Form $form
do {
  Start-Sleep -Seconds 2
  $job = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/v1/ingestions/$($upload.job_id)" -Headers $headers
  $job
} while ($job.state -in 'queued', 'running', 'retrying')
```

```powershell
$headers = @{ 'X-API-Key' = '<tenant-query-key>' }
$body = @{
  question = 'How do I rotate an API token?'
  tenant_id = 'default'
  product = 'router'
  version = '1.0'
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/query -Headers $headers -ContentType 'application/json' -Body $body
```

Endpoints:

- `POST /v1/documents` — authenticated asynchronous ingestion
- `GET /v1/ingestions/{job_id}` — ingestion status
- `DELETE /v1/documents/{document_id}?tenant_id={tenant_id}` — authenticated deletion; the
  `tenant_id` query parameter defaults to `default`
- `POST /v1/query` — authenticated retrieval and grounded answer
- `GET /healthz` and `GET /readyz` — liveness and dependency readiness
- `GET /metrics` — Prometheus request counters and latency histogram buckets for p95 alerts

## Retrieval evaluation

Create JSONL rows using the schema in `eval/example.jsonl`. This command gates retrieval quality:

```powershell
uv run prodrag-eval .\eval\customer-questions.jsonl `
  --min-recall 0.95 --min-precision 0.30 --min-hit-rate 0.95
```

Use the lowercase command `prodrag-eval` on case-sensitive hosts. The command exits nonzero
when a configured gate fails. `mean_recall` is the fraction of expected document IDs returned;
`mean_precision` is the fraction of unique returned document IDs that are expected, averaged over
answerable questions. `empty_retrieval_rate` reports how often unanswerable questions retrieve no
context, but it is not an answer-level abstention measurement. Precision gating is disabled by
default (`--min-precision 0`) so teams can set a target that matches the number of expected sources
per question.

The checked-in `eval/salesforce-streaming-api.jsonl` dataset contains golden questions, expected
answers for human review, expected document IDs for automated recall/precision scoring, and negative
questions for abstention testing against the ingested Streaming API guide.

Use `--end-to-end` to call triage, retrieval, answer generation, and citation validation. This mode
measures actual abstention, answerability, citation coverage, and whether citations point to an
expected document:

```powershell
uv run prodrag-eval .\eval\customer-questions.jsonl --end-to-end `
  --min-recall 0.95 --min-precision 0.30 --min-hit-rate 0.95 `
  --min-answerability 0.95 --min-citation-hit-rate 0.95 --min-abstention 0.90
```

The end-to-end run makes OCI model calls and therefore incurs usage charges. Tune in this order:
metadata labels/filters, parsing errors, parent size, semantic threshold, candidate count,
reranker choice, and only then the chat prompt/model.

Add optional `expected_category` and `expected_human_review` fields to JSONL rows to measure triage
and routing accuracy. Those metrics return `null` when the dataset contains no corresponding labels.
Evaluation output also includes `retrieval_p95_ms` and, in end-to-end mode,
`end_to_end_p95_ms`.

## Production checklist

- Run Qdrant and Redis on persistent encrypted volumes with backups and resource limits.
- Keep Qdrant/Redis on a private network; the compose file binds them to loopback for local use.
- Put the API behind TLS and rate limits. Tenant-bound service keys enforce application-level
  isolation; use your identity-aware gateway when end-user identity or OAuth is required.
- Store API keys and OCI configuration in your secret manager; never commit `.env`.
- Configure `RAG_UPLOAD_SCAN_COMMAND`, or attest to upstream scanning with
  `RAG_UPLOADS_PREVALIDATED=true`. Archive source documents outside this temporary upload path if
  retention policy requires it.
- Run at least two API replicas. Scale ingestion workers separately; start with one worker for
  this small corpus to avoid unnecessary OCI bursts.
- Alert on failed/retrying jobs, retrieval abstention rate, p95 latency, OCI errors, and Qdrant
  availability. Do not log document bodies, prompts, credentials, or customer PII.
- Scrape `/metrics` from every API replica and collect the JSON request logs. Configure
  `RAG_QUERY_TIMEOUT_SECONDS` and `RAG_MODEL_RETRY_ATTEMPTS` for the deployment latency budget.
- Version collections when the dense or sparse embedding configuration changes. Never mix vectors
  produced by different embedding or BM25 configurations.
- Re-run the labeled evaluation gate for every document, chunking, embedding, or prompt change.
- Connect responses with `routing_destination: customer_support` to the ticketing platform used
  by the support team. The reference service makes the routing decision but does not create an
  external Zendesk, ServiceNow, or Salesforce ticket by itself.
