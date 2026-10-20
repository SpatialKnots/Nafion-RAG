# Records stage05: source-token selection with immutable reconstruction

Date: 20 October 2026. Development experiment, not independent scientific acceptance.

## Changed

Added `app/records/spans.py` with explicit OpenAI-only `span_full` and `span_compact` wire formats, CLI selection and native-response evaluator routing. GPT selects numbered source-token endpoints; code reconstructs raw values and citations from the original source string. The full format preserves sixteen observations, representation and linkage proposals. Compact preserves five nullable fields, unsupported unrequested dimensions, unparsed representation and absent linkage. Historical full/compact formats and default local backend remain unchanged.

Token IDs map deterministically to Unicode codepoint offsets in each selected region. Word runs, digit runs and individual punctuation/signs are addressable. Inclusive token endpoints become the existing end-exclusive character evidence spans. Internal whitespace, line wrapping, Unicode signs and ligatures are copied from immutable source text. Identical words at different positions remain distinguishable. Raw spans must be contained by coordinates in cited evidence, preventing a repeated phrase elsewhere from satisfying the check. Unknown, reversed, non-integer or out-of-range coordinates fail; nothing is clipped, normalized or repaired. Candidate schema, units, metrics, scientific state, source PDFs, database, ingestion and retrieval were not changed. See the [versioned protocol](records/token_span_protocol_v0.1.md).

## Frozen scope

Copied exactly the stage04 reference/input/task bytes. Reference SHA-256 remains `be40335d686490d430d0091d1a2b6e8d312d4947f887b5537c6c833b9f6af1c6`. These are exposed assistant-authored development cases with `needs_independent_review`; no independent gold was added. Three positive records retain sixty dimensions; bibliography remains a separate negative. Expected values and deferred dimensions were not revised.

Before inference, froze protocol, actual requests, source token maps including character offsets, input/task/reference hashes, original/layer PDF hashes and code. Private experiment: `data/experiments/records/pilot/stage05_20261020/`. Token counts: Abstract 43, table 415, cited result 467, bibliography 115. These are evidence-addressing tokens, not provider billing tokens. Pre-inference source snapshot: 400 files, fingerprint `941ea88a65c4a02a24552e4c50d594afe2e85fb1f0c552ce4538bba223d5190c`, at `output/records_stage05_20261020/baseline_ready/`.

Planned execution order was explicitly frozen as Abstract → Sanginov table → Istomina cited result → Kayumov bibliography. Same `gpt-6-astra` alias and remote settings as stage04: medium reasoning, default tier, strict JSON schema, store=false, no tools/temperature/seed, truncation disabled. One attempt per case, compact output/reasoning cap 2,048 and each full cap 8,192; timeout 180 seconds each. The predeclared stop rule stops remaining requests on transport/provider/completion-contract failure, while evidence-selection failures alone permit continuation. Selected source plus token map enters the API, without full stored pages, PDF paths or reference answers. Global RAG settings were not changed.

## Observed results and stop rule

**Two requests were attempted; two were not attempted.** No retries, repair, duplicate-link removal, model switch or token-budget extension followed. No execution-order deviation occurred.

| Case | Actual attempt | Result |
| --- | --- | --- |
| Sanginov Abstract | 5.765 s; 879 input / 87 output tokens | Integrity-valid compact selection; four raw fields exact and null sample abstention matches the bounded expectation. Full record remains deferred. |
| Sanginov table | 37.383 s; 4,092 input / 2,295 output tokens | Native response completed, but full-wire validation rejected a duplicate `conditions_measurement` linkage role. No candidate admitted. |
| Istomina cited result | Not attempted | Retained unavailable under the stop rule; no current-stage attribution result. |
| Kayumov bibliography | Not attempted | Retained unavailable; no current-stage negative-abstention result. |

The rejected table proposal contains four linkage entries: sample_value, property_value, conditions_measurement, conditions_measurement. Its JSON shape fits the provider schema, but role uniqueness is an application invariant enforced by the existing-style validator. Structured Outputs does not establish semantic invariants. Raw response, returned model, request/response IDs, usage and validation error remain saved. There is no validated `reply.json` or `candidates.json` for this case. The offline review labels its raw JSON as an unvalidated proposal; it neither removes a duplicate nor treats the answer as successful extraction.

Separate coordinate audit found **53 individual coordinate references, zero invalid coordinates** across the two raw proposals, including repeated references. This establishes source reconstruction for those references, not correct scientific selection or accepted records. The table's conditioning text reconstructs the original `equilibrat- \ning` exactly, eliminating the stage04 model-written `equilibrat- \nning` corruption in this proposal. Raw value `1.1 × 10 −4`, footnote temperature `20 °C`, initial plasticiser composition `ω(SL) = 0.40` and origin `This work` match their historical reference text. Nine of ten non-deferred field/status proposals agree exactly; composition_basis selects a longer verbatim phrase than the reference's `mass fraction`. This partial audit does not override atomic rejection. Conditioning and unresolved linkage remain deferred in the reference.

