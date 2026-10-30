# Offline quantity / experiment / source prototype

29 October 2026, Asia/Yekaterinburg. This stage implements the user's request to
prototype requested-information links on saved answers and counterexamples.
It introduces no new model/API/OAuth calls or production behavior.

Changed:

- Added the pure module `scripts/requested_context_links.py` and runner
  `scripts/run_requested_context_links.py`. The finite RU/EN grammar proposes
  duration versus equilibrium criterion, explicit sample labels, work/author/year,
  property/method cues, experimental-stage cues and literal temperature.
  All fields are experimental diagnostics, not a production schema.
- Source values/criteria retain exact offsets into the supplied evidence. Each
  source statement is mapped, only when unique, to an exact registered page
  substring with article/chunk/citation identity, page, selected text layer,
  layer ID, original PDF path and SHA256. Extraction noise is preserved. Missing
  or ambiguous page mappings remain unresolved; source text is never repaired.
- Added diagnostics for preparation/drying/soaking versus measurement dwell,
  competing or mixed sample labels/stages, other recorded author/year metadata,
  missing method/property/temperature links, negations, hypotheses, bounds,
  ranges and multiple distinct duration candidates. Partly recognized comparison
  or multi-requirement queries explicitly retain unparsed requirements.
- Claims can link only to their cited source candidates. Matching a value or a
  criterion is an unverified proposal. Claim-side sample/stage/property/condition
  conflicts remain visible even if a source has the same number. No context or
  scientific identity is inferred from equal values or a shared sentence.
- Source inventory is kept separate from answer validity: the three previously
  rejected outputs and one valid model abstention keep their historical layer.
  Inventorying a filtered case does not validate an answer that was never produced.
- Runtime `/answer`, prompts, models, limits, retrieval, DB/index, immutable PDFs,
  historical responses and consumed slots were unchanged. The runner uses local
  files and pure modules, without database imports; socket operations are forbidden.

Tests run:

- **81 tests passed**: 47 new constructed context/anchor tests plus the earlier
  34 duration-expression tests. Final JUnit:
  `output/requested_context_links_tests_20261029_v05.xml`.
- Coverage includes a fully explicit local-link proposal, preparation/soaking/
  drying, wrong sample/article/method/temperature, missing metadata, uncited
  matches, negation, hypothesis, mixed stages/samples, conflicting values,
  multi-part questions, bounds/ranges, cross-sentence association and exact
  source/page/layer/quote mapping failures. Invalid provenance dimensions fail
  explicitly. These are constructed software fixtures, not scientific gold.
- Ruff passed on both new scripts and their test file. Strict mypy passed on the
  pure link module, one source file; runner-wide typing is not claimed.
- The runner verified the parent HTML/report manifest and all frozen parent
  bindings, including native requests/responses, prior attempt records and PDF
  hashes. Checked selected evidence equals registered chunk text. Every returned
  value/statement offset and page anchor was checked against its exact input.
  No retrieval, embedding, model transport or DB connection was performed.
- Final output:
  `output/requested_context_links_20261029/review_v04/` contains the bound JSON,
  searchable HTML, copied bound Python/Markdown source snapshot and manifest.
  Static HTML checks verified eight case cards, six documents in the eight TAC
  columns and 118 existing PDF links (including repeated page links). Missing
  metadata and uncollected Conclusions/Terms remain explicit. Browser rendering
  and interactive search execution were not tested.
- Intermediate test logs and `review_v01`–`review_v03` are retained separately.
  Development checks caught a negative fixture that actually contained the
  criterion pattern, typing issues, and missing recognition of the Russian word
  `электропроводность`; these were corrected before the final 81-test run.
  Early output bindings describe earlier code, not current admission contracts.

Observed results:

- Eight exposed historical cases produced **112 source candidate occurrences**,
  all with exact unique page anchors. Counts include repeated sources across
  repeated questions; they are not 112 independent experiments or distinct facts.
- **All 112 experimental-context links remain unresolved.** A syntactically
  complete constructed example gets only an unverified local-link proposal;
  real selected text does not become scientifically supported by that test.
- For both previously accepted exact-duration failures, the answer expresses a
  criterion rather than a duration. Their source `E3` separately contains
  preparation-related time expressions and the unchanged-spectrum criterion.
  The prototype does not promote those preparation values into a measurement
  dwell time or infer a number from equilibrium.
- The repeated criterion statement maps to Kayumov page 3 with its original
  line breaks and formula noise. In isolation, that statement often lacks a
  literal requested conductivity/method or stage link. The prototype deliberately
  does not silently attach the preceding sentence or infer coreference.
- The `blacklist` case retains the provider finish reason and historical HTTP
  502. Its selected-source inventory is not a completed qualitative model answer;
  the cause of provider filtering is still unknown.

Limitations:

This is a finite context-link prototype, **not general semantic coverage or
scientific entailment validation**. Same-statement mentions, recorded author/year
metadata and exact quotation establish traceability, not experimental truth.
The grammar misses implicit samples, synonyms, unsupported conditions, tables,
multi-clause relations and cross-sentence references. It does not convert units
or establish numeric equivalence. Some stage cues are intentionally coarse:
`высушенные образцы` can trigger a drying mention without proving which duration
belongs to drying. Such cases remain unresolved, rather than being assigned a
scientific category by the prototype.

Missing links are not proof of insufficient source evidence, source-wide absence
or an incorrect scientific answer. All real candidates remaining unresolved is
evidence of the prototype's limited coverage, not successful semantic validation.
No accuracy, recall, reliability or scientific acceptance estimate is available.
The exposed cases and assistant-authored fixtures are not independent annotation.
The existing long-lived-server ORM/cache limitation remains open.

Verdict:

The offline prototype now exposes the requested quantity, experimental-context
diagnostics and exact source anchors together, with regression checks against
misattribution. It is suitable for development inspection and **not ready as a
runtime scientific gate**. The original user workflow remains automatic; no
mandatory per-case or per-Term approval was introduced.

The next substantial step is source-linked event extraction with explicit
cross-sentence/context dependencies and separate requirements for multi-part
questions, followed by an independently annotated evaluation set. Decide its
method and partial-answer/uncertainty policy before connecting any diagnostic to
`/answer`. Further live model calls and a general semantic implementation are
not claimed by this bounded prototype; all earlier live budgets remain closed.
