# Records stage18: source-supported article-level development scope

21 October 2026. ARIADNE S02/S04/S05 preparation.
[Protocol](records/article_scope_protocol_v0.1.md).

## Changed

Added a separate source-bound screening/task exporter in
`app/records/article_scope.py`, CLI `scripts/records_article_scope.py` and 25
constructed tests. The strict versioned sidecar covers every supplied document
exactly once, preserves assistant authorship and provisional interpretations,
and rejects foreign/inexact evidence, invalid page declarations, missing or
duplicate supplement parents and unsupported schema/independence claims.

The existing stage16 auditor verifies the historical source packet first. The
exporter retains the original inventory, screening input, full source-only
bundles, evidence spans, PDF/page/layer hashes and code/input/output manifests.
Final postflight rechecks the source artifacts and PDFs. Existing destinations
are never overwritten. Failed exports may leave partial fresh directories;
only a completed root manifest records the final combined export.

Every proposed primary article has a task covering every original PDF page,
including explicit empty/missing selected-page states. Proposed supplements are
attached as separate source-only bundles with preserved document boundaries.
The tasks contain no record proposals or model responses. Every page retains
`non_text_completeness=not_established`; stored text is not proof of complete
figure, image-table, equation or scientific-notation coverage.

An HTML table retains all 33 source documents, search, exact screening excerpts,
expandable complete stored text, original PDF/page links and source/diagnostic
details. This is an article-scope development report, not a new TAC stage or a
Terms resolution interface. Source type is absent from the historical region
schema and explicitly marked unavailable; original/ocr text-layer labels and
all existing source identities remain unchanged.

Updated README, roadmap and the development plan. Replaced the obsolete blanket
statement that S07–S08/S10–S17 were unstarted with an evidence-qualified summary
of the later engineering work. The initial S01 assignment remains historical
and is no longer presented as the current next step. Pre-existing working-tree
changes from stages14–17 were retained; no commit, reset, database write or
production migration was performed.

## Frozen source scope and screening proposals

Input: `data/experiments/records/pilot/stage01_20261014/`.
Source fingerprint:
`f133dcf1d95bf94d38f0d1cf49da24ca55082a42a8867e51f6f343fd84811a94`.
This is the historical development-exposed packet, not a new live-database
census or an untouched test set.

The versioned assistant screening preserves all documents:

| Provisional status | Documents | Interpretation |
| --- | ---: | --- |
| `proposed_primary` | 3 | Kayumov 2021, Sanginov 2021, Istomina 2021; proposed conductivity development tasks |
| `proposed_supplement` | 1 | Sanginov supplementary materials; proposed attachment with source evidence on both sides |
| `related_dissertation` | 1 | Chernyuk dissertation; relationship/measurement overlap remains unresolved |
| `other_property_context` | 1 | Chernyuk 2024: stated swelling-enthalpy/microcalorimetry context, not a primary conductivity task in this version |
| `unresolved` | 27 | Identity excerpts only; no scientific eligibility or exclusion established |

These are assistant interpretations, not independent annotations or accepted
scientific eligibility. Inspected pages are declared separately from exported
scope. Exporting complete text does not imply scientific inspection of every
page. No lexical hit or default unresolved status becomes a scientific label.

The three article tasks preserve:

| Primary source | Source documents | Original PDF pages |
| --- | ---: | ---: |
| Kayumov 2021 | 1 | 10 |
| Sanginov 2021 + proposed supplement | 2 | 38 |
| Istomina 2021 | 1 | 14 |
| Total | 4 | 62 |

All 62 pages have stored selected-text regions in this snapshot. Their bundles
are byte-identical copies, with zero candidate records. Coverage is not top-k
retrieval or reuse of only the four previous oracle regions.

Istomina page 2 explicitly attributes a conductivity range to recent work [26].
Pages 4–6 describe conductivity measurement, the reported isotherm and cases in
which conductivity could not be measured. These excerpts are retained without
turning the cited range into a new independent experiment or inventing numeric
values from Figure 3. The source-side distinction is a screening diagnostic;
sample/condition equivalence and measurement duplication remain unassessed.

The source inventory has one same-recorded-DOI pair: the two Welch-related
entries share `10.1021/mz3005204`. Their original PDF hashes differ. This is
retained as a metadata identity diagnostic, without silently merging documents
or asserting work/measurement equivalence. No exact-original-PDF duplicate
group was observed in this packet.

