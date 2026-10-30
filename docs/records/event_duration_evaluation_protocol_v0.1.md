# Offline event-duration comparison v0.1

Scope: inspect the three already exposed, rejected GigaChat event-pilot replies.
No API/OAuth, DB, retrieval, embedding, model generation, request preparation,
slot reservation or runtime integration. Preserve original schemas, parsers,
raw bytes, failures, PDFs, all historical artifacts and closed budgets.

This stage implements evaluation infrastructure, not semantic extraction.
Reference annotations are assistant-authored, post hoc and preliminary. They
consume the same exact excerpts and frozen lexical duration inventory as the
pilot. An exact operation anchor identifies each annotated atomic operation;
each duration atom is assigned to one annotated owner or explicitly left
unannotated. Distinct owner IDs mean separate atomic operations. An operation
may own multiple atoms. Absence means absent in this selected excerpt only.
No inference about absence across a page, article or corpus is permitted.

Validate source hashes, raw anchors, operation IDs, the complete annotated /
unannotated atom partition and duration-state consistency before evaluation.
Use the unchanged v0.1 parser for the original acceptance/error. Inspect raw
duration selections separately, without filling diagnostics, normalizing IDs,
changing status or accepting rejected replies. Native filtered/incomplete,
malformed or structurally invalid content must not receive semantic comparison.
Invalid duration/context selections remain unscored. Unrelated field failures
remain visible; a raw duration comparison does not validate an entire event.

For the target, compare its selected atoms against the explicitly annotated
target owner: distinguish missing expected atoms, atoms of another operation,
unannotated atoms, and an absent-duration status disagreement. For every event,
report selections spanning multiple annotated operations, including values in
the same source statement. Repeated duration selection across records is a
diagnostic, not independently a scientific error. Do not infer operation identity
from model kind, shared contexts, numeric equality or statement adjacency.
Do not score unannotated atoms as negatives or turn agreement into accuracy.
Sample identity, method, units/bounds interpretation, conditions, coreference,
event completeness and question semantics beyond the supplied target annotation
remain unevaluated. No automatic scientific acceptance is possible.

Deliver a separately versioned report and searchable HTML for all three cases,
all raw replies/catalogs/reference labels and exact full registered pages, plus
all three source works in the existing eight TAC columns and local PDF links.
Bind code/tests/protocol, annotations, native replies/catalogs and original
source identities. Verify original parser rejection equality and raw manifests;
prohibit socket operations during the runner. Independent annotation and a
separate evaluation set remain prerequisites for reliability claims.
