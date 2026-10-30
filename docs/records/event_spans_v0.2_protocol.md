# Exact-span event contract v0.2: offline preparation

Scope: implement a separately versioned contract, prepare twelve unsent GigaChat
request candidates from the unchanged real-excerpt set, and run constructed
contract/source-binding controls. No transport, OAuth, DB, retrieval, embeddings,
slot reservation, purchases, provider/model change or `/answer` integration.
All older source files, schemas, raw replies, failures and consumed slots remain
unchanged. Any later live pilot requires separately declared authorization/scope.

The neutral catalog exposes raw text and token indices with exact character
offsets. Tokens are lexical addresses, not semantic labels. Selecting inclusive
first/last token indices restores the exact raw substring, including internal
line breaks, hyphenation and nonbreaking spaces. Each event identifies one
operation and separate source fragments for sample, method, duration, conditions,
completion criterion, result and exclusion. Multi-operation questions may target
multiple events. There is no inherited two-other-event limit. Relations cite
existing distinct event IDs and exact bridge spans; their meaning remains a
proposal. No values or conditions propagate through a relation.

Native JSON schema and local structural models share definitions for nonblank
diagnostics and status/selection alternatives: present has nonempty spans,
not_found/uncertain has empty spans. Duration-present includes a proposed
relation (exact/range/at_least/at_most/approximate/unresolved); missing duration
uses not_established. Source spans preserve bound cues; the local parser does not
infer or validate their scientific interpretation. `not_found` is excerpt-local.

Local source-integrity checks supplement the schema: exact catalog identity,
strict integer address representation, forward/in-range intervals, ordered
nonoverlapping selections, unique event/target IDs, target membership and valid
nonduplicate relation endpoints/evidence. These checks are not all expressible
in the emitted schema. Native schema validation alone does not imply local
source integrity. Exact selected text also does not imply atomicity, ownership,
sample identity, scientific support, answerability or extraction completeness.
Filtered/truncated/malformed native outputs fail; no output is repaired.

Prepare reference/control fixtures separately from native requests. The twelve
already exposed excerpts retain original questions, preliminary annotations and
open notes. Assistant-authored event fixtures and sparse required/forbidden
source-binding checks are development controls, not model answers or independent
gold. A source-anchor comparator reports unaligned/ambiguous/compound operations
as unscored. Unannotated operations and fields are not assumed negative. Its
field checks do not evaluate target semantics or semantic event relations.

Before any future model run, freeze the fixtures, sparse checks, requests,
schema, code, tests and source hashes. Test wrong-stage borrowing, different
samples/temperatures, lower bounds, criterion versus duration, explicit exclusion,
status contradictions, blank diagnostics, malformed/filtered output, source
drift and invalid IDs/spans. Include a deliberate drying/storage mutation that
remains source-exact and formally valid but violates the annotated boundary.
This demonstrates the limit of the parser; it does not demonstrate automatic
semantic detection without annotations.

Use current model name GigaChat-2-Max and the existing 1200 output-token setting
for unsent candidates; do not infer affordability, provider schema support,
completion under this ceiling or improved model quality from offline validation.
Schema JSON is checked separately using the installed local jsonschema package;
this does not establish which constraints GigaChat supports. No request is sent
and no SHA slot is reserved by these preparation tools.

Deliver a separate JSON report, frozen native candidate bodies and searchable
HTML for all twelve cases and all five works in the eight agreed TAC columns,
with exact source details/full registered pages and working original-PDF links.
Clearly label every constructed output and distinguish contract tests, source
verification, preliminary field checks and independent scientific evaluation.
