# Twelve real experimental excerpts: preliminary relation review

29 October 2026, Asia/Yekaterinburg. The user authorized preparing twelve real
experimental excerpts with questions, exact quotes and preliminary annotation,
then checking the unchanged offline dependency prototype. No API/OAuth or DB
calls, retrieval, embedding, model generation or production changes were made.

Changed:

- Added `docs/records/real_experiment_cases_v0.1.json`: twelve distinct raw page
  intervals from five works, selected purposefully from the 25 already exposed
  registered source pages. The set covers measurement, preparation, different
  samples/temperatures, lower bounds, an explicit exclusion and values absent
  from the selected operation's description. Source selection is not random.
- Each case includes a question, exact unmodified quote, page offsets and hashes,
  original PDF/layer identity, a preliminary qualitative expected answer and
  source-linked annotations. These answers are assistant interpretations, not
  model-generated or independently confirmed scientific answers.
- Seven dependencies are provisionally required, two same-measurement
  interpretations are prohibited, and two cases retain explicit open notes.
  Dependency types and finite-template scope are separate. Unannotated pairs are
  not treated as negatives. Procedure sequence is broader than the prototype's
  existing measurement-reference templates.
- Added `scripts/real_relation_evaluation.py` and
  `scripts/run_real_experiment_cases.py` for sparse directed-anchor comparison.
  The scorer records aligned matches, misses, forbidden interpretations,
  unmappable references and unannotated proposals separately. It cannot establish
  scientific correctness or infer a complete answer from a graph.
- The builder and its provenance are archived in
  `output/real_experiment_cases_20261029/build_cases_v01.py` and
  `build_manifest_v01.json`. Source quotes, annotation and unchanged prototype
  hashes were bound before relation evaluation. No prototype rules were tuned
  against these cases.

Tests run:

- **8 new scoring-control tests passed**, JUnit:
  `output/real_relation_evaluation_tests_20261029_v01.xml`. Covers directed
  matching, missing versus forbidden relations, unannotated proposals, unmappable
  references, input immutability and invalid raw spans/graph IDs/direction.
- Ruff passed for the scorer, evaluation runner and scoring tests. Strict mypy
  passed for the scorer module, one source file. The earlier 113 prototype tests
  belong to the preceding stage and were not rerun or counted as new tests here.
- The one-off frozen selection builder retains its original long data lines;
  its initial Ruff invocation reported line-length diagnostics. No claim of
  builder-wide lint success is made. Final evaluator scripts passed Ruff.
- Verified parent/build manifests and frozen bindings, all twelve exact quote
  offsets/hashes, immutable original PDF hashes, and **all eight selected full
  pages against fresh PyMuPDF `get_text("text")` extraction**. All pages matched
  the registered original text exactly. No PDF or stored extraction was changed.
  Python/PyMuPDF versions are recorded in the final JSON report.
- Executed the unchanged prototype on all twelve curated exact excerpts. These
  are explicitly derived excerpt IDs, not DB chunk IDs, production retrieval
  results or native LLM requests. Socket operations were forbidden; runner
  imports no database modules. Model calls and scientific-answer scoring: zero.
- Final output: `output/real_experiment_cases_20261029/review_v02/`. Searchable
  HTML includes every question, exact quote, preliminary annotation, graph,
  comparison, full registered page and all five source works in the eight TAC
  columns. Static QA verified twelve case cards, five TAC rows and seventeen
  existing original-PDF links. Missing metadata and uncollected fields remain
  explicit. Browser rendering and search execution were not tested.
- `review_v01` is preserved before the final runner's line-wrap correction and
  addition of extraction-runtime versions. Data/annotations and prototype
  remained the same; no old result was overwritten.

Observed comparison with preliminary annotation:

| Quantity | Count |
| --- | ---: |
| Required source dependencies | 7 |
| Matched | 1 |
| Missed | 6 |
| Unmappable required references | 0 |
| Forbidden same-measurement interpretations checked | 2 |
| Forbidden interpretations proposed | 0 |
| Unannotated proposals | 0 |
| Cases without a proposal | 11 of 12 |

The one match is the previously exposed Kayumov impedance-instrument / recorded
spectra semicolon relation. It is not new evidence of generalization. Misses
include cleaning followed by rinsing; the drying/thermostatting/breaking sequence
of calorimetry ampoules; degassing followed by connecting an ampoule to a sorption
instrument; the dissertation's two-hour dispersion-cell hold followed by spectra
registration across a figure caption; and the reference to obtained impedance
dependencies. Those six relations fall outside the current finite templates.

The two checked boundaries keep H2O2 cleaning separate from HCl protonation and
calorimetry measurement separate from drying. Zero violations of these two
annotations does not establish general specificity or safe scientific answers.

The questions also expose distinctions that the graph itself does not answer:
at least 24 hours is a bound, not an exact dwell time; a solvent-specific 40°C
condition is not the generic 30°C condition; sample 3 cannot inherit sample 2's
conductivity; low-frequency elements are explicitly excluded in resistance
determination; thermal equilibrium/constant mass do not supply a numeric wait.
The dispersion-cell excerpt really reports two hours, while Kayumov's selected
criterion excerpt does not. These remain preliminary source readings with exact
quotes, not an evaluated scientific answer pipeline.

Limitations:

- Annotation is assistant-authored and preliminary. No independent annotator or
  reviewer participated. Counts are comparisons with those annotations, not
  independent scientific accuracy, recall or confidence estimates.
- All source pages were exposed in earlier stages. Twelve intervals are not
  twelve independent experiments: several share pages/works, and the two
  dissertation contexts overlap in their spectra-registration sentence. The
  only successful dependency was already used while developing the prototype.
- Required annotations are sparse and cover a broader procedure-reference task
  than the current templates. Misses describe that coverage gap; they do not
  alone measure an in-scope statistical error rate. Cases without a proposal
  include both source boundaries and unsupported syntax; 11/12 is not a general
  scientific uncertainty rate. Open annotation notes remain visible.
- Questions/expected answers were saved for review but no LLM answered them in
  this stage. Response correctness, absence across the article/corpus and a full
  event-extraction method remain untested. Original provider-filter failures,
  runtime ORM/cache limitations and all closed live slots remain unchanged.

Verdict:

The requested real-text set and preliminary comparison are complete. The current
finite templates recover only their already known example and miss six broader
source dependencies. Further rule additions alone are not established as a
scientific solution. Preserve this set as exposed development evidence; a justified
semantic extraction method and separate independent annotation/evaluation are
needed before runtime admission or reliability claims. `/answer` remains unchanged.
