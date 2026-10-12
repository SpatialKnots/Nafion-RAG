# ARIADNE S06: simpler model-facing formats, 2026-10-09

## Verdict

The requested format simplification and repeat experiment are complete. Both new formats produced parseable, complete JSON in all 60 field requests. The smaller responses did not establish reliable scientific extraction: the model still confused fields, ignored a temperature footnote and extracted bibliographic identifiers as measurement values. No scientific records were accepted or created.

The two-key format is useful for diagnosing literal-span extraction, but is not a production extractor. `integrity_valid` means the proposed text exists in the specified source region, not that it answers the requested scientific field correctly.

## Changed

Added two explicit optional contracts to `app.records.cli smoke`. The existing ten-field v0.1 contract remains the default when `--field` is omitted.

- `--field FIELD`: `records_smoke_single_field_v0.2`, one field per request; five output keys (`status`, `raw_text`, `region`, `quote`, `note`). One quote/raw text is limited to 240 characters and note to 160 characters. Status/value consistency and exact evidence are still required.
- `--field FIELD --field-format span`: `records_smoke_span_field_v0.3`, two output keys (`region`, `text`). Region is constrained to supplied aliases or null; text is a single exact answer span of at most 240 characters. Both keys must be supplied together or both null. A non-null span produces a proposed present observation. A null pair produces a client-authored missingness diagnostic explicitly stating that source absence has not been independently verified; ambiguous, unsupported and absent cannot be distinguished by this minimal wire format.

The minimal format also places field meaning in the system message and the requested field before source context. Existing quote validation is shared rather than weakened. No whitespace repair, value conversion, PDF modification or scientific admission was added. Every model call now has a separate `smoke_run_id`, while the source bundle retains its original `run_id`.

The input/output format and usage are documented in [local model smoke](records/local_model_smoke.md). The private experiment recipes, raw responses and manifests are preserved below `data/experiments/records/`.

## Experiment configuration and provenance

The same installed Qwen2.5-1.5B-Instruct Q4_K_M weights and llama.cpp b11429 runtime were reused. Model and server executable SHA-256 checks passed again before launching the new hidden process. CPU configuration remained two threads, two batch threads, one slot, 8192-token context, no GPU, loopback port 18086 and Windows `BelowNormal` priority. Seed 42 and temperature 0 were retained.

Each format made ten independent requests on each of the original three cases, in the same declared order: sample, property, value, unit, temperature, medium, composition, composition basis, method and origin. Each request used the baseline's saved `input.json` and task. The final artifact audit verified all **60 input byte snapshots and prompt source contexts/tasks match the baseline**. No manual answers or selection notes entered a model prompt.

The three cases are the original agent-selected/oracle contexts, not independent gold or retrieval outputs:

1. Sanginov Table 2 own row, footnotes, method and composition-basis context; target is the conductivity cell carrying footnote d.
2. Kayumov bibliographic entry only; no measurement proposal should be extracted.
3. Istomina cited-result paragraph, present-article method and reference [26]; present methods must not be transferred to cited results.

Maximum output was 384 tokens per field in v0.2 and 192 in v0.3. Prompt wording, field placement, schema and output budgets changed together. Cache reuse also differed. This is a comparison of engineering configurations, not an isolated causal test of schema size.

The frozen v0.1 baseline remains unchanged. Its three whole-output requests are not directly equivalent to thirty independent field requests. Code fingerprints in historical manifests describe the code used at those times; they were not rewritten to match a later version.

## Actual results

| Format | Field requests | Parseable JSON / normal completion | Literal-integrity success | Integrity failure | Sum of request latency | Output tokens |
|---|---:|---:|---:|---:|---:|---:|
| v0.2: five keys | 30 | 30 | 3 | 27 | 238.244 s | 3931 |
| v0.3: two keys | 30 | 30 | 17 | 13 | 236.563 s | 725 |

All failures occurred at `evidence_integrity`; no transport, JSON parsing, wire-schema or truncated-completion failure occurred in these two batches. These counts describe literal integrity checks, **not extraction accuracy**.

| Case | v0.2 literal successes | v0.3 literal successes | v0.2 latency sum | v0.3 latency sum |
|---|---:|---:|---:|---:|
| Sanginov | 0/10 | 3/10 | 81.469 s | 100.996 s |
| Kayumov bibliography | 3/10 | 10/10 | 66.452 s | 34.443 s |
| Istomina cited results | 0/10 | 4/10 | 90.323 s | 101.124 s |

The minimal format reduced output tokens substantially but total request time remained similar. Repeated context processing and changed cache reuse matter; individual field latency must not be compared with baseline whole-output latency as if the workloads were identical.

## Scientific inspection of the saved outputs

Inspection was performed by the coding agent against the saved source fragments. It is diagnostic development review, not independent adjudication or a precision/recall evaluation.

