# Stage29: query evidence packets versus current answer contexts

22 October 2026. Algorithm `query_evidence_packet_v0.1`.
Prospective [protocol](records/query_packet_protocol_v0.1.md); inherited
[stage28 association outputs](records_stage28_protocol_association_2026-10-22.md).

Changed:

- Added a separate, opt-in packet builder and prepare/capture/export CLI. Production
  routes, retrieval selection/scoring, adequacy thresholds, database schema,
  chunking and extraction are unchanged. No original PDF or record is modified.
- A source association anchors only through an entire, uniquely occurring target
  sentence in selected evidence with exact article/page/text-layer/PDF identities
  and offsets. Unproven, derived or ambiguous bindings retain diagnostics. A
  missing part of an anchored block is attached in full, including unselected,
  unsupported and clipped qualifiers; no baseline evidence is removed.
- Reused all five stage28 cases and their saved native replies. Associations,
  origin and applicability remain unreviewed. The candidate wire excludes local
  PDF paths; the local artifact retains source identities, paths and diagnostics.
- Froze four questions, code, sources and settings before current-context capture:
  `literature`, `hybrid_cross_lingual`, `top_k=5`, `claims`, `auto` language.
  Captured actual `answer_question` traces inside a PostgreSQL repeatable-read,
  read-only transaction. An injected provider stops before generation and uses no
  real credential. A genuine insufficiency return remains a gate result.
- Exported searchable, read-only HTML and complete JSON for all four questions,
  including unmatched and rejected cases. Complete-page, registry and byte-budget
  checks prevent candidate network eligibility; no network-send implementation or
  runtime activation is added.

## Observed development results

These questions are exposed development evidence, not an independent scientific
evaluation. `context_prepared_before_generation` means that the current gate
allowed preparation; it is neither an answer nor proof of sufficient evidence.

| Frozen question ID | Baseline gate | Evidence items | Association contexts | New blocks | Current prompt bytes | Candidate bytes | Complete page occurrences, both |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| conductivity_protocol | allowed | 5 | 1 separate control | 0 | 71622 | 76793 | 10 |
| dsc_protocol | allowed | 4 | 0 | 0 | 62168 | 65846 | 7 |
| preparation_atmosphere | insufficient_evidence | 5 | 1 separate control | 0 | 64675 | 69173 | 8 |
| absent_material | allowed | 5 | 0 | 0 | 54734 | 57583 | 10 |

The two anchored contexts are occurrences of the **same Kayumov separate-control
block**, not two independent transfer successes. None of the four transfer cases
anchored in these selected contexts. The full control block was already present,
so no attachment was needed. Lack of an anchor is not absence of relevant evidence
in the corpus or a scientific recall score.

All **19 baseline Evidence objects**, in original order and with unchanged text,
IDs and metadata, were retained: **193240 raw characters**. All page registries
were proven for this capture. There were **35 complete page occurrences** in both
the existing prompts and new packets; these are repeated occurrences, not a count
of distinct pages. All four packets fit the frozen 100000-byte ceiling, but **0/4
are network eligible** because they retain complete pages. The third also retains
the baseline insufficiency gate. No scope condition was relaxed to produce a pass.

Combined current user-prompt bytes: **253199**; candidate JSON bytes: **269395**.
The JSON adds metadata and preserves text. These different representations are
reported as actual serialized sizes, not a compression ratio, token-cost measure
or projected saving. System prompts/API envelopes are not included in that byte
comparison.

The unchanged adequacy diagnostics expose a separate issue:

- The Istomina DSC question passes while its `missing_distinctive_terms` include
  `istomina`, `programme`, `dsc`. Generic matches do not prove those qualifiers.
- The Mars-regolith question passes while `mars`, `regolith` are missing. The
  question's negative-control intent does not establish corpus-wide absence.
- The preparation-atmosphere question returns `insufficient_evidence` while the
  selected evidence contains the control protocol block. No independent reference
  was supplied to label this a scientifically correct rejection or false negative.

No model answer or hallucination was generated. There were **zero new generative
API calls**; existing local BGE query embeddings did run for retrieval. The five
stage28 API calls were only replayed and remain a consumed historical budget.

## Capture infrastructure and provenance

