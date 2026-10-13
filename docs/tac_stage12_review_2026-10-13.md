# TAC stage12: persistent Terms review

Date: 2026-10-13. Terms implementation plan stage4, engineering scope only.
All 33 frozen documents, 2 266 local candidates, 4 195 mentions/uses and 12 585
classification assignments are retained. Initial user history is empty; test
decisions exist only in separately named QA stores and are declared assistant fixtures.

## Delivered workflow

Open `http://127.0.0.1:8766/ui/terms-review`. Choose an axis/queue, select a term,
then select an assignment or whole-term relevance. The form shows the exact
selected context and offers confirm/correct/reject/uncertain/restore, reason and
declared reviewer. Classification decisions apply to the selected use/axis.
The derived graph updates memberships/counts; original proposals and sources stay
available. Initial type-conflict queue has 17 terms.

The SQLite store preserves decisions across refresh/restart. Restore appends a
revision rather than deleting history. Competing windows receive a conflict rather
than overwriting each other. Changed snapshot/policy/PDF sources require rechecking;
annotations are not silently carried to a different snapshot. A full ledger export
and consistent ZIP backup support inspection and recovery.

Snapshot ID:
`5bb8c2f73a797a02551d758d7ebb10240d708077c2fb396f9bdcd419f6e5bcd6`.
User root: `data/reviews/terms`. Source root: `D:\Nafion-RAG`.
Snapshot schema: `tac_terms_review_snapshot_v0.1`; graph schema: `tac_terms_graph_v0.3`.
Input hashes are embedded in the snapshot and full export; upstream inputs are
the stage08 profiles/metadata/boundary review, stage09 inventory, stage10 contexts
and stage11 classification on `20261012_v01/corpus.json`.

Separate initial cutoff-0 outputs:

- `output/tac_stage12_20261013/ARIADNE_Terms_Atlas_stage12_initial_2026-10-13.html`
- `output/tac_stage12_20261013/ARIADNE_TAC_stage12_review_initial_2026-10-13.html`

The table retains eight columns, full expandable TAC and Terms, search,
diagnostics, source links and explicit proposal/review status. It includes all 33
documents. Live HTTP source links use verified asset routes; static HTML retains
local links. Legacy stages and outputs remain separate and unchanged.

## Operations

From repository root, restart the local standalone server when needed:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.terms_review_server --root data/reviews/terms --port 8766
```

Prepare a matching snapshot; original and selected-layer PDFs are read-only:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_review prepare `
  --snapshot data/experiments/tac/20261012_v01/corpus.json `
  --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json `
  --inventory data/experiments/tac/20261013_stage09/terms_final.json `
  --contexts data/experiments/tac/20261013_stage10/contexts_final.json `
  --classification data/experiments/tac/20261013_stage11/classification_final_v01.json `
  --metadata data/experiments/tac/20261013_stage08/metadata_final_v02.json `
  --boundary-review data/experiments/tac/20261013_stage08/boundary_review_final_v02.json `
  --source-root . --root data/reviews/terms
```

Use new backup/output paths and an empty restore destination. These are command
examples; they do not claim that example paths have already been created:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_review backup --root data/reviews/terms --archive output/terms_review_backup_new.zip
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_review restore --root output/terms_review_restored_new --archive output/terms_review_backup_new.zip
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_review export --root data/reviews/terms --sid 5bb8c2f73a797a02551d758d7ebb10240d708077c2fb396f9bdcd419f6e5bcd6 --cutoff 0 --graph output/terms_graph_cutoff0_new.html --table output/terms_table_cutoff0_new.html
```

Existing `app/main.py` includes the Terms router; the main UI links to it. The
standalone command avoids ingestion/PostgreSQL startup. Package data includes
`app/static/terms_review.js`. Main ingestion, retrieval, extraction and numeric
store schemas are not amended by this stage.

## Validation and evidence

16 new tests cover persistent history/restore, immutable events, real two-thread
revision races, cutoff projection, independent axes/relevance, stale sources/code,
changed snapshots, invalid requests, escaping, HTTP Origin/CSRF/loopback peers,
backup recovery and corrupt archive rejection.

Final full pytest: **950 passed, 1 existing Starlette/httpx warning**, 11.64 s,
recorded in `output/tac_stage12_20261013/pytest_full_verified.log`. After the
loopback-peer and restored-current-pointer refinements, targeted tests also
passed: **16 passed**, 3.51 s. The final full run includes these refinements.
Ruff for all app/tests/scripts passed; mypy passed for **92 source files**.

Real Edge QA uses a separate store. It confirms, corrects and restores one fixture
assignment, checks a competing window receives HTTP 409 and retains its reason,
verifies original proposals, source PDF delivery, export history, eight table
columns/33 documents and mobile width. A real server process restart retains all
three fixture events; ZIP restore reproduces history and graph exactly. Evidence:
`browser_verification.json`, `restart_backup_verification.json` and
`qa_backup_v01.zip` in the stage output directory. These events are engineering
fixtures, not human science decisions.

Final read-only working-store QA verifies zero events, 17 queue terms, exact
selected context, source delivery, all 4 195 table mentions, 1 275 basis quotes,
91 present metadata values, TAC text, search, all expanded Terms/assignments,
7 636 source links, and both initial static outputs. Screenshots are inspected. The first
QA attempt counted only materialized links before expanding remaining terms;
the QA was corrected to expand them. No source text or scientific output was repaired.

Initial test failures exposed canonical dictionary ordering and a Windows SQLite
temporary-file handle that was not closed; both were corrected. A browser request
fixture initially used a relative URL; it was corrected and rerun in a new QA
store. Sandbox localhost access returned WinError 10013; those runtime checks
were rerun with the required escalation. A later full pytest within sandbox
stalled after creating two fixtures and producing no log; only its identified
processes were stopped. The escalated rerun passed all 950 tests in 11.64 s.
A first background launch found an
occupied port; only the identified Terms server processes were stopped before
the final successful launch. These failures are not hidden as successful runs.

Before source baseline: 324 files, fingerprint
`efe0f51e704eee96750f4ccb8cb1b7c5cc6f6ebb65b32914fef7dec0f2da7307`.
Stage recipes, final integrity report, source archive and artifact inventory are
under `data/experiments/tac/20261013_stage12`. JS/CSS/HTML/JSON assets excluded by
the baseline extension policy are archived separately. The mutable user database
is not treated as an immutable stage artifact; an initial consistent backup is
sealed instead. Existing dirty-tree changes from earlier stages are retained.

## Changed / Tests run / Limitations / Verdict

Changed: separate immutable Terms snapshots/SQLite review ledger, per-use decisions,
whole-term relevance, source checks, optimistic concurrency, append-only restore,
review queues, derived graph/TAC annotations, exports, backup/recovery and local UI.
Existing app integration is limited to the router/navigation; four Terms review
modules and the live form are added. No extraction/ranking/scientific labels are
silently changed.

Tests run: full 950 pytest passed; final targeted 16 passed; Ruff and mypy 92 files
passed; Edge/source/restart/backup checks passed, with separate QA decisions.

Limitations: reviewer identity is declared, not authenticated; originals remain
external to backups at absolute paths. Human scientific acceptance, classification
accuracy, scientific relations, cross-article equivalence and workflow superiority
remain unmeasured. UI/history/source-integrity success does not establish them.

Verdict: Terms plan stage4 engineering delivered. Next: review initial conflicts
against sources, then define bounded scientific-relation scope for stage5.
