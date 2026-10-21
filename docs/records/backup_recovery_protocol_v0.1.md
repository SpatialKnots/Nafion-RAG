# Full-record review backup and recovery v0.1

Scope: the independent `records_revision_store_v0.1` SQLite store, its immutable
baseline and snapshot, and byte-identical copies of every registered PDF. This
does not back up PostgreSQL, the complete literature corpus, other review
systems, model weights, credentials or vector indexes. No scientific acceptance
is implied by recovery.

## Capture and verification

Use a fresh destination outside the review store. `sqlite3.Connection.backup`
captures committed database state, including WAL transactions, without a raw
copy of the live SQLite file. Later commits are outside the captured snapshot.
The copied database is checked with SQLite `integrity_check` and loaded through
the existing history/context validators. The immutable baseline, exact saved
inputs, hashes, provenance, statuses and event chains are preserved.

The directory contains `store/`, content-addressed `pdfs/` and a final
`manifest.json`. The manifest records every file checksum/size and the canonical
loaded-state checksum. Save the printed `manifest_sha256` receipt separately:
verification and restore require that expected checksum. Checksums provide
integrity relative to the receipt, not authenticated authorship. Verification
requires no access to the original PDF paths. A missing final manifest means an
incomplete backup. Failures remain visible; partial destinations are not silently
reused or deleted. Keep backups private: they contain literature and local paths.

```powershell
.\.venv\Scripts\python.exe -m scripts.records_backup create --root data/reviews/records/stage15_20261020 --output data/backups/records/new_backup
.\.venv\Scripts\python.exe -m scripts.records_backup verify --backup data/backups/records/new_backup --manifest-sha256 <printed-checksum>
.\.venv\Scripts\python.exe -m scripts.records_backup restore --backup data/backups/records/new_backup --manifest-sha256 <printed-checksum> --output output/records_restored_new
.\.venv\Scripts\python.exe -m scripts.records_review inspect --root output/records_restored_new
.\.venv\Scripts\python.exe -m scripts.records_review serve --root output/records_restored_new --port 8768
```

## Restore boundary

Restore targets must not exist. Unsafe relative paths, linked paths, unlisted,
missing or modified files are rejected. Before creating the target, restore
requires every original/selected PDF at its historical absolute path with the
recorded hash. It never overwrites source PDFs, changes evidence offsets or
rewrites historical paths, code hashes, source identities or review decisions.
The restored state must equal the captured state, including code compatibility.
Copied PDF bytes remain available for a separately planned disaster recovery;
automatic source-path replacement and cross-machine relocation are unsupported.

The intended source version must be retained separately, for example using
`scripts.freeze_baseline`. Clean startup means fresh dependencies and frozen
source with an independently restored store. It does not prove whole-system
offline operation, clean PostgreSQL migration/recovery, OCR engine availability,
model inference or independent scientific accuracy. Those require separate
acceptance checks and must be reported separately.

## Clean-source test invocation

The Terms subprocess pipeline intentionally confines its files to the source
root. Its synthetic PDF fixtures must therefore be generated beneath that root.
Create the parent directory first; pytest does not create missing parents of an
explicit `--basetemp`. Use a dedicated disposable directory: pytest clears the
chosen base directory when a run starts.

```powershell
New-Item -ItemType Directory -Path output -Force | Out-Null
python -B -m pytest -q -p no:cacheprovider --basetemp=output/pytest_tmp
```

This is a test-launch requirement, not permission to relax production path
validation. Run from the frozen source directory with the fresh environment's
Python executable. Source snapshots exclude `output/` and Python caches; retain
JUnit evidence outside the frozen source tree.
