# Production readiness status

Status snapshot: 2026-08-11.

## Completed locally

- Qdrant server mode uses HNSW search with `m=16`, `ef_construct=128`, and `hnsw_ef=128`.
- PDF ingestion rejects documents above 200 pages. The selected 82-page Salesforce Streaming API
  guide produced 82 parent sections and 227 chunks. No other downloaded PDF was ingested.
- Query and document embeddings use the same OCI model, version setting, and vector dimension. They
  use the model's distinct `SEARCH_QUERY` and `SEARCH_DOCUMENT` input modes.
- Hybrid dense and local FastEmbed BM25 retrieval runs before OCI reranking. The v2 collection keeps
  these vectors separate from the earlier term-frequency sparse vectors. The answer prompt restricts output to
  retrieved evidence, requires source markers, and returns an abstention when evidence is missing.
- `eval/salesforce-streaming-api.jsonl` contains nine answerable golden questions with expected
  answers and two unanswerable questions.
- The 2026-08-11 `technical_support_v2` evaluation scored recall 1.00, precision 1.00, hit rate
  1.00, and MRR 1.00. The end-to-end evaluation scored answerability, abstention, citation coverage,
  and citation document hit rate at 1.00.
- JSON retrieval traces contain request ID, metadata scope, elapsed time, result count, and scores.
  `/metrics` exports HTTP latency histogram buckets suitable for Prometheus p95 calculations.
- The regression suite passes with 42 tests. Ruff and `git diff --check` pass.

## Blocking production deployment

- The two-second p95 target is not met. With local FastEmbed BM25, retrieval p95 measured 2.66
  seconds in the retrieval-only run and 2.33 seconds during the end-to-end run. End-to-end p95
  measured 3.93 seconds. These are 11-question samples, not a load test. The OCI embedding network
  call remains the main retrieval latency source.
- A tenant- and revision-safe semantic response cache is not implemented. Its cache key and
  invalidation policy must include tenant, product, version, embedding model, and document revision.
- Model token usage, per-query cost, online faithfulness drift, and cost-spike alert rules are not
  exported. Offline golden evaluation now scores answer correctness, completeness, faithfulness,
  and citation correctness, but the repository contains a planning estimate for 1,000 queries,
  not a billing meter.
- The deployment owner must provide persistent encrypted Qdrant and Redis volumes, backups, private
  networking, TLS, rate limits, production secrets, at least two API replicas, metrics scraping,
  alert routing, and ticket-system integration.

Do not label this deployment production-ready until these blockers are closed and a representative
concurrent load test confirms the latency target.
