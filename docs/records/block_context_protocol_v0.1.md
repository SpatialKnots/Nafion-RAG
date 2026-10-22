# Whole source-block preparation v0.1

22 October 2026, stage32, `query_block_context_v0.1`.

Add explicit POST `/answer/prepare/blocks` and GET/POST `/ui/answer/prepare/blocks`.
Retain the complete stage31 preparation payload under `baseline`; do not change
its schema, selection, adequacy threshold, original evidence or stored PDF/text.
Existing generation/preparation endpoints remain separate. Generation and external
request construction stay disabled; `network_ready` is always false.

Use exact registered selected-PDF blocks, existing layout/table proposals and the
stage19 all-block context planner (whole core plus one neighbor, protected groups
expanded to closure; 6000-character context limit diagnoses rather than clips).
Require proven full-page coverage by selected baseline chunks before proposing
block windows. Extraction/layer/PDF mismatch, damaged geometry, unresolved page
structure, visual assets and visual-registry diagnostics retain/defer the page.
Preserve every page/block and every unselected range in local accounting. File,
source, PDF and parsing errors propagate; no fuzzy alignment or arbitrary slices.

Finite query anchors are the unchanged stage30 method/property/material aliases;
article selectors never anchor on bibliography text. No generic stopwords, first
two matches, top-k block cap or hand-picked real paragraphs. Within articles with
any literal anchor, retain all blocks carrying anchor, existing finite condition/
method cues, stage27 negation/reported-work/modality guards or unproven sentence
boundaries. Keep complete source events and all unsupported clauses. Select the
existing planner's full windows whose core contains retained blocks. Other blocks
remain explicitly not selected in the unchanged local baseline; do not claim they
are irrelevant or that finite cues establish complete scientific context.

All candidate text is exact source block text, with original article/PDF/layer/page
identities, absolute offsets/hashes and seed citation IDs. New B citation IDs and
inherited source_type/score metadata are explicit proposals, not new retrieval
scores, stored chunks or independently classified block semantics. Preserve context
states and incomplete boundaries. Recheck necessary query qualifiers on candidates;
old baseline refusals or missing qualifiers cannot become allowances.

Check the entire candidate aggregate for complete registered page text AND union
coverage by source intervals: overlapping windows or whitespace gaps cannot bypass
the full-page rule. A complete page split across proposals still blocks. Keep
deferred/oversize text locally; diagnose the 100000-byte candidate wire ceiling
without clipping. Report actual characters and serialized bytes, not token-cost
savings. `technical_checks_passed` is not scientific sufficiency or API permission.

Freeze questions, inputs, rules, code/tests/protocol and all inherited source/PDF/
index/cache bindings before the real comparison. Use all four exposed stage31
questions unchanged, not independent scientific gold. Current source changes may
invalidate strict historical runners. Verify the complete stage31 source snapshot,
bind changed historical code to matching archived bytes with explicit path/hash
mapping, and leave original manifests/results intact. Never rebind private PDFs,
indices or arbitrary changed inputs to archives. Record historical/current code
separately; new code must also be frozen. Test archive conflicts/drift explicitly.

Run real read-only preparation through the new API with existing offline query
cache, no downloads, index rebuild or model API. Save all four native responses and
UI fragments, compare baseline evidence against stage31 without repairing changes,
and export all cases including deferred/unmatched/failed qualifiers in separate
searchable HTML/JSON with local original-PDF links. Two exports must be identical.
No question/rule/alias/cap tuning after observed outcomes.

Constructed tests cover full baseline preservation; exact block/neighbor/protected
closure; negative/reported/unknown tails; unsupported query anchors; foreign page/
layer/PDF mappings and partial baseline coverage; absent qualifiers and preserved
refusals; individual AND assembled full-page guards; oversize text retention;
explicit API wiring/validation/errors; escaped UI and library scope; immutable
inputs; frozen/archived integrity; exclusive deterministic exports. Run targeted/
full regression, Ruff/mypy, source/cache/native/offset/link QA and source/dependency
snapshot. Static/TestClient checks do not establish browser rendering, independent
scientific precision/recall, experiment identity, paragraph completeness or answer
quality. No mandatory per-Term human resolution is introduced.
