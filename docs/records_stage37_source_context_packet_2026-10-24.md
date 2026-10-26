# Stage37: lossless source context and co-preservation dependencies

Started 23 October, completed 24 October 2026 after a connection interruption.
Version `source_context_packet_v0.1`.
[Prospective protocol](records/source_context_packet_protocol_v0.1.md),
[preceding metadata audit](records_stage36_metadata_quality_2026-10-23.md),
[source risk preparation](records_stage34_risk_preparation_2026-10-22.md).

Changed:

- Added a separate, opt-in local packet builder and frozen CLI workflow. Each exact
  registered source block is stored once and referenced by its original contexts.
  Identity includes article, original/selected PDF hashes, physical page, layer
  ID/hash and absolute offsets. Identical text at different locations stays distinct.
  Every original context can be reconstructed without whitespace normalization.
- Added transitive co-preservation dependencies for existing protected layout/table
  groups and unresolved initial/terminal boundaries from unchanged source events.
  Interleaved formula blocks stay between split method text and its continuation.
  Existing adjacent pages can connect only within the same article, selected PDF
  and layer kind. Missing pages and unproven mappings remain explicit; no page is
  fetched automatically. Connectivity is not scientific applicability or verified
  paragraph/table reconstruction.
- Preserved complete source events, negation, citations, modality, preparation/
  conditioning/measurement proposals, all visual/structural diagnostics, every old
  refusal, the full local parent and all unselected blocks. Protected captions,
  headers, rows, notes and intervening text cannot be partly retained by closure.
  Necessary query checks, source extraction, chunking, metadata and providers are
  unchanged. Literal and aggregate interval-union full-page guards remain active.
- Added local searchable packet HTML plus a companion TAC table for all ten scoped
  documents, with full historical sections, metadata proposals, original-file links
  and explicit unknowns. Reused stage35 proposals only after verifying their exact
  PDF/text/layer sources. Terms were not recomputed or confirmed.
- No runtime endpoint was wired to the new builder and no existing JSON contract
  changed. The new packet schema is versioned separately. No model request is
  constructed or sent. This is a local source representation, not an API activation.

## Frozen real comparison

All four stage34 requests were retained, including missing qualifiers and the old
insufficient-evidence case. Six source-based development challenges were fixed
before new real packet outcomes. Original Kayumov physical page 3 was visually
inspected: the bottom-left method text continues at the top of the right column,
while selected-text order inserts formula fragments between those pieces.
References and scientific rules were not tuned after outcomes.

| Question | Original windows | Unique source blocks | Unique source-text bytes | Complete-page unions | Wire-proposal bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | 150 | 163 | 39545 | 6 | 5015307 |
| dsc_protocol | 0 | 0 | 0 | 0 | 286251 |
| preparation_atmosphere | 165 | 173 | 34322 | 6 | 958743 |
| absent_material | 212 | 225 | 53665 | 10 | 1896333 |
| Total | 527 | 561 | 127532 | 22 | 8156634 |

All **19 baseline Evidence objects** remain in the unchanged parent. The **527
original diagnostic windows** reconstruct exactly. Their repeated source text
occupies **354553 UTF-8 bytes**; unique represented block text occupies **127532
bytes**, before and after dependency closure. This compares diagnostic-window text
with its unique blocks, not baseline evidence, token billing or an API request.
No extra source block was needed in these real cases: closure added relationships
among blocks already present across different windows. Constructed tests also
exercise adding previously unselected blocks through closure.

**6/6 development retention challenges passed**, with explicit scope:

- Kayumov page 3 blocks 6–10: method, interleaved formula fragments and thermal-
  equilibrium continuation now share one co-preservation unit. No single old
  diagnostic window contained all five blocks. No reconstructed scientific sentence
  or per-result condition assignment is asserted.
- Table 1 caption, all four temperature notes, units and all solvent rows remain
  together. These are solvent physical properties; they were not relabelled as
  membrane conductivity measurements. This protected group already fit an old
  window, so it is a preservation check rather than a new scientific improvement.
- The full preparation/plasticisation/argon block is retained without assigning
  preparation atmosphere to conductivity measurement conditions.
- DSC, preparation-atmosphere and unsupported-material queries retain their old
  refusals. Missing selected Istomina evidence was not fetched or fabricated.

**Network eligibility remains 0/4.** All four proposals exceed the unchanged
**100000-byte ceiling**, including the zero-node DSC case. The complete local
diagnostic/event/asset relations are expensive: total wire proposals are **8.16 MB**.
Deduplicated source text does not establish a smaller useful API prompt. Complete
page unions, unresolved source/page boundaries and unassessed scientific sufficiency
also remain blockers. No text was clipped, ceiling raised or old refusal upgraded.

Tests run:

- Final targeted regression: **94 passed**, one existing Starlette/httpx deprecation
  warning, no failures/errors/skips; `pytest_target_v05.xml`. Covers native PDF
  identity/reconstruction, interleaved formulas, protected groups and source-order
  closure, same-text/different-location identity, guards and scope proposals,
  cross-page same/foreign-article/mixed-layer cases, absent pages, unproven mapping,
  complete-page unions, oversize retention, tampering, frozen inputs and exports,
  HTML escaping and the TAC metadata-JSON link.
