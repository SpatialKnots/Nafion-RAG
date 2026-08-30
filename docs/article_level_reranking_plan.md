# Article-Level Reranking Plan

## Status

This is a detailed implementation plan for the next retrieval-quality step in
Nafion-RAG / ARIADNE. It is a plan, not an implementation record.

The current accepted public method remains `hybrid_cross_lingual`. This plan
does not promote a new default method and does not change ingestion, OCR,
chunking, vector-index storage, answer generation, or PDF access.

## Goal

Improve user-facing ranking for Russian, English, and mixed-language scientific
queries by adding an article-level reranking layer with explicit, inspectable
features.

The target is not merely to keep the expected article somewhere in top-10. The
target is to move the strongest source article into top-3 more often while
preserving current top-10 recall and evidence traceability.

Current evidence from project documents:

- `hybrid_cross_lingual` is the current accepted cross-lingual method.
- The extended cross-lingual set reached 31/31 top-k pass after M3.
- The user-style smoke set reached 24/25 top-k pass, with one known ambiguous
  water-sorption query.
- Ranking remains weak for comfortable top-3 use.
- Broad glossary expansion is explicitly discouraged.

## Non-Goals

- Do not broaden the cross-lingual glossary without corpus-backed evidence.
- Do not replace `hybrid_cross_lingual` with a new public method until it beats
  the current baseline on saved evaluations.
- Do not change exact, semantic, or hybrid scoring formulas.
- Do not silently alter answer evidence-selection policy.
- Do not add an LLM reranker.
- Do not use external metadata lookup.
- Do not mutate original PDFs or stored chunk text.
- Do not claim scientific answer correctness from ranking metrics alone.

## Current Implementation Baseline

The current retrieval stack has these relevant pieces:

- `app.retrieval.search`
  - exposes `exact`, `semantic`, `semantic_multilingual`, `hybrid`, and
    `hybrid_cross_lingual`;
  - returns source-linked `SearchResult` records with article, chunk, page,
    text layer, snippet, full text, method scores, and method ranks;
  - supports filters and grouping.
- `app.retrieval.cross_lingual`
  - detects query language;
  - loads `docs/cross_lingual_glossary.yaml`;
  - builds original and glossary query variants.
- `app.retrieval.query_features`
  - extracts protected tokens, chemical-like tokens, and numeric conditions.
- `app.retrieval.reranking`
  - already computes result-level features;
  - includes protected-token matches, phrase matches, title phrase matches,
    variant matches, cross-language bonus, numeric table bonus, plasticizer
    conductivity bonus, and conflict penalty;
  - computes a lightweight article score from the best two chunk scores.

The next step should evolve this into a clearer article-level layer rather than
adding more ad hoc result-level boosts.

## Proposed Design

### 1. Keep The Retrieval Candidate Set Stable

Use the existing `hybrid_cross_lingual` candidate-generation path. Do not change
which exact, semantic, or multilingual component queries are executed in this
stage.

The reranker should operate on the already gathered candidate window, preserving:

- original component ranks;
- original component scores;
- article id;
- chunk id;
- page range;
- source type;
- text layer;
- PDF and context links.

This keeps rollback simple and isolates ranking changes from retrieval plumbing.

### 2. Add Explicit Article Features

Introduce an article-level feature object, for example:

```text
ArticleRerankFeatures
  article_id
  best_chunk_score
  second_best_chunk_score
  chunk_support_count
  distinct_query_term_coverage
  protected_token_coverage
  phrase_coverage
  title_match_score
  cross_language_source_match
  numeric_condition_coverage
  source_type_support
  property_conflict_penalty
  concept_conflict_penalty
  final_article_score
```

The exact shape can be adjusted during implementation, but every score-affecting
feature must appear in reranking metadata for the top results.

### 3. Separate Article Score From Chunk Score

Compute article score once per article, then order chunks with a two-level key:

```text
1. final_article_score desc
2. best chunk's article-local support desc
3. current feature result score desc
4. best original component rank asc
5. fused score desc
6. original candidate position asc
```

This avoids a single lucky chunk dominating when another article has broader
support across title, multiple chunks, protected terms, and cross-language
variants.

### 4. Use Conservative Features First

Initial feature set:

- protected token match:
  - exact DOI, EC, SL, DMF, DMSO, NMP, DMAc, Li-Nafion, H-Nafion, ions, numeric
    conditions;
  - use boundary-aware matching for short tokens.
- title and bibliographic alignment:
  - query phrase in title;
  - glossary variant phrase in title;
  - article title contains the named method/material/property.
