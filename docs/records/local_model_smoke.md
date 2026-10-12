# Local structured-field smoke

The `app.records.cli smoke` command exercises a local model on saved source regions. It does not create full `RecordCandidate` objects, accept scientific records, or change the existing answer provider. Without `--field`, the experimental output contract remains `records_smoke_fields_v0.1`. With `--field`, the default `records_smoke_single_field_v0.2` contract requests one field per invocation. Adding `--field-format span` selects the explicit two-key `records_smoke_span_field_v0.3` contract.

## Input and output

Input is an integrity-valid `CandidateBundle`. Only exact region text, region aliases, article IDs, page numbers and text-layer labels enter the prompt. Existing manual candidates and source-selection notes are excluded. A manually selected context must still be declared as such in the input artifact and experiment report; this is not an evaluation of retrieval.

In v0.1, the model must either return no observations for a bibliography-only input, or return ten distinct fields: `sample_label`, `property_name`, `value`, `unit`, `temperature`, `medium`, `medium_composition`, `composition_basis`, `method`, `data_origin`. Unsupported fields require explicit status and a diagnostic note. JSON Schema constrains decoding, while Python validation checks the field set and evidence.

In v0.2, the requested field and its scientific meaning are supplied by the caller. The model returns only `status`, `raw_text`, `region`, `quote`, `note`. A single quote and raw text are limited to 240 characters; note is limited to 160 characters. Citation region and quote must be supplied together or both be null. Missing observations remain explicit and require a diagnostic; present raw text must occur in the exact cited source. This format does not represent multiple citations or a complete record. Cross-field and sample/condition linkage still require independent review.

In v0.3, the model returns only `region` and `text`. The requested field and meaning precede the source context; the region JSON Schema enum contains only the supplied aliases and null. Text must be one exact, unique source span of at most 240 characters. Both values must be non-null together or null together. Non-null text becomes a proposed `present` observation with that same text as evidence. A null pair becomes `not_found_in_context` with a client-authored diagnostic that source absence has not been independently verified. This model abstention does not distinguish absent, ambiguous and unsupported source cases. The saved wire response and contract version preserve that limitation.

Minimal single-field invocation, using a new output directory and the identity of a currently running server:

```powershell
.\.venv\Scripts\python.exe -m app.records.cli smoke `
  data/experiments/records/smoke/sanginov_table_20261009_v01/input.json `
  --output-dir data/experiments/records/smoke/new_temperature_span `
  --task 'Extract one conductivity proposal from the row marked This work, specifically the conductivity cell carrying footnote d. Preserve author property wording and use the applicable temperature. Use method only if attributable to this work.' `
  --field temperature --field-format span --max-tokens 192 `
  --model ariadne-qwen25-15b-q4km `
  --runtime-manifest data/experiments/records/runtime/current_server_identity.json
```

The comparative field experiment is described in [S06 format comparison](../ariadne_s06_format_comparison_2026-10-09.md). Historical outputs use their recorded contract and code fingerprints; they are not overwritten to match a later format. Saved batches can now be checked with the offline `compare` command described in the [development reference protocol](semantic_review_rubric.md). Its finite source-bound agreement counts are separate from literal integrity and scientific acceptance.

Evidence quotes must be exact, unique substrings of the specified region. The resolver derives Unicode codepoint offsets without correcting whitespace, ligatures, minus signs or broken lines. A present raw value must occur verbatim in its evidence. These conditions establish textual integrity only: a literal quote can still refer to the wrong sample, column, temperature or article.

Each invocation requires a new output directory. It preserves input bytes, runtime identity, request, code/schema fingerprints, raw response, model text and result diagnostics. A distinct `smoke_run_id` identifies the model call separately from the input source bundle's `run_id`. Valid observations are written only after all integrity checks pass. Transport, JSON, schema, truncation and quote failures remain explicit failures; they do not become empty successful outputs.

`scientific_admission` always remains `not_evaluated`, and `review_state` remains `needs_review`.

## Example

Run from the repository root after starting the local server and saving its current runtime identity:

```powershell
.\.venv\Scripts\python.exe -m app.records.cli smoke `
  data/experiments/records/development/sanginov2021_smoke_context_v01.json `
  --output-dir data/experiments/records/smoke/new_table_run `
  --task 'Extract one conductivity proposal from the row marked This work, specifically the conductivity cell carrying footnote d. Preserve author property wording and use the applicable temperature. Use method only if attributable to this work.' `
  --model ariadne-qwen25-15b-q4km `
  --runtime-manifest data/experiments/records/runtime/current_server_identity.json `
  --max-tokens 1536 --timeout-seconds 600
```

The runtime manifest must match the requested model alias and endpoint. It is caller-supplied metadata, not remote attestation: the harness does not independently determine which weights a server actually loaded. Installation checks, process identity and server logs must accompany an experiment.

Only explicit loopback HTTP origins with a port are accepted (`127.0.0.1` or `::1`). Environment proxies and HTTP redirects are disabled. No database connection or live PDF validation is performed by this command. Use `validate --live` separately when current corpus identity needs verification.

The observed installation and first development runs are recorded in [S06 execution](../ariadne_s06_execution_2026-10-09.md). Historical runtime identities must not be reused as evidence of a later process launch. Seed and temperature are recorded; byte-identical generation across runtimes is not promised.

The frozen development reference, matched 1.5B/3B comparison, runtime resource limits and actual outcomes are recorded in [S06 reference comparison](../ariadne_s06_reference_comparison_2026-10-09.md). Both models produced 3/30 provisional reference agreements, all abstentions. These results do not authorize scientific ingestion or model selection for production.
