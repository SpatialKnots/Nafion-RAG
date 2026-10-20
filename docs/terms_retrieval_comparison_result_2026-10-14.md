# TAC + Terms comparison: development replay result

Date: 2026-10-14. Protocol: [v0.1, fixed before evaluation](terms_retrieval_comparison_protocol_2026-10-14.md).

## Finding

The tested **offline adapter does not improve the previous retrieval baseline**.
Do not deploy this equal-weight TAC/Terms fusion as a search improvement. This
finding concerns the explicit adapter, the known 33-document development corpus
and its existing judgments; it does not establish that Terms cannot help another
workflow or a differently evaluated retrieval design.

Production is the saved `hybrid_cross_lingual` response from 2026-10-12. Both arms
use the same source snapshot, 619 chunks, 46 questions (38 answerable, 8 negative),
and the same current evaluator. Every saved production result remains in the
common candidate pool, whose size ranges from 20 to 24. The baseline top-ten is
preserved as the common-pool prefix. No historical/current baseline metric drift
was detected. The active stage17 Terms snapshot remains
`e1bb627bed090e77ec88695e239f735b68338804ec9e99cb2aedf6708f1caa74`.

| Arm | Passed | Top-one hits / 38 | Article recall | Judged chunk recall | MRR | nDCG |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previous production | 46/46 | 34 | 100% | 100% | 0.9342 | 0.8808 |
| TAC soft + full text | 45/46 | 34 | 97.37% | 100% | 0.9193 | 0.8633 |
| TAC + typed Terms soft + full text | 45/46 | 30 | 97.37% | 100% | 0.8461 | 0.8075 |
| TAC + all inventory Terms soft + full text | 45/46 | 31 | 97.37% | 100% | 0.8665 | 0.8234 |
| TAC shortlist + full-text rescue | 45/46 | 34 | 97.37% | 100% | 0.9193 | 0.8633 |
| TAC only, five article summaries | 42/46 | 31 | 94.74% | 76.92% | 0.8728 | 0.8247 |

All arms passed the eight negative-case adequacy checks and retained complete
source traces. This is not an evaluation of generated answers. The TAC-only row
uses article summaries rather than original chunks; its chunk metric is lexical
coverage under the existing evaluator and must not be read as equivalent evidence.

Against production, typed Terms improved the first relevant rank on two questions,
worsened it on eight and left it unchanged on 28 answerable questions. Including
untyped Terms performed better than filtering to typed Terms on the aggregate MRR
in this run, but still below production. Type coverage does not imply retrieval
quality. Judged hit fractions are incomplete-judgment diagnostics, not true precision.

## Source-bound cases

**Supplementary material regression:**
`qext025_sanginov_sup_dielectric_constant`, query
`M05-2X TZVP SMD dielectric constant quantum chemical calculations`.
Production returned the target supplement at rank 3, source pages 21–23. TAC/Terms
arms displaced it outside top-ten. Its TAC profile contains only the title on
page 1: Abstract and Conclusions are `not_detected`. It has no typed query signal
in the saved pool. The source remains present in the common pool; loss occurs
during ranking/truncation, not candidate deletion or PDF modification.

Source IDs: article `7bc8d131-9060-4484-bf72-9749468b833b`, chunk
`ff8e74f1-4d1f-4643-90b0-f6f3f006ba2f`, original SHA256
`72facadf39cdb1ddf220320ea2ccbb7cc3c5bcdb7fa2e4c8907b0e44841dbd27`.
The selected text begins `D. Influence of dielectric constant value on the results
of quantum-chemical` followed by `calculations (M05-2X/TZVP + SMD theory level)`.
The complete unchanged text is expandable in the comparison HTML.

**Additional Terms ranking regression:** `qext011_kim_sans_dispersion_particles`.
The first judged Kim result moved from rank 1 in production/TAC soft to rank 6
with typed Terms. The added channel promotes Welch candidates containing
`nafion` and `sans modeling`; the two Welch uploads occupy separate article
scopes. Lexical matches are not equivalent to the intended particle/gelation
relationship. This is an observed ranking mechanism, not a new scientific annotation.

**Improvement:** `qext016_cho_solvent_casting_condition` moved from rank 2 to rank 1
with typed Terms. The target source supplies `electrochemical properties`,
`solvent`, `nafion`, `casting` and `blend membrane`. The other improved query is
`qext003_ma_table_solvent_set`. No outcome-dependent tuning followed these results.

Known duplicate works are grouped by DOI, otherwise exact selected-page-text hash,
in an additional diagnostic: 33 documents produce 32 such groups. The mean
first-relevant-work reciprocal rank remains lower for typed Terms: 0.8618 versus
0.9474 for production. Repeated questions about the same works remain development
observations, not independent samples or a significance test.

## Artifacts and verification

`output/terms_benchmark_20261014/replay_v01/` contains the HTML comparison,
`report.json`, a copy of the complete eight-column stage17 TAC table for all
33 documents, the pre-evaluation manifest/protocol, and frozen adapter source.
The source script is `scripts/terms_retrieval_compare.py`; it requires explicit
input paths and a fresh output directory. Input/code/PDF hashes bind the run.
The original PDFs, production retrieval, database schemas and active Terms result
were not modified. The JSON/code watcher was not reconfigured.

Changed: added a separate frozen replay adapter, protocol, development results and
engineering tests. No production Terms search channel was enabled.

Tests run: six adapter tests passed (pool preservation, empty-channel rollback,
exact page/layer/quote matching, exclusion of unresolved types, repeated-mention
coverage, source corruption rejection and evidence preservation). Ruff passed
for the new script and tests. Real replay validated the frozen inputs, reproduced
context/classification outputs and checked source PDF hashes. Full app pytest and
live latency/model benchmarks were not run for this isolated experiment.

A second run reproduced `report.json`, comparison HTML, complete TAC HTML,
pre-evaluation manifest, protocol and frozen adapter source byte-for-byte.
Static verification found 46 comparison questions, all 33 TAC document rows,
the eight agreed TAC columns and 113 existing local-link targets. All original
baseline candidates were preserved and the active snapshot ID remained unchanged.
Browser verification showed the six metric rows, search narrowing to the one
supplementary regression, the exact selected page-21 heading inside the expanded
baseline evidence, and reset to all 46 questions. A global text selector timed out
on the large HTML; a scoped row/cell locator successfully opened the same evidence.
The screenshot and browser observations are stored beside the replay artifacts.

Limitations: known development corpus, incomplete judgments, no independent gold,
no user-time measurement, no role/origin/relation-correctness evaluation. The
lexical/RRF adapter is new experimental code; results do not describe production
TAC/Terms retrieval because that integration remains unimplemented.

Verdict: the predeclared acceptance gate failed both recall preservation and
ranking gain. Keep production retrieval; retain Terms for evidence inspection.
Future search work needs protection for unsupported/supplementary documents,
duplicate-aware ranking and query-specific context signals, followed by evaluation
on new documents. Do not silently retune this result into a successful benchmark.
