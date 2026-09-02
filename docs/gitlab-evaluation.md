# GitLab CI/CD RAG evaluation gate

This pipeline runs prodRAG and DeepEval locally on a GitLab runner. It does not log in to or
upload results to Confident AI. OCI remains the configured provider for embeddings, reranking,
answer generation, and the DeepEval judge.

## Gate design

The default-branch pipeline creates `artifacts/reference.json`. A merge-request pipeline downloads
that latest successful reference, rebuilds the candidate index from the same checked-in corpus,
and compares the two reports using `eval/gates.toml`.

```text
default branch -> rag-reference -> reference.json
merge request  -> rag-candidate -> candidate.json
                                  + reference.json -> rag-ab-gate
```

The evaluation jobs use `--report-only` so their JSON artifacts survive quality failures. The
`rag-ab-gate` job is the single blocking decision: it enforces the candidate's absolute thresholds,
allowed regression from the reference, and latency budget. Its nonzero exit blocks the pipeline.

The two reports are comparable only when their dataset and corpus-manifest SHA-256 values match.
Each evaluation gets a new Qdrant service and a new parent SQLite database, so A and B never share
mutable retrieval state.

## GitLab setup

1. Import or mirror this repository into GitLab.
2. Configure a protected runner that can call OCI. Do not expose OCI credentials to fork pipelines
   or untrusted merge requests.
3. Under **Settings > CI/CD > Variables**, configure the prodRAG OCI variables required by the
   selected authentication mode, including `OCI_COMPARTMENT_OCID`, `OCI_REGION`, and
   `OCI_AUTH_TYPE`. For API-key authentication, use protected file variables and a dedicated CI
   principal; never commit the config or private key.
4. Do not define `CONFIDENT_API_KEY`. `scripts/run_ci_evaluation.py` fails closed when that variable
   is present. The pipeline also disables DeepEval telemetry, dotenv loading, the legacy key file,
   and interactive inspection.
5. Run the default-branch pipeline once to seed the `rag-reference` artifact. Merge-request A/B
   jobs cannot run before this successful reference exists.
6. Enable **Pipelines must succeed** in the merge settings. Enable merged-results pipelines if the
   candidate should also include the target branch's latest changes.

GitLab must allow the merge-request job token to download artifacts from the same project. The
baseline fetch uses the job-artifacts API and the merge request's target branch.

## Versioned inputs

- `eval/b2b-saas-ci.jsonl` is the CI golden set. Answerable rows include expected answers,
  document IDs, and required context phrases; negative rows measure answer-level abstention.
- `eval/corpus-manifest.json` fixes the tenant/product/version and SHA-256 of every fictional source
  file under `samples/b2b-saas`.
- `eval/gates.toml` contains reviewed absolute floors, allowed quality drops, and allowed relative
  latency increases.

Any corpus edit must update its manifest checksum. Any evaluation-policy change is therefore visible
and reviewable in the same merge request as the code change.

## Local reproduction

Use a clean output directory. The runner deliberately refuses to reuse a non-empty data directory
unless local recovery is explicitly requested.

```powershell
$env:UV_CACHE_DIR = ".uv-cache"
Remove-Item Env:CONFIDENT_API_KEY -ErrorAction SilentlyContinue
uv sync --frozen --group dev

uv run python .\scripts\run_ci_evaluation.py `
  --variant candidate `
  --git-sha (git rev-parse HEAD) `
  --data-dir .\.ci-data\candidate-local `
  --output .\artifacts\candidate.json
```

If evaluation failed after ingestion completed, reuse that exact local index instead of deleting or
re-ingesting it:

```powershell
uv run python .\scripts\run_ci_evaluation.py `
  --variant candidate `
  --git-sha (git rev-parse HEAD) `
  --data-dir .\.ci-data\candidate-local `
  --reuse-data-dir `
  --output .\artifacts\candidate.json
```

Only use `--reuse-data-dir` when the prior run finished every ingestion step. GitLab jobs continue to
use clean per-job directories and never enable this recovery option. DeepEval uses
`RAG_EVAL_MAX_TOKENS=4000` by default because its faithfulness schemas can require substantially more
structured output than a normal prodRAG answer.

The runner prints a readable sequence for every document and question: ingestion counts, the user
question, expected answer and document IDs, retrieved document IDs, prodRAG's answer and citations,
each DeepEval metric score, and the judge's reason. The complete contexts and structured per-case
results remain in `artifacts/candidate.json`, keeping the console useful without dumping the full
JSON report.

If the corpus is already indexed, the same readable mode is available directly:

```powershell
uv run prodrag-eval .\eval\b2b-saas-ci.jsonl `
  --end-to-end --deepeval --verbose --no-print-report `
  --output .\artifacts\candidate.json
```

Compare two completed local reports:

```powershell
uv run prodrag-compare `
  --baseline .\artifacts\baseline.json `
  --candidate .\artifacts\candidate.json `
  --policy .\eval\gates.toml `
  --output .\artifacts\comparison.json `
  --junit-output .\artifacts\comparison.xml
```

## Calibrating the gate

The checked-in thresholds are an initial release policy, not a claim that the current pipeline has
already achieved them. Before making the GitLab pipeline mandatory, inspect the first reference run,
review every failing and borderline case, and adjust only with documented evidence. Keep a separate
held-out set for release confirmation when real anonymized support questions become available.

Run the small checked-in set for merge requests. Run a larger representative dataset on a schedule
and before production deployment. LLM judge results can vary even at temperature zero, so investigate
small changes near a threshold rather than weakening the gate automatically.

## References

- [DeepEval unit testing in CI/CD](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd)
- [DeepEval local result files](https://deepeval.com/docs/evaluation-flags-and-configs)
- [DeepEval data privacy and telemetry opt-out](https://deepeval.com/docs/data-privacy)
- [GitLab merge request pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/)
- [GitLab job artifacts](https://docs.gitlab.com/ci/jobs/job_artifacts/)
- [GitLab JUnit reports](https://docs.gitlab.com/ci/testing/unit_test_reports/)
