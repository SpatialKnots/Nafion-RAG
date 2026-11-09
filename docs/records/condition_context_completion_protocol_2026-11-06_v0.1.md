# Bounded condition context completion v0.1

User authorized point 3: complete missing source context before answer generation.
This stage has no live model/OAuth allowance and no new reservations. Historical
sources, requests, outputs, reference answers and guards remain immutable.

Initial production scope: Li-Nafion equilibrium swelling/enthalpy queries already
recognized by requested_context. Require a body-qualified table in selected
evidence, exactly one qualifying article/text-layer, and a preceding methods block
with explicit membrane/sample, lithium exchange, equilibrium swelling measurement
and initial solvent-water reporting. Methods must occur in that order in an
experimental section. Other explicitly named ion forms in this block, negative or
future measurement cues, or multiple distinct qualifying method blocks remain
unresolved. This finite grammar is development evidence, not semantic validation.

Fetch only the same collection/article/source type/text layer, with all original
search filters, in the two pages preceding the table start through the table start.
Only chunks fully inside that range; deterministic order and at most 12 rows plus
one overflow sentinel. Overflow fails closed. Reject wider chunks and scopes.
Prefer existing selected context; otherwise append at most one unchanged raw
chunk. Among overlapping copies of exactly the same recognized methods block,
choose shortest raw chunk, then page range/chunk ID. Distinct blocks fail closed.
Do not evict selected evidence or alter scores, ranking, retrieval top_k, tables,
stored source types, public top-level response fields, units or gate thresholds.
Generation may have at most one additional evidence object; disclose this budget
and raw SHA/offset support, loader candidates and scope decisions in versioned
metadata. Existing citation numbering remains stable.

Do not propagate numeric values to another method, sample or table row. Context
availability/finite attachment cues do not establish experimental ownership,
performed status, table completeness or scientific answerability. The ordinary
answer gate still runs; no new universal fact parser or paraphrase work (point 4).

Validation: constructed positive/negative/scope/ambiguity/overflow controls, SQL
scope inspection, actual service and native unsent boundary on the five frozen
question-only cases, previous exposed 76-case regression inventory, raw bindings
and actual prompt context, fresh read-only Q03 preparation/rollback with network
and gold-read guards. No references enter inference. Preserve failed attempts.
Run affected tests, Ruff and app mypy. Review links must use registered PDF paths.
Any coverage comparison is source availability, not independent scientific quality.
