# GigaChat DSC: named fields and source-span selection

28 October 2026, Asia/Yekaterinburg. Version `gigachat_dsc_named_spans_v0.1`.
User authorized implementation, offline checks and one new model attempt with
`Выполняй`. The first failed response remains the baseline, without repair.

Changed:

- Added isolated new files `app/records/gigachat_dsc_spans.py` and
  `scripts/gigachat_dsc_spans.py`, with a prospectively written
  [protocol](records/gigachat_dsc_spans_protocol_v0.1.md).
  Previous frozen adapter/source files, output files and reservations were not
  changed. No production provider integration or provider-default change.
- Replaced the reply's array with exactly six required named fields. Each field
  selects registered span IDs or explicitly abstains. Duplicate/unknown keys,
  foreign/unknown/duplicate IDs, reversed source order and inconsistent outcomes
  are rejected, without automatic repair or sorting.
- Partitioned the complete M1 body into four neutral, exact sentence spans.
  Heading plus all spans reconstructs the unchanged source text. All Unicode,
  whitespace, original units and semicolon-linked clauses remain intact. The
  model receives IDs and text without a topic-to-ID answer key.
- The complete temperature-programme sentence is one protected fragment. A
  present programme must select it in full, including the ordered heating,
  cooling, holds and additional homogenisation wording. Missing or ambiguous
  programme boundaries block preparation with an explicit diagnostic.
- Code restores exact source substrings, then runs the unchanged original DSC
  reply/M1-quote/PDF-offset validator. Returned diagnostic prose is not accepted
  as scientific evidence. Exact restored text is a codec property, not improved
  model copying accuracy.
- The final prospective request is **9913 bytes**, SHA256
  `0f54ea0b82f6c88bfb1618bd55eb98d940a00189b93105acaed75b4c567afca4`.
  Catalog SHA256:
  `2a2cb569f2ab68775b43d818d139c9f532ddac1f0d9e9d678d375d6f3886950b`.
  Same question, five original context regions and complete M1; same requested
  `GigaChat-2-Max`, 4096 output-token ceiling, 180 s timeout and provider-default
  sampling. No retry, fallback, purchase or billing upgrade.
- Source, code (including the durable-write helper), runtime and historical
  guards were checked. Full baseline output hashes are new experiment inputs.
  Both parent and baseline snapshots are saved separately.

## Prospective comparison reference

Before the new dispatch, this assistant checked the four actual source sentences
and froze these exposed-case expectations in
`output/gigachat_dsc_spans_20261028/comparison_reference_v01.json`:

| Named field | Expected complete source span |
| --- | --- |
| instrument | M1:S001 |
| sample_handling | M1:S002 |
| measurement_environment | M1:S003 |
| flow_rate | M1:S003 |
| temperature_range | M1:S003 |
| temperature_programme | M1:S004 |

The reference preserves exact source anchors and hashes and binds the offline
audit script. It is assistant-authored after the first failure and before the
second response on an already exposed development case. It is **not independent
scientific gold** and is not sent to the model. Agreement means selection of the
same source sentence, not generalized scientific correctness or sample-specific
applicability.

## Observed real result

Exactly **one new model request** completed, with status `integrity_valid`.
One OAuth exchange and two read-only account calls preceded generation. Scope
`GIGACHAT_API_PERS`, verified TLS, no proxies/redirects/retries/fallbacks. The
observed pre-request Max package balance was **24997139** tokens. No post-request
balance was requested, and monetary cost remains unknown.

Both responses declared `GigaChat-2-Max:2.0.30.01`; that is a provider declaration,
not independent model-identity verification.

| Observation | First direct-quote reply | New named-span reply |
| --- | --- | --- |
| Result | response_invalid | integrity_valid |
| Topic coverage | 5 unique topics; sample_handling duplicated; measurement_environment missing | All 6 named fields present exactly once |
| Source integrity | 0/5 model-typed quotes are unique exact M1 substrings | 6/6 selected references restored exactly, across 4 unique source spans |
| Complete programme retention | The typed programme quote omitted source wording | Full protected source programme retained |
| Frozen exposed-case sentence agreement | Not evaluated by remapping or repairing old quotes | 6/6 named selections agree |
| Prompt tokens | 2167 | 2529 |
| Completion tokens | 694 | 313 |
| Total tokens | 2861 | 2842 |
| Precached prompt tokens | 3 | 3 |
| Model request elapsed, seconds | 14.086752800038084 | 8.701256099971943 |
| Recorded dispatch phase elapsed, seconds | 40.98074979998637 | 77.15059519989882 |

Request elapsed includes the network response transfer, not pure inference time.
The recorded dispatch phase also includes account calls and local checks, and
excludes initial validation before that phase. New local validation is more
extensive; no profiling or end-to-end speed improvement is claimed.

