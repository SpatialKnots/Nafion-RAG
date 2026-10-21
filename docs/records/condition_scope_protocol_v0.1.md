# Condition scope overlay v0.1

21 October 2026, ARIADNE stage25. Separate offline `records_condition_scope_v0.1`
over the frozen stage24 roles and stage23 source registry. No model calls.

Preserve all existing candidates, schemas, checks, review states, source text,
old role proposals and outputs. Verify parent manifests, code, inputs, original
PDFs, native artifacts and regenerated geometry. Recompute stage24 projections
and require exact equality before proceeding. Copy both parent reports byte for
byte. No database or production/review-store writes.

## Bounded source policy

Use every declared slot and candidate version, including missing and unresolved
cases. This policy concerns selections in temperature, method, preparation and
conditioning; names or model notes do not determine scope. Preserve selected
occurrences and identify their source context separately.

For the registered same-article non-table source, split exact text into clauses
at sentence-ending punctuation followed by whitespace and an uppercase/parenthesis
start, or at the region end. Decimal points do not create boundaries. Never join
another source block or repair hyphenation. Retain unsupported clauses and the
incomplete final clause, including the parent's boundary diagnostics. Complete
interior clauses may be scoped even though the whole source region is incomplete.

Recognize only anchored literal Russian cues: conductivity was measured;
preparation of electrodes and assembly of cells; samples were held before
measurements; measurements in symmetric cells; impedance instrument used.
All are development source-scope proposals, never independent semantic validation.
Unknown or negated/reported cues are unsupported rather than guessed.

A selected full complete recognized clause, impedance-method phrase, cooling
schedule, or preparation-atmosphere phrase can propose its clause's scope.
No normalization or numeric conversion occurs. A cooling schedule within a
measurement clause proposes measurement_protocol, even if selected as conditioning.
An argon/dry-box phrase within an electrode/cell preparation clause proposes
preparation_procedure, never a measurement environment. A table title adjective
such as plasticised does not supply a preparation procedure. Conditioning requires
its own explicit before-measurement cue; do not infer conditioning from cooling.

An exact printed temperature substring of the bound conductivity column header
proposes measurement_temperature. Other columns, identical values elsewhere,
general method temperature ranges and stability tolerances cannot substitute.
Preserve original selected text and table-header context without numeric parsing.

Selections crossing multiple clauses stay ambiguous; selections in the incomplete
tail retain incomplete_source. Unrecognized fragments remain unassigned, with
exact evidence. Missing fields remain missing even where source opportunities
exist. Do not expand candidate context availability to fill fields.

Each projection accounts for all four legacy fields exactly once, contains an
unchanged candidate fingerprint and uses a strict standalone schema. Proposed
scopes are measurement_temperature, measurement_protocol, preparation_procedure
and conditioning_procedure. A source event also may describe measurement_setup
without automatically creating a candidate binding. Every binding's per-result
applicability and all scientific support/admission remain not_evaluated.
Measurement environment and equilibration completion remain unknown. The clipped
phrase after attainment cannot establish equilibrium or a waiting duration.

## Validation and artifacts

Test misleading field names/notes, cooling versus conditioning, preparation
atmosphere versus measurement, literal temperature cell identity, repeated text,
negation, incomplete and multi-clause selections, missing fields, source drift,
duplicate/lost selections, strict scientific states and frozen-parent failures.
Run targeted tests, full regression, Ruff and mypy. Export separate JSON/schema,
source-event catalog and searchable read-only HTML for all 42 slots / 37 versions,
with old material roles, exact contexts and PDF/native links. Repeat export and
compare bytes; verify hashes, links and source-only snapshot. No independent
precision/recall or whole-article extraction claim follows from these checks.
