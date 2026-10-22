# Stage35: connect the existing TAC metadata extractor to ingestion

22 October 2026. Bridge `registered_tac_metadata_v0.1`, unchanged extractor
`tac_file_metadata_v0.1`.
[Prospective protocol](records/bibliography_bridge_protocol_v0.1.md),
[stage34 scope](records_stage34_risk_preparation_2026-10-22.md).

Changed:

- Reused `scripts.tac_metadata.extract_article` and its source validator. Their
  source bytes, and shared `scripts.tac_experiment` bytes, match the stage34
  archive exactly. No replacement author/year parser or new scientific heuristic
  was written. The adapter explicitly supplies empty TAC sections and uses the
  existing metadata-only front-title fallback on registered physical pages 1–2.
- Connected this adapter to new ingestion, text reselection and duplicate imports.
  Duplicate handling refreshes metadata without rechunking. Original/selected PDF
  hashes, current PDF extraction, exact registered text/layer IDs and candidate
  quotes are checked. Empty/missing pages, unsupported and ambiguous outputs stay
  visible. Errors propagate through the existing ingestion transaction handling.
- Added migration `0006_metadata_extractions` and append-only
  `article_metadata_extractions`: a monotonic database identity, input/code/payload
  hashes, full source evidence, raw alternatives and before/after projection data.
  Existing article column types are unchanged. Empty authors/year/journal fields
  can receive algorithm proposals; nonempty existing values are preserved. Only
  values matching the preceding managed projection can be automatically refreshed
  or revoked. Divergent manual values detach from automatic ownership.
- Unchanged refreshes retain the same history record. Corrupt history cannot
  authorize an overwrite. An existing immutable history record remains valid when
  a new preview describes the same already-applied field values; its historical
  before-image is retained rather than rewritten.
- Added read-only `/articles/{id}/bibliography` and
  `/ui/articles/{id}/bibliography`, with links from preparation results. The API
  rechecks source/payload identity and exposes proposals and projection matches;
  it never reports independent confirmation. Stale evidence fails visibly.
- Packaged the existing scripts needed by the runtime adapter. Added an explicit
  build backend; installed local build tools for verification. No external metadata
  lookup, generation, embeddings, retrieval-score change or index rebuild was added.

## Real bounded application

Scope: the **ten unique articles** in stage34's four native responses, within the
existing **33-article** collection. The additive migration was applied from
`0005_library_sources` to `0006_metadata_extractions`. A database content/metadata
snapshot was saved before the bounded backfill; its history-table row count was zero.

Code/protocol/tests and predecessor bindings were frozen before the first real
metadata preview. The read-only preview used the existing extractor without
post-outcome tuning. All existing scoped authors/year/journal fields were empty.
The frozen preview was then applied in one transaction, with source/current-field
rechecks under article locks. **26 field values were filled, with ten source-bound
history records.** No other existing article was bulk processed.

| Field | Proposed and projected | Explicit unresolved/not applicable |
| --- | ---: | --- |
| Authors | 9/10 | Choi 2025: not found |
| Year | 9/10 | Guo 2020: not found |
| Journal | 8/10 | Guo 2020: not found; dissertation: not applicable |

These are output-state/coverage counts, **not accuracy**. In particular, the filename
`Guo 2020` did not supply a year when the finite extractor found no supported year
candidate. Raw forms such as `NatUre Energy` remain unchanged. Proposed names,
issue-year priorities and any retained alternatives were not independently evaluated.

The original 23 out-of-scope articles' metadata is unchanged. Thirteen database
table fingerprints for nonmetadata content match before/after; for `articles`, the
three intended metadata columns were excluded from that fingerprint and compared
separately. Pages, selected layers, chunks, tags, jobs, library state and vector-index
state are unchanged. Original/private PDF and cached input hashes verify.

The review includes all ten documents and the agreed Title, Authors, Journal, Year,
Abstract, Conclusions, Terms and original-file columns. **34** complete historical
TAC section proposals from the separately identified frozen snapshot still match
current selected-PDF/text/layer evidence. They are shown in full, without repairs,
as historical algorithm proposals. Terms were not recomputed or integrated by this
metadata step; the review says so explicitly. There are **37** exact metadata
candidate-evidence spans, including alternatives, not 37 independent measurements.

No generative API, external metadata lookup, retrieval or embedding request ran.
Existing preparation reads the newly recorded fields; its old-refusal behavior was
checked against the four saved evidence contexts without rerunning retrieval or
creating a model request. Frozen earlier results remain unchanged historical evidence.

Tests run:

- Final targeted regression: **189 passed**, one existing Starlette/httpx warning,
  `pytest_target_v04.xml`. Includes legacy equivalence, native PDF source integrity,
  missing/ambiguous states, existing/manual values, managed refresh/revocation,
  immutable history, payload corruption, repeat application, API errors/escaping,
  unchanged preparation behavior and exclusive deterministic review exports.