The new response selected S001 for instrument, S002 for handling, S003 separately
for environment/flow/range, and S004 for the full programme. All six agreed with
the prospective exposed-case reference. This establishes the specific observed
retention and selection result; independent scientific acceptance remains
`not_evaluated`, independent accuracy remains null.

Raw new response SHA256:
`25622b6de3a078f7fb357d606f2fdd946918017e02079f68a6846eaf590ae67e`.
Header request ID `1a9613b1-9f4f-4c8e-b350-2be266964cf2`.
The native response ID was absent and remains null. No credential redaction was
needed. The raw GigaChat bytes were saved before parsing; a derived local decoder
restores sources without pretending that the provider returned those quotes.

Tests run:

- Final affected suite: **93 passed**: 36 new named-span cases, 33 previous
  GigaChat cases, 24 previous DSC experiment cases. JUnit:
  `output/gigachat_spans_tests_20261028_v02.xml`. The preceding 88-case run is
  superseded by this run; counts are not added together.
- Covered complete/partial/abstention; required/extra/duplicate fields and IDs;
  unknown/bibliographic IDs; wrong source role; missing/ambiguous programme cue;
  source ordering, whole-programme retention, Unicode/linebreak/homogenisation
  preservation, source/catalog/baseline drift, permission/key/Scope, model/quota
  admission, raw response and metadata recording, no retry/refund after timeout
  or HTTP error, secret redaction, post-transport drift and escaped HTML.
  These tests use constructed sources and transports, not real scientific gold.
- Ruff `app tests scripts`: passed. Mypy `app`: **179 source files**, no issues.
- Actual new model attempt: **1**, automatic retries **0**, fallbacks **0**.
- Offline comparison reconstructed source/code bindings, checked prepared/live
  manifests and all historical baseline file bindings, and confirmed 6/6 reference
  matches. Its Python network guard was installed before application imports;
  blocked network events were empty. No model calls were made by comparison.
- Static HTML QA checked 11 local links, all six result rows in each new review,
  expandable content and the copied one-document historical TAC scope. Exact
  original PDF page 4 has a direct link. Missing/unimplemented TAC fields remain
  historical, without invented metadata or new Terms classification.
- Literal credential scanning found no key in 86 generated/reservation files.
  Registry result bytes match the saved output; the OpenAI attempt registry
  remains absent. QA evidence:
  `output/gigachat_dsc_spans_20261028/qa_v01.json`.

## Artifacts and recovery

- Final preparation: `output/gigachat_dsc_spans_20261028/prepared_v02/`.
- Real raw response/result/decoded evidence/HTML:
  `output/gigachat_dsc_spans_20261028/live_v01/`.
- Searchable comparison with exact source text, both outcomes, actual usage,
  prospective reference and links to TAC/PDF:
  `output/gigachat_dsc_spans_20261028/comparison_v01/review.html`.
- Reproducible offline reference/comparison script:
  `output/gigachat_dsc_spans_20261028/comparison_v01.py`.
- The initial `prepared_v01` candidate predates the added durable-helper code
  binding and source-role guard. It was not sent and remains untouched, with stale
  bindings. Final checks and the real dispatch used only `prepared_v02`; no old
  manifest was rewritten to suppress drift.
- Consumed request slot:
  `data/experiments/gigachat_dsc_attempts/0f54ea0b82f6c88bfb1618bd55eb98d940a00189b93105acaed75b4c567afca4/`.
  Preserve it during workspace transfer/recovery. A copied output directory does
  not reset the attempt; deleting or rolling back the registry is outside its
  local guarantees. The first experiment's slot is also preserved.

Local revalidation without model calls:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.records.gigachat_dsc_spans import read_prepared; read_prepared(Path('output/gigachat_dsc_spans_20261028/prepared_v02'))"
```

Limitations:

- One exposed question, one observed response per format, assistant-authored
  reference, default sampling. Prompt, schema and catalog changed together; no
  causal isolation, statistical superiority, generalized accuracy, inference
  savings or independent scientific acceptance is established.
- Exact quote restoration does not prove that the selected fragment entails a
  field or applies to a particular sample. Model diagnostics remain unvalidated.
  The known-case source review does not replace an independent evaluation.
- Sentence partition and literal programme cue are finite English rules for this
  source, not a universal extraction algorithm. Unknown/ambiguous boundaries fail
  explicitly; future documents require separately frozen evaluation.
- Production integration, additional article tests, full application regression,
  browser interaction/visual QA and monetary cost verification were not performed.
  Original PDFs, DB, OCR, retrieval, Terms workflow and production defaults remain
  unchanged. API permission remains scoped to these GigaChat experiments.

Verdict: **The new named-span experiment passes the six-field/source-integrity
contract and all six prospective exposed-case sentence expectations.** The full
temperature programme is retained, and the first failed baseline is preserved.
Independent scientific quality remains a separate next step; no further model
request was sent.
