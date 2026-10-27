# Istomina DSC source context v0.1 — stage47

27 October 2026. Prospective source-packet construction only, implementing item 1
of the agreed pre-API plan. Admission evaluation, provider requests, API probing,
model output, runtime integration, new retrieval/OCR and database access are out
of scope. No source file, old artifact, selection, threshold or schema is edited.

Use the frozen stage46 v0.2 run, exact original DSC question, separately registered
Istomina PDF and first-page header identity anchors. Verify the entire parent
manifest and live PDF hash, and re-extract pages using the unchanged ingestion
extractor. First-page and physical-page-4 text must match stage46 exactly.
The article/capture layer IDs remain local, not newly claimed database records.

Keep four bounded identity contexts from page 1 (title, full byline, publication
quote, DOI context) and one complete page-4 methods context: from the unique
`2.4. Thermal Analysis` heading up to, excluding, unique `2.5. Wide-Angle X-ray
Diffraction (WAXD)`. A missing/repeated/reordered heading or identity anchor fails
loudly. Never crop the methods paragraph, normalize units, signs, ligatures,
whitespace or temperatures, interpret numeric values, or borrow WAXD/AC conditions.
The fixed boundaries are exposed source-development choices, not a general
section detector or independent quality annotation.

The new versioned wire contains the exact question and five citation contexts,
their roles, article/PDF/page/layer identities, source-region IDs and absolute
Unicode offsets. Absolute local paths and whole page text remain in a separate
SourceRegion registry. Original text, full two-page capture, retained block bbox
overlaps and selection boundaries remain inspectable locally. Every wire quote
must equal its entire registered region, not a shortened paraphrase.

Reuse existing full-page literal/decoded guards and interval-union coverage guard;
enforce the existing 100000-byte ceiling against the actual saved UTF-8 wire.
These are source-packet invariants, not readiness/admission or scientific quality
assessment. Keep all old DSC blockers separately as history. Current network_ready
is false; API remains prohibited. Sample identity, per-result applicability and
scientific acceptance remain unestablished. No requirement to manufacture those
links is introduced.

Prepare/run/export freeze code, original inputs, installed runtime and expected
full methods-span hash before packet outcomes. Require exclusive output paths,
source/code/PDF drift detection and deterministic exports. CLI denies audited
CPython connect/DNS/sendto operations before application imports and records
attempts/completion, including failure. This is not an OS/native-network firewall.

Source checks require all five exact regions and complete heading-bounded methods
text. Constructed tests challenge wrong/repeated identity, truncated/reordered
sections, foreign page/layer identity, modified quotes, full-page union, byte
ceiling, changed inputs, overwrites and escaping. Checks are exposed development
evidence, not independent scientific gold or measured accuracy.

Produce searchable local HTML with full expandable citations, source spans/bbox,
actual wire, diagnostics and PDF links. TAC scope is the single registered article:
Title, Authors, Journal, Year, Abstract, Conclusions, Terms, Original file. Show
raw identity proposals and full first-page source evidence; mark unimplemented
TAC/Terms fields explicitly. Preserve stage46 metadata and other questions; no
XLSX or per-Term review workflow. Inspect the decisive PDF pages and HTML, test
an actual PDF click, compare repeat exports, and report actual test outcomes.