- Full regression: **2158 passed**, one existing Starlette/httpx warning, no
  failures/errors/skips, **208.58 seconds**, `pytest_full_v02.xml`. API/full tests
  ran outside the sandbox because of the prior TestClient restriction. Ruff
  passed; mypy passed for **153 app source files**. The unchanged legacy modules
  are behind an explicit runtime-validated import boundary; this does not claim
  that their existing standalone strict-type diagnostics were fixed.
- Applied PostgreSQL migration successfully; repeated **ten** real refreshes
  return the same history IDs and leave the row count at ten. A constructed native
  PDF ran through the actual production ingestion and duplicate paths, filling
  expected metadata without adding a second history record. That entire test
  transaction rolled back; copied synthetic files remain local.
- **Ten actual API GETs and ten actual UI GETs** returned current source-validated
  provenance. Four saved query contexts use the new recorded metadata without
  upgrading an old refusal. All 37 metadata spans and 34 historical TAC spans
  match exact source text.
- Verified bindings: **949** final preparation, **952** preview, **955** application
  and **958** per review. Independent exports are byte-identical for report, HTML
  and manifest. Static review has ten document rows, one search input, no writable
  forms and **12 existing local links**. Exact configured-credential scanning over
  **34** final prepared/preview/application/review/API/UI files finds zero matches;
  keys were not printed. The stage34 **564-file** source archive verifies.
- A final wheel was built and unpacked into a separate local directory. Runtime
  bridge and legacy source files match the working source; importing them from an
  empty directory resolves the unpacked package and computes the same implementation
  hashes. Existing dependencies were reused; this is not a clean-install claim.
  Final wheel SHA-256: `eb513a78be755d3d95e9a426061f62ad43538f371d78352b07357c4aad0a1605`.
- Preliminary freezes `prepared_v01` and `prepared_v02` were superseded before any
  real preview. Added history-corruption protection, repeated-projection validation
  and complete current-code bindings before final `prepared_v03`. The first full
  regression was interrupted for those software checks and is not a pass. The
  first wheel attempt failed on a sandbox temp-directory permission; the approved
  outside-sandbox build succeeded. Earlier wheels predate final checks and are
  retained as superseded. Generated build files were moved into the stage output.

Limitations:

- Algorithm proposals are now usable recorded metadata, not human-confirmed
  bibliographic identities or accepted scientific results. Missing names/year,
  incomplete bylines and erroneous candidates remain possible. No independent
  precision/recall or full author-list completeness was measured on this exposed scope.
- Only the first two physical selected pages feed the metadata extractor. A cover
  page or an unusual front layout can leave fields unresolved. The adapter did not
  silently widen this limit, guess from filenames/references, normalize raw source
  anomalies or change the legacy priority rules after seeing results.
- Provenance history is deliberately retained after source reselection; stale
  records are not silently reused. Manual metadata without this bridge's source
  record remains recorded data with unknown provenance. Reselection replaces layer
  IDs as before, so new automatic records can be required even with identical text.
- Browser rendering/search acceptance, clean install, other-machine restore and
  independent scientific acceptance are unverified. The prior local-file browser
  restriction was not bypassed. Existing `/answer` generation behavior and provider
  support remain separate and unchanged.

Verdict:

The existing extractor is connected to the main ingestion flow, with durable exact
source provenance and automatic ownership rules. The bounded real backfill is
complete. Further metadata work should use separately defined quality checks and
independent examples, retaining Guo/Choi unresolved states rather than guessing to
make this development scope complete.

## Use and artifacts

Run migrations before deploying the new importer:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

New ingestion, duplicates and text reselection then invoke the bridge automatically.
Open `/ui/articles/{article_uuid}/bibliography` for a recorded source audit, or use
the links in preparation results. No metadata-editing/confirmation form is required.

Local root: `output/records_stage35_20261022/`.

- `prepared_v03/`: final pre-preview protocol/code/input freeze.
- `preview_v01/`: complete read-only proposals, before/after projections and TAC review.
- `applied_v01/`: committed scope, extraction IDs and recorded API-equivalent provenance.
- `review_v01/`, `review_repeat_v01/`: independent searchable HTML/JSON/manifest exports.
- `database_before_v01.json`, `database_state.py`: bounded before-state and content fingerprints.
- `api_ui_v01/`, `postflight_v01.py`, `postflight_v01.json`: API/UI/native-ingestion/
  idempotence/source/database/link/credential checks.
- `wheel_v03/`, `wheel_unpacked_v01/`, `package_qa_v01.json`: final packaging evidence.
- `pytest_target_v04.xml`, `pytest_full_v02.xml`: final successful software regressions.
- `baseline_final_v01/`, `final_qa_v01.json`: final source/dependency snapshot and QA;
  private corpus, database, outputs, weights and credentials are excluded.

Offline re-export, with no new database/model requests, to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.metadata_bridge export --captured output/records_stage35_20261022/applied_v01 --output-dir output/records_stage35_new_review
```

The CLI also has `prepare`, `preview`, and `apply` stages. Applying a frozen preview
requires unchanged sources/current input fields; it is not a bulk unconditional
overwrite. Historical/private artifacts are needed for replay and are not supplied
by a source-only clone.
