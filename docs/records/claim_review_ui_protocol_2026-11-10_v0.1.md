# Explicit claim/evidence review UI v0.1

10 November 2026, Asia/Yekaterinburg. User requested the next step after offline
claim checks. Scope: a readable, explicit inspection UI and thin API around the
existing checker. Do not change inference, source recipes, admission, retrieval,
context budgets, DB/PDF/index, old schemas or checker behavior. No model/OAuth,
slots, ingestion, automatic context actions, server persistence or deployment.

Freeze current app Python/YAML/protocol/controls and replay five current plus76
old service cases/five unsent native bodies before app edits. Preserve dirty work,
old outputs and failures. New code is opt-in through new routes only.

Routes: explicit POST /answer/prepare/requirements/packet/checks takes existing
PreparationRequest fields plus a required pinned expected_packet_id and strict
bounded structured claims. Reprepare through the existing read-only packet path;
the client cannot supply parent, packet, sources, reports, paths or scientific
decisions. Reject a changed packet with HTTP409; no silent rebasing, retry, merge
or weaker checks. A supplied packet/report hash is a binding, not authenticity.
The original checker and packet contracts remain unchanged. Return a separately
versioned canonical review capsule binding packet, claims, report and UI code.

GET UI shows a preparation form and preserves the selected library/cookie. POST
first explicitly prepares sources without assertions. Show existing source facts,
quotes/refs and unknowns as a catalog, not generated claims or a validated answer.
The advanced structured-input form submits explicit JSON assertions and a pinned
packet ID; it does not parse answer prose or auto-select claims. Browser form scope
must preserve collection, top_k, method, answer style/language and library.
No claims/report upload is treated as trusted evidence. Empty assertion lists
stay no_claims, not approval. Reject malformed/duplicate JSON keys, schema/budget
violations and foreign refs before processing a report. UI errors retain caller
input safely escaped and never display a successful stale result.

Render readable claim values, conditions/status/unknowns beside exact source
quotes, page range, text layer and available title. Keep literal, finite semantic,
arithmetic and scientific-validity statuses separate. Show field differences,
alternative/uninspected/role-identity limitations and inherited blockers. Render
exact page links only for proven packet page mappings, otherwise a source-range
link explicitly without claiming an exact page; missing titles remain unknown.
Use registered article routes, never file paths from client/embedded data. PDF
links must preserve original vs selected layer distinction. Exact text and
technical refs/JSON remain expandable. No arbitrary HTML/JS, actor attribution,
human confirmation or writable decision forms. Journal is deterministic system
observations, not human review; show source-bound observations and stop reason.

Use a separately bound canonical capsule/replay for UI adapters; validate from
trusted fresh packet/claims and pinned IDs before rendering. Keep old packet and
checker code bindings intact; only main router/navigation drift is expected.
Existing archived snapshots with navigation hashes may be stale: preserve them,
never migrate/overwrite or advertise them as current.

Controls: complete/mismatch/ambiguous/unknown/no-claims and unsupported cases;
Unicode/dehyphenation, escaping of all input/ref/title/source/attribute surfaces;
valid/missing/cross-page PDF mappings and source-layer links; invalid/injected
requests and forged/stale packet/report/capsules; library/cookie and every scope
field; bounded input and error round trips; no provider/context-action calls.
Run affected tests/Ruff/full app mypy, compare81 complete results/five native
bodies, and preserve canonical UI capsules/runtime fragments. Generate local HTML
review reusing33 TAC/eight columns/existing PDF links with explicit inherited
audits. Static HTML verification is not browser visual verification. If supported,
inspect the new actual HTTP UI on a local synthetic test app; do not bypass the
earlier file:// denial for archived review HTML. Stop if browser policy denies.
No fresh DB preparation, real SQL or live model behavior is implied by seams.
