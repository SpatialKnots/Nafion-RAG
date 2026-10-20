# ARIADNE: source audit of the stage12 Terms conflicts

Date: 2026-10-14. Scope: assistant review proposals and a bounded relation-pilot
worksheet. This is not a new classification algorithm, human scientific acceptance,
or completion of Terms implementation-plan stage5.

## Scope and source binding

Current stage12 snapshot:
`5bb8c2f73a797a02551d758d7ebb10240d708077c2fb396f9bdcd419f6e5bcd6`.
The active ledger contained zero events when inspected. The type-conflict queue
contains 17 article-local Terms in 13 documents, corresponding to 54 assignments
in 21 exact TAC page contexts. All original proposals are property/condition
conflicts for temperature or concentration; there is no generic failure to assign
every scientific concept in the corpus implied by this queue count.

The physical original PDFs, selected-layer PDFs, registered source assets, seven
upstream stage inputs, frozen review snapshot, working ledger and tracked
app/scripts/tests source files were checked against a 325-file local baseline.
Nineteen relevant original PDF pages were rendered with Poppler at 110 dpi and
visually inspected. PDF page numbers are physical one-based file pages, not an
assumption about printed pagination. Full quotes, exact offsets, selected text
layer, article/use/assignment IDs and hashes remain in the audit JSON.

Algorithm label: `manual_assistant_source_audit_v0.1`. Output schema:
`tac_terms_conflict_audit_v0.1`. Input bindings retain the stage12 input and policy
hashes. Audit judgments are separate from the persistent review-event contract.

## Findings

The proposed contextual interpretation is a reported characteristic/threshold
for property and a preparation/test/comparison parameter for condition. It is an
assistant interpretation for individual uses, not an approved automatic policy.

- 7 assignments have a property proposal: charge-carrier concentration; the
  temperature of decomposition onset; gas-generation onset temperature; two
  references to glass transition temperature; two critical gelation concentration
  mentions. Full phrases and referents matter, even when the selected Term is
  only the nested word temperature/concentration.
- 39 assignments have a condition proposal: casting/annealing/mixing parameters,
  temperature ranges or comparison conditions, and salt-concentration strategies.
  A proposed type does not establish sample identity, attribution, a method link
  or a completed measurement.
- All 8 concentration assignments in Doi remain `requires_taxonomy_review` with
  both alternatives retained. Prepared electrolyte concentration describes
  composition and can also be a controlled variable. The draft guide does not
  resolve this taxonomy boundary. No arbitrary category priority was introduced.

The Satoh Conclusions context and thesis Conclusions context retain their
`boundary_error` diagnostics. Original damaged unit glyphs, word-per-line text
and metadata remain unchanged. The source-audit interpretation never repairs a
stored quote or overrides a boundary assessment. The worksheet also flags the
existing local label Lin 2023 versus the printed 2024 footer without amending
metadata. Future/cited language is not treated as a completed own-study result.

No assistant audit proposal was written to the user review ledger. The queue
therefore remains 17 Terms, and scientific decisions remain pending. The HTML
offers inspection, not a hidden bulk-accept action.

## Artifacts and reproduction

Private output directory: `output/terms_conflict_audit_20261014/`.

- `ARIADNE_TAC_conflict_audit_2026-10-14.html`: all 33 documents, original eight
  columns, full inventory and TAC text, original diagnostics, 54 separate audit
  cards, source links and per-assignment assistant annotations.
- `audit_proposals_v01.json`, `assistant_judgments_v01.json`, `inspection.json`:
  audit judgments, exact source bindings, input hashes and the immutable baseline.
- `relation_pilot_cases_v01.html` and `.json`: nine explicit development cases in
  seven documents; three proposed class-level property-of links, three deferred
  cases and three abstentions. These are not gold labels or extracted records.
- `source_pages/`: the 19 inspected original-page renders.
- `static_verification.json`: executed static checks and explicitly missing QA.
- `artifact_manifest_v01.json`: hashes of the local artifacts and recipes.

Run from the repository root with the existing virtual environment and Poppler
on PATH. The inspection recipe requires the same active zero-event snapshot; it
fails rather than adapting silently to changed review state or changed inputs.
These recipes reproduce this private audit, not a production extraction service.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m output.terms_conflict_audit_20261014.recipes.inspect_sources
.\.venv\Scripts\python.exe -X utf8 -m output.terms_conflict_audit_20261014.recipes.build_audit
.\.venv\Scripts\python.exe -X utf8 -m output.terms_conflict_audit_20261014.recipes.build_pilot_worksheet
.\.venv\Scripts\python.exe -X utf8 -m output.terms_conflict_audit_20261014.recipes.verify_artifacts
```

Recipes and literature-bearing artifacts remain ignored/local. The new tracked
files are this report and the [bounded stage5 scope](terms_relation_pilot_scope_2026-10-14.md),
plus a pointer in the Terms implementation plan.

## Changed / Tests run / Limitations / Verdict

Changed: isolated source-bound assistant conflict audit, a full 33-document review
HTML, nine relation-planning examples and a concrete bounded pilot scope. Production
code, classification policy, extraction, source files and review events are unchanged.

Tests run: source/hash checks; visual inspection of 19 original PDF page renders;
static HTML validation of eight columns/33 rows/2,266 Terms/12,585 assignments;
all original row markup/text compared with the frozen table after removing added
audit annotations; all 54 audit identities and context quotes verified; six
worksheet endpoints checked; 136 distinct local link targets verified; Node
syntax checks passed for three script blocks; Ruff passed for the four private
recipes. The first recipe lint run reported long lines; those were reformatted,
and the final check passed. No pytest/mypy/full runtime suite was run for this
artifact-only work; prior stage12 results are not presented as new results.

Limitations: Edge was unavailable through Browser Use; the in-app browser rejected
`file://` under its URL security policy. Browser visual QA and runtime interaction
checks were not executed, and no alternate surface/protocol workaround was used.
Original-page visual inspection and static checks do not establish the layout or
interactive behavior of the final HTML. Category proposals, relation examples,
origin/sample assignments and scientific acceptance require reviewer assessment.
The relation extractor and persistent relation review are not implemented here.

Verdict: conflict source audit and bounded pilot preparation delivered. Scientific
conflicts are documented, not counted as accepted/resolved. Terms stage5 engineering
and independent scientific review remain open.
