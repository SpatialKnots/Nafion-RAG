# Records stage17 — backup/restore and clean-source startup, 20 October 2026

## Changed

Added `app/records/backup.py`, `scripts/records_backup.py`, 16 synthetic recovery
tests and the [recovery protocol](records/backup_recovery_protocol_v0.1.md).
`records_backup_v0.1` captures the independent record-review SQLite database
through SQLite's online backup API, verifies its integrity and existing history
validators, and preserves the immutable baseline, saved inputs and source/code
snapshot. Every registered PDF is also copied with its original checksum.

The final manifest inventories all files and the complete loaded-state digest.
Create prints a separate manifest checksum receipt; verify/restore require that
expected checksum. Restore uses a fresh target directory, rejects modified,
missing, additional and unsafe members, and never replaces original PDFs or a
live database. Historical paths and evidence identities are unchanged. Existing
hashed stage15 store/UI modules were not modified; the live context remains
compatible. README test commands now specify workspace-local temporary fixtures.

This is a separate records operations stage. It changes no TAC extraction,
Terms decisions/subsets, retrieval, database schema or scientific metrics.
The unrelated `data/terms_pipeline_config.json` was not changed.

## Actual recovery exercise

`output/records_stage17_20261020/exercise_v01.py` ran against two real saved
development stores, without creating review events in either source:

- Live `data/reviews/records/stage15_20261020`: four input cases, three candidates,
  zero review events. Backup:
  `data/backups/records/stage17_20261020/live_v01/`.
- Stage15 demonstration store: four cases, three candidates and two explicitly
  assistant-authored development events (edit then restore). Backup:
  `output/records_stage17_20261020/demo_backup_v01/`.

Both were restored into separate `live_restored_v01/` and `demo_restored_v01/`
directories under the stage17 output root. Full loaded states, canonical JSON
exports and exact CSV strings matched before/after. All three registered PDF
paths retained their hashes; source store states remained unchanged. All
declared review statuses remained `unreviewed`. No independent annotation or
scientific confirmation was created.

Both stores retain snapshot ID
`773875fca848c01e88733349ae75fd8da3c68983376f1c8656418cf63fdd6427`.
Separate receipts and results:

- `live_backup_receipt_v01.json`, manifest SHA256
  `1a60b2724ad336714bf70bb930c6ed9d038cf09fa8547fcb3678d40a2877b79e`;
- `demo_backup_receipt_v01.json`, manifest SHA256
  `e9272cc05db4c1730d8bc654e35ee4d2c996a2b23215dba5f93e6299baf396a8`;
- `recovery_qa_v01.json` records exact-state/export/source checks.

## Clean-source startup

Created a new Python 3.12.7 virtual environment under
`output/records_stage17_20261020/clean_env_v01/`, with
`include-system-site-packages = false`. Installed the 83 observed dependency
pins from stage16 into this environment. `pip check` passed. Runtime metadata
confirmed every observed version matched and every distribution resided inside
the new environment. Installation used network/cache access; this is not an
offline installation or a test of an independently built wheel.

The frozen source used for execution is `clean_source_v01/source/`: 458 selected
files, 22 untracked, fingerprint
`669e592e7b1c5ebf703fda0e727ea281714f1ebd6f7666b5d64f9450fd6acd5f`.
It includes source, tests, documentation, migrations and runtime assets, excluding
the working `.env`, corpus, secrets and model weights. The exercise explicitly
checked imports came from this source copy, with dependency distributions from
the fresh environment. Test/runtime caches and synthetic output are disposable
artifacts outside the snapshot selection rules.

`clean_smoke_v01.py` started and stopped two temporary localhost processes from
that source with the clean Python, no copied `.env`, an intentionally unused DB
URL, separate data root, empty generation API key and offline model setting:

- Main API on port 8779: `/health`, `/openapi.json` and exact brand PNG passed.
  Health is process liveness; database endpoints/migrations were not exercised.
- Restored demo editor on port 8778: complete state, dashboard, all three record
  pages, JSON/CSV exports and all **18** original/selected PDF responses passed.
  Returned PDF hashes matched frozen region declarations. Three records/two
  historical events remained unchanged and `stale_code` was false.

Evidence: `clean_smoke_qa_v03.json`, `main_server_v03.log`,
`review_server_v03.log`. Live working servers were not reconfigured. Temporary
test servers were terminated after checks. Clean-source CLI `records_backup
verify` and `records_review inspect` also passed; the live backup has 13 verified
files. These are HTTP checks, not browser interaction or new scientific review.

## Tests run

- Targeted synthetic backup suite: **16 passed**, one existing warning, 22.53 s.
  `pytest_backup_v02.xml`. Cases cover exact history/context recovery, committed
  WAL capture, later-event isolation, tampering, pinned manifest checksums,
  unsafe paths, original PDF loss/change, extra files and overwrite refusal.
- Full suite from the frozen source with the clean environment: **1479 passed**,
  one existing Starlette/httpx deprecation warning, **97.03 s**.
  `pytest_clean_full_v03.xml`.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in **115** source files.
- `git diff --check`: passed, with existing LF/CRLF notices.
- Actual two-store recovery and fresh-runtime HTTP/CLI checks passed as above.

Failures were retained and corrected, not counted as successful acceptance:
initial sandbox venv/pip/pytest/HTTP attempts failed due permissions, DNS or
startup timeout. Outside sandbox, the first full clean run had 1474 passed and
five Terms fixture path failures: its temporary root was outside the source
root. The second had 903 passed and 576 fixture setup errors because the new
workspace-local `output` parent did not yet exist. Creating that parent and
using a dedicated `--basetemp` under the source root produced the final complete
pass. No production path checks or test assertions were weakened. The HTTP QA
script initially expected a CSRF marker in dashboard text; inspection showed
the token is a cookie and editor payload. The corrected check verifies actual
dashboard content. Earlier failed logs/JUnit remain separate.

Reproduce from the source directory using the clean environment's executable:

```powershell
New-Item -ItemType Directory -Path output -Force | Out-Null
python -B -m pytest -q -p no:cacheprovider --basetemp=output/pytest_tmp
```

The chosen base directory must contain disposable test data only: pytest clears
it. Recovery commands and the expected checksum policy are in the protocol.

## Limitations

This is same-machine recovery of the independent record review store. Original
PDFs must still exist at historical paths; copied PDFs are retained, but restore
does not automatically replace missing sources or relocate a corpus. There is
no whole-system/PostgreSQL backup or restore, migration acceptance, model-weight
backup, clean OCR-engine check, model inference or complete offline workflow in
this stage. Main API liveness does not prove retrieval/database readiness.

Checksums are not authenticated signatures. If both the backup and separately
held receipt are replaced, authenticity is not established. Failed operations
can leave partial fresh directories, without a successful manifest/receipt;
these must not be silently reused. Backups and receipts remain on this disk,
so resilience to disk loss has not been demonstrated. The installed dependency
snapshot is OS/Python-specific, not a portable release lockfile.

Independent chemist/reference and measured human-time evidence remain absent,
as confirmed by the user. Scientific precision/recall/time savings remain
unmeasured; no revised MVP completion percentage is inferred from test counts.

## Verdict

Same-machine record-review backup/restore and fresh-dependency source startup
passed their declared checks. Complete project disaster recovery, offline
scientific workflow and independent pilot acceptance remain open.
