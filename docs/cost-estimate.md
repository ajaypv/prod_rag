# OCI cost estimate for 1,000 queries

This estimate uses public Oracle prices checked on August 7, 2026. Prices, regions, taxes, and
contract discounts can change. Confirm the SKUs in the Oracle price list before budgeting.

## Assumptions

Each automatic query uses:

- one short `openai.gpt-oss-120b` safety-triage call, assumed at 350 input and 80 output tokens
- 200 query characters for one Cohere Embed 4 query embedding
- one Cohere Rerank 4 search unit with at most 100 effective documents or chunks, conservatively
  costed below at the published Pro rate
- 4,000 input tokens and 300 output tokens for `openai.gpt-oss-120b`
- local Qdrant and Redis, with their compute and storage costs excluded

Sensitive tickets use only the triage call and stop before embedding, reranking, and answer
generation. Low-confidence tickets use triage, query embedding, and reranking but stop before
answer generation. The calculation below represents 1,000 fully answered queries.

## Published rates used

| Service | Public rate used |
|---|---:|
| Cohere Embed | USD 0.0010 per 10,000 input characters |
| Cohere Rerank 4 Pro | USD 2.50 per 1,000 search units |
| gpt-oss-120b input | USD 0.15 per 1,000,000 tokens |
| gpt-oss-120b output | USD 0.60 per 1,000,000 tokens |

Oracle defines one embedding transaction as one input character. Oracle defines a rerank search
unit as one query returning up to 100 documents or chunks; a document above 500 tokens can count
as multiple chunks. See Oracle's [on-demand pricing method](https://docs.oracle.com/en-us/iaas/Content/generative-ai/pay-on-demand.htm),
[service-unit definition](https://www.oracle.com/sa-ar/contracts/docs/paas_iaas_universal_credits_3940775.pdf?download=false),
and [global price list](https://www.oracle.com/ae-ar/a/ocom/docs/corporate/pricing/oracle-paas-and-iaas-global-price-list.pdf).

## Calculation

| Component | Formula for 1,000 queries | Estimate |
|---|---:|---:|
| Triage input | `350,000 / 1,000,000 x $0.15` | USD 0.05 |
| Triage output | `80,000 / 1,000,000 x $0.60` | USD 0.05 |
| Query embeddings | `200,000 / 10,000 x $0.0010` | USD 0.02 |
| Reranking | `1,000 / 1,000 x $2.50` | USD 2.50 |
| Chat input | `4,000,000 / 1,000,000 x $0.15` | USD 0.60 |
| Chat output | `300,000 / 1,000,000 x $0.60` | USD 0.18 |
| **Estimated OCI total** | | **USD 3.40** |

At 100 queries per day for 30 days, the same assumptions produce about 3,000 queries and USD
10.20 in OCI model charges. This excludes local compute, storage, monitoring, network egress,
support plans, retries, taxes, and ingestion.

Initial document ingestion is small for this corpus, but semantic chunking can embed text more
than once while locating boundaries and then creating final vectors. Measure actual OCI usage
after ingestion instead of estimating it from final document size alone.

## Main cost controls

- Use Rerank 4 Fast only after the labeled evaluation shows acceptable quality; its published
  rate is lower than Pro.
- Reduce retrieved candidates only when recall remains above the evaluation gate.
- Keep parent context within the configured character budget.
- Cache safe, repeated answers only when tenant, product, version, and document revision match.
- Track the percentage of sensitive, low-confidence, and unanswered tickets because they skip
  some or all model calls.
