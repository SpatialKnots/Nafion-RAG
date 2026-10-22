# Records stage28: bounded property/protocol association through API

22 October 2026. ARIADNE, `records_protocol_association_v0.1`.
[Prospective protocol](records/protocol_association_protocol_v0.1.md).

The new provider-independent sentence-reference contract was exercised by **five
real OpenAI Responses requests**, all structurally/source-integrity valid. Every
one of the **11 declared targets** is accounted for. On seven transfer targets,
API and local baseline property-family categories agree on six; the separate
four-target control agrees on all four. These are **category agreement counts,
not scientific accuracy**. No experimental measurement records are created or
scientifically admitted.

## Why this stage

The [MVP direction](mvp_inference_strategy_2026-10-22.md) prioritizes local evidence
preparation and checks with replaceable API analysis. Stage27 exposed generic
measurement wording in an Istomina block about DSC. This stage tests a bounded
source-context association contract rather than requiring a universal local
scientific grammar before an API can be used.

The API adapter is native OpenAI Responses using the existing fixed HTTPS
transport. The reply/resolver contract is separate from that adapter. This does
not implement YandexGPT, GigaChat, another runtime provider, production integration
or universal API compatibility.

## Frozen inputs and scope

Unchanged stage27 raw output is replayed before preparation. Selection is fixed:
every stage27 transfer block with at least one literal cue, in parent page/block
order, followed by the separate Kayumov control. Guarded and ambiguous cue-bearing
sentences remain targets. Every sentence of each selected complete block stays
available as source context. No post-hoc sentence rescue, source repair or tuning
was performed after inference.

The parent **52-page / 851-block** transfer inventory remains immutable and bound
by inherited manifests. The bounded API scope is **four transfer blocks / seven
targets from two development-exposed PDFs**, plus one separate control / four
targets from a third PDF. No API inference is claimed for the remaining parent
blocks, including the proposed supplement.

The five exact requests, source page registry, local baseline, new code/tests,
protocol and inherited source/code/PDF hashes were saved in `prepared_v01/`
before inference. Preparation made no network request. Full registered blocks
were represented by the unchanged stage27 sentence spans; inter-sentence
whitespace is not supplied as separate evidence. Local complete source quotes
remain available for inspection. No complete registered page, PDF, local path,
baseline category, old policy state or scientific reference answer is transmitted.

All original PDFs, source text, ingestion/retrieval behavior, schemas and fields
of existing measurement candidates, database/review stores and stages25–27 code
and outputs are preserved. The new association schema is a separate versioned
development artifact.

## Contract and local baseline

Each reply target has one coarse `property_kind`: conductivity, thermal_analysis
or unknown. This separates property/method context families; it is not a complete
scientific property taxonomy or an extracted DSC property such as enthalpy.
Property, method and condition evidence are selected using sentence IDs from the
same supplied block and restored locally to exact source spans. A known property
requires property evidence. Unknown can retain conflicting evidence. Duplicates,
foreign/missing targets, foreign/duplicate references and malformed replies fail.

The local baseline identifies a finite literal conductivity/DSC family inventory
in the complete same block. It proposes the unique family only when stage27 also
has a scope_proposal; otherwise it preserves unknown. This is co-context evidence,
not a scientific association. The baseline does not infer method/condition links.

The API can propose broader links using the full block. Its response does not
replace stage27 guards, mixed-role states or incomplete-source diagnostics. All
results retain scientific_admission=not_evaluated and per_result_applicability=
not_established. A sentence reference proves location, not that every clause in
the sentence applies to the target or to a numerical result.

Origin is a separate model declaration (own_work_proposal, reported_work_proposal
or unknown). There is no dedicated origin-evidence field in this version;
origin declarations and explanatory notes are not scientifically verified by
the source-ID resolver. Their preservation must not be described as proven
own-work attribution. No numeric values, units or row-level record fields are
filled by this experiment.

## Actual bounded run

Requested/returned model alias: `gpt-6-astra`. One attempt per case, sequential,
no retries, repairs, model switch or budget extension. Medium reasoning, strict
schema, default service tier, no tools/temperature/seed, store=false,
stream=false, truncation disabled, 4096 output/reasoning tokens and 180-second
transport timeout per request. Maximum declared output cap was 20480 tokens;
maximum serialized request size was 100000 bytes. All requests passed the frozen
source/settings and no-complete-page guards before transport.

| Context | Targets | Result | Elapsed including local checks |
| --- | ---: | --- | ---: |
| Sanginov, PDF p.3, membrane drying block | 1 | unknown; no method/condition selection | 20.349 s |
| Sanginov, PDF p.3, conductivity protocol block | 3 | conductivity proposals | 15.446 s |
| Istomina, PDF p.4, DSC block | 1 | thermal_analysis proposal | 9.003 s |
| Istomina, PDF p.4, conductivity block | 2 | conductivity proposals; origin unknown | 16.892 s |
| Kayumov, separate PDF p.3 control | 4 | three conductivity proposals, one clipped unknown | 21.693 s |

Post-hoc inspection of every output, saved in `observed_proposals_v01.json`, found:

- The DSC target cites the source sentence naming the differential scanning
  calorimeter for property/method and the DSC conditions/programme sentences.
  These IDs remain confined to that block; no conductivity record is filled.
- The membrane-drying target stays unknown rather than becoming a conductivity
  measurement condition. The model still declares own_work_proposal; that is an
  unverified declaration, not acceptance or a correction of the prior citation guard.
