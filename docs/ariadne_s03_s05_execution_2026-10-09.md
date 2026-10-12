# ARIADNE S03/S05: experimental record contract and source adapter

Date: 9 October 2026. This step continues [the development plan](ariadne_development_plan_2026-10-09.md). The completed work is technical groundwork for full records. It is not completion of scientific schema review, gold annotation, model extraction, or the pilot.

## Changed

Added `app/records/` as an independent experimental package:

- `schema.py`: versioned candidate/source/evidence models; raw observations, missingness, value representation, conditions and linkage proposals; exact text/hash/reference checks; candidates restricted to `needs_review` and Li-ion confirmation restricted to `not_reviewed`.
- `sources.py`: existing selected or explicit page layer export with original PDF checksum, separate OCR identity, source path checks, selected text consistency and live revalidation. No layer reselection or text normalization.
- `readiness.py`: the user's selected mandatory conditions are sample, temperature, medium composition and method. Reports missing observations and linkage roles; scientific admission is always `not_evaluated`.
- `runs.py`: validated artifact and current code/schema/environment fingerprints, without `.env` contents or PDF copies.
- `cli.py`: `source`, `validate [--live]`, `schema`, and `manifest`. Read-only database transactions, exclusive output creation, failures left visible.

Added 39 unit cases across `test_record_contract.py` and `test_record_sources.py`, the draft JSON Schema, and [the contract/CLI guide](records/experimental_record_contract.md).

Production database schema, migrations, original PDFs, OCR/chunking, numeric cap and refresh behavior, retrieval ranking, legacy annotations, and UI were not changed by this step. No blanket commit or reset was performed. Earlier dirty/untracked work remains present.

## Real source evidence

Artifacts are local, inside ignored `data/experiments/records/`; they are not public release assets.

### Sanginov 2021 abstract: one incomplete candidate

Article UUID `aec95165-f993-4576-9dba-0ec4bb8ecee1`, page 1. Exact stored original layer exported to `sources/sanginov2021_page1_v01.json`. A manually specified development annotation script selected the abstract and created `development/sanginov2021_abstract_candidate_v01.json`. This is not an automatic extractor or scientific gold.

The source reports “single-ion lithium conductivity” and a range with raw lexeme `6.3 × 10 −6 to 6.9 × 10 −4`, raw unit `S cm −1`, and temperature range `-40 to + 80 °C`. These strings are preserved verbatim. The author calls it the “best sample”; its unique label, actual mixture composition, and measurement method are not established in this abstract context. General medium information is retained without transferring a series composition to that sample. Conductivity endpoints are not automatically paired with temperature endpoints. The electronic-conductivity value in the neighboring sentence is not substituted for this property.

The candidate's evidence passed live verification against local PostgreSQL/text layer/PDF. Readiness output:

```json
{
  "missing_fields": ["sample_label", "medium_composition", "method"],
  "missing_linkage_roles": ["sample_value", "property_value", "conditions_measurement"],
  "review_state": "needs_review",
  "scientific_admission": "not_evaluated"
}
```

The author claim is stored, while independent Li-ion confirmation remains `not_reviewed`.

Manifest: `development/sanginov2021_abstract_candidate_v01.manifest.json`. Manual annotation recipe: `development/create_sanginov_abstract_case.py`.

### Kayumov 2021 bibliography: context counterexample

Article UUID `1445f31a-0de7-482b-b335-029ebdd552a5`, page 9. The full page was exported to `sources/kayumov2021_page9_v01.json`. The inspected page also contains the article's conclusion; the page or whole article must not be labeled negative.

Only bibliography entry 10 was isolated in `development/kayumov2021_reference_context_v01.json`. Its cited title mentions ionic conductivity and lithiated Nafion; bibliographic year/volume/page are not conductivity measurements. The bundle contains no candidate records. That empty context bundle is a manually identified development counterexample, not a system detection result, exhaustive negative label, or gold set.

The isolated region passed live verification. Manifest: `development/kayumov2021_reference_context_v01.manifest.json`. Recipe: `development/create_reference_case.py`.

