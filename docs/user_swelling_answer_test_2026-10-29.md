# User question through the current /answer: maximum Li-Nafion swelling

29 October 2026, Asia/Yekaterinburg. User question, verbatim:
«Какая максимальная степень набухания Li-Nafion при комнатной температуре
задокументирована?» The user explicitly requested a neural answer through the
current answer architecture. One new bounded model/OAuth slot was used; all older
budgets remain closed.

Changed:

- Added a small process-local test wrapper `scripts/user_swelling_answer_test.py`,
  three authorization/provenance controls and
  `docs/records/user_swelling_answer_test_v0.1.md`. Reused the unchanged smoke
  observer/helper with this question/version/protocol. Production code, question,
  prompt/schema, ranking, evidence selection, adequacy thresholds and cache
  settings were not changed. Existing original PDFs and DB/index were immutable.
- Actual in-process ASGI POST `/answer` used `literature`, `hybrid_cross_lingual`,
  top-k 5, `claims`/`auto`, real PostgreSQL repeatable-read/read-only transactions
  and existing offline cached local embeddings/index. Three query variants
  returned 100 result occurrences each before fusion/reranking; these are not
  300 unique documents or proof of exhaustive corpus coverage. Final generation
  evidence: five chunks across three works/eight registered pages.
- Preparation stopped at the production transport boundary, without real OAuth
  or model calls, and froze a 52481-byte native request. Fresh-process live
  retrieval/evidence/source/metadata and native bytes matched preparation. The
  global append-only request SHA slot was reserved before OAuth.
- Exactly one GigaChat POST and one OAuth exchange completed, no retry/fallback.
  Model: GigaChat-2-Max; returned declaration: GigaChat-2-Max:2.0.30.01.
  Existing personal scope, verified TLS, 1200 output tokens and 120-second per-HTTP
  timeout were preserved. Model finish_reason=stop. Provider-reported usage:
  9930 input, 79 output, 10009 total tokens. Monetary cost remains unknown.

Actual system result, unchanged:

HTTP 200, status `answered`, one claim citing `E1`:

> Максимальная степень набухания Li-Nafion при комнатной температуре достигает значения αLi = 1.54.

This is the actual model/system answer, not the assistant's corrected scientific
answer. E1 is the dissertation fragment on pp.96-97. IDs and structural contracts
passed. The raw native reply, full API response and original status are preserved.

Separate post-hoc source inspection:

- E1 p.96 describes `1.54` as a limiting value obtained by regression, compared
  with an experimentally observed `1.536` for N,N-diethylformamide. Temperature
  is not stated in that local paragraph. The displayed E1 citation snippet omits
  `1.54`, although the complete E1 text sent to the model contains it.
- Additional reading of the same original PDF found Table 4.3 on pp.88-89. Its
  header explicitly gives 25°C and a compiled set of 30 individual solvents;
  N,N-diethylformamide has rounded alpha_Li=1.54, with literature references
  [2,228]. These primary reference papers were not independently verified here.
  The table supports a value within that declared solvent set, not a maximum
  across all mixtures, the corpus or the entire literature.
- **Counterexample:** p.75, section 3.2.1/figure 3.8, reports about **1.8 for the
  Li form** in water/2-propanol at alcohol mass fraction about 0.4-0.5. The figure
  caption explicitly states 25°C. Filled H-Nafion points and open Li-Nafion points
  were checked visually; the H-form value about 2.3 was not assigned to Li-Nafion.
  This is enough to refute 1.54 as an unrestricted maximum in the supplied corpus.
  It does not establish 1.8 as the ultimate corpus/literature maximum.
- Supplemental p.55 defines alpha=(swollen mass-dry mass)/dry mass. Thus alpha
  about 1.8 corresponds to about 180% mass gain; this conversion is assistant
  arithmetic from the visually checked definition, not wording added to the
  original model answer. No units or values in the saved answer were changed.
