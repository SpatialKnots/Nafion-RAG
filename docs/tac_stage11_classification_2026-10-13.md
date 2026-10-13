# TAC stage11: proposed classification and overlapping subsets

Date: 13 October 2026. This implements the engineering part of Terms plan stage3.
Taxonomy/domain review and scientific acceptance remain pending.

## Delivered

Graph:
`output/tac_stage11_20261013/ARIADNE_Terms_Atlas_stage11_v02_2026-10-13.html`.

Review table:
`output/tac_stage11_20261013/ARIADNE_TAC_stage11_classification_v02_2026-10-13.html`.

Both contain all 33 documents, 2 266 original local candidates, 4 195 exact uses
and 98 frozen TAC contexts. The table keeps Title, Authors, Journal, Year,
Abstract, Conclusions, Terms and original-PDF hyperlink. Full expandable text,
existing boundary/metadata diagnostics and all exact sources are retained.
No XLSX is generated. Previous stages and v01 previews are preserved separately.

Graph switches between articles, TAC, type, role and origin; axes can be viewed
across the frozen corpus or within a selected article. It shows memberships of
the selected term, source/context/PDF and classification bases. Circle areas count
distinct local term IDs; sorting/search do not change group membership or area.
Unknown and conflict groups remain visible. Alpha/source/rank ordering and JSON
export of the current subset are available. A source-bound term selection from a
global group drills into its article; identical labels across articles are not merged.

The taxonomy, classification contract and annotation guide are drafts:
[contract](terms_classification_contract_v0.1.md),
[guide](terms_annotation_guide_v0.1.md).
Stage09 generation/ranking and stage10 source identity/containment are unchanged.

## Measured output, not accuracy

Each use has assignments for three axes: 12 585 assignments total.

| Axis | Proposed uses | Unclassified uses | Unresolved uses |
| --- | ---: | ---: | ---: |
| Type | 1 161 | 2 980 | 54 |
| Role | 4 | 4 191 | 0 |
| Origin | 2 | 4 193 | 0 |

| Type subset | Distinct article-local Terms |
| --- | ---: |
| Material/substance | 133 |
| Object | 115 |
| Property | 124 |
| Process | 20 |
| Method | 0 |
| Condition | 24 |
| Unclassified | 1 867 |
| Unresolved | 17 |

Counts of overlapping groups are not additive. The 17 conflict Terms also belong
to proposed property/condition groups. Roles have 2 study-object Terms, 1 comparison
Term and 2 265 Terms with at least one unclassified use. Origin has 1 own-report
Term and 2 265 unclassified Terms. A known assignment in one occurrence does not
classify other occurrences. No confidence probabilities or accepted labels are created.

All automatic role/origin rules abstained on this frozen corpus. The nonzero role,
origin and compound-type examples come from **8 explicitly declared assistant manual
proposals in one Laporta abstract**, not independent human review. This demonstrates
different roles of a local `Nafion` without assigning them to every occurrence.
Most Terms remain unknown under the deliberately narrow whole-phrase lexicon;
zero method count reflects this input/policy and does not prove absence of methods
in the full papers. Extraction coverage is a separate task.

## Reproducibility

Classification sidecar:
`data/experiments/tac/20261013_stage11/classification_final_v01.json`.
SHA256: `18c262229346991cbd11e03527f830c488e97eca446f5af99f6e1555dc7a3f6f`.
Schema `tac_term_classification_v0.1`; classified graph `tac_terms_graph_v0.2`.
The new graph format is explicit; unclassified structural v0.1 remains supported.

Inputs are frozen corpus `20261012_v01/corpus.json`, stage08
`profiles_final_v02.json`, stage09 `terms_final.json`, stage10 `contexts_final.json`,
draft `app/terms/taxonomy_v01.json` and stage11 `manual_proposals_v01.json`.
Full byte/canonical hashes, producer rules, code hashes, source references and
input snapshot binding are recorded in the sidecar, graph and stage manifests.
Manual input is embedded with a canonical content hash. Physical original/layer
PDF hashes are verified read-only by exporters. No source text is rewritten.

To reproduce, use a new output path for each command:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_term_classification `
  --snapshot data/experiments/tac/20261012_v01/corpus.json `
  --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json `
  --inventory data/experiments/tac/20261013_stage09/terms_final.json `
  --contexts data/experiments/tac/20261013_stage10/contexts_final.json `
  --manual data/experiments/tac/20261013_stage11/manual_proposals_v01.json `
  --output data/experiments/tac/20261013_stage11/reproduced_classification.json
```

Add `--classification` to `scripts.tac_review_html` with the matching contexts,
inventory and existing metadata/boundary inputs. Add the same sidecar through
`--classification` to `scripts.tac_terms_graph`, and `--review` to link the new
table. Exporters refuse existing outputs. Timestamp changes HTML bytes on replay;
assignments/memberships/order are deterministic for the same inputs and policy.

Before snapshot: 318 files; fingerprint
`a42304b2aa8044ba95f695a69625fa26b4889966ddb1208a51f2a0ca0ca2da44`.
Stage manifests and code/asset archive are in `data/experiments/tac/20261013_stage11`.
The existing baseline extension rules exclude JSON taxonomy and graph JS/CSS/HTML;
`source_stage11.zip` separately retains these assets together with module/scripts,
tests, documentation and recipes. `pyproject.toml` includes the taxonomy as package
data. Existing dirty-tree work is retained; no blanket commit/reset is performed.

## Validation

15 new tests check per-use roles/origin, explicit unknown/conflict states, overlapping
counts, same-use AND intersections, deterministic sort/identity, manual targets,
exact Unicode basis spans, tamper rejection and eight-column exporter compatibility.
The method-role test uses an explicit synthetic seed because the ordinary lexical
fixture did not produce that full method name; production generation was not changed.
An initial temp-directory setup failure was corrected by creating the stage folder.
The manual example guard caught original `proce-/dures` wrapping; its check was
adjusted to the literal preserved fragment, without repairing source text.

Full pytest: **934 passed, 1 existing Starlette/httpx warning**, 8.23 s.
Ruff for app and changed Python scripts/tests: **All checks passed**.
Mypy: **88 source files, no issues**.

Browser audit checks all 660 axis/category article groups, 2 266 term selections,
4 195 exact graph and table mentions, 2 926 graph context cards, 12 585 assignments
in each view and 1 275 exact classification basis quotes in each view. It checks
source sort, multiple roles, subset JSON download, proportional areas, mobile width,
all 91 present metadata values, 70 distinct graph links and 7 636 table links.
Local targets exist. No page errors or external requests. Screenshots are inspected.
These are engineering/source-integrity checks, not independent scientific evaluation.

## Changed / Tests run / Limitations / Verdict

Changed: isolated classification module, draft taxonomy/guide, manual proposal input,
sidecar validator, saved subset definitions and classification views in graph/review.
Package data includes the taxonomy. Existing app source files, source extraction,
retrieval/database schemas, ranking and frozen outputs are preserved.

Tests run: 934 full pytest passed; Ruff passed; mypy 88 files passed; full-scope
browser/source audits and PDF hash checks passed.

Limitations: whole-phrase policy has limited coverage; roles/origin examples are
assistant proposals in one development article. Domain taxonomy and independent
accuracy remain open. No persistent decision log, human acceptance, scientific
relations, cross-article equivalence or production integration is added.

Verdict: Terms plan stage3 engineering delivered for source-bound review. Next
stage4 is persistent review/history; scientific acceptance remains separate.
