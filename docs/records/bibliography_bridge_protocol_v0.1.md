# Registered TAC metadata bridge v0.1

Stage35 prospective protocol, 22 October 2026. `registered_tac_metadata_v0.1`.

Reuse `scripts.tac_metadata.extract_article` and `validate_metadata` unchanged.
Register existing selected physical PDF pages 1–2 using stored page/layer IDs,
original/selected PDF hashes and exact full text; require current PDF extraction
to match. Supply empty TAC sections explicitly, using the existing metadata-only
front-title fallback. No new heuristics, filenames, PDF creation dates, reference
list guesses, external metadata lookup or generative API calls.

Add migration `0006_metadata_extractions` with an append-only proposal/projection
history table, monotonic database identity, input/code/payload hashes and exact
source evidence. Existing article column types stay unchanged. In one transaction,
fill empty authors/year/journal fields from `proposed` outputs. Preserve existing
nonempty values. Refresh/revoke only automatic values matching the latest stored
managed projection; a divergent value is preserved. Ambiguous/not-found cases
remain explicit and unfilled. No output becomes independent bibliographic or
scientific confirmation. A repeated unchanged refresh creates no extra record.

Call the bridge after ingestion and text reselection, and on duplicate imports
without rechunking. Metadata errors propagate through existing ingestion failure
handling. Callers retain commit/rollback ownership. Original PDFs and selected
text/chunk behavior remain unchanged. No vector scoring or threshold changes.
Package the existing scripts needed by the runtime bridge. Provide read-only
JSON/UI provenance links; stale/mismatched source/payload data must fail visibly.

Bounded real scope: the ten unique articles selected in stage34's four native
results. Freeze their parent manifest/source snapshot, exact source/proposed
metadata and existing fields before mutation. Apply the additive migration, then
prepare a read-only preview and review for every scoped document. Apply only
these frozen proposals atomically, rechecking sources and existing metadata under
article locks. Retain before/after values and verify idempotence, exact source
spans, API/UI provenance and all unrelated article/chunk/page/index contents.
Do not tune the extractor after outcomes. Other existing articles are not bulk
updated; future imports use the bridge automatically.

Produce a local searchable HTML table with Title, Authors, Journal, Year,
Abstract, Conclusions, Terms and original-file links for all ten documents.
Reuse full historical TAC section proposals only when their exact PDF/text/layer
evidence still matches current registered sources; identify their separate frozen
algorithm/input, do not present them as newly extracted or human confirmed.
Terms are not recomputed in this integration; label that explicitly. Preserve all
metadata proposals, alternatives, unresolved fields, diagnostics and exact quotes.

Constructed tests cover legacy equivalence, source/payload drift, ambiguous output,
existing/manual field preservation, automatic refresh/revocation, idempotence,
immutable PDFs, duplicate ingestion and error propagation. Validate the PostgreSQL
migration, runtime packaging and full regression. None establishes independent
scientific precision/recall or browser acceptance.