## Tests run

1. Initial targeted integrity tests: **36 passed in 1.26 s**.
2. After readiness and manifest additions: **39 passed in 1.72 s**.
3. Full current-workspace suite: **650 passed, 1 warning in 6.58 s**.
4. Full current-source suite in the previously isolated S01 clean Python environment: **650 passed, 1 warning in 6.61 s**. This checks current source modules with the isolated environment; it does not assert that the old S01 wheel contains the newly added package.
5. `ruff check app tests scripts`: **All checks passed**.
6. `mypy app`: **Success: no issues found in 80 source files**.
7. Real page exports: Sanginov p1 and Kayumov p9; narrowed candidate/reference live verification succeeded. Both manifests were generated from structurally valid bundles.
8. `git diff --check` reported no whitespace errors in tracked diffs; the new experimental files were checked by Ruff.
9. Exported JSON Schema matches the current Python contract; 9 local Markdown links resolve. Both development manifests were rechecked against artifact bytes, every recorded code hash, current schema hash and code fingerprint.

Unit tests cover modified quotes/checksums/offsets, Unicode preservation, repeated quote identity, unknown/wrong-article references, duplicate IDs, unbacked raw observations, explicit missingness, disallowed acceptance/confirmation states, timezone requirement, mandatory-field/linkage diagnostics, code/artifact fingerprints, selected text mismatch, source path traversal, original checksum change, separate OCR identity, missing layers, live text drift, and overwrite refusal. Fixtures are explicitly synthetic, not scientific gold.

The existing Starlette/httpx deprecation warning remains. The first live export in sandbox failed with local TCP permission error `10013`; the approved rerun outside sandbox succeeded. Full suites used an approved process and explicit fresh basetemp directories because earlier project checks established sandbox async/temp-file restrictions. Failures were not converted into successful empty outputs.

### Reproduction

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_record_contract.py tests/unit/test_record_sources.py `
  -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/records_next_unit
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m app.records.cli validate `
  data/experiments/records/development/sanginov2021_abstract_candidate_v01.json --live
.\.venv\Scripts\python.exe -m app.records.cli validate `
  data/experiments/records/development/kayumov2021_reference_context_v01.json --live
```

Output creation refuses overwrite. The annotation recipes require their existing source exports and also refuse replacing outputs. To repeat artifact generation, deliberately choose new output names; do not delete the observed artifacts merely to rerun a command. Runtime/source identity is captured in the adjacent manifests.

## Limitations

- v0.1 is an experimental contract. Final scientific schema, supported representations, interpretation rules, and admission thresholds remain unapproved.
- Mandatory user conditions are implemented as completeness diagnostics. They do not establish semantic correctness, numerical plausibility, comparability, or human approval.
- No model/extractor/table parser, structured numeric parser, conversion, full-record store, review UI, comparative export or record evaluation metric was implemented.
- One manually constructed incomplete candidate and one bibliography context do not estimate precision/recall, coverage, chemical accuracy, user time, or feasibility at production scale.
- Evidence checks verify stored text and immutable-original identity; they do not repeat PDF extraction, validate OCR quality, infer coordinates, or establish source entailment.
- No exhaustive corpus adapter audit, independent gold, work grouping, or dev/test split. Main article, supplements, related publications and dissertation may overlap.
- Manifests capture current code and selected runtime versions, without reconstructing a past unrecorded run or providing the full offline environment. The S01 sealed baseline remains the earlier baseline; this step has not rebuilt its wheel.

## Verdict

The technical draft of S03 and source/manifest prototype of S05 are implemented and tested. The first part of S09 provides completeness diagnostics only. S03 scientific acceptance, S04 gold, S05 full experiment protocol, and S09 scientific admission remain open.

Next useful step: inspect methods/results to resolve actual sample IDs, medium composition and conductivity method in development sources; prepare independently reviewable annotation cases and work grouping. Then finalize scientific contract/scope and run S06 local model smoke before implementing extraction. No automatic acceptance or production refresh is justified by these results.
