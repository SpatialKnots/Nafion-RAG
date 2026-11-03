# Offline retrieval ablation, 31 October 2026

Freeze this protocol, the candidate implementation, tests and case recipe before
measurement. Four arms: baseline, ligatures only, RU/EN expansion only, both.
No production changes, model/OAuth calls, new slots, retries or external network.
Use one verified repeatable-read/read-only transaction and rollback; preserve PDFs.

Candidate normalization applies only the existing five fi/fl/ff/ffi/ffl mappings
to SQL matching/scoring text. Query processing, raw returned text, schema, units,
scientific logic, embeddings and original PDFs remain unchanged. No NFKC, casefold,
dehyphenation or stemming is introduced.

Candidate expansion is a finite conjunction of Nafion, dispersion, particle,
morphology/shape and solvent cues in RU/EN. Add two generic RU/EN lexical variants;
never use reference shapes, solvent classes, dimensions, article IDs or answers.
Preserve existing glossary variants. The candidate receives only the raw query.

For each question freeze the baseline variant top-k and feature-window limits,
and reuse them across all four arms. Final top-k remains five. Additional query
channels consume additional search budget; record their count explicitly.
Keep production fusion, reranking, language diversity and evidence selection.
Local semantic responses may be cached and deep-copied between arms because
the original semantic query/model/index/limit is identical. Log cache and actual
local embedding calls. SQL exact tie order has no unique final tie-breaker;
do not hide observed instability as a candidate effect.

Controls: all 24 existing baseline and 46 extended retrieval fixtures, three
verbatim user questions, the exposed morphology question and two predeclared
RU/EN development paraphrases. Existing fixtures/labels are exposed, overlapping
and not independent gold. Preserve all cases and failures; report unique query
count. Evaluate only existing positive article labels with known denominators.
Article-label retention, row changes and adequacy decisions are distinct from
semantic correctness. Do not manufacture negatives or answer-level accuracy.

For the three morphology development questions report all eight pre-existing
exact source windows separately at channel, fusion, feature/top-5 and generation
evidence stages. Source windows are post-hoc diagnostic targets, not an oracle
for retrieval. Preserve Na-form/conditions and the user's original reference.

Require unchanged baseline trace for the original morphology question and exact
channel prefix checks against the frozen earlier expanded capture. Compare all
arms with baseline per case: expected article gains/losses, exact windows gained/
lost, actual evidence/adequacy changes, channel counts and timings. Failure or
regression is a result; no tuning after seeing this run, no automatic rollout.

Replay actual fusion/ranking/evidence against frozen channel outputs with DB
connections forbidden. Reject a deliberately corrupted boundary. Verify source
windows by fresh extraction and all original PDF hashes. Produce JSON and a
searchable HTML review with all scoped works/eight agreed TAC columns and local
PDF links. Browser/full-suite/mypy status must be explicit.

This iteration compares retrieval candidates only. Requested-relation semantic
gate design and independent scientific evaluation remain separate open work.
Do not infer permission for live GigaChat calls. Plan work remains 75% while
the independent evaluation stage remains open.

Operational amendment before the replacement run: capture_v01 was explicitly
interrupted during the fourth case because repeated identical exact queries
were expensive. Its partial artifacts and original runner/protocol snapshots
are preserved and are not a completed comparison. The replacement driver also
deep-copy caches exact responses by normalization arm, query, collection, limit
and filters. SQL results are measured once per identical key; no scientific
candidate, case, limit, threshold or ranking parameter changes. Preserve cache
inventory and compare the already captured complete arms before accepting reuse.
