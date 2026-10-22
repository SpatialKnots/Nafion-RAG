# Frozen query evidence packet development comparison v0.1

22 October 2026, stage29, `query_evidence_packet_v0.1`.

## Scope and prospective boundaries

Implement an opt-in query evidence packet, preserving source links and unresolved
qualifiers. Compare it with **current** production answer contexts captured
without inference. No runtime route/configuration, retrieval score/selection,
database schema, prior record fields, original PDF or model adapter is changed.
No new paid/model API calls; the stage28 five-call budget remains consumed.

Before live current-context capture, freeze this protocol, new code/tests, the
four exact QUESTIONS in query_packet_run.py, source-only stage28 cases/replies,
all inherited source/code/PDF/output bindings and baseline settings: literature,
hybrid_cross_lingual, top_k=5, claims, auto language. Questions cover conductivity
protocol/equilibration, Istomina DSC, preparation versus measurement atmosphere,
and Nafion/Mars-regolith wording. They are development questions with no newly
invented independent reference labels. Do not tune questions/rules after capture.

Preparation replays old native association responses locally and executes no new
inference or retrieval. Every stage28 case, including unknown and separate control,
is available; source roles remain attached. Association context is not a gold
answer. The local rule accepts no semantic/fuzzy matching or inferred properties.

## Existing-context capture

Use actual answer_question, unchanged retrieval, selection, deduplication and
adequacy gates, with its existing observer and an injected capture-only provider.
The provider raises the explicit PreparationComplete boundary before generation;
it cannot call a model. A genuine gate return stays insufficient_evidence, never
a fabricated model answer. Preserve all four traces and current prompt formatting.
Use a PostgreSQL repeatable-read, read-only transaction. Record selected raw chunks,
exact page/layer/PDF identities, diagnostics and vector-index artifact hashes.
Verify stage28 source regions against the live database/PDFs before capture.
Use existing model caches for retrieval; no model answer or token saving is measured.
Read failures and source/hash drift propagate; do not switch retrieval methods,
manually select chunks or repair sources to obtain a more favorable comparison.

## Additive packet policy

Start with every baseline Evidence object in its original order and unchanged
text/IDs/metadata. Query specificity comes from production selection, not a new
scientific filter. Unknown properties, no_literal_cue, unassigned roles, guards
and clipped tails cannot delete baseline evidence.

An association anchors only when an entire stage28 target sentence occurs exactly
once in selected evidence from the same article, page range and proven text layer.
Derived, missing-layer, repeated or unaligned text remains unbound with diagnostics;
no fuzzy whitespace repair or same-title/other-layer substitution. If a full source
block already occurs once in anchored baseline evidence, keep it there and add
reference offsets. Otherwise attach the complete exact source block with a new,
non-colliding citation ID. Retain every block sentence and old diagnostics, including
sentences the model did not select as property/method/condition evidence. Preserve
model proposals as unreviewed and origin/applicability as unverified.

Local provenance includes article, original/selected PDF hashes and paths, page,
text layer/ID, absolute source offsets and inherited source_type. The candidate
wire contains evidence text and source IDs, without local PDF paths. Exact offsets
into the corresponding supplied evidence resolve every sentence reference.
This is a proposed wire representation, not a supported new provider/runtime schema.

Do not claim compression: the first version preserves all baseline text and may
add context/metadata. Report raw character counts and serialized bytes separately;
neither is a token-cost metric. A 100000-byte ceiling marks over_budget and retains
the full local artifact; no silent truncation. Check complete registered pages
in baseline formatted prompts and candidate evidence text. Incomplete registries,
complete-page retention, budget overflow or a baseline insufficiency gate prevent
candidate network eligibility. This technical flag is not scientific acceptance
or authorization for inference; this stage sends no candidate to a model.

## Verification and review

Constructed tests cover full baseline preservation, exact Unicode/offset binding,
unknown/guarded/clipped context closure, incomplete-block attachment, ambiguous
occurrences, foreign layers/articles/pages, derived evidence, citation collisions,
malformed/duplicate source targets, wire/path separation, byte-budget diagnostics,
no-inference capture boundaries, frozen questions/code/source/capture failures,
exclusive output, deterministic exports and escaped read-only searchable HTML.
Run targeted/full regression and Ruff/mypy, repeated real offline exports, PDF/
index/input hash checks, full evidence and sentence-offset checks. No scientific
precision/recall, claimed answer quality, human time saving or independent study
is established. Browser acceptance requires actual rendering; distinguish static
checks. Independent annotation is separate from the user's Terms workflow.

Deliver HTML/JSON for all four queries, including rejected/unmatched/gated cases,
current baseline traces, full new packets, old uncertainty, exact original-PDF links,
version and frozen input manifests. Save source/dependency snapshot separately.