- article-wide term coverage:
  - count distinct non-stopword query terms across all candidate chunks for the
    article;
  - keep English and Russian normalized variants separate in diagnostics.
- chunk support count:
  - count how many candidate chunks from the article have non-trivial feature
    support;
  - cap the contribution to avoid rewarding duplicate chunks too much.
- cross-language source match:
  - EN query retrieving RU article, RU query retrieving EN article, mixed query
    retrieving either only when source evidence terms match.
- numeric/condition support:
  - temperatures, percentages, alpha columns, EC/SL ratios, conductivity-related
    table fragments.
- negative conflict checks:
  - ionic/lithium conductivity query should not be boosted by proton/electronic
    conductivity unless lithium/ionic evidence is also present;
  - water thermodynamics query should distinguish water sorption from broad
    solvent swelling when possible;
  - phase diagram query should prefer EC/SL phase diagram evidence over generic
    EC/SL conductivity evidence.

Do not add broad domain concepts unless a failing query and corpus evidence show
that the concept is needed.

### 5. Keep Ambiguity Visible

The known query:

```text
Which Russian paper discusses Nafion-water sorption thermodynamics?
```

is ambiguous between the Chernyuk dissertation context and the standalone
Chernyuk 2023 paper. The plan should not force a single target by hidden
special-case logic.

Instead:

- keep both documents visible when both are relevant;
- add evaluation variants that distinguish "paper" from "dissertation";
- report article-level near ties in metadata;
- allow the user regression set to accept the dissertation if it is explicitly
  marked as relevant there.

## API And Metadata

No public API shape should be removed.

Add metadata under the existing retrieval metadata, for example:

```json
{
  "reranking": {
    "strategy": "cross_lingual_article_feature_rerank",
    "candidate_count": 50,
    "article_count": 12,
    "feature_version": 1,
    "top_articles": [
      {
        "article_id": "...",
        "title": "...",
        "final_article_score": 18.4,
        "features": {
          "protected_token_coverage": 2,
          "distinct_query_term_coverage": 7,
          "title_match_score": 3,
          "chunk_support_count": 2,
          "property_conflict_penalty": 0
        }
      }
    ]
  }
}
```

The metadata must be diagnostic only. It must not expose local filesystem paths
or unstored source claims.

## Evaluation Plan

### Baselines To Run Before Implementation

Run these before changing ranking:

```powershell
python -m app.ingestion.cli doctor
python -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_cross_lingual_extended.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_cross_lingual.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_regression_extended.yaml --top-k 10 --method hybrid_cross_lingual
```

Save report paths in a short implementation note or final report.

### Metrics

Primary metrics:

- article recall@10;
- MRR;
- top-1 passed;
- top-3 passed or rank <= 3 count;
- mean rank;
- nDCG@10 for graded user regression questions.

Guardrail metrics:

- no drop in article recall@10 on
  `docs/evaluation_questions_cross_lingual_extended.yaml`;
- no drop in article recall@10 on
  `docs/evaluation_questions_user_cross_lingual.yaml`, except for an explicitly
  documented ambiguity relabeling;
- no loss of evidence trace completeness;
- no increase in false-answerable count for unanswerable controls;
- no hidden fallback from semantic/hybrid failures to exact-only behavior.

### Acceptance Thresholds

Accept the change only if all are true:

- extended cross-lingual set remains 31/31 article recall@10;
- user-style cross-lingual set remains at least 24/25 article recall@10, with
  the remaining miss explained or relabeled by evidence;
- user regression extended set has no regression in nDCG@10 or MRR;
- top-3 count improves on at least one user-facing set;
- MRR improves on at least one user-facing set;
- no new top-k failures appear in core same-language questions;
- unit tests, Ruff, and mypy pass.

If top-3 improves but recall drops, reject the change unless the user explicitly
accepts the tradeoff.

## Implementation Steps

### Step 1. Capture Current Baseline

Run doctor, corpus-manifest check, and the three evaluation commands listed
above. Record summaries and report file paths.

If the local corpus or vector index is not ready, stop and fix the environment
before changing ranking.

### Step 2. Add Article Feature Data Structures

In `app/retrieval/reranking.py`, add internal dataclasses for article-level
features and diagnostics.

Keep public `SearchResult` unchanged.

Expected tests:

- empty input returns unchanged empty result;
- one article with one chunk produces deterministic features;
- multiple chunks aggregate into one article feature record;
- metadata contains top article diagnostics.

### Step 3. Implement Article-Level Scoring

