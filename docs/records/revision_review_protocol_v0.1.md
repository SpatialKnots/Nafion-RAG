# Full-record revision and review protocol v0.1

20 October 2026. Separate experimental S10–S12 store and local editor. This is
not a Terms workflow, independent annotation system or scientific-admission
engine. Existing candidate schemas and production services remain unchanged.

## Storage boundary

Initialize a fresh directory from a declared list of saved candidate bundles,
including empty inputs. The existing stage14 exporter verifies and freezes the
baseline there. Original PDFs and historical extraction files remain read-only.
A SQLite database has its own application/schema identifiers, immutable-event
triggers, a baseline/context hash, per-record revision numbers and hash chains.
No production PostgreSQL tables or Terms ledgers are modified.

Revision zero is the original candidate. Each edit, decision or restore appends
a complete candidate/check/decision event with actor, declared actor kind,
reason, UTC timestamp, previous-event hash and context identity. A serialized
SQLite write transaction compares `expected_revision` before saving. Unknown
records, altered evidence, changed PDF bytes, changed baseline/code/schema,
invalid action payloads and stale revisions fail with explicit diagnostics.
Read operations do not initialize or repair a missing/damaged database.
Hash chains detect accidental alteration, not authenticated malicious rewriting
or deletion of a complete terminal history by a database administrator.

## Editing and review states

Edits may change observations, representation, linkage and optional work-group
proposal within the frozen source regions. Record/article identity is immutable.
The unchanged candidate contract validates exact source spans and raw strings.
New evidence is resolved by exact source region, exact quote and explicit
one-based occurrence, including overlapping occurrences. There is no fuzzy
matching, whitespace repair, Unicode normalization or new source extraction.
All new revisions rerun versioned technical checks.

The candidate remains `needs_review` and Li-ion confirmation remains
`not_reviewed`. A separate declared review status is `unreviewed`, `confirmed`,
`rejected` or `needs_changes`. Only an explicit human-declared decision can set
`confirmed`; it also requires an explicit source-review attestation and no
failed technical prerequisite. Unknown semantic checks remain unknown. This is
a reviewer assertion, not proof of identity, independent expertise, scientific
accuracy or automatic scientific admission. Assistant-originated events cannot
claim human confirmation. No real human decision is fabricated for the demo.

Every edit/restore resets the decision to `unreviewed`. Restore copies a chosen
historical candidate (including revision zero) into a new revision, never an old
confirmation. Current sources/context are checked again. No history is deleted.

## Local editor and export

A dedicated FastAPI application runs on `127.0.0.1`. It reads only the initialized
store, shows all declared inputs, full source text, registered PDF pages,
fields/statuses/notes/evidence, checks and history. A field editor retains
unchanged evidence spans; new source snippets require an explicit exact
occurrence. Linkage proposals and quantity representation can be edited
separately. Text is escaped and displayed as text. Cookie/header CSRF checks and
allowed local Host/Origin checks protect writes. There is no remote login or
multi-user authentication; actor identity is caller-declared.

JSON exports contain the complete baseline, current revisions, checks, declared
review status, exact source context and complete event history. CSV includes
revision and review metadata plus source-linked JSON references. Formula-like
CSV cells use a documented apostrophe prefix; exact raw strings remain in JSON.
Unreviewed/rejected/needs_changes records remain visible and are never silently
converted to confirmed rows. Exports do not assert scientific admission.

## Planned verification

Constructed tests: edit/reopen/export, unchanged source identities, wrong
article/record/evidence, missing/duplicate linkage, missing required conditions,
stale revisions/concurrent saves, declared-human confirmation constraints,
decision reset on edit/restore, stale PDF/code/baseline, malformed/foreign DB,
event tampering, exact repeated quotes, HTML escaping, CSRF/Origin/Host checks,
registered PDF navigation and export provenance. Separate saved-source demo:
load every stage06 case, perform one clearly labeled assistant development edit
using an exact source substring, restore revision zero, reopen and export. No
scientific confirmation, paid API or fresh extraction is needed.

Independent scientific evaluation, whole-article extraction, numeric/unit
interpretation, production integration and full offline extraction acceptance
remain separate work. This source-preserving editor cannot correct source OCR
by inventing text outside the frozen source contract.