- The sole transfer category disagreement is the Sanginov impedance/equilibration
  target: API proposes conductivity using same-block property sentences; the
  local baseline remains unknown because stage27 retained ambiguous_scope.
  The ambiguity concerns roles and remains visible. A property-family proposal
  does not resolve equilibrium completion or method-to-result applicability.
- Istomina pre-measurement equilibration remains source-supported context in the
  proposed association; model notes explicitly distinguish equilibration from a
  confirmed measurement temperature. Notes themselves are not source quotes.
- The clipped Kayumov tail remains unknown. The argon preparation sentence gets
  no condition selection; its note does not treat preparation atmosphere as an
  established measurement/conditioning atmosphere.

These are descriptions of model proposals on exposed sources, not independently
annotated success labels. Agreement is not a test against gold. In particular,
reported-work robustness and scientific precision/recall are not established.

Native total usage: **3469 input + 1824 output = 5293 tokens**, with **913 reasoning
tokens already included in output**, zero reported cached reads/writes. Request
and response IDs, usage, returned model and raw bytes are preserved locally.
Billing/invoice, token savings and controlled latency improvements were not
measured. The five-call budget is consumed; do not rerun it as inference.

## Validation

Changed:

- Added `protocol_association.py`: provider-independent contract, duplicate-key
  rejection, exact sentence/target accounting, finite local baseline and resolver.
- Added `protocol_association_run.py` and CLI: inherited frozen replay, source-only
  requests, explicit budget/page guards, raw persistence, first-failure stop,
  offline response replay and read-only searchable HTML/JSON comparison.
- Added 40 constructed tests and the prospective protocol. Project status and
  decision memory now record this bounded result and the remaining limitations.

Tests run:

- Targeted final suite: **40 passed, 8.74 seconds**, JUnit `pytest_target_v02.xml`.
  Tests use constructed sources/mocked transport; they do not make paid requests.
- Full regression: **1894 passed, 292.51 seconds**, one existing Starlette/httpx
  deprecation warning, JUnit `pytest_full_v01.xml`. Full regression ran outside
  sandbox with a dedicated temporary/cache directory.
- `ruff check app scripts tests`: passed. `mypy app`: passed, **136 source files**.
  An initial local mypy no-redef error was fixed before freezing/inference; both
  targeted constructed test runs passed. No later policy/request/schema tuning.
- Five real requests: five integrity-valid replies, all eleven targets accounted
  for. These results are separate from passing software tests.
- Two offline exports are byte-identical across report, HTML and manifest.
  Native raw responses replay exactly; **73** restored target/evidence spans are
  checked against unchanged exact block/page text and source identities.
- **738** preparation bindings and **765** live run bindings verify, including
  inherited original/selected PDF and execution code hashes. Old raw outputs replay
  unchanged. No current raw response or old field is silently repaired.
- Static HTML: five case cards, all complete source blocks, seven existing local
  artifact/PDF links, search and no writable form. Browser acceptance is not
  claimed: the browser previously rejected local file navigation in this chat.
- Exact configured credential scan: **35** prepared/live/replay artifact files,
  zero credential matches; the secret was not printed or included in requests.

Limitations:

- Four transfer blocks and a reused control are exposed development evidence,
  not a held-out scientific evaluation, full-article extractor or representative
  sample of conditions/negation/reported-work forms. Precision/recall remain null.
- Finite three-way context family labels; no full property taxonomy, numeric
  extraction, row/cell linkage, scientific admission or per-result applicability.
- Full-sentence evidence can include several roles. No semantic entailment checker,
  dedicated origin evidence or proof of independent experiments is added.
- API runtime/model alias are external. Offline raw replay is reproducible;
  deterministic equality of a new paid model response is not promised.
- No new provider/runtime activation, database/review-store write, user time study,
  invoice check, clean install, other-machine restore or browser acceptance.

Verdict:

The bounded stage28 contract/API comparison is complete. It provides locally
checkable source references for proposed property/method/condition associations,
including explicit DSC/conductivity separation in these saved model outputs.
It does not establish general scientific accuracy or authorize filling existing
records from category agreement. Next useful development is a versioned query
evidence-packet builder that preserves associated source sentences and unresolved
qualifiers, compared with the current answer context on independently assessed
questions. Keep the same-block and unverified-origin limitations explicit.

## Local artifacts and reproduction

Root: `output/records_stage28_20261022/`.

- `prepared_v01/plan.json`, `manifest.json`: pre-inference sources, requests,
  baseline, registry, budget and hashes.
- `live_v01/`: five native request/response/reply/resolved/result sets, final report
  and manifest. Raw responses must be preserved; the live budget is consumed.
- `replay_v01/review.html`, `report.json`, `manifest.json`: complete comparison.
- `replay_repeat_v01/`: byte-identical second offline export.
- `postflight_v01.py`, `postflight_v01.json`, `observed_proposals_v01.json`:
  artifact QA, native usage and all post-hoc proposal inspection.
- `pytest_target_v02.xml`, `pytest_full_v01.xml`: successful constructed test results.
- `baseline_final_v01/`, `final_qa_v01.json`: source-only dependency snapshot and
  final verification, excluding private corpus, outputs, databases and credentials.

Offline replay to a fresh directory makes no model calls:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_protocol_association export --prepared output/records_stage28_20261022/prepared_v01 --run-dir output/records_stage28_20261022/live_v01 --output-dir output/records_stage28_new_replay
```

The current clone alone lacks private corpus/run artifacts; the local snapshot
does not establish a portable clean environment. All artifact directories are
exclusive. Official references used before implementation: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).
