# TAC stage13: automatic Terms workflow

Date: 2026-10-14. Scope: remove per-Term user resolution and add automatic
source-bound context rules. All 33 frozen documents remain in the exports.
Scientific-relation extraction and ingestion-triggered jobs are outside this stage.

## Delivered behavior

`http://127.0.0.1:8766/ui/terms-review` now displays automatic classifications,
subsets and read-only diagnostics. Manual classification/relevance forms,
reviewer/reason fields and revision-restore actions are removed. The old decision
POST returns 410, including cached-form requests, without appending an event.
Old decisions remain archival and do not alter automatic subset memberships.
See the [v0.2 contract](terms_automatic_contract_v0.2.md).

The default taxonomy/sidecar versions are `tac_terms_taxonomy_v0.2` and
`tac_term_classification_v0.2`. Per-occurrence context rules distinguish property
frames from preparation/test settings while retaining exact source quotes.
Inconclusive cases remain unknown/unresolved, without a user resolution task.
Manual input is disabled for the automatic policy; v0.1 replay remains supported.

New active snapshot:
`c45f422ead9144d2dbe5b3c5fa98e8ad0a1efae9b2247aecc1f3292d7bbfdadc`.
The previous stage12 snapshot is intact. A 328-file source archive and consistent
user-store backup were created before edits. The ledger remains at zero events;
only its active-snapshot pointer changed intentionally.

## Corpus and observed results

Inputs remain `20261012_v01/corpus.json`, stage08 profiles/metadata/boundaries,
stage09 complete inventory and stage10 exact contexts. The corpus retains
2,266 local Terms, 4,195 uses, 98 contexts and 12,585 axis assignments.

Type assignments: **1,208 proposed / 2,979 unclassified / 8 unresolved**.
All 4,195 role and all 4,195 origin assignments remain unclassified on this input:
the bounded automatic cues do not match these uses. Former manual demonstration
labels are not promoted to automatic results. This run has 1,224 policy proposals
and no manual proposals.

Of the 54 prior type-conflict uses, 46 now receive an automatic category proposal
matching the prior assistant development audit. Eight concentration uses in Doi
retain both alternatives. This is a development check, not classification accuracy.
The first candidate retained nine conflicts; the prepared-membrane comparison
clause was added as an explicit bounded rule and the final v02 output retains
eight. Candidate/final files are separate, not silently overwritten.

Separate local artifacts:

- `output/tac_stage13_20261014/ARIADNE_Terms_Atlas_stage13_auto_2026-10-14.html`
- `output/tac_stage13_20261014/ARIADNE_TAC_stage13_auto_2026-10-14.html`
- `data/experiments/tac/20261014_stage13/classification_final_v02.json`
- `output/tac_stage13_20261014/integrity_report.json`

The table keeps the eight agreed columns, expandable TAC/full inventory,
original-file links and missing/undetected/source diagnostics. Static checks
verified all TAC text, 91 present metadata values, all 2,266 Terms/12,585
assignments, 113 distinct local link targets and unchanged hashes for 120 source/
input files. Every subset was recomputed and compared with the exported memberships.
The new ledger pointer is excluded from the byte-invariance claim; event count
and retention of the old snapshot are checked separately.

## Reproduction and executed checks

Run `scripts.tac_term_classification` without `--manual`, using the unchanged
snapshot/profiles/inventory/contexts and a new output path. Prepare the Terms
snapshot through `scripts.tac_terms_review prepare`, then export its graph/table
through `export`. Automatic exports reject nonzero manual revision cutoffs.
Private stage recipes and manifests retain exact paths/hashes and versions.

Ruff passed for app/tests/scripts; mypy passed for 92 source files. Full pytest:
**957 passed, 1 existing Starlette/httpx deprecation warning**, 36.18 seconds:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=output/tac_stage13_20261014/pytest_full_v01
```

Tests cover per-occurrence isolation, exact evidence, new-corpus membership,
same-use intersection, competing rules, unknown labels, manual-input rejection,
HTTP 410 and retention of legacy events without effects on automatic subsets.
An earlier targeted run passed 37 tests; the full run includes the final added
comparison-rule test. An initial mypy Match-variable error and missing-directory
test fixture were fixed. The first sandbox targeted run stalled at HTTP/TestClient;
only its identified Python processes were stopped, and targeted/full reruns
outside the sandbox passed. Those failed/stalled attempts are not counted as passes.

Real in-app-browser Atlas checks showed automatic mode, one diagnostic Term
for Doi, 24 read-only axis cards for its eight uses and zero manual decision
forms. No console errors/warnings were observed in that Atlas check. Screenshot:
`preview_automatic_terms.png`. The table's eight columns/33 rows and search
filtering to one article were observed. Its mass-expansion action timed out
globally and after filtering; neither attempt is reported as passing. Static
checks of full text/inventory/links are separate from this incomplete runtime check.

Live API verification additionally confirmed automatic mode, 410 for a manual
POST, a real original PDF response/signature and zero events before/after. The
first localhost attempt was blocked by sandbox WinError 10013; the authorized
outside-sandbox rerun passed. `live_api_verification.json` records these checks.
Node syntax checking passed for the new read-only client script. Project guidance
and the future relation-pilot scope now specify automatic processing without a
per-Term user resolution task.

The real post-stage backup was restored into a separate empty QA directory.
Its active snapshot, empty history and automatic graph exactly match the working
store. The working store and external original files were not replaced by this check.

## Changed / Tests run / Limitations / Verdict

Changed: automatic policy/classification v0.2, exact context rules, automatic CLI
default, disabled manual input/UI/API, archival-only prior decisions, navigation,
policy packaging and new complete 33-document snapshot/exports. Ingestion,
retrieval and numeric-store schemas are unchanged; original PDFs remain immutable.

Tests run: 957 pytest passed; Ruff/mypy passed; live Atlas manual-form absence and
diagnostic navigation checked; table columns/search observed; full static source,
TAC/metadata, inventory, subset and link checks passed. Mass browser expansion
remains a recorded timeout, not a pass.

Limitations: bounded type coverage; unknown role/origin on this corpus; no
independent accuracy, relation extraction or ingestion-triggered rebuild. The
in-app browser did not complete mass expansion of the large table. All source
data are present in the export; runtime performance requires separate work.

Verdict: user resolution of Terms is removed. Automatic source-bound subset
formation is active on the prepared corpus, with explicit unknown/ambiguous diagnostics.
