# B2B SaaS support demo

This demo models a fictional SaaS company named NimbusFlow. It receives about 100 daily tickets
about billing, API limits, authentication, and integration failures. The files contain no real
customer data and do not describe a real product.

## What the demo tests

| Area | Sample source | Example question |
|---|---|---|
| Billing | `billing-invoices.md` | When does a failed payment make a workspace read-only? |
| Usage | `plans-usage.md` | Why does today's usage look incomplete? |
| API capacity | `api-rate-limits.md` | What should a client do after HTTP 429? |
| Authentication | `api-authentication.md` | How should an administrator rotate a key? |
| Webhooks | `webhooks.md` | Why does signature verification fail after JSON parsing? |
| Salesforce | `salesforce-integration.md` | How do I recover from `invalid_grant`? |
| Error lookup | `error-codes.md` | What does `INT_503_PROVIDER_UNAVAILABLE` mean? |
| Escalation | `support-escalation.md` | Which tickets require human review? |
| HTML FAQ | `frequently-asked-questions.html` | Where can I download an invoice? |

## Run the scenario

Start from the `prodrag` directory and configure `.env` with working OCI credentials. For a test
that keeps the vector index inside this folder, set `QDRANT_PATH=./data/qdrant`. This embedded
mode does not require Docker or a separate service:

```powershell
Copy-Item .env.example .env
$env:UV_CACHE_DIR = (Join-Path (Get-Location) '.uv-cache')
uv sync
```

The sparse exact-term encoder is implemented locally and does not download a Hugging Face model.
The eight Markdown samples bypass Docling's optional document-model downloads. The HTML FAQ is
parsed locally through Docling and verifies that heading structure and FAQ answers reach the same
semantic chunking pipeline.

To exercise a local Qdrant server with HNSW, leave `QDRANT_PATH` empty, enable
`QDRANT_HNSW_ENABLED=true`, and start Qdrant with `docker compose up -d` instead.

Run all ingestion and query examples:

```powershell
.\scripts\run-b2b-saas-demo.ps1
```

Or ingest all nine documents, including the HTML FAQ, and ask one question manually:

```powershell
uv run prodrag ingest .\samples\b2b-saas `
  --tenant demo --product nimbusflow --version 1.0

uv run prodrag query "What should my client do after HTTP 429?" `
  --tenant demo --product nimbusflow --version 1.0
```

The document IDs are the lowercase file stems, such as `api-rate-limits` and
`salesforce-integration`.

## Response classification

Every query response includes:

- `category`: `billing`, `api_limits`, `integration_error`, `account_security`, or `other`
- `confidence`: `high`, `medium`, or `low`
- `requires_human_review`: the routing decision
- `routing_destination`: `customer_support` for human review, otherwise `null`
- `escalation_reasons`: one or more machine-readable reasons
- `sensitive_data_types`: detected types without captured values

An OCI LLM first returns structured ticket category, sensitive-data types, policy routing, and
classification confidence. Malformed or low-confidence triage fails closed to customer support.
For safe questions, the retrieval grader assigns high confidence when the top rerank score is at
least `0.75`, medium at `0.35`, and low below `0.35`. Both retrieval thresholds are environment
settings. A low-confidence result does not call the answer-generation prompt; it returns a
human-review decision.

Sensitive-data detection uses the OCI triage LLM instead of regular expressions. The classifier
receives the question, returns only data-type labels, and is instructed never to reproduce a
sensitive value. A question containing a credential, private key, payment-card number, government
identifier, personal data, financial data, or health data stops before embeddings, reranking, and
answer generation. The response requests secure human handling.

Policy rules also flag refund requests, duplicate or fraudulent charges, permanent API-limit
changes, contract-specific capacity, and documented high-impact integration failures. These
tickets can receive a grounded draft, but `requires_human_review` remains true.

Example sensitive-data test:

```powershell
uv run prodrag query `
  "My API key is nf_live_DEMOSECRET123456789. Why is authentication failing?" `
  --tenant demo --product nimbusflow --version 1.0
```

Expected routing fields:

```json
{
  "category": "account_security",
  "confidence": "low",
  "requires_human_review": true,
  "routing_destination": "customer_support",
  "answered": false,
  "escalation_reasons": ["sensitive_data"],
  "sensitive_data_types": ["credential"]
}
```

## Prompt strategy

The safety-triage prompt treats the question as untrusted data, distinguishes an actual sensitive
value from a generic mention such as "How do I rotate an API key?", and requires one schema-checked
JSON decision. Invalid output and low classification confidence are routed to customer support.

The answer prompt uses five controls:

1. It permits facts only from retrieved sources.
2. It labels source text as untrusted data, which reduces prompt-injection risk from documents.
3. It requires `[S1]`, `[S2]`, and similar citations for factual claims.
4. It requires the exact `NOT_FOUND` response when evidence is insufficient.
5. The application rejects an answer that lacks a valid source marker.

Retrieval uncertainty is handled before answer generation. The answer prompt is not used when
retrieval is low confidence, and sensitive questions stop after the dedicated triage call. The
retrieval confidence remains score-based; the answer model does not grade its own evidence.

## Evaluate retrieval

The labeled set contains billing, HTML FAQ, rate-limit, authentication, webhook, Salesforce, error-code,
escalation, and unsupported questions:

```powershell
uv run prodrag-eval .\eval\b2b-saas.jsonl `
  --min-recall 0.95 --min-hit-rate 0.95 --min-abstention 0.90
```

Do not treat a passing sample set as proof of production accuracy. Add anonymized real support
questions, review incorrect results, and tune thresholds before enabling automatic replies.

## Edge cases to inspect

- A valid document is retrieved with a low score: the response must request human review.
- The model answers without a source marker: the response must be rejected.
- A question includes a credential or payment-card number: LLM triage must route it before
  retrieval runs.
- A refund request has strong supporting evidence: it still needs policy review.
- A question is outside the corpus: the response must require human review and set
  `routing_destination` to `customer_support`.
- An error code and natural-language description disagree: the cited runbook must control.

See [Cost estimate](cost-estimate.md) for the per-1,000-query assumptions.
