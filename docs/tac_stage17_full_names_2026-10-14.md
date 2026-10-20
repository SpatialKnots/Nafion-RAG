# TAC stage17: full names, automatic roles and corpus-snapshot rebuilds

Date: 2026-10-14. Scope: the same 33 frozen development documents. Original PDFs,
TAC text and populated metadata remain unchanged. Production ingestion/retrieval
and database schemas are outside this stage.

## Changed

Implemented additive full-name inventory v0.2, default automatic taxonomy/sidecar
v0.4, compatible source/context/table validation and a local automatic pipeline.
The pipeline builds fresh versioned inventory, contexts, subsets, relations and
complete HTML before publishing; incompatible inputs retain the prior snapshot.
It regenerates TAC/metadata when a changed snapshot makes the supplied versions
stale, without transferring the previous boundary audit. No per-Term user decision
workflow or invented method endpoint was added. See the [contract](terms_full_names_pipeline_contract_v0.1.md).

Final active snapshot:
`e1bb627bed090e77ec88695e239f735b68338804ec9e99cb2aedf6708f1caa74`.
Run fingerprint:
`9dfda2e7d919f266ae7b407c3afe92fd3585a3397b0044c6a4f52625b5b64f03`.
The immutable run is under
`output/tac_stage17_20261014/automatic_pipeline/runs/9dfda2e7d919f266-e513858b`.
Earlier candidate/failed run files and previous stage snapshots remain separate.

## Observed corpus result

The inventory has **2,283 Terms / 4,214 uses**, versus 2,266 / 4,195 previously.
The full-pattern producer participates in 82 candidates; that is not 82 new Terms
or a scientific accuracy figure. All 2,266 old term IDs, 4,195 old use/mention IDs
and exact old source records are retained. The 98 contexts remain exactly equal.

Classification has 12,642 assignments:

| Axis | Proposed | Unclassified | Unresolved |
| --- | ---: | ---: | ---: |
| Type | 1,333 | 2,873 | 8 |
| Role | 36 | 4,178 | 0 |
| Origin | 65 | 4,149 | 0 |

Role proposals increased from 3 to 36 uses. Repeated rules can supply multiple
bases for one category; rule-proposal counts must not be mistaken for unique uses.
The relation pilot produces **9 property-of proposals, 2 measured-by proposals
and 36 deferred property-of cases**. Both measured-by links quote `mobilities
measured by 19F NMR` from the two uploads of the same Welch article; they are not
independent results or evidence of general measurement extraction accuracy.
No numeric records, acronym equivalences or human-confirmed links were created.

## Artifacts and operation

- `output/tac_stage17_20261014/ARIADNE_TAC_stage17.html`
- `output/tac_stage17_20261014/ARIADNE_Atlas_stage17.html`
- `output/tac_stage17_20261014/integrity_report.json`
- `output/tac_stage17_20261014/restore_verification.json`
- `output/tac_stage17_20261014/live_api_verification.json`
- `output/tac_stage17_20261014/browser_verification.json`
- `output/tac_stage17_20261014/preview_atlas.png`
- `output/tac_stage17_20261014/current_auto.zip`
- `output/tac_stage17_20261014/artifact_manifest.json`

The local Atlas remains `http://127.0.0.1:8766/ui/terms-review`. A hidden local
watcher was started with:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_pipeline --config data/terms_pipeline_config.json --output-root output/tac_stage17_20261014/automatic_pipeline --watch 30
```

Without `--watch`, the same command performs one build/no-op check. The initial
watch log reports `unchanged`; unchanged polls emit no repeated status. The
config and run cache are outside the existing review-store backup. The watcher
depends on the host session; OS startup registration is not implemented.

## Tests run

Full pytest: **990 passed, one existing Starlette/httpx deprecation warning,
90.28s**. Command: `.venv\Scripts\python.exe -X utf8 -m pytest -q -p
no:cacheprovider --basetemp=output/tac_stage17_20261014/pytest_final`.
Ruff passed for `app tests scripts`; mypy passed for 94 app source files. The final
raw HTML script passed Node syntax checking; Git diff whitespace check passed.

New synthetic checks cover full names beyond legacy token limits, exact Unicode
source mapping, retention of legacy candidates, no expansion of an isolated DSC,
method versus instrument typing, component/object/method roles and modeled-method
abstention. Real subprocess tests use actual synthetic PDFs for build/no-op,
corpus growth, old-corpus TAC/metadata regeneration, preserved old snapshots,
quote-corruption refusal, cache tampering, concurrency locks and workspace bounds.
These are engineering checks, not an independent gold set.

Initial fixture failures came from a T/A assessment-key mismatch and missing DOI
field in a synthetic snapshot; fixtures were corrected before passing runs. A
first real-corpus attempt was rejected while the full-name policy was being
changed to distinguish microscope from microscopy; its outputs remained in the
failed run and the old active snapshot was not published over. The final stable
run succeeded. No failed attempt is counted as a passed check.

Actual static verification preserved all eight columns/33 rows, full TAC,
91 populated metadata values, all old source identities, 113 existing local
targets and hashes for 120 source/input files. Every subset and relation sidecar
was reproduced. Ledger event count stayed zero. Actual live API checks reported
automatic mode, no decisions/events, POST 410 and original PDF HTTP200/`%PDF`.
Restoring the current snapshot reproduced the complete automatic graph exactly.

Browser checks loaded the Atlas without manual forms, all 33 rows/47 relation
cards, and expanded 60 A/C texts/33 Terms containers without materializing all
context evidence. Search `Welch` showed three article rows; the selected measured-by
card expanded to the exact source quotation and original page-1 link. Expanded
evidence was checked in the DOM; complete visual inspection of every source is
not claimed. Individual screenshots document the visible Atlas/table state.

## Limitations

Most roles and origins remain unknown; full-name patterns are bounded, mostly
English surface rules. Source integrity is not scientific acceptance. Duplicate
uploads remain independent article scopes. Unsupported tables, footnotes, derived
procedures and damaged text are not repaired. Automatic rebuild watches the JSON
snapshot/config boundary; a direct PostgreSQL ingestion → snapshot bridge and
OS-startup scheduling remain unimplemented.

## Verdict

Full-name enrichment, bounded role/method reuse and automatic rebuild from changed
corpus snapshots are implemented and checked. Earlier artifacts/PDFs remain
intact, and users receive no compulsory contextual Terms-resolution tasks.