Outputs:

- [All-document article-scope HTML](../output/records_stage18_20261021/run_v01/review.html).
- `output/records_stage18_20261021/run_v01/report.json`, `manifest.json`,
  `screening.json`, `source_inventory.json`, `tasks/` and nested `source_audit/`.
- Independent repeated export at `repeat_v01/`; 12 artifact files per export,
  including manifests, match byte-for-byte.
- `screening_v01.json`, `build_screening.py`, `preflight_v01.json`,
  `postflight.py` and `postflight_v01.json` retain local screening/QA provenance.

Source PDFs and full text remain local and private; generated outputs and
screening sidecars are absent from a clean clone. The program does not modify
production ingestion/retrieval, record schemas, selected text, OCR, numeric
normalization, thresholds or the existing revision-store code context.

## Tests run

- New targeted suite: **25 passed**, 6.42 seconds. Cases cover complete
  document/page accounting, unchanged source-only bundles, explicit empty/missing
  pages, all-empty unresolved sources, relation ownership/roles/duplicates,
  source/quote/PDF tampering, invalid schema/independence declarations, repeat
  equality, overwrite refusal and HTML escaping. One pytest cache ACL warning;
  no test failed. JUnit: `pytest_target_v01.xml` under the stage18 output root.
- Full regression outside sandbox: **1504 passed**, one existing Starlette/httpx
  deprecation warning, **101.41 seconds**. JUnit: `pytest_full_v02.xml`. The first
  sandbox run stalled after 13 progress marks and was interrupted; no passing
  result is attributed to that run. Cache writes were disabled for the full run.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 116 source files
  after fixing local task-list type annotations. Initial mypy errors are not
  counted as a pass. CLI `--help` executed; `git diff --check` passed with existing
  LF/CRLF notices.
- Both actual source exports completed; all inputs, source PDFs, output and code
  hashes verified. Static HTML checks account for 33 document rows, 493 exact
  full source-page texts, 33 distinct original PDF paths and 526 distinct local
  PDF/full-document/page link targets. All source-supported screening excerpts
  survive HTML parsing unchanged. Every task bundle is source-only and matches
  its source inventory regions. JSON scientific rates remain null.

Static artifact checks are separate from visual/click acceptance. Browser QA
was not attempted; no HTTP serving workaround was introduced for the earlier
file-URL navigation restriction. No model/API call, PDF mutation, external
metadata lookup or human-time observation occurred in this stage.

## Reproduction

Use fresh output paths from the repository root:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_article_scope --packet data/experiments/records/pilot/stage01_20261014 --screening output/records_stage18_20261021/screening_v01.json --output-dir output/records_article_scope_new
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_record_article_scope.py -q -p no:cacheprovider --basetemp=output/records_article_scope_test_tmp
```

The pytest basetemp must be dedicated disposable test data under the source root;
pytest clears it. The source packet, screening sidecar and original/selected
PDF paths must remain available and match their declared hashes.

## Limitations

The target of 10–15 scientifically eligible independent publications has not
been reached. Three proposed primary documents are not three verified
independent studies. The other 27 documents have not been scientifically
excluded. New sources, independent eligibility/measurement grouping and an
untouched work-level split remain necessary for the intended quality pilot.

Whole-article extraction and recall have not been measured. No figure/table
values were inferred, OCR candidates were not promoted into generation and no
new numbers were scientifically accepted. Independent annotation, scientific
precision/recall and human-time savings remain unavailable. PostgreSQL/whole
corpus recovery, portable paths and complete offline inference remain open as
recorded in stage17. This stage does not close those tasks.

## Verdict

The bounded source-scope stage is complete: three development article tasks
cover all 62 original PDF pages with explicit non-text uncertainty, and all 33
documents remain auditable. Independent corpus eligibility and the scientific
pilot remain open.

Next bounded engineering step: freeze an offline extraction plan for these
three full article scopes, identify protected bounded text/table/footnote
contexts and unresolved graphical sources, then separately freeze model runs.
Keep previously cited values, unmeasurable samples and repeated mentions in the
denominator diagnostics; do not send full stored pages under the earlier
bounded-context protocol. New independent source acquisition/annotation remains
a separate prerequisite, not an assistant-generated claim of scientific gold.
