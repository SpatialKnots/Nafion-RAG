# Records stage14: automatic checks and comparative proposal export

20 October 2026. Development-only increment toward S09/S12.
[Protocol](records/checks_export_protocol_v0.1.md). This is not completion of
the full-record pilot or scientific acceptance.

## Changed

Added `app/records/checks.py`, `app/records/table_export.py` and
`scripts/records_table.py`. The check sidecar is `records_checks_v0.1` and the
export format is `records_comparative_export_v0.1`. Existing candidate schemas,
completeness policy, scientific metrics and production behavior are unchanged.

Checks revalidate the bundle's exact evidence contract, report required-field
presence using the existing readiness policy, and report missing/duplicate
linkage proposals without silently combining them. Proposed scientific linkage
always remains `unknown`. Conservative scalar-notation recognition retains exact
coefficient/exponent substrings and performs no conversion or text repair.
Ranges, bounds, ambiguous notation, units, origin and scientific identity remain
unresolved where no scientific interpretation is implemented. `43` can be a
syntactically valid scalar despite an OCR error; this check cannot certify it.

Every record remains `needs_review`, Li-ion confirmation remains `not_reviewed`,
and scientific admission remains `not_evaluated`. Technical outcome is
`incomplete` when a required technical check fails, otherwise `unresolved`.
There is no accepted-record state or human-confirmation shortcut.

The offline exporter reads all declared input bundles, including empty ones,
verifies original/selected PDF hashes and refuses existing output directories.
It writes exact input-byte copies, complete JSON/evidence, comparative CSV,
searchable read-only HTML with original-PDF page links, and an input/PDF/code/
runtime/output manifest. CSV formula-like strings receive a documented display
prefix with per-row `csv_escaped_columns`; original strings remain exact in JSON
and input copies. No metadata, experimental measurements or confirmations are
invented. There are no Terms review decisions or compulsory resolution forms.

## Frozen development scope and observations

All four existing stage06 candidate bundles were declared and hashed before
export, in order: Sanginov Abstract, Sanginov table, Istomina cited result,
Kayumov bibliography. `output/records_stage14_20261020/scope_v01.json` records
their exact hashes plus the historical reference/batch/preflight hashes and
this stage's protocol/helper hashes. These are exposed development cases,
not new articles, independent gold or whole-article enumeration.

| Saved input | Records | New technical outcome | Interpretation |
| --- | ---: | --- | --- |
| Sanginov Abstract | 1 | incomplete | Six required observations and all three linkage proposals are absent; representation remains unparsed. |
| Sanginov table | 1 | unresolved | Required observations and unique linkage proposals are present; scalar syntax is recognized. Scientific relationships, units and origin remain unvalidated. |
| Istomina cited result | 1 | incomplete | Sample, composition, composition basis and method are not present; range interpretation is not implemented by this checker. |
| Kayumov bibliography | 0 | no record outcome | Empty bundle retained in the declared scope; export alone does not certify a correct scientific negative. |

Total: four inputs, three proposed records, two incomplete, one unresolved.
No record is scientifically admitted. There were no new API/model requests,
database queries, OCR runs, index rebuilds or production corpus writes.

Both complete exports are byte-identical, including HTML/CSV/JSON, manifest and
input copies. Historical input/reference/batch/preflight hashes remained
unchanged. Three original/selected PDF files were hash-verified, with eight
distinct PDF-page link targets in HTML. The three candidate records retain 59
individual evidence references, counting repetitions. These counts describe
artifact coverage, not scientific accuracy or independent measurements.

## Tests run

- New constructed counterexample suite: **58 passed**, 6.36 seconds. Includes
  exact signed/exponent syntax, ambiguous notation, ranges/bounds, semantically
  wrong fields despite exact citations, missing/duplicate links, tampered
  evidence/PDFs, formula-like CSV cells, HTML escaping, complete empty-input
  visibility, duplicate-input and overwrite refusal, and identical repeat exports.
- Full regression: **1394 passed**, one existing Starlette/httpx deprecation
  warning, 131.39 seconds. JUnit report:
  `output/records_stage14_20261020/pytest_full_v02.xml`.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 110 source files.
- Offline real-scope export/repeat: identical outputs, candidate content and
  frozen input/PDF identities verified. CLI help executed successfully.
- Static HTML/JSON/CSV inspection: all four inputs, all three record rows,
  exact evidence contract, existing PDF targets, output hashes and unreviewed
  states checked. Results are in `static_qa.json` and `replay_qa.json`.

The first targeted attempt lacked the parent of its explicit pytest temporary
directory: 32 tests passed and 26 fixture setups failed. Creating that parent
resolved the setup failure; it was not an application defect. The initial mypy
run found five typing errors, corrected before the passing runs above.

The first full regression stalled after 13 tests at the existing upload API
test in the sandbox and was interrupted. Only the separate unrestricted full
run is counted successful. A later optional process-inspection command could
not access Windows CIM; no test result was inferred from it.

Browser navigation to the local HTML was explicitly rejected by its file-URL
security policy. No workaround was attempted. Browser rendering, search
interaction and PDF clicks are not verified; static checks are separate.

## Artifacts and reproduction

Private outputs are excluded from Git:

- [HTML review](../output/records_stage14_20261020/run_v01/review.html),
  [CSV](../output/records_stage14_20261020/run_v01/table.csv),
  [complete JSON/evidence](../output/records_stage14_20261020/run_v01/table.json);
- `run_v01/manifest.json`, exact `run_v01/inputs/`;
- `repeat_v01/`: second byte-identical export;
- `scope_v01.json`, `replay_qa.json`, `static_qa.json`;
- private reproducibility helpers `replay.py`, `static_qa.py` and JUnit report.

From the repository root, use fresh output paths:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_table --inputs data/experiments/records/pilot/stage06_20261020/runs/sanginov_abstract/candidates.json data/experiments/records/pilot/stage06_20261020/runs/sanginov/candidates.json data/experiments/records/pilot/stage06_20261020/runs/istomina/candidates.json data/experiments/records/pilot/stage06_20261020/runs/kayumov/candidates.json --output-dir output/records_stage14_new
```

A clean clone does not include these private source bundles/PDFs. The export
manifest identifies current checks/export code and selected runtime versions,
not a complete installation lock or independently attested historical model.
The unrelated local `data/terms_pipeline_config.json` was not modified.

## Limitations

This is a comparative table of proposals from already saved extraction results.
Automatic article-wide detection, numerical/range/unit interpretation, cell
reconstruction, semantic linkage validation and cross-paper scientific identity
remain open. Persistent edit/decision history, record revisions, verified-table
export, independent quality evaluation, expert time measurement and a full
offline extraction workflow are not implemented by this stage. An offline
exporter does not make the earlier remote extraction autonomous.

## Verdict

The first checks/export increment is complete and reproducible on its declared
development scope. It exposes incomplete and scientifically unresolved records
without promoting them to confirmed data. Next product step: a separate
revision/decision store and source-linked full-record editing/export; independent
annotation remains a parallel scientific-evaluation task. No new percentage of
MVP readiness or scientific-accuracy claim is inferred from software tests.