- Repository Ruff passed. Mypy passed for **155 app source files**. Full runtime
  regression was not rerun because no runtime route or existing subsystem changed.
- Each frozen preparation rechecks current selected-PDF block/layout/asset plans,
  complete predecessor bindings and historical TAC sources. Six historical source
  changes use matching archived bytes with explicit mappings; private PDF/index/
  cache drift has no archive fallback. No database, retrieval, embedding or model
  request was needed for this stage.
- Initial constructed-test run finished with 25 passed and one fixture error:
  a native fixture returned a tuple which the test failed to unpack. Its synthetic
  oversize case was also unnecessarily slow (425.95 seconds). Fixed the fixture
  and replaced thousands of artificial sentence endings with equally oversize
  continuous text; the byte-ceiling assertion and production parser stayed unchanged.
  Intermediate regressions passed 61, 68 and 94 tests before final 94-test validation.
- First frozen run and both initial exports are retained as `*_v01`. Review found
  the companion TAC page linked to packet `report.json` instead of `metadata.json`.
  Archived the complete pre-repair source, changed only that renderer link and its
  regression assertion, then froze and repeated the same scope under `*_v02`.
  The connection interruption did not discard the first test result or references.

- Final source/export QA passed: **964** prepared bindings, **977** per final run/
  review and **981** for the preserved first run using explicit archived-source
  mappings. Verified 527 restored contexts, 561 exact nodes, **1148 unchanged source
  events**, **449 dependency records** and **ten original/selected PDF files**.
  All **13 output files** are byte-identical across the final run and two exports.
  Native packet JSON, expanded contexts and the report are also byte-identical
  before/after the companion-link repair; only review navigation/bindings changed.
- Isolated headless Chrome QA passed: four question cards, search counts 1/0/4,
  expandable exact context, ten TAC rows/eight columns, metadata search, the correct
  metadata JSON link and no writable review forms. Screenshots were inspected;
  there were no page errors or network requests. All **45 local PDF-link targets**
  and **13 relative artifact links** exist. Actual PDF clicks/browser file access
  behavior remain untested. Evidence: `postflight_v01.json`, `browser_qa_v01.json`.

Limitations:

- The four queries and source annotations are exposed development examples, not
  independent human scientific gold or a new holdout. Six passing retention checks
  do not establish scientific relation precision/recall, correct interpretation of
  every table, author intent or answer quality.
- Boundary closure is conservative source-order co-preservation. It can connect
  unrelated interleaved content, page headers or other uncertain text. It does not
  prove complete paragraphs, actual table continuation or that a method/condition
  applies to a particular measured value. Exact source evidence and unknowns remain.
- The diagnostic-rich wire format is over budget and is not ready for inference.
  Separating full local diagnostics from a compact source-preserving model view
  requires a separately frozen schema/coverage comparison. Compression must not
  remove scientific evidence, hide diagnostics locally or evade aggregate page guards.
- Production preparation remains the previous implementation. No browser-driven
  production form submission, other-machine restore, clean installation, paid answer
  comparison or new inference provider is claimed. Original PDFs and database
  contents were not modified by this file-only workflow.

Verdict:

The bounded local context representation is implemented and tested. It preserves
source text and adds an explicit group across the observed method/continuation
break, while retaining table units/notes and old refusals. General scientific
adequacy and API readiness remain unestablished. Next bounded task: a compact
model-facing view with full local diagnostic sidecars and exact coverage checks,
before any paid answer comparison. Retain this baseline and its over-budget result.

## Artifacts and replay

Local root remains `output/records_stage37_20261023/`, reflecting its start date.

- `retention_challenges_v01.json`, `make_retention_challenges_v01.py`,
  `kayumov_page3.png`: pre-outcome source challenges and inspected original page.
- `prepared_v01/`, `run_v01/`, `review_v01/`, `review_repeat_v01/`: first frozen run
  and exports before repairing the companion metadata link.
- `baseline_before_review_fix_v01/`: verified **582-file** pre-repair source and
  installed dependency snapshot; no private corpus, model weights or credentials.
- `prepared_v02/`, `run_v02/`, `review_v02/`, `review_repeat_v02/`: final inputs,
  native packets, exact expanded contexts and separate review exports.
- `review_v02/review.html`, `review_v02/metadata_review.html`: question/context
  review and complete ten-document historical TAC table, respectively.
- `pytest_target_v05.xml`, `browser_qa_v01.cjs`, `browser_qa_v01.json`,
  `postflight_v01.py`, `postflight_v01.json`: final verification evidence.
- `baseline_final_v01/`: final complete source and installed dependency snapshot,
  excluding private corpus, generated outputs, model weights and credentials.

Offline re-export to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.source_context_packet export --captured output/records_stage37_20261023/run_v02 --output-dir output/records_stage37_new_review
```

Repeat assembly without database/search/model calls:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.source_context_packet run --prepared output/records_stage37_20261023/prepared_v02 --output-dir output/records_stage37_new_run
```

Bound private predecessor outputs/PDFs remain necessary. Commands reject changed
code, data or registries and require new output directories. Source-only cloning
does not supply those private inputs. The initial source snapshot permits recovery
of the pre-link-fix implementation; original manifests were not rewritten.