Compute article-level score from existing result-level features plus conservative
new coverage features.

Do not tune weights against one query only. Use small integer or simple float
weights and document why each feature exists.

Expected tests:

- article with broader protected-token coverage outranks article with only a
  generic semantic match;
- title match contributes but does not override missing protected scientific
  tokens;
- duplicate chunks from one article are capped;
- original order is stable when feature scores tie.

### Step 4. Add Conflict Penalties

Add narrow negative checks for confirmed confusion classes:

- ionic/lithium vs proton/electronic conductivity;
- EC/SL phase diagram vs EC/SL transport property;
- water sorption thermodynamics vs generic solvent swelling;
- dissertation vs standalone paper only when the query wording explicitly
  distinguishes them.

Expected tests:

- wrong conductivity property is penalized only when the right property is absent;
- phase-diagram query prefers phase-diagram evidence;
- water query does not hide the dissertation when it is genuinely relevant.

### Step 5. Integrate Behind Existing Method

Use the article-level reranker inside `hybrid_cross_lingual` after the current
candidate window is built.

Do not add a new method unless comparison requires an A/B path. If an A/B path
is useful during development, keep it internal or temporary and remove it before
acceptance unless documented.

Expected tests:

- `hybrid_cross_lingual` metadata reports the new strategy;
- search results keep article/chunk/page/source/text-layer fields;
- grouping still works;
- filters still apply before reranking;
- invalid semantic index still returns the existing diagnostic failure.

### Step 6. Run Evaluation And Compare

Run the same three evaluation commands after implementation.

Compare:

- before vs after summaries;
- per-question rank changes;
- regressions where rank worsened from top-3 to outside top-3;
- improvements where rank moved into top-3;
- any top-k loss.

Do not accept the patch if only one hand-picked query improves while aggregate
metrics regress.

### Step 7. Update Documentation

Update the relevant docs after implementation:

- `docs/cross_lingual_m1_evaluation_summary.md`;
- `docs/user_cross_lingual_smoke_summary.md`;
- `docs/operations.md` only if commands, method behavior, or interpretation
  changed.

Add report paths and exact metric summaries. Do not overwrite historical
results without noting the new date.

## Test Plan

Run focused tests first:

```powershell
python -m pytest tests\unit\test_reranking.py tests\unit\test_cross_lingual_retrieval.py tests\unit\test_retrieval_search.py -q
```

Run full checks before acceptance:

```powershell
python -m pytest -q
python -m ruff check .
python -m mypy app
```

Run retrieval evaluations:

```powershell
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_cross_lingual_extended.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_cross_lingual.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_regression_extended.yaml --top-k 10 --method hybrid_cross_lingual
```

Optional UI smoke:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then inspect:

```text
http://127.0.0.1:8000/ui/search
http://127.0.0.1:8000/ui/reports/retrieval-extended
```

## Risks

### Overfitting To The Current 16-Article Corpus

Mitigation: require aggregate metric improvements, keep diagnostics, and avoid
single-query special cases unless they represent a documented corpus-backed
feature.

### Glossary Growth Hiding Ranking Problems

Mitigation: this plan does not rely on broad new glossary entries. Feature
signals should come from the query and stored evidence.

### Strong Article Score Hiding The Best Chunk

Mitigation: order by article first, but still choose article-local best chunks
using result features and original component ranks.

### False Confidence In Generated Answers

Mitigation: treat this as retrieval ranking only. Answer correctness still
depends on evidence adequacy and citation validation.

### Cross-Language Boost Promoting Weak Evidence

Mitigation: cross-language bonus should require term, phrase, protected-token,
or concept support. It should not boost a result merely because the script differs
from the query.

## Rollback

Rollback should be limited to `app/retrieval/reranking.py` and any tests/docs
added for this stage.

No database migration, corpus rebuild, PDF mutation, or vector-index rebuild
should be required unless evaluation commands reveal an unrelated stale index.

The previous `hybrid_cross_lingual` behavior can be restored by removing the
article-level scoring path and returning to the current result-level rerank.

## Acceptance Report Format

When implementation is complete, report:

```text
Changed:
- files and behavior changed

Tests run:
- exact commands and observed results

Limitations:
- unresolved ambiguity, unverified runtime paths, or metric tradeoffs

Verdict:
- accepted/rejected against this plan's thresholds
```

## Verdict

Proceed with article-level reranking only as a measured retrieval experiment
against the current `hybrid_cross_lingual` baseline. The change is acceptable
only if it improves top-3 or MRR without reducing current top-10 recall and
without weakening evidence traceability.
