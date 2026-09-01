# Production readiness status

Status snapshot: 2026-08-18.

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
- Parent sections now have character and conservative-token limits. Every split part repeats its
  heading hierarchy and persists part numbers plus previous/next references. Parent splitting keeps
  ordinary paragraphs, loose lists, tables, and fenced code intact while they fit.
- Retrieval expands a matched parent with complete adjacent parts only within a separate token cap.
  Answer evidence is packed under token and character budgets and stops at Markdown block
  boundaries instead of cutting the last context in the middle of a paragraph.
- The regression suite, Ruff, and `git diff --check` pass locally.

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
- Full parent sections now persist in local SQLite while Qdrant stores child text, vectors, and
  parent references. This is appropriate for the current single-host deployment. Multi-host API or
  worker replicas require a shared `ParentStore` implementation (for example PostgreSQL), plus
  encryption and coordinated backups with Qdrant.
- Markdown tables and fenced code now retain dedicated child boundaries. Parent splitting also keeps
  loose lists atomic while they fit, but lists, blockquotes, admonitions, formulas, and image/chart
  captions do not yet have dedicated *child* policies. Child metadata also does not expose content
  type, code language, row span, or a chunking-strategy version. All hard token limits use the same
  conservative counter because OCI Embed 4 does not expose its tokenizer through the inference API;
  validate limits against real model calls after a tokenizer or official counting endpoint exists.
- The 2026-08-11 quality scores above are a historical baseline. Reingest the corpus and rerun the
  golden retrieval and end-to-end evaluations after these chunking changes before accepting them.

Do not label this deployment production-ready until these blockers are closed and a representative
concurrent load test confirms the latency target.
