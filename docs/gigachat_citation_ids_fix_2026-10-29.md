# GigaChat citation IDs: request-format fix, 29 October 2026

The [live /answer smoke](gigachat_answer_smoke_2026-10-29.md) returned HTTP 502
because both claims used `"[E1]"` instead of the registered ID `"E1"`. The user
authorized the proposed minimal format fix. This stage makes no new model call.

Changed:

- `app/generation/gigachat.py` now adds a request-local `enum` to the native
  schema's `citation_ids.items`. Values come only from the supplied Evidence IDs,
  deduplicated in their existing order. Evidence text cannot add allowed IDs.
  Each generation builds its own schema; IDs do not leak between requests.
- Both `claims` and `mini_review` prompts explicitly list the allowed exact ID
  strings and explain that heading brackets are display delimiters. The shared
  historical/OpenAI prompt functions were not changed.
- Source text, the scientific system prompt, model, limits, source selection,
  scoring and public answer shape remain unchanged. `_parse_response` and the
  production service's citation validation are unchanged. No bracket stripping,
  whitespace trimming of IDs, remapping, retry, fallback or answer repair.
- Added regression coverage in `tests/unit/test_gigachat_generation.py` for both
  styles, duplicate supplied IDs, misleading IDs inside source text, separate
  request scopes, and rejection of `"[E1]"`, `" E1"`, `"E1 "` and foreign IDs.
  The known raw ID `"E1"` remains accepted by the actual answer service with
  constructed retrieval/transport.

Tests run:

- Final affected suite: **155 passed**, failures/errors/skips = 0, one existing
  Starlette/httpx TestClient deprecation warning. Covers GigaChat runtime,
  generation, smoke reservation, UI, answer evaluation and historical trace tests.
  JUnit: `output/gigachat_citation_ids_tests_20261029_v02.xml`.
  The earlier 115-case run is superseded, not added to this count.
- Ruff `app scripts tests`: passed. The offline audit script also passed Ruff.
  Mypy `app`: **180 source files**, no issues. `git diff --check`: passed.
- Offline transport-boundary capture on the frozen real question/evidence:
  **74093 bytes**, SHA256
  `6d16aa501118f63a5a19238d7d33ba5d14e33a134a63d8f5f2fb6e82ed48ce38`.
  Allowed IDs: `E1`–`E5`. Only the exact-ID user instruction and schema enum were
  added; question, evidence block, system prompt, model and limits match the
  historical request. This candidate was not sent to the provider.
- Replayed the unchanged historical native response through the current parser
  and service validator: the same `generated claim contains unknown citations:
  ['[E1]']` rejection is retained. This is a negative regression result, not an
  accepted or repaired answer.
- Verified all five current-smoke output manifests, the five older DSC output
  manifests, and both current-smoke parent/continuation registry results. All
  saved output bytes remain unchanged. Old current-code bindings now detect the
  expected `app/generation/gigachat.py` drift; no manifest was rewritten to hide it.
- Archived both pre-fix provider and runtime-test files before editing. The
  provider archive matches the historical contract; both archive hashes match
  their separate baseline manifest. The first offline audit incorrectly assumed
  the historical contract also bound the runtime test file and stopped at an
  inventory assertion. The corrected audit checks the actual declared inventory;
  the incomplete `offline_v01` remains separate from successful `offline_v02`.
- Offline audit installed its network guard before application imports.
  Network events: `[]`; new model/API/DB calls: **0**.

Evidence and reproduction:

- Pre-fix code/test archive:
  `output/gigachat_citation_ids_20261029/baseline_v01/`.
- Audit script: `output/gigachat_citation_ids_20261029/offline_check_v01.py`.
- Successful candidate request, report and manifest:
  `output/gigachat_citation_ids_20261029/offline_v02/`.
- The native `response_format.schema` / `strict` envelope was checked against
  [official GigaChat structured-output documentation](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output).
  This documentation check is not a live test of enum enforcement for this patch.

Limitations:

- Exact endpoint acceptance/enforcement of the new enum and a successful real
  model reply after the fix remain unverified. No new paid call was made; the
  previous smoke's one-model budget and slots remain consumed.
- Software/format checks are not scientific acceptance or independent accuracy.
  Existing whole-page exposure, context relevance and extraction noise are not
  addressed by this patch. The complete unit suite was not rerun; only the stated
  affected tests and static checks are new results.
- The old offline smoke helpers that require the original current-code hashes
  will now reject drift. Preserve historical evidence and prepare a fresh
  separately authorized experiment before any future live verification.

Verdict: the minimal request-format fix is implemented and passes offline
regression checks. Unknown IDs still fail explicitly. Live verification and
independent scientific acceptance remain open.
