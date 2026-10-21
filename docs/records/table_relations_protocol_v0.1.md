# Table relation evidence audit v0.1

21 October 2026, ARIADNE stage23. Offline audit only; zero new model calls.
No candidate rewrite, admission, review-store change, normalization or unit change.

## Scope and immutable evidence

Audit all table candidate versions from stage20 kayumov_table, all four stage21
cases and all eight stage22 cases. Include every record identity in the final
42-slot ledger, including the deliberate revisit. Non-table stage20 abstract,
prior-work and method-only cases are outside this declared audit scope.

Verify inherited preparation/code/PDF hashes and each run's artifact manifest.
Replay the 13 table native responses, compare exact reply/records/regions/
unresolved output and source-cell bindings, and reconcile the complete identity
set with the final ledger. Regenerate the base cell ledger from the frozen stage19
line geometry and compare all source fields. Fail on drift or missing history.
Original PDFs and all frozen stage20–22 modules/outputs remain immutable.

## Versioned evidence rules

These are source-coordinate and literal-cue diagnostics, not an independent
scientific reference or new acceptance rules. Retain a separate scientific
support state of not_evaluated/unknown for every candidate, even when all
coordinate checks match.

- Preserve the existing exact sample/value/temperature/unit cell binding.
- Locate a unique printed `пластификатора` header line in the protected group;
  its horizontal interval defines the composition column. Locate the unique
  `(масс. доли)` basis line in that column. Missing/ambiguous headers yield
  unsupported diagnostics, never a guessed column or unit.
- Associate a row composition line only within its sample block, with center in
  the composition-header interval and positive y overlap with the sample label.
  Multiple sample labels in the same PDF block remain unsupported/shared.
- Recognize literal section cues `Индивидуальные растворители` and
  `Смеси COMPONENT/COMPONENT[/COMPONENT]` in the protected table. Use the unique
  nearest heading physically above the row as a geometric group proposal. Ties,
  missing cues, unrecognized syntax or unknown geometry stay unresolved. Preserve
  printed component order; do not expand abbreviations or infer chemical identity.
- Compare actual raw token selections with the row composition cell, its proposed
  component group and the printed mass-fraction basis by source coordinates,
  never by first occurrence/string equality. A pure-solvent code is not silently
  converted into a numeric fraction. Missing candidate fields remain not_proposed
  even when a possible source cell exists.
- Report the source label as plasticiser composition only. Mapping to external
  measurement environment, final membrane composition or exact specimen identity
  remains scientifically unknown; model notes are not confirmation.
- Check whether the medium_composition field's cited evidence separately covers
  the sample label, row composition, plasticiser header, fraction basis and
  mixture group where applicable. Missing cited endpoints are an evidence-chain
  diagnostic, not proof the relationship is false or absent from other fields.
- For a present method, require a same-article source region on a different page
  from the table and a literal `импедансной\s+спектроскопии` cue in its actual raw
  selection. Unknown wording yields unsupported, not a claim of incorrect science.
  Method applicability remains unknown; the registered selected method block's
  incomplete sentence boundary is retained explicitly.
- For sample_value, property_value and conditions_measurement, check whether the
  role's exact cited coordinates cover its selected endpoints (sample/value;
  property/value; temperature/value plus method when proposed). Coverage does not
  prove scientific support. Missing endpoint fields remain unresolved, and a
  missing role remains not_proposed.

Record all expected and observed exact spans and each outcome's reason. Do not
replace old readiness/check results. Do not turn audit differences into required
per-case user decisions, writable resolution forms or independent gold labels.

## History and reproducibility

Keep all 42 slots and every candidate version in a searchable local HTML table.
Include exact sources, original PDF page links, raw selections, old checks,
new diagnostics, method boundary and input/code versions. Add a separate history
comparison for cells with multiple candidates: show changed field statuses and
coordinates, together with changed source contexts. Different proposals/contexts
are not automatically conflicting facts or independent measurements.

Test identical ratios in different rows/groups, swapped group component order,
mass-percent versus mass-fraction columns, partial/broad selections, missing and
ambiguous source cues, shared blocks, absent fields, unrelated method-region
text, wrong/missing linkage endpoints, native replay mismatch, source drift and
history loss. Preserve deterministic exports and a source-only baseline snapshot.
Verify complete 42-slot/candidate coverage, all local links and exact source text
statically; browser acceptance requires a separate observed check.

Independent scientific annotation, semantic correctness, method applicability,
experimental identity, accuracy and whole-article completeness remain open. This
audit must not be described as those evaluations being completed.
