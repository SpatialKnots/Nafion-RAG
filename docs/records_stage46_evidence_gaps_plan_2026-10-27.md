# Plan: Stage46 evidence-gap audit

Date: 2026-10-27, Asia/Yekaterinburg.
Interview decisions settled with the user; implementation has not started.
Interviewer: this Codex assistant. No Claude model or independent reviewer participated.

## Goal

For the four unchanged development questions inherited from stage45, explain which
evidence is available, which required links remain unsupported, and what exact
source evidence would be needed to resolve each gap. Distinguish a gap in the saved
packet from material found elsewhere in an inspected local PDF and from source
areas not yet checked. Produce a useful next-action list rather than another count
of unresolved occurrences. This stage does not produce scientifically accepted
answers, repair old packets, or increase API admission.

## Agreed decisions

1. The user selected identifying missing evidence as the goal.
2. The user retained the four previous questions; no new questions are added.
3. The Mars-regolith question is an exposed negative control, not a reported
   scientific observation or an assumption that such measurements exist.
4. The user authorized searching full corresponding local PDFs when evidence is
   missing from the saved packet. New findings remain separate from old packets.
5. The existing prohibition on API calls remains active.

## Questions and initial scope

Copy exact question strings and IDs from the frozen stage45 files; verify agreement
with `app/evaluation/query_packet_run.py` rather than rewording evaluation inputs.

| ID | Purpose | Evidence to account for |
| --- | --- | --- |
| conductivity_protocol | Substantive | Conductivity measurement method, sample equilibration/preparation, and the source support connecting each applicable statement to the relevant samples/results |
| dsc_protocol | Substantive | Identity of the requested Istomina 2021 article, DSC measurement conditions and temperature programme, and their actual applicability |
| preparation_atmosphere | Substantive, premise challenge | Whether the source explicitly connects preparation atmosphere to the measurement environment; proximity or preparation alone does not establish this |
| absent_material | Negative control | Whether available evidence supports all distinctive query qualifiers; neither an unsupported premise nor missing lexical matches proves corpus-wide absence |

Baseline: `output/records_stage45_20261027/run_v01`, including all 561 block / 1148
event occurrences, existing selected context, table supplement/catalog, refusals,
and ten historical TAC documents. These are recorded stage45 counts, not new results.

Read-only inspection confirmed that the saved DSC page registry contains Choi,
Yu and the Chernyuk dissertation. It also located
`data/pdf/7519b88c1b0a0bf3_Istomina_2021.pdf`, outside those ten packet documents.
This is a candidate source identified by filename only. Verify its bibliographic
identity from the PDF before attributing anything to the requested article. If
confirmed, register it as an explicit separate source supplement and add it to the
new stage's review scope; do not insert it into historical metadata or packets.
If identity cannot be established, keep the source mismatch unresolved. Do not
silently expand the search to unrelated documents or external services.

## Approach

1. Preflight current source/code bindings, original PDF hashes, dependencies, and
   parent artifacts. Freeze a new prospective protocol, input inventory, search
   rules, and development checks before new audit outcomes. Preserve stale-binding
   failures. As in stage45, an explicitly new source capture is distinct from a
   successful historical runtime replay; never rewrite an old manifest to pass.
2. Build a question-specific evidence checklist from the exact question and
   existing audits. Reuse `context_completeness`, `source_origin`,
   `condition_applicability`, and `sample_identifiers` outputs wherever possible.
   Inventory article/sample/method/condition endpoints and unsupported connecting
   links separately. Do not require irrelevant fields for a particular question.
3. Search the complete text of relevant registered local PDFs, including the
   candidate Istomina document after source registration. Record the actual
   inspected document/page/layer scope and search expressions. Keep extraction
   failures and uninspected visual/OCR regions explicit. Existing extraction/OCR
   behavior remains unchanged; do not run a new OCR process or infer absent content
   from an empty text layer. Inspect decisive pages visually during source QA.
4. Save new exact source fragments and surrounding context in an additive
   source-only supplement. Every finding retains article identity or explicit
   unverified identity, original PDF path/hash, physical page, source type, selected
   text layer/hash, exact text, offsets, and available geometric context. Keep
   citations/reported work, sample ambiguity, and applicability diagnostics.
5. Create a separate versioned gap report for every question. Each entry states
   the required evidence, existing endpoints, unsupported relation or missing
   endpoint, actual search coverage, observed status, and next source check.
   Proposed additive statuses must distinguish `supported_in_packet`,
   `found_outside_packet`, `relation_unresolved`, `not_found_in_inspected_scope`,
   `not_inspected`, and `source_identity_unresolved`. Finding a term is not proving
   a relation. The negative control has its own visible designation and is not
   described as an unfilled real measurement.
6. Export searchable local read-only HTML with four question summaries, prioritized
   gap details, expandable exact quotations, and local PDF links. Blocking gaps
   needed to answer the actual question take priority over optional context.
   Preserve a separate complete TAC table with Title, Authors, Journal, Year,
   Abstract, Conclusions, Terms, and original-file hyperlink. Include all documents
   in the declared new stage scope; retain historical metadata unchanged and mark
   missing/unimplemented fields for any new source explicitly. No writable Terms
   forms or compulsory user classification are introduced.
7. Run the checks below, preserve artifacts in new exclusive output paths, write
   the stage report, update the project plan/status, and make a local commit.

## Acceptance and verification

- All four exact questions are present; the negative control is distinguished.
- Every question has a concrete evidence checklist and gap dispositions. Every
  unresolved gap records what was inspected and what evidence would resolve it.
- Complete-document text-search coverage is enumerated separately from visually
  inspected pages and unresolved graphical/OCR coverage. No general scientific
  absence or completeness claim follows from a finite text search.
- Exact source spans and original PDF hashes verify. New source identity is
  checked before scientific attribution; a wrong article or ambiguous sample
  cannot satisfy a required link.
- Tests cover evidence outside packets, empty/refused scopes, wrong/ambiguous
  article identity, repeated sample IDs, missing links despite co-occurring terms,
  preparation-versus-measurement atmosphere, the negative control, extraction
  gaps, input drift, exclusive outputs, and escaped HTML. These are exposed
  development/constructed checks, not independent scientific gold.
- Targeted affected tests, Ruff, and mypy run as appropriate. Test outcomes and
  counts are reported only after execution. Avoid duplicating old audit logic or
  tests merely to create another stage.
- Repeat exports match byte for byte; all historical parent/wire/metadata files
  and original PDFs remain unchanged. Review HTML search, expandable evidence,
  question coverage, TAC columns, and actual local PDF link behavior.
- No API/model/embedding/retrieval/database calls or downloads. Use the existing
  Python socket/DNS guard before application imports for stage execution, retain
  network evidence, and state the guard's limits. API admission remains unchanged.

## Risks and open questions

- Full PDF text can omit tables, figures, or scanned content; mark coverage gaps.
- The Istomina filename does not establish bibliographic identity or DSC evidence.
- Source-supported endpoints may remain unconnected. Do not convert a row
  candidate or generic method description into sample-specific applicability.
- Future external model review is unavailable under the current API prohibition.
  No review verdict, accuracy score, or independent scientific acceptance exists.
- Implementation details may be refined from local evidence without changing the
  agreed goal, input questions, source boundaries, or scientific evidence rules.

## Out of scope

Runtime integration, new answer generation, external metadata/source lookup, new
OCR or extraction policy, retrieval/scoring/schema changes, automatic scientific
assignment, full-corpus absence claims, independent quality evaluation, resolving
every unknown, forced per-Term decisions, external reviewer/build sessions, and
changes to historical artifacts or original PDFs.
