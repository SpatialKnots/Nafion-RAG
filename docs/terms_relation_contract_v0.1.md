# ARIADNE experimental automatic relation pilot v0.1

Date: 2026-10-14. Engineering contract, not scientific acceptance.
Implements a bounded portion of the [relation pilot scope](terms_relation_pilot_scope_2026-10-14.md).

## Sidecar and endpoint contract

`scripts.tac_term_relations` produces a new immutable JSON sidecar with schema
`tac_term_relations_pilot_v0.1`. Input bindings include frozen corpus, profiles,
inventory, contexts, classification file hashes and relation-algorithm file hash.
Canonical content hashes bind context/classification content; the embedded policy
has its own version/hash. Every article in the declared input remains represented,
including articles without recognized templates.

The experimental algorithm supports only explicit `property of object` and
`property [was] measured by/using method` templates. The subject must be a uniquely
classified property. A proposed object must be a uniquely classified material/
object for `property-of`, or method for `measured-by`. Both endpoints are existing,
disjoint exact TermUses in the same selected A/C context and sentence. Direction
is property → object/method. Maximal existing endpoint spans take precedence;
unsupported compound endings are deferred rather than replaced with a known root.

Every recognized template produces `proposed` or `deferred`, with diagnostics.
A missing endpoint has a null object ID and never an invented TermUse. No new
source-span method endpoint is introduced. Unknown/ambiguous types, non-pass TAC
boundaries, title-only text, citation/hypothesis/future/negation cues, comparisons,
models/derived wording and object/procedure lists cause abstention. Unrecognized
templates produce an explicit article-level diagnostic. They are not a negative
claim about whether a scientific relation exists.

Each record retains predicate, endpoint IDs/exact labels, Context ID, a complete
source-bound local evidence fragment, offsets/page/layer/PDF/text/quote hashes,
reason, diagnostics, automatic producer and `human_confirmation=false`. Relation
identity binds payload and frozen inputs. Reproduction validates classification
assignments first; a matching quote or arbitrary edited type is insufficient.
The validator rejects any output that does not reproduce, including edited
direction, IDs, evidence, policy or input bindings.

## Presentation, persistence and rollback

Optional `tac_terms_review prepare --relations` validates the sidecar before
embedding it as `graph.relation_pilot` and adding read-only diagnostics inside
the Terms column. The existing eight main columns are preserved. Every row has
a pilot section. No production table, manual-event schema or writable relation
router is added. Current Terms categories/subsets do not depend on relations.

The prepared snapshot and backup include the embedded relation output, policy,
input bindings, table and source definitions. Original PDFs remain external and
immutable. A changed relation-algorithm hash is diagnosed as stale. Earlier
sidecars/prepared snapshots remain separate files. The existing store backup
includes the current snapshot and snapshots referenced by its historical ledger;
it is not a backup of every experimental output directory. Separate development
artifacts and run manifests must be retained for earlier zero-event runs.

Rollback: prepare the same validated classification without `--relations` and
use a new snapshot. Classification/retrieval behavior is unchanged; prior relation
artifacts remain inspectable. Disable only the separate CLI/pilot input, without
deleting original PDFs, source contexts or historical snapshots.

## Scientific limits

This grammar does not establish measurement-method suitability, direct versus
derived numerical quantities, sample identity, experimental completion, accuracy
or cross-article equivalence. Guo's combined modeling procedure and missing method
names are not repaired; no Abstract-to-Conclusions joins are attempted. Flat TAC
does not provide a general table/footnote/bibliography parser. All unsupported
cases abstain or remain outside the recognized templates. No precision/recall,
independent gold labels or scientific acceptance threshold is asserted.

The observed run and executed checks are in
[stage16](tac_stage16_relation_pilot_2026-10-14.md).