`capture_v01` failed before a context/provider call because the default temporary
FastEmbed cache could not load `BAAI/bge-small-en-v1.5`. The failure directory is
preserved. The same frozen preparation/code/questions were retried as `capture_v02`
with process-local `FASTEMBED_CACHE_PATH` pointing at the existing project cache.
No download, index rebuild, question change or selection repair was performed.

All **eight cached files** match the historical stage07 query-cache hashes before
and after capture. The historical manifest SHA256 is
`3b864431a38e658e21ea83ae1bc2f65f9194fb49dd7e5d9b5c1f38db4f6607ac`.
The historical index-time weight identity was not independently established;
matching query-cache hashes do not repair that limitation. Original/selected PDFs,
existing index files, inputs and execution code hashes verify unchanged. Read-only
source capture is not a full database backup or portable restore test.

Tests run:

- Targeted constructed cases: **33 passed**, no failures/errors/skips;
  `pytest_target_v02.xml`. Full regression: **1927 passed**, no
  failures/errors/skips; `pytest_full_v01.xml`. Full regression used a dedicated
  temporary/cache directory outside the sandbox.
- `ruff check app scripts tests`: passed. `mypy app`: passed,
  **138 source files**. Initial type/import diagnostics were fixed before freezing;
  no execution policy, source rule or test was tuned after capture.
- Two real offline exports are byte-identical across report, HTML and manifest.
  **783** prepared and **813** capture bindings verify. Postflight checks confirm
  all baseline evidence, **10** exact sentence-offset references and **8** exact
  seed references. These are technical checks, not semantic entailment results.
- Static HTML checks: four query cards, one search input, no forms, **37** existing
  artifact/PDF links. Browser acceptance is unverified; local file navigation was
  rejected by the browser earlier in this chat.
- Exact configured-credential scan: **10** prepared/capture/export artifact files,
  zero matches. The credential was not printed. Eight local query-cache files
  remain unchanged. Final source/dependency snapshot and QA are separate artifacts.

Limitations:

- This additive development packet is not a compact production context. It cannot
  make an irrelevant baseline relevant. There is no scientific filter, independent
  answer reference, entailment validation, numeric admission or answer-quality
  comparison. Precision/recall remain null.
- Exact source identity and offsets do not validate the model's association or
  distinguish reported work from current experiments without scientific evidence.
  Origin and per-result applicability remain unverified.
- No new provider support, production guard activation, database write, new answer,
  clean install, other-machine restore, browser rendering, user time study or
  measured API cost saving is claimed. Local outputs/private corpus are not in Git.

Verdict:

The bounded stage29 implementation and offline comparison are complete. Source
preservation and repeatable export pass; the observed packets are **not ready for
API transmission**. Before paid answer comparison or compaction, the next bounded
stage should address query qualifiers and evidence sufficiency: preserve material,
article and property constraints, expose missing/unknown coverage, and test against
a separately frozen question/reference set. Do not hardcode the observed names or
silently change the current thresholds. Scientific annotation remains separate
from the user's automatic Terms workflow.

## Artifacts and reproduction

Local root: `output/records_stage29_20261022/`.

- `prepared_v01/`: questions, associations, code/input hashes saved before capture.
- `capture_v01/`: preserved failed attempt; `capture_v02/`: successful read-only
  traces, original prompts, evidence and source registry.
- `runtime_cache_preflight_v01.json`: cache hashes and process-local retry settings.
- `run_v01/review.html`, `report.json`, `manifest.json`: all four comparisons.
- `run_repeat_v01/`: byte-identical second export.
- `postflight_v01.py`, `postflight_v01.json`: source/offset/link/replay QA.
- `pytest_target_v02.xml`, `pytest_full_v01.xml`: successful regression results.
- `baseline_final_v01/`, `final_qa_v01.json`: source/dependency snapshot and final QA,
  excluding original corpus, database, model weights, outputs and credentials.

Offline re-export to a fresh directory, with no retrieval or API call:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.query_evidence_packet export --prepared output/records_stage29_20261022/prepared_v01 --captured output/records_stage29_20261022/capture_v02 --output-dir output/records_stage29_new_export
```

The clone alone lacks private run/corpus artifacts. Capturing again also requires
the existing PostgreSQL snapshot state and verified local model cache; a new live
retrieval run is not promised byte-identical. Exclusive artifact directories prevent
overwriting this frozen result.
