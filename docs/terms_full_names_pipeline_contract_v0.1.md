# ARIADNE full-name Terms and automatic corpus-snapshot pipeline

Date: 2026-10-14. Extends automatic context policy v0.3. No manual Terms
decisions or human-confirmed state is introduced.

## Inventory and classification compatibility

`tac_term_inventory_v0.2` is an explicitly selected additive inventory mode:
`scripts.tac_terms --format inventory-v0.2`. Legacy selected-only v0.3 and complete
inventory v0.1 remain unchanged defaults for their existing CLI paths. The new
pipeline explicitly selects the enriched mode. Existing lexical candidates and
source occurrences remain; supported full names add candidates/occurrences and
may change rank/preview. Rank remains the existing declared heuristic, not accuracy.

Bounded patterns in `app/terms/phrases.py` recognize full method names, qualified
Nafion/object names and component phrases from selected TAC. They operate on the
existing mapped normalization view and preserve exact original source spans,
line breaks, ligatures, page/layer/PDF/text identity and quotes. No translation,
guessed broken-word repair or acronym-to-full-name equivalence is added. Names
outside the declared patterns remain available as lexical candidates or undetected.
New `TAC_full_phrase_v0.1` method markers and embedded full-pattern policy are
validated separately; legacy schemas cannot silently accept this method marker.

Default classification/taxonomy v0.4 adds full-surface type patterns, explicit
object-preparation/method-conjunction role cues and mobility property names.
Scanning electron microscopy is a method; scanning electron microscope is an
object. The latter is not silently used as a measured-by method endpoint.
Full-surface patterns are available only in the new taxonomy version. v0.1–v0.3
taxonomy files remain unchanged. New categories are still proposals with exact
basis, without sample identity or scientific admission. Unknowns/conflicts and
same-TermUse subset intersections remain intact.

The relation pilot retains its two templates and exact existing endpoint
requirements. New full names can become endpoints only after compatible source
classification. Derived/model-qualified procedures, such as Guo's combined
procedure, are not forced into a direct measured-by relation.

## Automatic rebuild contract

`scripts.tac_terms_pipeline` consumes a local JSON config (example:
`docs/terms_pipeline_config.example.json`) identifying a frozen corpus snapshot
and optional profiles, metadata, boundary audit and glossary. Paths and writable
output/review roots must resolve inside the declared source workspace. The corpus
snapshot's original/selected PDFs must satisfy their frozen checksums.

The input/config/code fingerprint determines rebuild need. Unchanged inputs
validate cached artifact hashes and reuse the prepared snapshot. Changed inputs
are copied into a new run directory before executing fresh subprocesses for
inventory → contexts → classification → relations → candidate preparation → HTML.
Subprocess invocation uses argument lists without shell interpolation. Complete
stderr/stdout accompanies failures; the workflow does not swallow scientific errors.

If profiles/metadata are omitted, existing local TAC/metadata algorithms generate
new versioned outputs. If the snapshot changes and supplied profiles belong to
the previous corpus, old profiles/metadata are retained as input history and new
ones are generated automatically. The previous boundary audit is explicitly
retired; new contexts remain unreviewed, and relations abstain. A malformed
same-snapshot quote is not repaired: validation fails. The run records retired
inputs so this change is visible rather than a silent transfer of acceptance.

An atomic directory lock serializes pipeline writers at the review root. A busy
or stale lock is diagnosed and never silently deleted. Builds use a separate
candidate store. Input/code fingerprints are checked again before publication;
only a fully validated snapshot becomes current. Recognized failures retain the
previous snapshot and are reported. Watch failures are also exposed through
`pipeline_status.json` and the Atlas freshness diagnostics. Unknown exceptions
terminate with their diagnostics rather than a broad exception handler.

`--watch 30` checks the bundle/code every 30 seconds after work completes; logs
remain quiet while status is unchanged. This is a local software watcher, not a
scientific acceptance process. The stable stage HTML remains separate from later
immutable run HTML. Original PDFs and earlier snapshots are never modified.

This boundary is a **frozen JSON corpus snapshot**. It does not directly monitor
the PostgreSQL ingestion tables, discover PDFs, modify retrieval indexes or
produce a live DB snapshot. The upstream ingestion → snapshot bridge remains
separate work. To switch the active corpus, its producer publishes a new snapshot
and updates the config path; Terms stages then execute without per-Term user action.

## Persistence and limitations

The existing review-store backup contains the current prepared snapshot and
historical event references, including embedded classifications/relations/table.
It excludes external PDFs and pipeline config/cache/status. Preserve the separate
run directory/config and stage manifest for complete reconstruction of the pipeline.
Do not claim that a review-store restore alone restarts the watcher.

Coverage remains finite and mostly English. Coarse lexical types and grammar do
not establish measurement suitability, sample identity, completed experiments,
synonymy or independent scientific accuracy. Executed evidence is in
[stage17](tac_stage17_full_names_2026-10-14.md).
