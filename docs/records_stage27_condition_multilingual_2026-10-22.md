# Records stage27: frozen RU/EN source-scope comparison

22 October 2026. ARIADNE, `records_condition_multilingual_v0.1`.
[Prospective protocol](records/condition_multilingual_protocol_v0.1.md).

The additive finite RU/EN policy emits **five source-scope proposals in three
transfer blocks**. One further block has a cue but all proposals are withheld;
847 blocks have no literal cue. This demonstrates recognition of additional
wording on development-exposed sources, not scientific accuracy, generalization
or completeness. **No new measurement records or model/API calls.**

## Frozen design and preserved evidence

Preparation was saved after constructed tests and before executing the new
policy on real transfer blocks. It binds the new code, tests and protocol,
the unchanged stage26 packet/report and inherited code/source/PDF hashes.
Preparation executes neither policy; this is covered by a constructed test.
The same prepared packet was used for two real runs, with no policy tuning after
inspection. The stage26 post-hoc English examples explicitly informed development;
these sources are not an independent holdout.

All stage26 scope is retained: **two primary task groups, three source PDFs,
52 pages and 851 complete registered blocks**. The proposed Sanginov supplement
remains part of its primary task, not an independent study. All 25 pages with
historical layout deferrals are included in the local raw-rule comparison with
their old diagnostics. This does not activate them for measurement extraction or
prove paragraph adequacy. No mappings were deferred in this packet.

Before applying the new policy, the old stage26 execution was replayed exactly,
including all 851 no_literal_cue outcomes, 2252 original raw events, summary and
the separate five-event Kayumov control. The new control also has five events
and is preserved separately; neither control contributes to transfer counts.
Old event boundaries and schemas are not rewritten to resemble new output.

Original PDFs, source text, candidate fields/identities, database/review stores
and prior execution code/outputs remain unchanged. The new policy adds no field
projection, temperature/unit parsing, environment assignment, equilibrium claim
or method-to-result applicability.

## Policy and observed output

The finite rules match literal Russian protocol phrases and selected English
passive measurement/preparation, equilibration and before-measurement wording.
They preserve line breaks, printed hyphen breaks and absolute Unicode offsets.
Every sentence-like source unit is retained, including unsupported text and
clipped boundaries. A finite abbreviation list suppresses some false punctuation
boundaries. Syntactic completion is not scientific paragraph completeness.

Negation, reported-work/citation and modal/future cues guard the **entire block**.
Exact guard spans stay visible even outside the event's clause. This deliberately
over-abstains: it does not resolve the semantic scope of negation, citation or
origin. The absence of a guard never establishes own-work origin. Mixed roles
and unproven initial/terminal boundaries withhold a single role assignment.

| Source document | Blocks | No literal cue | Cue withheld, no proposal | At least one scope proposal |
| --- | ---: | ---: | ---: | ---: |
| Sanginov 2021 | 321 | 319 | 1 | 1 |
| Sanginov 2021 - sup | 369 | 369 | 0 | 0 |
| Istomina 2021 | 161 | 159 | 0 | 2 |
| Total | 851 | 847 | 1 | 3 |

The new segmentation emits **2312 events**: 841 incomplete_source,
1183 guarded_source, 282 unsupported_clause, five scope_proposal and one
ambiguous_scope. Different sentence policies mean these event totals are not
paired scientific before/after measurements; comparison is by the same block.
Five proposals comprise four measurement_protocol and one conditioning_procedure.

236 blocks contain a guard: 194 have reported-work/citation cues, 52 negation,
19 modal/future cues; these sets overlap. Most guarded events have no condition
cue. Their guarded state is a diagnostic, not a detected experimental condition.

Post-hoc inspection of **all four cue-bearing blocks**, saved separately in
`observed_cue_units_v01.json`, illustrates the boundary:

- Sanginov, PDF page 3, block 14: the literal AC conductivity and cooling-mode
  sentences are measurement_protocol proposals. The impedance-spectra sentence
  also contains printed `equilibrat- ... ing`; both kinds remain visible and its
  state is ambiguous_scope. No equilibrium completion or record binding follows.
- Istomina, PDF page 4, block 14: the through-plane lithium conductivity sentence
  is a measurement_protocol proposal; the explicit pre-measurement equilibration
  sentence is a conditioning_procedure proposal.
- Istomina, PDF page 4, block 6: the generic `The measurements were performed`
  sentence belongs to a full block about **DSC thermal analysis**. It remains a
  generic measurement_protocol proposal, with no property attribution. Nitrogen
  flow and the temperature programme must not be inherited by conductivity records.
- Sanginov, PDF page 3, block 3: literal membrane drying is detected, but a `[28]`
  citation elsewhere in the block withholds assignment. This is an intended
  conservative refusal, not proof that the drying sentence describes prior work.

