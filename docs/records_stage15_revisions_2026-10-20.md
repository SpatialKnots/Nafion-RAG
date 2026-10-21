# Records stage15: persistent full-record revisions and local editing

20 October 2026. Experimental S10–S12 increment.
[Protocol](records/revision_review_protocol_v0.1.md).

## Changed

Added `app/records/revision_store.py`, `app/records/revision_ui.py`,
`scripts/records_review.py` and 37 constructed regression cases. The new
`records_revision_store_v0.1` is independent of production PostgreSQL, numeric
review and Terms. The existing candidate schema and stage14 exporter remain
unchanged. The latter freezes and verifies the initial input/PDF baseline.

Revision zero retains the exact original candidate. Edits, separate declared
review decisions and restores append complete revision events in a dedicated
SQLite database. Every event has actor/kind, reason, UTC timestamp, original
context identity, candidate, technical checks and a previous-event hash.
Immutable triggers prevent ordinary event update/delete. A serialized write
transaction checks `expected_revision`; a stale tab receives a conflict.
Changed baseline/PDF/code/schema context, invalid source spans, changed record/
article identity and malformed actions cannot produce a successful saved revision.
Read operations do not create or repair missing databases.

The local editor shows all declared inputs, including zero-record bundles, and
offers observation/status/note editing, exact evidence selection by frozen
region/quote/explicit occurrence, linkage editing, representation editing,
registered PDF navigation, history, restore and revision-aware JSON/CSV exports.
Unchanged evidence objects and original raw text remain intact. Existing CR/LF
is restored for an unchanged textarea value; newly entered evidence must match
the exact frozen source without normalization. No new source text is inferred.

The candidate's `review_state=needs_review` and
`li_ion_confirmation=not_reviewed` remain unchanged. Separate declared review
states are unreviewed/confirmed/rejected/needs_changes. A confirmed decision
requires a caller-declared human, explicit source-review attestation and no
failed technical prerequisite. Unknown scientific checks remain unknown.
This is a reviewer assertion, not authenticated identity, independent expert
acceptance or automatic scientific admission. Every edit/restore resets the
declared decision to unreviewed; restoring an old confirmed revision copies its
candidate into a new unreviewed revision, never its confirmation.

The dedicated server binds to `127.0.0.1`, with local Host checks and
cookie/header/Origin checks on writes. No general filesystem route is exposed:
PDF responses resolve only registered source regions and verify their bytes.
There is no remote multi-user authentication or production deployment.

## Saved-source development demonstration

Declared scope: all four saved stage06 bundles, ordered Abstract, table, cited
result and bibliography. They contain three proposed records and one empty input.
Their hashes and the prior stage14 outputs were frozen in
`output/records_stage15_20261020/scope_v01.json` before this replay.

In a separate `demo_store_v01/`, an explicitly assistant-labeled development
edit changed the table candidate's composition-basis raw phrase to the exact
substring `mass fraction`, retaining its original evidence and original
candidate. This illustrates an editable text boundary, not a scientifically
accepted correction. A fresh Python process reopened revision 1 successfully.
Restore then appended revision 2 with the exact original candidate and
unreviewed status. Both events and both candidate versions remain in JSON.
No real human confirmation was created.

The user-facing store at `data/reviews/records/stage15_20261020/` was initialized
separately. All three records remain at revision 0 and unreviewed. It references
the same four declared inputs; the empty bibliography input is visible without
being labeled a confirmed scientific negative. Historical inputs, prior stage14
outputs and original/selected PDF hashes remained unchanged.

## Tests run

- Targeted new tests: **37 passed**, one existing Starlette/httpx deprecation
  warning, 11.39 seconds. These are synthetic fixtures, including synthetic human
  declarations; none constitutes a real person's scientific approval.
- Final full regression: **1431 passed**, the same one warning, **65.49 seconds**.
  JUnit: `output/records_stage15_20261020/pytest_full_v01.xml`.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 112 source files.