**Five-key format:** the model repeatedly emitted `not_found_in_context` with an asserted non-null value, including the literal string `not_found_in_context` in `raw_text`. Those contradictions and altered quotes were rejected. Its three literal successes were null raw values for bibliography composition, composition basis and origin; one generated origin note incorrectly claimed that the source contained a measurement. A structurally valid missingness observation does not certify its explanatory note.

**Two-key format, Sanginov:**

- Temperature was `at 25 o C` from the exact generic table header. This passed literal integrity but is wrong for the requested cell: footnote d gives 20 °C. The wrong-header linkage remains a scientific error.
- `medium_composition` and `composition_basis` both returned the exact mass-fraction-basis phrase. The basis phrase is relevant to `composition_basis`, but does not supply the requested composition fraction; the latter field is wrong.
- Sample/property/value repeatedly returned `6.3 × 10 −6` attributed to the method region R3, where it does not occur. Other fields also pointed to the wrong region. These were rejected without remapping citations.

**Two-key format, bibliography:** all ten non-null literal spans passed source integrity, but the measurement task was not satisfied. `A5253`, the bibliographic page identifier, was used for value, unit, temperature and composition basis. Other fields reused the article title, journal and electrolyte wording. The model returned **no null abstention** in this negative case. All ten fields are unsuitable as a conductivity-measurement proposal despite existing verbatim in the entry.

**Two-key format, Istomina:** `sample_label=EC/SL` confuses medium with sample; composition was filled with the temperature range; composition basis was filled with article identifier `137914`. The literal solvent-component phrase is relevant to the medium field. Other outputs used wrong regions, flattened line breaks or incomplete fragments. A complete, correctly attributed cited-result proposal was not produced, and the requested method/origin test was not passed.

An intermediate assistant update prematurely described the bibliography result as abstention based on integrity status. Raw-output inspection disproved that statement; it was explicitly corrected in chat. The results above follow the saved wire outputs, not that earlier interpretation.

## Runtime diagnostics and resources

The new process was PID 1568. `/health` returned `{"status":"ok"}`. Saved `/props` identifies the model path, alias, b11429 build and Qwen chat template with `<|im_start|>` / `<|im_end|>` delimiters. The read-only `/apply-template` diagnostic formatted synthetic system/user turns with those delimiters and real newlines. This endpoint formats messages without inference, as described in the [pinned official server documentation](https://github.com/ggml-org/llama.cpp/blob/d81235049384534c167caea52b85a694f6103d14/tools/server/README.md#post-apply-template-apply-chat-template-to-a-conversation). These observations do not prove the cause of the scientific errors.

The server log preserves its warning about a control-looking `</s>` token whose type was overridden. No causal claim about that warning or parameter count is made. A Python-side template diagnostic was unavailable because `jinja2` was not installed; the native server diagnostic was used, without installing another dependency.

Final working set was 2,651,222,016 bytes; Windows peak working set was **2,691,973,120 bytes, about 2.51 GiB**. This measures the server process, not total RAM use or interactive laptop responsiveness. Model path and process start time were verified before stopping it. `server_stop_v02.json` records exit at `2026-10-09T09:21:31.9388134Z`. Weights remain installed; no other model was downloaded.

## Tests run

- First single-field patch: **36 smoke unit cases passed**; full regression **694 passed, 1 warning in 6.00 s**.
- Final two-format implementation: full regression **705 passed, 1 warning in 7.94 s**, including **47 smoke unit cases**. Tests cover original behavior, literal Unicode spans, normalized/wrong-region rejection, null/status consistency, quote limits, extra fields, separate run identities, source-context preservation and both new output contracts.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 82 source files**.
- Actual model runs: **30 v0.2 requests and 30 v0.3 requests**, both batches completed normally and preserved all outputs.
- Artifact audit: **60 identical baseline input byte snapshots and identical source contexts/tasks**, all saved JSON outputs parseable and all completions `stop`; inventory captures **451 artifacts** with SHA-256 and byte sizes.

Executed final full regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  --basetemp D:/Nafion-RAG/tmp/s06_span_full_20261009
```

## Limitations and next step

The simplified contract improves inspectability and removes repetition of output field labels, but literal span validation cannot reject every wrong scientific assignment. No format is approved for scientific ingestion. All proposed observations remain `needs_review` and `not_evaluated`; no fields were combined into accepted records.

Further development needs a fixed semantic review rubric separating literal source matches from correct field, sample, condition and origin linkage. The demonstrated errors should remain explicit counterexamples: bibliography identifiers as values, header temperature versus cell footnote, solvent versus sample, and current-article method versus cited result. After freezing that rubric, compare another model/configuration on the same contexts. Do not continue prompt retries until a superficially successful JSON appears, and do not infer quality from the 17 literal successes.

Independent gold, scientific completeness, grouping/split, production extraction and interactive review remain open. Source PDFs, database, extraction/OCR, chunking, retrieval scoring and existing answer routes were not changed. S06 model quality selection remains open.
