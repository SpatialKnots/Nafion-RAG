# Guarded TAC + Terms v0.2: regression result

Date: 2026-10-14. Scope: the same 33 documents, 619 chunks and 46 known questions
(38 answerable, eight negative). This is a follow-up development/regression
experiment after the v0.1 failure. [Protocol fixed before evaluation](terms_retrieval_guarded_protocol_2026-10-14.md).

## Finding

The v0.2 safeguards recover the original top-ten membership and all 46 pass
outcomes, but **do not improve the original baseline ranking**. The primary
guarded combination has MRR 0.9035 and 32/38 top-one hits, versus 0.9342 and 34/38
for production. The previous v0.1 combination had MRR 0.8461 and 45/46 passes.
Do not select another arm or tune weights after seeing this run to declare a win.

| Arm | Passes | Top-one / 38 | MRR | nDCG |
| --- | ---: | ---: | ---: | ---: |
| Previous production | 46/46 | 34 | 0.9342 | 0.8808 |
| TAC RRF within original top-ten | 46/46 | 34 | 0.9248 | 0.8736 |
| Typed Terms RRF within original top-ten | 46/46 | 31 | 0.8702 | 0.8309 |
| Combined RRF within original top-ten | 46/46 | 31 | 0.8693 | 0.8308 |
| Guarded TAC | 46/46 | 33 | 0.9211 | 0.8711 |
| Guarded typed Terms | 46/46 | 33 | 0.9167 | 0.8676 |
| Guarded TAC + typed Terms, primary candidate | 46/46 | 32 | 0.9035 | 0.8579 |

All seven arms preserve each query's original ten distinct chunk IDs, complete
source traces, 100% article/judged-chunk recall under the existing judgments,
and all eight negative-case adequacy outcomes. No production baseline metric
drift was detected. Preserving membership prevents source loss, not rank errors.
MRR and nDCG use incomplete existing judgments; related unjudged papers cannot
automatically be called scientifically irrelevant.

## Implemented changes

`scripts/terms_retrieval_guarded.py` is a separate offline adapter; production
retrieval and the stage17 automatic Terms result remain unchanged.

- Only reorder the original top-ten, with membership assertions for every arm.
- Compute token and full-phrase IDF per declared work group, counting duplicate
  uploads once. Known DOI groups and otherwise exact selected-text hashes are
  heuristics, not inferred concept or sample equivalence.
- A single generic Term supplies no guarded Terms boost. Require an exact
  multi-token phrase in a query variant, a proposed type on that exact use, a
  reviewed context and its complete exact containing clause inside the chunk.
- TAC scores apply to exact reviewed contexts inside the result chunk. No
  article-level score is transferred to unrelated body fragments.
- Adjacent swaps require containment of the defender's original-query token
  matches and a strict improvement without worsening another active signal.
- Results lacking reviewed Abstract/Conclusions stay at their original slots.
  Changed adequacy decisions roll back the query's guarded order.
- The grouped view preserves all chunks, article IDs and PDF paths inside known
  work groups. Four query views contain a group spanning both Welch uploads.

No classifications, relation claims, source layers, extraction boundaries or
metadata were silently repaired. Context support remains lexical, not entailment.

## Observed cases

**Recovered supplementary source:**
`qext025_sanginov_sup_dielectric_constant`. The original Sanginov supplement on
pages 21–23 stays at judged rank 3 in all guarded arms. In membership-only TAC
and combined RRF it remains present but moves to rank 6. The distinction explains
why preserving top-ten alone is insufficient to restore original ordering.
The supplement has no reviewed A/C context; its original slots are locked.

**Remaining Terms regression:** `qext021_sanginov_li_nafion_ec_sl`.
The first judged Sanginov article moves from rank 1 to rank 3 in guarded Terms
and the combination. Two first-page Istomina fragments are promoted using
`ethylene carbonate` and the exact clause describing Li-Nafion, EC and SL.
That clause is source-supported, but its lexical relevance does not establish
that the question's intended target is the same work or experiment. Under the
existing question judgment the Sanginov target is the expected one; the alternate
paper's broader relevance is not independently adjudicated in this experiment.

**Remaining TAC regression:** `qext033_chernyuk_2023_water_caps_ru`.
A Chernyuk 2024 first-page fragment rises above the judged Chernyuk 2023 target,
which moves from rank 1 to rank 2. The 2024 result has a TAC signal and contains
the defender's literal query-token matches; the target's body chunks have no
in-chunk TAC signal. The lexical guards cannot prove the requested relationship.

The guarded combination proposes swaps on 33 queries and preserves original
order with `no_supported_swap` on 13. No real query needed an adequacy-decision
rollback; that branch was exercised by a synthetic engineering test. The primary
candidate has zero first-judged-rank improvements and two regressions; no scientific
or user-time benefit is claimed.

## Artifacts

The canonical stable run is
`output/terms_benchmark_20261014/replay_v02_final/`: comparison HTML, full report,
pre-evaluation input/code/PDF manifest, fixed protocol, frozen adapter source,
and the complete eight-column stage17 TAC table for all 33 documents.
`replay_v02/` preserves the initial candidate separately. Before the final run,
set traversal and floating-point summation were made deterministic with sorted
keys/tokens and `math.fsum`; this was a reproducibility repair, not outcome tuning.
The observed metric summaries did not change. v0.1 artifacts remain separate.

Reproduction command, using a fresh output directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.terms_retrieval_guarded --previous-report output/terms_benchmark_20261014/replay_v01/report.json --protocol docs/terms_retrieval_guarded_protocol_2026-10-14.md --store data/reviews/terms --output output/terms_benchmark_20261014/replay_v02_reproduce
```

Changed: added guarded source-bound scoring, work-counted specificity, original
membership safeguards, explicit fallback and a grouped inspection view.

Tests run: 14 adapter tests passed (six v0.1 plus eight v0.2); Ruff passed for the
new script/tests. Real replay validated all frozen bindings, reproduced the
context/classification output and checked source PDF hashes. Full application
pytest, live index/model calls and latency benchmarks were not run for this
isolated adapter. Further artifact/browser/reproduction checks are recorded
beside the canonical run rather than counted as independent scientific evidence.

A second stable run with `PYTHONHASHSEED=23` reproduced the report, comparison
HTML, complete TAC HTML, manifest, protocol and frozen adapter byte-for-byte.
Independent artifact checks verified all seven arms' exact top-ten membership,
every work group's retained chunk IDs, and 181 derived clause slices against
the selected source-page text and quote hashes. The TAC copy has all 33 rows,
the agreed eight columns and 113 existing local-link targets. The active Terms
snapshot ID remains unchanged; baseline metric drift is zero.

Browser checks loaded seven metric rows and all 46 questions, narrowed search
to the supplementary case, lazily displayed its exact page-21 text, showed the
two Welch article IDs within one work group while retaining all ten fragments,
and reset to all questions. No quote was materialized before the first source
button click. Screenshots and browser observations are preserved in the stable
run. Non-focusable keyboard locators could not reliably position the screenshot;
documented browser scrolling and a table-region capture produced the final image.

Limitations: development/regression data, incomplete judgments, lexical clause
boundaries and keyword containment, no scientific relation acceptance, no new
document-level holdout and no measured user-time savings. The known work grouping
does not discover unlabelled duplicates or main-paper/supplement associations.

Verdict: source-loss protection improved relative to v0.1, but the predeclared
ranking-gain condition failed. Keep original production ranking and automatic
Terms inspection. A future experiment needs query-intent/relationship handling
and independently judged document-level cases before enabling this channel.
