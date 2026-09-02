# Phase 3 Retrieval Design Gate

This document is a design gate for semantic or hybrid retrieval in ARIADNE.
It is not an implementation record. At the time this plan is written, the
verified retrieval method remains the Phase 2 exact baseline, `exact_ilike`.

No embeddings, semantic search, hybrid search, or RAG answer generation should be
reported as implemented until source code, migrations, tests, and evaluation
reports prove it.

## Current Baseline

The current baseline is exact chunk retrieval over indexed article chunks:

- method: `exact_ilike`
- corpus manifest: `docs/corpus_manifest.json`
- evaluation set: `docs/evaluation_questions.yaml`
- expected evaluation size from the current handoff: 24 questions
- expected current top-k baseline from the current handoff:
  - `passed`: 24
  - `failed`: 0
  - `top_1_passed`: 18
  - `recall_at_k`: 1.0
  - `mean_rank`: 1.4583333333333333

These values are a comparison target, not a guarantee for future local runs.
Every Phase 3 change must run the evaluation locally and compare against the
newly generated exact baseline report.

## Goals

Phase 3 should improve retrieval quality for scientific literature inspection
while preserving source traceability.

Required outcomes:

- keep exact retrieval available as a reproducible baseline;
- add semantic or hybrid retrieval only behind an explicit method selection;
- preserve article, chunk, page range, source type, text layer, and snippet
  evidence for every returned result;
- make retrieval evaluation compare exact, semantic, and hybrid methods with
  the same gold questions;
- provide rollback paths that do not require re-ingesting immutable PDFs.

Non-goals for this gate:

- no automatic answer generation;
- no external metadata lookup;
- no mutation of original PDFs;
- no silent change to existing exact retrieval scoring;
- no schema or output changes without tests and documentation.

## Candidate Retrieval Methods

### Option A: Local Semantic Retrieval

Add embeddings for chunks and retrieve by vector similarity.

Expected behavior:

- embed each chunk text with a selected local embedding model;
- store one embedding per chunk;
- search by embedding the query and ranking by vector distance;
- return the same evidence fields as exact retrieval.

Strengths:

- can find conceptually related text when exact words differ;
- useful for broad or paraphrased scientific queries.

Risks:

- model choice affects reproducibility;
- CPU-only indexing and search may be slow;
- scientific terminology and Russian/English mixed queries require explicit
  model validation;
- semantic rank may return plausible but weakly evidenced chunks.

### Option B: Hybrid Retrieval

Combine exact and semantic signals into a single ranked result set.

Expected behavior:

- run exact retrieval and semantic retrieval independently;
- combine ranks with a documented method, such as reciprocal rank fusion;
- preserve per-method scores in diagnostics;
- return a final rank plus method evidence.

Strengths:

- exact matches for DOI, table terms, names, and formulas remain strong;
- semantic retrieval can improve broad or paraphrased queries;
- easier rollback because exact retrieval remains unchanged.

Risks:

- fusion weights can hide regressions if not reported clearly;
- score normalization across methods is non-trivial;
- evaluation must show both top-k and top-1 effects.

### Option C: Postgres Full-Text Plus Semantic Hybrid

Add PostgreSQL full-text search as a stronger lexical baseline, then combine it
with semantic retrieval.

Strengths:

- uses the existing PostgreSQL dependency;
- improves lexical ranking without requiring embeddings first;
- can support Russian/English dictionaries if configured deliberately.

Risks:

- dictionary and tokenization behavior must be documented;
- schema changes are required for generated text search vectors or indexes;
- it may still miss paraphrased scientific queries.

## Recommended Phase 3 Path

Implement in stages, with a stop/go decision after each stage:

1. Add retrieval method plumbing and evaluation support for multiple methods.
2. Add a lexical comparison method if needed, without removing `exact_ilike`.
3. Add local semantic retrieval for chunks.
4. Add hybrid ranking after exact and semantic methods are independently
   measurable.
5. Promote a default method only after evaluation shows a clear benefit and no
   traceability regression.

The preferred first implementation target is hybrid-ready method plumbing plus
semantic retrieval behind an explicit CLI/API method flag. It should not become
the default until evaluation reports justify the change.

## Dependencies

Dependency decisions must be made before implementation.

Candidate local embedding dependencies:

- `sentence-transformers`: common local embedding interface, but adds PyTorch
  and model download/runtime weight concerns.
- `transformers` plus ONNX/runtime-specific model: more controlled deployment,
  but more implementation work.
- `fastembed`: lighter local embedding workflow, but model selection and
  multilingual/scientific suitability must be verified.

Candidate vector storage dependencies:

- `pgvector`: keeps vectors in PostgreSQL and makes rollback/migrations clear,
  but requires a PostgreSQL extension installed locally.
- local FAISS index: fast local search and no database extension, but index
  files must be versioned as rebuildable artifacts and synchronized with chunks.
- pure Python/Numpy brute-force: acceptable only for a small corpus prototype,
  not a scalable default.

Current storage decision:

- `pgvector` is not available in the current PostgreSQL installation;
- prototype semantic retrieval with a rebuildable local index under
  `data/processed/vector_indexes/`, keeping the source of truth in `chunks`;
- see `docs/phase3_storage_decision.md` for the evidence and rollback path.

No model weights, generated vector indexes, or exported reports should be
committed unless explicitly designed as small tracked fixtures.

## Storage Design

If using `pgvector`, add a migration for a separate embedding table rather than
adding opaque columns directly to `chunks`.

Proposed table:

```text
chunk_embeddings
  id
  chunk_id
  embedding_model
  embedding_dimension
  embedding
  source_text_checksum_sha256
  created_at
```

Required constraints:

