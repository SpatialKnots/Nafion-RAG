# Terms persistent review contract v0.1

Historical contract. Since 2026-10-14, the user-facing manual workflow is disabled
by request: [automatic contract v0.2](terms_automatic_contract_v0.2.md). The ledger
and archival helpers below remain for preserving/replaying old work; they do not
drive current automatic subsets or expose a writable Terms form.

Status: local development workflow, 2026-10-13. Independent scientific acceptance
is pending. This contract supplements the inventory, context and classification
contracts; it does not change their outputs or the production retrieval schema.

## Identity and storage

`app/terms/review_store.py` stores decisions in
`data/reviews/terms/terms_decisions.sqlite3`. SQLite application ID is `TREV`,
user version is 1. Numeric review uses a different store and is not migrated.
The current snapshot pointer and append-only event table are local to this store.

A snapshot has schema `tac_terms_review_snapshot_v0.1`; its ID is the SHA256 of
canonical JSON stored as `snapshots/<id>.json`. It contains all source-bound
graph records, the full eight-column TAC table, frozen viewer assets, PDF/PNG
asset hashes, absolute source root, input hashes and policy dependency hashes.
Exact source text, offsets, page, article, selected text layer and original PDF
references remain preserved. Same prepared content gives the same snapshot ID.

Policy binding covers `schema.py`, `contexts.py`, `classification.py`,
`taxonomy_v01.json`, `review_store.py` and `review_projection.py` in `app/terms/`.
HTTP routing, bundle utilities and the live form are presentation/delivery code;
their edits do not automatically invalidate a prepared snapshot. The frozen graph
viewer is part of snapshot content. Stage archives retain delivery code separately.

## Targets and actions

Classification target is one existing assignment ID: one term use, one axis
(`type`, `role`, `origin`). Relevance target is one local term ID across its uses.
Relevance rejection does not delete the term, mentions or classification proposals.
Separate article uploads and repeated uses retain their separate identities.

Each request declares snapshot ID, target kind/ID, expected target revision,
action, categories, reason, reviewer and `reviewer_kind` (`human` or `assistant`).
Reviewer identity is self-declared, not authenticated. A saved human declaration
does not establish independent scientific acceptance.

- `confirm`: classification categories must be existing substantive proposals;
  relevance confirms the local term's relevance.
- `correct`: classification explicitly selects substantive taxonomy categories.
- `reject`: rejects an assignment or the term's relevance; no category payload.
- `uncertain`: records an unresolved review decision; no category payload.
- `restore`: references an earlier revision of the same target in the same
  snapshot. It appends a new event carrying that revision's effective action and
  categories, with a new reason and reviewer. Earlier events remain intact.

Empty reason/reviewer, unsupported categories, invalid targets and unsupported
restore references fail explicitly. Classification and relevance remain separate.
No taxonomy/category or extraction algorithm is silently amended by review.

## Concurrency and source checks

Writes use `BEGIN IMMEDIATE` and require the submitted expected revision to match
the latest target revision. A competing edit receives HTTP 409; the form retains
the unsaved reason. Every saved event contains source fingerprint, timestamp,
revision, prior event hash and event hash. SQL triggers reject event UPDATE/DELETE;
history loading validates each target's revision/hash chain.

Before a write, snapshot bytes, active snapshot identity, bound policy code and
the target's physical original/selected-layer PDF hashes are checked. They are
checked again under the SQLite write lock. Changed/missing sources and historical
snapshots require rechecking. File hashes are checks at particular times, not a
transactional lock on external PDF files. Original PDFs remain immutable by policy.

Preparing changed inputs creates/selects a new snapshot. Earlier annotations can
be inspected as history, but are not transferred automatically. The UI reports
changed input/dependency hashes and added/removed/retained assignment IDs. This
is an identity diff, not an automatic scientific assessment of changed meaning.

The standalone server binds to `127.0.0.1`. POST requires loopback hostname and
peer address, exact same Origin, and a matching CSRF header/cookie. Asset delivery
allows only registered PDF/PNG paths inside the source root and verifies bytes.
No PostgreSQL connection is required by this standalone review server.

## Derived views and exports

Graph `tac_terms_graph_v0.3` derives group membership from decisions without
overwriting original proposal states, basis quotes, sources or candidate records.
The effective view overlays decisions, proposals view shows original proposals,
reviewed view marks targets without decisions explicitly. Rejected assignments,
rejected terms and uncertain uses remain visible in separate groups. Category
counts are distinct local term IDs; one term can belong to several groups through
different uses. Circle area follows the derived group count.

Queues select conflicts, unknowns or all assignments without a conclusive decision,
per axis, grouped by term. Initially the type-conflict queue contains 17 terms.
Uncertain decisions remain in the pending queue. This is a classification queue;
relevance is selected separately in the term form.

Global SQLite event ID provides a revision cutoff for reproducible derived views.
Full ledger export records snapshot identity, input bindings and event history.
Subset JSON records member IDs, input hashes and cutoff; use the full ledger or
backup together with it to replay reviewed membership. Static HTML has no writable
review form; the local HTTP workbench saves decisions. TAC exports retain the
agreed eight columns and append review annotations within existing Terms content.

## Backup and recovery

`backup` uses SQLite's consistent backup API, then includes the captured ledger,
all referenced frozen snapshots and an inventory of hashes in ZIP schema
`tac_terms_review_backup_v0.1`. Original PDF/PNG files remain external. `restore`
requires an empty destination and validates archive paths/inventory/checksums,
snapshot identities, SQLite integrity, event chains and source fingerprints.
It also validates the restored current snapshot pointer.

Backup is portable as review data, but source root paths are absolute. Another
machine needs the original files at the expected paths, or a newly prepared
snapshot; decisions are not automatically rebound. Restarting the server preserves
decisions in SQLite. Hash chains diagnose accidental corruption; they are not
cryptographic authentication against someone who can rewrite the entire store.

## Changed / Tests run / Limitations / Verdict

Changed: immutable snapshots, separate SQLite decisions, source checks, revision
conflicts, append-only restore, derived graph/TAC views, backup/restore and local UI.

Tests run: see [TAC stage12 report](tac_stage12_review_2026-10-13.md), including
real-browser competing edits and real process restart/backup recovery.

Limitations: declared reviewer identity, local workflow, external originals;
independent science review, scientific relations and production integration remain open.

Verdict: persistent review contract implemented for frozen local TAC sources.