- Tests cover save/reopen/export, unchanged originals, concurrency with one
  winner, stale revision rejection, exact repeated/overlapping quotes, CR/LF and
  astral Unicode, invalid IDs/spans/actions, changed PDF/OCR/baseline/code,
  immutable events/hash checks, human confirmation constraints, edit/restore
  decision reset, CSRF/Origin/Host checks, HTML escaping, zero-record visibility
  and registered PDF responses.
- Bundled Node.js parsed the actual editor JavaScript successfully. A separate
  pure-JavaScript probe exercised six client behavior groups with a mocked DOM/
  transport: unchanged CR/LF/raw evidence, field payloads, representation,
  explicit review attestation, restore payload and visible server errors.
  This is not browser rendering or scientific evaluation.
- Saved-source edit/restore, new-process reload, complete history export and
  unchanged historical inputs/PDFs verified as described above. CLI help ran.
- Actual server startup and HTTP `/api/state` returned 200, three records,
  revisions `[0, 0, 0]`, stale_code=false.
- Browser opened the actual localhost application and the table record. It
  showed all four inputs, source regions, editing controls and empty live
  history. Selecting temperature displayed exact `20 °C` and two evidence
  cards; selecting conditions_measurement displayed the linkage editor and six
  cards. A screenshot was inspected. The tab was retained for the user.
  Browser save/restore and PDF-page visual accuracy were not tested; API tests
  and the source-level demonstration cover persistence separately.

The first targeted sandbox run stopped progressing during HTTP tests and was
interrupted. The separate unrestricted run above is the passing result. Initial
lint/type errors were corrected before final checks. An initial browser locator
using an exact label found no match; inspection identified the accessible
combobox and the role-based locator worked. No application data changed during
that browser check.

Sandbox loopback inspection failed with WinError 10013. The sandbox server
attempt was stopped. The separately authorized server and loopback check ran
outside the sandbox. These infrastructure failures are not counted as passes.

## Artifacts and commands

- [Local editor](http://127.0.0.1:8767/), while its server is running.
- Live store: `data/reviews/records/stage15_20261020/`, containing immutable
  baseline input copies, context snapshot and SQLite ledger.
- Demonstration history: [JSON](../output/records_stage15_20261020/demo_export_v01/review.json),
  [CSV](../output/records_stage15_20261020/demo_export_v01/review.csv).
- Private `scope_v01.json`, `replay_qa.json`, `fresh_process_after_edit.json`,
  client probe and JUnit reports under `output/records_stage15_20261020/`.

To reopen the existing local store:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_review serve --root data/reviews/records/stage15_20261020 --port 8767
```

To inspect or export it without a web server:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_review inspect --root data/reviews/records/stage15_20261020
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_review export --root data/reviews/records/stage15_20261020 --output-dir output/records_review_export_new
```

`init --inputs PATH1 PATH2 ... --root NEW_DIRECTORY` creates a separately
versioned context and refuses an existing directory. Store/data/outputs are
private local artifacts, absent from a clean clone. The source/protocol/tests
are in the working tree; no commit or clean installation is claimed here.

## Limitations

This editor works within frozen source regions; it does not enumerate missing
records, extract new pages, repair OCR, parse numerical/unit semantics or prove
scientific linkage/comparability. The confirmation identity is self-declared.
Hash chains are not digital signatures and cannot prevent a privileged actor
rewriting a complete database/context or deleting terminal history after removing
its protections. Full backup/restore and migration/rebasing of a review context
after code/source changes are not implemented. Stale contexts block saves and
applied exports explicitly. Installation on another machine, independent
annotation, expert-time measurements and autonomous local extraction remain open.
No external API/model calls or production database writes were made.

## Verdict

Persistent full-record editing, decision history, restore and revision-aware
export are implemented and verified on synthetic tests plus a clearly labeled
saved-source development demonstration. The live store contains no fabricated
human decisions. Next substantive milestone is an independently evaluated
article-level pilot with measured full-record errors and expert time; backup/
restore and fresh installation remain separate operational checks. This stage
does not establish scientific acceptance or a new measured MVP percentage.
