# TAC complete Terms inventory contract v0.1

Implemented in `scripts/tac_terms.py` for the isolated development pipeline.
Schema: `tac_term_inventory_v0.1`. Existing selected-only schema
`tac_term_candidates_v0.3` remains supported with its original storage semantics.
Neither schema establishes scientific acceptance or production glossary terms.

## Scope and compatibility

Candidate generation is unchanged: frozen T/A/C text, existing glossary aliases,
surface phrase anchors, stopwords, unit and broken-word exclusions, exact source
offset mapping, existing score and stable sorting. No full-text/body/filename or
external metadata inference is added.

The CLI defaults to the existing legacy v0.3 output. New complete storage requires
`--format inventory`; its display parameter is `--preview-limit` (default 12).
The legacy `--max-terms` keeps its meaning and is valid only in legacy mode.
Mixing modes and parameters returns a CLI error before reading source files.
The maximum preview/legacy display setting is still 50; the inventory itself
has no 50-candidate cap. Existing output files are not overwritten.

`validate_terms` explicitly recognizes only these two schemas. Legacy rows
still have `terms` and are subject to their stored-list limit. Inventory rows
have `inventory` and a separately validated `preview`; they are not silently
interpreted as legacy rows. Historical selected-only outputs cannot reconstruct
discarded candidates: complete inventory must be regenerated from the original
frozen profiles and glossary/code/settings.

## Inventory article row

- `article_id`, `original_pdf_sha256`, `original_pdf_path`: unchanged source scope.
- `inventory`: all ranked candidates produced before preview selection, including
  nested surface phrases and candidates beyond the display limit.
- `candidate_count`: equals `len(inventory)`.
- `inventory_sha256`: SHA-256 of UTF-8 JSON serialization of the inventory with
  `ensure_ascii=False`, sorted object keys and separators `(',', ':')`. List
  order is preserved. This detects changes relative to the recorded fingerprint;
  it does not independently prove candidate recall or scientific correctness.
- `preview`: display policy and references described below.
- `status`: `proposed` for a nonempty inventory, otherwise `not_detected`.
- `diagnostics`: lexical scope, source issues and retained nested candidates.

Every candidate retains the existing `term`, `label`, proposal status, methods,
seed concepts, language, score, occurrences and evidence. New fields:

- `candidate_id`: SHA-256 of UTF-8 JSON `[article_id, term]`, with
  `ensure_ascii=False` and separators `(',', ':')`. This is a local lexical ID,
  not a global concept or immutable source-mention ID. Separate uploads have
  separate article scopes; no automatic scientific equivalence is introduced.
- `rank`: 1-based position in the complete sorted inventory.
- `rank_features`: `occurrences_by_kind`, `weighted_capped_occurrences`,
  `token_count`, `seed_match`. The existing score equals weighted capped
  occurrences × token count + the seed-match indicator. These are ranking
  components, not confidence probabilities.

Evidence preserves containing section/page boundaries, exact quote offsets,
selected layer/type/ID, page-text hash, source type and inherited TAC boundary
assessment. A matching quote does not establish semantic relation or correctness
of the source glyphs. Evidence occurrences can overlap across different candidates;
their aggregate count is not a count of unique physical source fragments.

## Preview selection

Policy: `legacy_greedy_surface_v0.3`. Scan the unchanged ranked inventory:

1. If a candidate is a nested/inclusive surface phrase relative to an already
   selected candidate, mark it `nested_surface_suppressed` in preview only.
2. Otherwise, select it if the display limit is not reached.
3. Otherwise, mark it `preview_limit`.

This reproduces the existing selection, including its comparison only against
already selected phrases. It does not produce a general phrase-containment graph.
Changing the preview limit may change preview decisions, but never stored
inventory/quotes/identities/ranks or its fingerprint.

`preview` stores `limit`, `policy`, ordered `candidate_ids` and one decision per
inventory entry. Each decision has `candidate_id`, `state` and
`against_candidate_ids`; the latter reference the selected phrases involved in
surface suppression. The validator recomputes the policy and checks these exact
references, rather than trusting submitted display annotations.

## Validation

Validate input hashes, article inventory/PDF identity and inherited profile source
spans. Check every candidate, including hidden ones: uniqueness, proposal state,
allowed generation methods, finite nonnegative score, source-derived label,
exact quotation/layer/offsets, occurrences, ID, rank features and duplicate evidence.
Inventory count, fingerprint, rank order and preview policy/references must match.
Unknown schema versions, corrupted hidden evidence and fabricated preview choices
are rejected. No successful validator run creates human acceptance.

Completeness relative to the generator is also checked by replaying the same
frozen input in the development audit and comparing its original pre-selection
candidate counts. A maliciously rewritten self-consistent artifact is not made
trustworthy by its own hash; authoritative inputs and saved manifests remain needed.

## HTML behavior

Keep all eight TAC columns and the existing source/boundary diagnostics. The Terms
cell reports the full count and preview count. Selected candidates appear first;
remaining candidates retain their complete-inventory order and are available in
groups of 50. Their cards show source evidence and reasons for omission from preview.

Remaining cards are encoded in HTML templates, materialized when their group is
opened. The complete candidate labels/matching strings are present in the search
index before materialization; table search can find a hidden candidate. Opening
a group repeatedly must not duplicate cards. Global expand materializes all groups
and opens their text; collapse retains all data and closes the controls.

The HTML remains a read-only review artifact. It does not save decisions, assign
semantic categories or scientifically accept relations. Render-on-expand reduces
initial live DOM nodes; it is not compression or an unmeasured latency guarantee.
