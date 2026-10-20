# Block 4: Li-Nafion record pilot initialization, stage01

Date: 14 October 2026. Scope: initialize the user-selected conductivity scenario. This is a completed source-preparation stage, not a completed extraction module or independent scientific evaluation.

## Changed

The existing source snapshot script omitted runtime JSON taxonomies and JS/HTML/CSS assets. Its selection rules now include these files under `app/` and `scripts/`; private data, `.env`, outputs and caches remain excluded. A regression test verifies inclusion and exclusions.

Added `app/records/pilot.py`, `scripts/records_pilot.py` and the fixed [initialization protocol](records/pilot_initialization_protocol_v0.1.md). The exporter uses a repeatable-read, read-only PostgreSQL transaction, the existing exact-page source adapter and original-PDF checksum checks. It does not invoke retrieval, TAC filtering, OCR or a model. Existing candidate schema, scientific logic, database schema, ingestion, chunking, retrieval scoring and numerical facts are unchanged.

The exporter accounts for every document in the frozen profile, preserves complete selected page text and records missing/empty-page diagnostics. It refuses overwrite and candidate-filled source bundles. A separate selection audit keeps lexical signals outside the source-only HTML. The HTML provides complete expandable pages, document search and original-PDF links, with no annotation decisions or suggested record fields.

## Observed scope and artifacts

The fresh lexical profile inspected 33 documents and verified 33 original PDFs. Six documents have Li-Nafion lexical anchors, five also have conductivity in the same chunk. These are document candidates, not six scientifically eligible publications or six independent works. The pool includes a supplement and a dissertation; publication/work identity requires scientific/source review. The target of 10–15 eligible publications is not established. Absence of a lexical hit does not establish scientific absence.

All 33 documents were exported: 493 stored pages, 493 exact full-page source regions and 493 pages in the original PDFs. No missing/empty pages were detected in this run. There are zero candidate records and zero annotations. All inputs remain development-only; no untouched evaluation or independent gold is claimed.

- Before-patch snapshot: `output/records_stage01_20261014/baseline_before/`, 370 selected files; fingerprint `b0ab035f06a029cdb609866e427caa98a32172ba2bae202c620a213c46d23bea`.
- Corrected source baseline: `output/records_stage01_20261014/baseline_ready/`, 382 selected files, 44 untracked within the selection; fingerprint `853ecdffb3f143da6b3dafa497ba22b4a94e8bf02d7694b83eacf9283fed6971`. The snapshot precedes this report/README update. No missing dependencies or installed-version requirement mismatches were reported. This is an observed environment snapshot, not a portable dependency lock.
- Private profile: `data/experiments/records/profiles/li_nafion_20261014_stage01.json`.
- Private source-only packet: `data/experiments/records/pilot/stage01_20261014/`, including `manifest.json`, `source_inventory.json`, `selection_audit.json`, protocol/profile/baseline copies and 33 source bundles.
- [Source-only HTML](../data/experiments/records/pilot/stage01_20261014/ARIADNE_records_source_only.html).
- Separate repeat: `data/experiments/records/pilot/stage01_20261014_repeat/`.
- Source fingerprint of both exports: `f133dcf1d95bf94d38f0d1cf49da24ca55082a42a8867e51f6f343fd84811a94`.
- [Verification result](../output/records_stage01_20261014/packet_verification.json).

The packet contains private full article text and local file paths. It remains under ignored `data/experiments/records/`, excluded from the source snapshot. PDFs are referenced, not copied or modified. Existing numeric/Terms historical decisions are not imported.

## Tests run

- Targeted source-packet, baseline, record contract and source-adapter suites: **70 passed in 2.14 s**. Fifteen new test cases cover runtime asset inclusion, candidate contamination, exact-source escaping, omitted-page diagnostics, source/profile mismatch, repeatable content identity and exclusive output.
- Full regression: **1054 passed, one Starlette/httpx deprecation warning, 50.47 s**. Run outside sandbox with a new declared temporary directory.
- Ruff `app tests scripts`: passed. Mypy: no issues in 95 app source files. `git diff --check`: passed; Git reported existing LF/CRLF notices.
- Corrected baseline: all 382 selected source files and snapshot artifacts passed checksum verification. Isolated source import resolved `app.records.pilot` from the snapshot directory; candidate schema and critical runtime assets were available. No clean dependency installation, live application startup or offline scientific workflow was tested from this snapshot.
- Two live exports: identical source inventories and source fingerprints. The original PDF hashes remained unchanged; selected-layer PDF hashes and all page text hashes verified.
- Offline Edge QA: 33 document sections, 493 expandable pages; all 493 displayed quotes match the frozen source exactly. Search returned both Sanginov 2021 entries. All 526 local PDF/page link targets exist. Page expansion and mobile width passed; no browser errors. Opening every individual PDF link in the browser was not tested.

## Reproduction

Use fresh output directories; existing snapshots/packets must not be reused or overwritten.

```powershell
.\.venv\Scripts\python.exe -m scripts.freeze_baseline --output output\records_stage01_reproduce\baseline
.\.venv\Scripts\python.exe -m scripts.profile_li_nafion --output data\experiments\records\profiles\li_nafion_stage01_reproduce.json
.\.venv\Scripts\python.exe -m scripts.records_pilot --profile data\experiments\records\profiles\li_nafion_stage01_reproduce.json --baseline-manifest output\records_stage01_reproduce\baseline\manifest.json --output data\experiments\records\pilot\stage01_reproduce
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_record_pilot.py tests\unit\test_baseline_snapshot.py tests\unit\test_record_contract.py tests\unit\test_record_sources.py -p no:cacheprovider --basetemp D:\Nafion-RAG\tmp\records_stage01_reproduce_tests
```

Source content repeats while corpus/page/layer metadata and source bytes remain unchanged. Run UUIDs, timestamps and bundle-file hashes can differ; they are excluded from the source-content fingerprint.

## Limitations

No independently annotated reference, work-level held-out split, 10–15 scientifically eligible-publication shortlist, extractor, full-record evaluator, record-review store or scientific table export was added. Zero packet records are an unannotated source state, not a scientific negative. A source-only packet does not make its future annotations independent by itself.

The clean source import reused the existing virtual environment. Clean installation, dependency lock, model/OCR availability on another machine, database recovery and full offline acceptance remain open. The corrected snapshot is local source evidence, not a cleared public release.

## Verdict

Block 4 is started with a reproducible, exact-source initialization stage. Next scientific prerequisite: independently establish eligible measurements and work groups, expanding the corpus where necessary. Next engineering stage: a bounded source-region-to-record adapter and a full-record evaluation harness against explicitly labeled development references. No extractor accuracy or scientific acceptance is claimed here.