- one active embedding per `(chunk_id, embedding_model)`;
- `chunk_id` references `chunks.id` with cascade delete;
- `source_text_checksum_sha256` detects stale embeddings after rechunking or
  text-layer changes.

If using a local vector index, store a manifest next to the index:

```text
data/processed/vector_indexes/<model>/<index files>
data/processed/vector_indexes/<model>/manifest.json
```

The manifest must include:

- embedding model name and version;
- embedding dimension;
- created timestamp;
- corpus manifest checksum or article checksums;
- chunk ids and text checksums;
- index build command;
- software versions.

## API And CLI Surface

The existing exact search behavior should remain available.

Proposed CLI evaluation shape:

```powershell
python -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10 --method exact
python -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10 --method semantic
python -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10 --method hybrid
```

Proposed API query shape:

```text
GET /search?q=...&collection=literature&top_k=10&method=exact
GET /search?q=...&collection=literature&top_k=10&method=semantic
GET /search?q=...&collection=literature&top_k=10&method=hybrid
```

The default should remain exact until the user explicitly approves a different
default.

Each result should continue to include:

- `article_id`;
- `chunk_id`;
- `title`;
- `doi`;
- `page_start`;
- `page_end`;
- `source_type`;
- `snippet`;
- `score`;
- `retrieval_method`.

Hybrid diagnostics should additionally expose component scores or ranks in a
backward-compatible field, for example:

```json
{
  "retrieval_method": "hybrid_rrf",
  "score": 0.052,
  "method_scores": {
    "exact_ilike": 1008.0,
    "semantic": 0.812
  },
  "method_ranks": {
    "exact_ilike": 1,
    "semantic": 4
  }
}
```

## Evaluation Metrics

Use the same gold questions for all methods unless a new question is explicitly
added with evidence.

Required summary metrics:

- `passed`;
- `failed`;
- `top_1_passed`;
- `recall_at_k`;
- `mean_rank`;
- `empty_result_queries`;
- method name;
- top-k value;
- model name when embeddings are used.

Required per-question diagnostics:

- `rank_of_expected`;
- `recall_at_k`;
- `top_1_passed`;
- missing DOI/title/checksum targets;
- missing keywords;
- top result;
- full returned results with evidence fields.

Additional Phase 3 comparison metrics:

- exact vs semantic vs hybrid delta for `top_1_passed`;
- exact vs semantic vs hybrid delta for `mean_rank`;
- list of regressions where exact passed and the candidate method failed;
- list of improvements where exact missed top-1 and the candidate method ranked
  expected evidence first;
- query language/category grouping when available from question notes or ids.

Acceptance should require no loss in top-k PASS unless the user explicitly
accepts a tradeoff for top-1 improvement. Any regression must be inspectable by
article, chunk, page range, and snippet.

## Reproducibility Requirements

Before a Phase 3 implementation is accepted:

- `python -m app.ingestion.cli doctor` must pass or document the local limitation;
- `python -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json`
  must pass;
- exact retrieval evaluation must be run and saved as the baseline report;
- candidate retrieval evaluation must be run and saved as a comparison report;
- `pytest`, `ruff`, and `mypy` must pass for changed code;
- dependency versions and model identifiers must be recorded.

Embedding builds must be deterministic enough to audit:

- same corpus manifest;
- same chunk text checksum;
- same model identifier;
- same embedding dimension;
- same index build command.

## Rollback

Rollback must not require PDF mutation or re-ingestion.

Required rollback mechanisms:

- keep `exact_ilike` implementation unchanged and selectable;
- keep exact retrieval as the default until approved otherwise;
- make embedding tables or local vector indexes rebuildable from existing chunks;
- make migrations reversible where practical;
- allow deleting generated vector indexes under `data/processed/`;
- document commands for dropping/rebuilding embeddings.

If a semantic or hybrid method regresses evaluation, the project should revert
the default method to exact and keep the failed report as diagnostic evidence.

## Implementation Gates

Status as of 2026-08-04: Gates 1-4 are complete. The evaluated hybrid candidate
preserved 24/24 PASS and improved aggregate top-1 and mean rank. Gate 5 retains
`exact` as the default pending explicit approval to change it. See
`docs/phase3_semantic_evaluation.md` and `docs/phase3_hybrid_evaluation.md`.

Gate 1: Method plumbing only

- no embedding dependency yet;
- exact retrieval behavior unchanged;
- evaluation can record method names;
- tests cover method validation and backward compatibility.

Gate 2: Embedding storage/index prototype

- selected dependency documented;
- embeddings built from existing chunks;
- stale embedding detection implemented;
- generated indexes remain ignored unless explicitly approved.

Gate 3: Semantic retrieval

- semantic method returns the same evidence fields as exact retrieval;
- evaluation report includes model metadata;
- exact baseline comparison is produced.

Gate 4: Hybrid retrieval

- exact and semantic component ranks are inspectable;
- fusion method is documented;
- regressions and improvements are listed.

Gate 5: Default-method decision

- user explicitly approves any change away from exact default;
- operations documentation is updated;
- rollback instructions are present.

## Open Decisions

The following decisions should be made before code implementation:

- embedding model and whether multilingual Russian/English support is required
  in the first Phase 3 build;
- embedding dependency/runtime for the rebuildable local index;
- whether to add PostgreSQL full-text search before embeddings;
- whether hybrid ranking should use reciprocal rank fusion or a weighted score;
- acceptance threshold for top-1 improvement versus any top-k regression;
- whether generated embedding artifacts may remain only local or need a tracked
  lightweight manifest.

## Verdict

Phase 3 can proceed only as a measured retrieval experiment against the current
exact baseline. The safest first step is method plumbing and comparison
reporting, followed by a deliberately selected local semantic backend. Hybrid
retrieval should be promoted only after exact and semantic methods are separately
measured and all result evidence remains source-traceable.