These observations explain outputs; they are not independent reference labels,
scientific error counts or a revised frozen denominator. Precision/recall remain
null, scientific support not_evaluated, applicability not_established.

## Validation

Changed:

- Added separate `condition_multilingual.py` policy and an additive event contract
  with exact cue/guard spans, explicit boundaries, mixed-role and refusal states.
- Added prepare/run comparison/export and CLI, preserving all old raw events
  beside new events for every registered block, separate controls and all sources.
- Added 63 constructed tests and the prospective protocol. Updated project
  status documents to describe the final result and its limitations.

Tests run:

- New targeted suite: **63 passed in 14.26 seconds**. JUnit:
  `output/records_stage27_20261022/pytest_target_v02.xml`.
- Full regression: **1854 passed in 274.63 seconds**, one existing
  Starlette/httpx deprecation warning. JUnit: `pytest_full_v01.xml` in the same
  directory. Both successful runs used dedicated temporary/cache directories
  outside the sandbox after its temporary-directory access failure.
- `ruff check app scripts tests`: passed.
- `mypy app`: passed, **134 source files**.
- Both real exports are byte-identical across report, packet copy, HTML and
  manifest. The preparation packet copy is exact. **731** frozen input/code/output
  bindings verify, including inherited original/selected PDF hashes and old code.
- Independent artifact QA checked all 851 blocks, all **4603** event/cue/guard
  spans, full event coverage except surrounding whitespace, old results/control,
  new control replay and every original source/layer/PDF identity.
- Static HTML checks: **52 page rows, 851 block cards, 55 existing local links**,
  one search input, no writable form, every exact full block present. The browser
  rejected the local `file://` protocol; no workaround was attempted and browser
  rendering/search/PDF-click acceptance is not claimed.

Initial test attempts are not successful validations: the first found an overly
strong constructed assertion about an abbreviation boundary plus inaccessible
pytest temporary storage. The assertion was corrected to reflect the declared
finite segmentation policy. The first external retry lacked the basetemp parent;
that directory was created before the successful targeted run. Two mypy typing
errors were fixed before freezing; no source-policy change followed real outputs.

Limitations:

- Finite, development-exposed RU/EN cues and guards; unsupported languages,
  paraphrases, attribution forms and paragraph joins remain unsupported.
- Block-wide guards intentionally suppress unrelated positive clauses. Punctuation
  heuristics do not establish complete paragraphs or semantic origin.
- Generic measurement wording can refer to DSC or another property. Property/
  protocol association and per-result condition binding are not implemented here.
- No independent scientific gold, precision/recall, corpus/article completeness,
  new measurements, new API calls, database/review-store writes or scientific admission.
- Static HTML checks are not browser acceptance. The source/dependency snapshot
  records this local environment; clean installation and other-machine recovery
  are not tested in this stage.

Verdict:

The requested bounded RU/EN comparison is complete and reproducible. It expands
literal source recognition while preserving negative results, ambiguous cases
and every prior event. It does not establish a general condition extractor.
Next bounded engineering work is a separately versioned source-only association
of generic protocol wording with its explicit property/method context, retaining
DSC/conductivity separation and unresolved cross-block boundaries. Freeze a new
comparison before execution. Independent scientific evaluation remains separate.

## Artifacts and reproduction

Local root: `output/records_stage27_20261022/`.

- `prepared_v01/`: immutable pre-execution packet and manifest.
- `run_v01/review.html`, `report.json`, `prepared_packet.json`, `manifest.json`:
  complete comparison and source evidence.
- `run_repeat_v01/`: second byte-identical export.
- `postflight_v01.py`, `postflight_v01.json`: read-only artifact QA and results.
- `observed_cue_units_v01.json`: post-hoc inspection scope, not gold annotations.
- `pytest_target_v02.xml`, `pytest_full_v01.xml`: successful test evidence.
- `baseline_final_v01/`: source-only snapshot with installed dependency versions,
  excluding PDFs, database, models, outputs and secrets. Its manifest and separate
  `final_qa_v01.json` record the final snapshot verification.

Preparation packet SHA-256:
`6e351ed4298c26f42ba2247969eb41c6ae772c20ee46cb0d4e8242457edeefb6`.
Report SHA-256:
`7b426635a6abaf62308ea27391b3f08fc319d0c0d9566ea406c472873be4ca38`.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_condition_multilingual prepare --output-dir output/records_stage27_20261022/prepared_v01
.\.venv\Scripts\python.exe -X utf8 -m scripts.records_condition_multilingual run --prepared output/records_stage27_20261022/prepared_v01 --output-dir output/records_stage27_20261022/run_v01
```

Output directories are exclusive. To repeat these commands, use new output
directories; never overwrite the preserved preparation or runs.
