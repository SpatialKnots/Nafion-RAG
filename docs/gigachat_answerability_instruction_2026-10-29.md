# GigaChat: requested-information guidance, 29 October 2026

After the [two-case live check](gigachat_abstention_live_2026-10-29.md), the user
requested the next offline step. That check found a structurally valid answer
which supplied an equilibrium criterion instead of the requested exact duration.
This stage adds generic model guidance; it does not add a local scientific
coverage classifier or claim that the observed semantic failure is solved live.

Changed:

- Added a common GigaChat user-instruction block for both `claims` and
  `mini_review`: `answerable=true` requires evidence for the user's requested
  information, tied to its sample, method and conditions. A citation for a
  neighboring fact is not sufficient by itself.
- For an exact reported value or duration, explicitly prohibit replacing the
  requested value with a completion criterion, unspecified waiting time or vague
  qualitative description. Do not borrow values from another sample/work or
  confuse preparation, drying or soaking durations with measurement dwell time
  without an explicit source link.
- When the question asks for a method or criterion itself, directly supported
  qualitative answers remain allowed. This is not a numeric-only filter or a
  new local all-or-nothing completeness gate.
- Only `app/generation/gigachat.py` user formatting changed. The scientific
  system prompt, public/native schema, citation enum, parser, consistency/ID
  validators, retrieval/scoring, thresholds, model/limits and source text are
  unchanged. Shared historical/OpenAI formatters were not edited.
- No article names, regolith terms or previous case IDs appear in the new
  guidance. No response repair, forced status override, regex-based scientific
  decision, fallback or retry was introduced.

Tests run:

- **180 affected tests passed**, failures/errors/skips = 0, one existing
  Starlette/httpx TestClient deprecation warning. JUnit:
  `output/gigachat_answerability_tests_20261029_v01.xml`. Covers runtime,
  generation, smoke/batch safety, UI, answer evaluation and historical trace paths.
- Twelve new constructed question/evidence/reply combinations across both styles:
  exact time versus equilibrium criterion; measurement dwell time versus a
  preparation duration; reported conductivity of one specimen versus an
  unreported value of another. These protect exact question/evidence transmission
  and adapter round-trip behavior for valid answers and abstentions. They do
  **not** test real model reasoning or automatically prove scientific coverage.
- After a line-length-only formatter correction, a focused style/fixture subset
  passed **15 cases**; this overlaps the 180-case suite and is not added to it.
  JUnit: `output/gigachat_answerability_style_tests_20261029_v01.xml`.
- Ruff `app scripts tests` and the audit script: passed. Mypy `app`: **180 source
  files**, no issues. `git diff --check`: passed.
- Offline ASGI replay on the two exact saved live responses reproduced both
  HTTP 200 statuses and full bodies, including the known semantically inadequate
  duration answer. The format validator still accepts that old contextual claim:
  **no local semantic coverage validator has been implemented**.
- Separately replayed the two earlier malformed `false + nonempty claims`
  responses through the current parser: both still raise the original
  `GigaChat answerable and claims are inconsistent` error. Old answers were not
  edited, reclassified or converted into correct abstentions.
- Captured two new native candidate requests. Verified that only the generic
  answerability block is inserted; existing language/abstention/ID instructions,
  question, evidence, scientific system message, schema and settings match their
  prior versions. The candidates were not sent or reserved for model dispatch.
- Verified old output manifests/slots and archived pre-edit provider/test files.
  Old current-source guards now observe the expected provider-file drift; no
  old guard or scientific result was reapproved. All other declared source
  bindings match. New model/API/DB calls: **0**; DB connections were forbidden
  during replay, network denials `[]`, exact credential matches **0**.

Artifacts:

- Pre-edit source/test archive:
  `output/gigachat_answerability_20261029/baseline_v01/`.
- Reproducible offline capture/replay:
  `output/gigachat_answerability_20261029/offline_check_v01.py`.
- Candidate requests, exact current-code hashes, audit and manifest:
  `output/gigachat_answerability_20261029/offline_v01/`.

Limitations:

The instruction may still be ignored or misapplied by a model. This stage does
not demonstrate a corrected live answer or scientific rejection of an irrelevant
but cited fact. The old task mismatch remains visible and accepted by the
unchanged format parser in replay. Independent scientific acceptance, general
accuracy and a validated intent/coverage algorithm remain open. Existing
source/extraction and cache/session limitations were not addressed. No complete
unit-suite run is claimed beyond the affected checks above.

Verdict: generic requested-information guidance is implemented and verified
offline without changing strict parsing or scientific data. A future bounded
live pair should check exact-value insufficiency together with a supported
method/criterion question, to detect both substitution and excessive abstention.
No live budget was authorized or spent in this stage; all previous slots remain
consumed. Keep the old exposed-case outcomes distinct from any future result.