Unchanged atomic evaluator over **all four declared cases**: one integrity-valid case, three failed/unavailable; one admitted positive candidate of three expected. Sixty record dimensions: **4 match, 16 deferred, 40 unavailable**. Full-record outcomes: one deferred, three unavailable. No current-stage negative abstention is counted correct because that request was not attempted. Successful generation of the table response does not equal a valid extraction.

Stage05 does not establish better full-record extraction than stage04. It demonstrates exact reconstruction on the attempted selections and exposes a distinct output-contract failure. Prompts, schemas, token-address maps, attempt counts and inputs measured in provider tokens differ; no isolated causal effect, general accuracy or controlled speedup is claimed.

## Usage and cost

Aggregate actual usage: **4,971 input, 2,382 output, 7,353 total tokens**. Input metadata reports 4,089 cache-write and zero cached-read tokens. Both returned model IDs are `gpt-6-astra`, an alias without an immutable snapshot guarantee.

Conservative cost estimate **$0.1812375**: all input charged at $12.50/million, output at $50/million using the verified stage04 rate basis. Estimate is not an invoice, actual billing check or hard dollar cap. The unattempted requests incur no observed usage. Existing privacy/credential controls remain in force; store=false is not Zero Data Retention. Official sources: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [model/rates](https://developers.openai.com/api/docs/models/gpt-6-astra), [data controls](https://developers.openai.com/api/docs/guides/your-data).

## Tests run

- Targeted new spans plus existing OpenAI/compact/full extraction: **84 passed**, 5.04 s. Initial two synthetic evaluator tests failed because Windows text writing changed newline bytes; the fixture now writes exact UTF-8 bytes. No production validator was relaxed.
- Full regression: **1,138 passed**, one existing Starlette/httpx deprecation warning, 52.10 s. Eighteen new synthetic cases cover repeated-occurrence coordinates, Unicode/CRLF preservation, invalid IDs/types/ranges, raw/evidence coordinate containment, null/missingness, duplicate fields/roles, source-only requests, native runs and tampered token maps. No paid calls in tests.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 100 source files.
- Two real API requests yielded one integrity-valid case and one completion-contract failure as above; they are separate from passing software tests.
- Offline replay of stage02/03/04: identical summaries and all scientific case/candidate fields. Comparison excludes only regenerated candidate-bundle run_id and created_at; record IDs, source/evidence, field values, outcomes, diagnostics and deferred dimensions are compared. Stage02/03 cases also remain fully identical. The initial stage04 whole-object assertion exposed those expected ephemeral fields; no metric or scientific field was excluded to force agreement.
- Original/layer PDF hashes, inputs/tasks/reference/protocol, token maps and actual request hashes matched frozen manifests. Static HTML: four case rows, nine existing local PDF links, exact escaped source fragments, expected/actual raw fields and unvalidated failure details. Credential scan of 115 experiment/review artifacts found no exact configured credential and printed no key.
- Browser visual/click checks were not run: local-file navigation had already been blocked by browser policy earlier in this session. Static verification does not replace those checks.

Private review outputs, excluded from Git:

- `output/records_stage05_20261020/comparison.html` — searchable four-case review, stage04 comparison, exact sources, coordinates and explicit unattempted cases.
- `output/records_stage05_20261020/comparison.json` — partial raw-field and coordinate audit without admission or repair.
- `output/records_stage05_20261020/evaluation/review.html` and `report.json` — unchanged atomic evaluator, including all missing dimensions.
- `output/records_stage05_20261020/qa.json` — replay/source/static checks.
- `data/experiments/records/pilot/stage05_20261020/` — frozen sources, requests, token maps and actual response artifacts. Raw literature and credentials are not part of the commit.

## Limitations

Only two of four planned requests ran; the stop rule intentionally leaves prior-work attribution and bibliography behavior unmeasured in this version. Source selection remains oracle-assisted, references exposed and non-independent, and full record/scientific admission unresolved. Token spans cannot split a word/digit token, select whitespace-only text or invent unsupported discontiguous raw values. Exact coordinates may still refer to semantically wrong text. No production integration, whole-corpus extraction, fresh independent evaluation, end-to-end retrieval test, clean installation or billing verification was performed. Remote model alias, incomplete experiment and missing browser QA prevent stronger reproducibility/quality claims.

## Verdict

Versioned source-coordinate reconstruction is implemented and tested. The compact real case succeeds; table source copying is exact in the audited proposal, but full-wire duplicate-role validation blocks admission and further calls. Preserve this negative result. The smallest next format experiment is fixed named linkage slots with nullable proposals, making duplicate roles unrepresentable in the schema, followed by a separately frozen comparison. Do not silently repair this stage's response or claim that scientific extraction is solved.
