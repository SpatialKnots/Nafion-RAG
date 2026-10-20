# TAC stage16: bounded automatic scientific-relation pilot

Date: 2026-10-14. Scope: all 33 frozen development documents. This stage completes
the three authorized engineering tasks together with stages14 and15; it is not
completion of the full scientific-relation roadmap or independent acceptance.

## Changed

Added `app/terms/relations.py`, a separate immutable relation-sidecar CLI and an
optional `tac_terms_review prepare --relations` input. Two explicit grammatical
templates support `property-of` and `measured-by`. Endpoints must be existing
exact TermUses with compatible unambiguous types in the same A/C context/sentence.
Every recognized case has a source-bound proposal or deferred diagnostic. No
co-occurrence inference, invented method endpoint, cross-context join, numeric
record, new production schema or user decision form was added.

The table keeps all eight main columns and has read-only pilot diagnostics in
each Terms cell, including empty-result rows. Source definitions and relation
output are embedded in the immutable prepared snapshot; the existing backup
preserves that snapshot. The relation-algorithm hash participates in input identity
and stale-output diagnostics. See the [relation contract](terms_relation_contract_v0.1.md).

Final active snapshot:
`ebf77165c6e62b1bd95c3e82730f2f663c19b3c98886f55b683fcab59602c673`.
All earlier stage12–16 snapshots remain files; no manual event was added. Only
the existing store's current-snapshot pointer changes intentionally.

## Inputs and observed output

The corpus, TAC profiles/metadata/boundaries, full inventory and exact contexts
remain unchanged: 33 articles, 98 contexts, 2,266 Terms and 4,195 uses.
Final automatic classification is
`data/experiments/tac/20261014_stage15/classification_final_v03c.json`:
SHA-256 `d74fdb52eef6888ade8ac19d16f8e79f928b6fc30ce2eb576d040acb2a230c0f`.
Its assignments/subsets are exactly equal to the preceding v03b development
output; the final stricter inherited role-type guard changes code/provenance,
not this corpus's classifications.

Final relations:
`data/experiments/tac/20261014_stage16/relations_pilot_final_v02.json`:
SHA-256 `a40a258f49558c785947214c924267fa0515f12065f1cbb39bebf6e229690a83`.
The sidecar schema remains experimental v0.1; `final_v02` names the second frozen
final run, not a schema upgrade. It records 45 recognized cases: **7 proposed
property-of / 38 deferred**. No measured-by template yields a corpus proposal.
The initial candidate had 10 proposals; stricter object-ending checks retained
qualified compounds such as lithium metal/Nafion-115 membrane as deferred rather
than replacing them with a known short root. Earlier candidate files are retained.

Roles: 3 proposed / 4,192 unclassified. Origin: 64 own-report proposals / 4,131
unclassified. Types: 1,208 proposed / 2,979 unclassified / 8 unresolved. No manual
proposals, human-confirmed links or accuracy estimate are implied by these counts.

## Artifacts

- `output/tac_stage16_20261014/ARIADNE_TAC_stage16_final.html`
- `output/tac_stage16_20261014/ARIADNE_Atlas_stage16_final.html`
- `output/tac_stage16_20261014/integrity_report_final.json`
- `output/tac_stage16_20261014/browser_verification_final.json`
- `output/tac_stage16_20261014/live_api_verification_final.json`
- `output/tac_stage16_20261014/current_auto_final.zip`
- `output/tac_stage16_20261014/restore_verification_final.json`
- `output/tac_stage16_20261014/preview_final.png`
- `output/tac_stage16_20261014/artifact_manifest_final.json`

Stage14 and stage15 HTML exports remain in their separate output directories.
The local Atlas/table URLs use `http://127.0.0.1:8766/ui/terms-review`. Exported
HTML links target the original local PDFs; online links use registered hash-checked
assets. Current snapshot backup includes external-source definitions, not PDFs or
all zero-event experimental archives.

## Reproduction

Use `scripts.tac_term_classification` on `20261012_v01/corpus.json`, stage08
`profiles_final_v02.json`, stage09 `terms_final.json` and stage10
`contexts_final.json`, with the default taxonomy v0.3 and a new output path.
Then run `scripts.tac_term_relations` with those four inputs, the newly generated
classification and a new output path. Finally run `scripts.tac_terms_review
prepare` with the same inputs, stage08 metadata/boundary files and `--relations`
pointing to that sidecar. Export using the returned immutable snapshot ID and
new graph/table paths. The CLI validates byte/content/source bindings and refuses
to overwrite existing outputs. Artifact hashes change when provenance/files change.

## Tests run

Final full command: `.venv\Scripts\python.exe -X utf8 -m pytest -q -p
no:cacheprovider --basetemp=output/tac_stage16_20261014/pytest_final_v03`:
**981 passed in 16.95s**. One existing Starlette/httpx deprecation warning remains.
Ruff passed for `app tests scripts`; mypy passed for 93 app source files. Node
syntax checks passed for the raw final HTML script and live Terms script.
`git -c core.safecrlf=false diff --check` passed.

The final focused classification/relation run passed 46 tests. Relation checks
cover exact existing endpoints, direction, altered quote/page/layer, stale input/
policy, fabricated classification, unknown/missing method, ambiguous or qualified
object, boundary errors, source isolation, negation, future, hypotheses, citation/
bibliography-style text, comparison and modeled wording. These are synthetic
engineering cases, not scientific labels or domain accuracy evaluation.

Actual exported-data checks reproduced every subset and validated the embedded
relation sidecar. They preserved all 33 rows/eight columns, exact TAC text,
91 populated metadata fields, all Term/source identities, 113 existing local
targets and hashes for 120 source/input files. The live API returned automatic
mode, no decisions/events, POST decision 410 and an original PDF with HTTP200/
`%PDF` signature. Event count remained zero. Restoring the final backup into a
separate empty directory reproduced the snapshot and automatic graph exactly,
including relations; current code bindings and freshness checks passed.

Actual browser QA loaded all 33 rows/45 relation cards, expanded 60 A/C texts and
33 Terms containers, and left the DOM at 30,873 nodes without materializing full
context evidence. Search reduced the table to one morphology article; its proposed
link expanded in the DOM to the exact source quotation and original page-13 asset
link. Atlas has no manual forms. These observations are interaction checks, not timings.
The partial table viewport did not provide a complete visual view of the evidence;
full-page capture returned `Unable to capture screenshot`. DOM/source and local
asset checks passed, but complete visual QA of every expanded source is not claimed.

An initial JavaScript extraction through the static HTML parser was truncated and
failed Node syntax checking; extraction from the complete raw script passed.
This was a verification-extraction failure, not a repaired algorithm result. The
failed extraction is retained separately. Stage14's first fixture setup errors
and the first two role-test failures are documented in those stage reports.

## Limitations

Automatic role coverage is small and most attribution remains unknown. Missing
methods, unsupported sentence grammar, compound endpoints and non-pass TAC
boundaries are retained as diagnostics. Method suitability, direct versus derived
quantities, sample identity, table/footnote discourse and scientific acceptance
are not solved by these templates. There is no ingestion-triggered Terms rebuild,
production relation retrieval or independent gold benchmark. The existing frozen
corpus remains development material, including its duplicate Welch upload.

## Verdict

The authorized table fix, bounded automatic role/origin extension and separate
automatic relation pilot are implemented and checked. No manual Terms resolution
workflow was restored. Scientific completeness and accuracy remain unestablished.
