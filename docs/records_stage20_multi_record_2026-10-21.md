# Records stage20: separate multi-record contract and real frozen smoke

21 October 2026. ARIADNE bounded development extraction, following stage19.
[Protocol](records/multi_record_protocol_v0.1.md).

## Changed

Added `app/records/multi.py`, `multi_run.py`, `multi_html.py`,
`scripts/records_multi.py` and 29 constructed test cases. The separate
`records_multi_fixed_reply_v0.1` supports zero to four proposals per context,
with the existing sixteen observations and three required nullable linkage
slots. Historical reply formats retain their one-record limit. Candidate
schemas, units, thresholds, metrics, ingestion/OCR, retrieval and the independent
review store remain unchanged. No original PDF or production database was written.

Four is an explicit operational reply budget, not a scientific maximum. At the
ceiling the contract requires `partial` and a source-supported `record_budget`
entry. Partial/unsupported replies need unresolved source evidence; returned
counts must match actual arrays. `claimed_complete_in_context` is explicitly
a model claim, not admission or verified recall. Empty proposals do not prove
absence. Duplicate JSON keys at every reply depth and repeated raw-coordinate/
status signatures are rejected, including changes only to notes, representation,
link wording or observation order. This is exact proposal identity, not general
scientific equivalence or duplicate-experiment detection.

The unchanged fixed-link/span resolver restores each proposal from exact token
coordinates, then revalidates the assembled bundle. It preserves ranges rather
than splitting endpoints. It does not establish that valid source spans support
the proposed sample/condition relation. A constructed counterexample explicitly
shows a wrong temperature association can remain integrity-valid while scientific
support stays unknown; no semantic validator is claimed.

The independent runner freezes four exact inputs, actual requests, protocol/code
hashes and the complete 62-page registry before any call. It verifies 460 bound
input/source/artifact paths and 19 dependency-code files, rejects a complete page
in decoded context/task or actual user-message text, and binds request bytes to
the unchanged builder/settings. The fixed HTTPS transport is reused without
proxy forwarding, redirects or retries. Inputs, code and source PDFs are checked
before/after calls and again by postflight.

All four cases remain in the HTML/JSON denominator, including any failed or
stopped cases. Raw native responses and usage precede schema/evidence parsing.
Successful records, unresolved spans and existing pass/fail/unknown checks stay
separate. No assistant proposal is written to the existing user revision store
or promoted to scientifically confirmed.

API schema/refusal/incomplete handling was checked against
[official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).
Schema adherence is not scientific correctness. The existing development model
alias `gpt-6-astra` was retained, not replaced by a model recommendation.

## Frozen inputs and live execution

Source window plan: `output/records_stage19_20261021/run_v01/`.
Historical source fingerprint remains
`f133dcf1d95bf94d38f0d1cf49da24ca55082a42a8867e51f6f343fd84811a94`.
The four selected context IDs, order, task, budget and stop rules were declared
in the protocol before live calls. They are exposed assistant-selected development
cases, not a random/independent evaluation sample. No expected values, references,
full stored pages, PDF paths or credentials entered model requests.

Preparation: `output/records_stage20_20261021/prepared_v01/`.
Serialized request sizes, in order: 15067, 14495, 10779 and 25855 bytes; all below
the fixed 100000-byte ceiling. Four actual calls were made, sequentially, using
medium reasoning and at most 8192 output tokens each, 180-second timeout and a
maximum total of 32768 output tokens. There were no retries, replacements,
provider failures, output repairs or budget increases. All four native responses
returned model alias `gpt-6-astra` and completed status.

| Case | Exact-source-valid proposals | Model coverage claim | Observed call seconds |
| --- | ---: | --- | ---: |
| Sanginov abstract | 2 | `partial` | 61.816 |
| Istomina cited prior-work passage | 2 | `claimed_complete_in_context` | 54.585 |
| Istomina method-only passage | 0 | `no_measurements_proposed` | 8.519 |
| Kayumov Table 2 | 4 | `partial` | 75.825 |
| Total | 8 | Not a scientific completeness metric | — |

These timings are observed development transport/processing durations, not
chemist time or general model latency benchmarks. Reported usage across the
four saved native envelopes: 17949 input tokens, 10755 output tokens (including
reasoning as reported by the provider), 28704 total tokens. No price/invoice,
portable model snapshot or Zero Data Retention claim is inferred.

## Source/record inspection and remaining gaps

The actual saved outputs retain:

- Abstract: a conductivity range and an electronic-conductivity observation.
  The unnamed “best sample” remains ambiguous; composition ratio and method are
  missing. Unresolved spans preserve the mixture-composition range and sample
  passage. The range is not split into two endpoint measurements.
- Prior-work passage: two proposals with literal `In recent work [26], we showed`
  origin evidence, missing method and ambiguous sample identity. Model coverage
  `claimed_complete_in_context` does not cure those missing fields. These repeated
  prior-work values are not counted as additional independent experiments.
- Methods: zero measurement proposals. This is a model outcome on the chosen
  method-only fragment, not independently established article-wide absence.
- Table: sample 1 at two stated temperatures, then one proposal each for samples
  2 and 3. The reply explicitly identifies remaining source rows/values outside
  its four-proposal budget. It separately cites rows 12–13 as ambiguous because
  flattened text does not establish the scope of vertically shared cells.
  Neither the unprocessed rows nor merged cells were silently assigned or repaired.

