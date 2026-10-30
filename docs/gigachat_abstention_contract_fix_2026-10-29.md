# GigaChat: explicit insufficient-evidence contract, 29 October 2026

The user requested the next step after the
[four-question batch](gigachat_answer_batch_2026-10-29.md). Its two negative
responses used `answerable=false` with nonempty explanatory claims and were
correctly rejected. This stage clarifies the model instruction offline; it
does not consume another model budget or turn the failed replies into successes.

Changed:

- Added an explicit GigaChat user instruction for both `claims` and `mini_review`:
  when evidence is insufficient, return exactly
  `{"answerable": false, "claims": []}`. Explanations and missing-information
  statements must not be inserted into `claims` for that result.
- Explicitly states that `answerable=true` requires at least one supported
  scientific statement with citation IDs. The existing exact-ID instruction and
  request-local citation enum remain unchanged.
- Minimal patch in `app/generation/gigachat.py`: user instruction only. The
  scientific system prompt, shared historical/OpenAI formatters, native JSON
  Schema, `_parse_response`, local consistency check, citation validation, public
  response shape, model/limits and evidence/retrieval behavior are unchanged.
  No conditional schema keywords or unverified endpoint capability were added.
- No claim deletion, ID normalization, new diagnostic response field, repair,
  fallback or automatic retry. An inconsistent response still raises
  `GigaChat answerable and claims are inconsistent`.

Tests run:

- Final affected suite: **168 passed**, failures/errors/skips = 0, one existing
  Starlette/httpx TestClient deprecation warning. Includes GigaChat runtime,
  generation, smoke/batch safety, UI, answer evaluation and historical trace tests.
  JUnit: `output/gigachat_abstention_tests_20261029_v01.xml`.
- Six new regression cases: two prompt styles with an exact empty-claims
  instruction and unchanged native schema; four real answer-service cases using
  constructed retrieval/transport. A valid `false + []` returns
  `insufficient_evidence` with no answer/claims/citations; both observed patterns
  of `false + nonempty claims` and `true + []` remain explicit errors.
- Ruff `app scripts tests`: passed. Separate offline audit script: passed.
  Mypy `app`: **180 source files**, no issues. `git diff --check`: passed.
- Offline ASGI replay of all four unchanged saved batch responses reproduced
  the exact historical HTTP statuses **200, 200, 502, 502** and full bodies.
  The two original malformed abstentions are still rejected, not reclassified.
- Captured four candidate native request bodies with the new instruction.
  Verified that schema, system message, language, question, citation instruction,
  evidence and other request settings are unchanged. Only the new common user
  instruction is inserted. Candidates were not sent or reserved for dispatch.
- Verified all four old preparation/live manifests, final batch reviews and
  source snapshot, plus all four result/attempt slots. Old current-source
  bindings now show the expected `app/generation/gigachat.py` drift; no manifest
  was rewritten or old guard reapproved. Pre-fix provider/test sources were
  archived before editing and their hashes verified.
- Replay DB connections were forbidden and native transport replaced only by
  explicit offline placeholders/saved bytes. New model/API/DB calls: **0**.
  Network denials: `[]`; exact configured-credential matches: **0**.

Artifacts:

- Pre-fix provider/test archive:
  `output/gigachat_abstention_contract_20261029/baseline_v01/`.
- Reproducible capture/replay script:
  `output/gigachat_abstention_contract_20261029/offline_check_v01.py`.
- Per-case candidate requests, audit and manifest:
  `output/gigachat_abstention_contract_20261029/offline_v01/`.

Limitations:

Prompt clarification is not a guarantee that the provider will obey it. No new
live result after this instruction change exists. The conditional relationship
between `answerable` and `claims` is still enforced locally, rather than claimed
as a new schema constraint. Independent scientific acceptance and general
accuracy remain unestablished. The ORM/session lifecycle observation and source
wording/citation caveats from the batch were not addressed by this format patch.
The complete unit suite was not rerun; only the stated affected suite is new.

Verdict: the minimal abstention instruction is implemented and passes offline
regressions while preserving strict rejection. Next live verification requires
a fresh separately authorized frozen experiment; the previous four-call budget
and slots remain consumed. Historical responses must remain unchanged.
