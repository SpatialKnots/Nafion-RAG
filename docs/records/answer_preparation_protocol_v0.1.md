# Answer preparation integration protocol v0.1

22 October 2026, stage31, `answer_preparation_v0.1`.

Integrate the unchanged `query_qualifiers_v0.1` as an explicit preparation mode:
new POST `/answer/prepare`, GET/POST `/ui/answer/prepare`, and discovery links from
the home/answer pages. Do not modify `/answer` or its existing request/output
contract, provider, adequacy threshold, selection or retrieval score. Declare the
new preparation JSON version, status and diagnostics explicitly. This stage is an
integration check, not a new scientific extraction or independent evaluation.

The mode uses actual `answer_question` retrieval/selection and captures its full
selected Evidence via the existing observer. A provider with no transport/credential
stops at a dedicated exception before generation. A baseline insufficiency return
is retained. Only that explicit boundary is caught; errors propagate. Start a
fresh PostgreSQL repeatable-read/read-only transaction and disable autoflush.
Do not write corpus, PDFs, metadata, indices or records. Session dependency closure
rolls back; there is no commit or fallback to paid generation.

Reuse existing source-registry collection, exact page alignment and complete-page
detection. Preserve every selected Evidence field and text; collect original/PDF
hashes, page/layer identities and diagnostics without repairs. Missing/unproven
registries, complete registered pages, old insufficiency, failed necessary-mention
checks and a 100000-byte canonical question/evidence bundle ceiling block checks.
No truncation or compacting. `checks_passed` means necessary local checks only;
`network_ready` stays false, no external request is constructed in any case.
Byte counts refer to that evidence bundle, not the larger local HTTP response,
tokens or a formatted model request. No generation-enabled flag is supported.

Article author/year inputs now come from the same read-only database snapshot,
with original raw fields retained. Finite author mapping uses exact nonempty values
in `name`, `family`, `last_name`, `lastName`; given-name-only or unsupported shapes
stay unknown for surname validation. Any unresolved author entry makes author
coverage unknown rather than silently treating a partial list as complete. Missing
year remains unknown. Metadata presence is not independent bibliographic validation.
These newly read fields do not retroactively fill stage30's missing metadata.

UI shows human-readable blockers, per-article qualifier states, all full evidence,
original PDF links, valid chunk-context links and expandable complete diagnostics.
All source/user strings are escaped. Derived evidence keeps PDF links but has no
fabricated raw-chunk context link. Preserve collection/method/top-k/library choices;
the GET form can inherit the existing library cookie. No automatic generation or
send button follows a result. Existing answer UI remains available separately.

Freeze four exposed stage29 questions/settings, current integration code/protocol/
tests, inherited source bindings and verified local query-cache identities before
real read-only preparation. Execute all four once, without tuning after outcomes;
capture native new JSON and UI result, request and hashes. Use the existing offline
cache, no model download, index rebuild or API request. Compare selected raw
evidence against stage29 as an observation, not a promised identical new retrieval
or an independent accuracy result. Preserve all differences/unknowns.

Constructed tests cover actual service stop boundaries, no provider creation,
source/citation preservation, qualifier/baseline refusal, unknown metadata mapping,
full-page/registry/budget blocking, no raw derived context, API validation and error
status, HTML escaping, form/cookie scoping, unchanged old routes and necessary-check
success without inference. Run full regression, Ruff/mypy, read-only real smoke,
source/cache/input hash checks and source/dependency snapshot. Save all four real
results in separate HTML/JSON review artifacts. Browser acceptance is separate from
static/rendered-response checks; the prior local-file restriction is not bypassed.
No scientific precision/recall, new answer quality, metadata accuracy, independent
pilot, cost saving or clean-machine acceptance is established. Terms remain automatic.