Electronic conductivity keeps the author's property wording; it is not renamed
Li-ion conductivity or silently accepted into a future scientific subset. Author
origin wording remains raw evidence; no numeric normalization or reference
matching was added. Every candidate still requires scientific assessment.

The unchanged checks classify **all eight candidates as `incomplete`**. Across
their technical checks: 90 pass, 22 fail, 64 unknown. Those are engineering
diagnostic counts, not accuracy percentages or independent scientific errors.
All eight have missing method; sample/condition ambiguity and source-only scope
remain explicit. Scientific precision, recall and human-time savings remain null.

Outputs:

- [Four-case multi-record HTML review](../output/records_stage20_20261021/live_v01/review.html).
- `live_v01/report.json`, `manifest.json` and per-case exact `input.json`,
  `request.json`, native `response.json`, `reply.json`, `candidates.json`,
  `unresolved.json`, `checks.json` and `result.json`.
- `prepared_v01/` contains all four source-only inputs, exact actual request
  bytes, policy/plan, complete page registry and input/code/artifact manifest.
- `postflight.py` and `postflight_v01.json` retain offline replay, source/HTML
  checks and observed usage totals. Private corpus/artifacts stay local.

## Tests run

- Final targeted suite: **29 passed**, **9.11 seconds**. Constructed cases cover
  distinct samples/temperatures/ranges, signature duplicates and note-only evasion,
  coverage/count contradictions, partial/unsupported scope, duplicate JSON keys,
  invalid/foreign coordinates, literal footnote evidence, semantic-validation
  limitations, unchanged historical schema, request privacy, mocked raw-response
  replay, source drift and full-page guards. Timeout, network error, incomplete
  output, refusal, duplicate keys and wrong spans each stop remaining cases after
  one attempt, with no successful abstention or fabricated candidate output.
- The first targeted run had **21 passed and 8 fixture setup errors** because the
  `--basetemp` parent did not exist. The stage output parent was created explicitly;
  fixtures and application checks were not weakened. Its JUnit remains separate.
  Final JUnit: `pytest_target_v02.xml` under the stage20 output root.
- Full regression outside sandbox: **1559 passed**, one existing Starlette/httpx
  deprecation warning, **206.98 seconds**. JUnit: `pytest_full_v01.xml`. The
  established outside-sandbox route was used for the project's HTTP tests.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues in 121 source files.
  Initial local type/unused-import errors were corrected before final tests and
  request preparation; they are not counted as passing checks.
- Actual frozen preparation and all four real provider attempts passed their
  declared request, completion and exact-evidence checks. All source/PDF/code/
  request/output hashes matched postflight.
- Each actual saved raw response was reparsed twice offline. Restored records,
  source regions and unresolved spans equal the saved output exactly. Fresh
  run IDs/timestamps are deliberately excluded from equality claims. No raw
  output or candidate was repaired to obtain equality.
- Static HTML verification accounts for all four case rows, all four exact
  context texts and four existing local PDF/page links, with complete candidate,
  unresolved and technical diagnostics. Browser/click acceptance was not attempted;
  there is no HTTP workaround for the earlier file-URL restriction.

## Reproduction and safety of reruns

Preparation is offline; use a fresh destination:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_multi prepare --windows output/records_stage19_20261021/run_v01 --output-dir output/records_multi_preparation_new
New-Item -ItemType Directory -Path output -Force | Out-Null
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/unit/test_record_multi.py -q -p no:cacheprovider --basetemp=output/records_multi_test_tmp
```

Basetemp must contain dedicated disposable fixtures under the source root;
pytest clears it. The saved stage19 artifacts, source PDFs and historical paths
must still match hashes. A clean clone lacks these private inputs. The `run`
subcommand performs external paid API calls using configured credentials; it is
not needed to reproduce offline replay. The four-call stage20 budget is consumed;
do not automatically rerun or expand it under this protocol.

## Limitations

This smoke demonstrates multi-record transport/format/evidence integrity on four
exposed bounded contexts. It does not establish correctness of every extracted
field/link, independent experimental identity, scientific precision/recall or
whole-article completeness. No independent reference or annotation was supplied.
The 352 context plan, 34 deferred pages, paragraph/page dependencies, original
10–15-publication target and whole-system recovery remain separate open work.

Budgeted table extraction is explicitly partial. The new format working on four
cases is not sufficient evidence to send all 352 contexts or call their output
exhaustive. The user review store and historical artifacts were preserved, and
no blanket commit/reset/production migration was performed.

## Verdict

Stage20 engineering contract and frozen live smoke completed: four real native
responses, eight exact-source candidate records and reproducible offline replay.
All candidates remain incomplete/unreviewed; scientific acceptance is open.

Next bounded work: source-supported continuation/decomposition of the partial
table scope with intact headers/footnotes and explicit row/cell accounting,
plus evidence joining for missing sample/composition/method where the source
actually supports it. Preserve merged-cell ambiguities, repeated prior-work
values and current raw artifacts. Freeze a separate protocol/budget before any
new provider run; do not repair the present responses or claim article-wide recall.