- Supplemental pages 55,75,88,89 were read **after** inference and were not in
  the five model evidence chunks. Exact supplementary page texts/anchors and
  their original PDF identity are archived separately from runtime evidence.
- The final evidence set omitted the higher-value mixture page. The trace does
  not localize whether initial candidate search, fusion/reranking or subsequent
  evidence selection lost it; no causal diagnosis or production fix is claimed.
  The adequacy gate allowed the query with distinctive-term coverage 0.75 and no
  required relation checks. The observational qualifier audit returned
  `outside_finite_qualifier_scope`. Neither established maximum/temperature
  ownership. The recent offline event audit accepts event proposals, not answer
  prose; it was not applied by fabricating an event or making another model call.

Tests run:

- **96 software tests passed**, including three new wrapper tests plus existing
  smoke/provider controls. JUnit: `output/user_swelling_preflight_20261029_v01.xml`.
  These software checks are not scientific answer accuracy. Ruff passed for the
  wrapper, its tests and the final archived postflight script. No new full-suite
  or mypy success is claimed.
- One actual live ASGI request completed with production retrieval and provider.
  Offline replay then substituted only frozen ranked retrieval/native response
  bytes and reproduced the **identical HTTP status and complete API body** through
  the current route/service/parser. Database connections were explicitly forbidden
  and not attempted; provider transport was replaced by local placeholders/saved
  bytes. Postflight external model/OAuth calls: zero.
- The first offline replay hung inside the sandbox. Its two exact Python PIDs
  were identified outside the sandbox and stopped. The same replay code completed
  outside the sandbox in about 3.4 seconds. The precise cause of the sandbox hang
  is unconfirmed; this was not another provider attempt or an automatic live
  retry. The existing Starlette/httpx deprecation warning remains visible.
- Verified prepared/live manifests, current code/cache/index/PDF input hashes,
  byte-identical prepared/live native requests and global slot/result equality.
  All eight captured source pages matched fresh original-PDF text extraction.
  Four additional original pages were archived with explicit post-hoc origin.
- Using the PDF skill, Poppler rendered and visual inspection checked full
  dissertation pages 55,75,88,89,96,97. PNGs are in the stage's `source_pdf_views/`.
  PDFs were read only. No new PDF was authored or edited.
- Final HTML: `output/user_swelling_answer_20261029/review_v02/review.html`.
  Includes the untouched system answer, separate scientific critique/counterexample,
  complete prompt/native/API responses, full search/ranking/evidence diagnostics,
  registered and post-hoc pages and all three selected works in the eight TAC
  columns. Static QA verified three TAC rows/eight existing PDF/page links.
  Missing metadata and uncollected Conclusions/Terms remain explicit. Browser
  rendering/search execution were not tested. `review_v01` preserves the initial
  generic runtime review before scientific inspection was added.

Limitations:

This is one user-authored question on the existing corpus, followed by an
assistant-authored source check; no independent annotation or accuracy estimate.
The one counterexample refutes the unrestricted 1.54 maximum but does not provide
an exhaustive corrected maximum. Numeric extraction from the full corpus and
scientific ownership/condition coverage remain open.

ASGI TestClient exercises the real route/service logic, not browser UI, a network
web-server/proxy stack, ingestion/OCR/index creation or a long-lived repeated-
request cache/ORM lifecycle. Preparation and live used separate fresh processes
with existing settings; the earlier lifecycle issue remains open. The raw-chunk
prompt contains eight complete registered source pages; no compact-packet policy
or general context-compression feature is claimed.

Verdict:

The requested end-to-end runtime test completed and produced a real GigaChat
answer. **Its unrestricted maximum claim is contradicted by a higher value in
the same source document.** The test exposes evidence-coverage and scientific
validation gaps while preserving the model answer and all diagnostics. The new
one-call budget is consumed/closed; no automatic follow-up call is authorized.
