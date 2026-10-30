# GigaChat DSC smoke: 28 October 2026

Changed:

- Added an isolated experimental GigaChat adapter and CLI:
  `app/records/gigachat_dsc.py`, `scripts/gigachat_dsc.py`.
  Production provider, OpenAI dispatcher, DB, PDFs, OCR, retrieval and Terms remain
  unchanged. The user's permission applies to this GigaChat test only.
- Froze a new GigaChat request from the unchanged stage49 question, five source
  regions, prompt and six-topic Reply schema. Request: **8329 bytes**, SHA256
  `c0d95fc74cf990186cbb23ed22ca255c0c73a8fb704ad56b942f81d5fadb1438`.
  `GigaChat-2-Max`, strict JSON Schema, max output 4096 tokens, timeout 180 s;
  one model attempt, no retries or fallback. Sampling uses provider defaults;
  OpenAI-specific settings are not claimed equivalent.
- Credentials loaded from the ignored local `.env`; values were not printed or
  committed. Scope `GIGACHAT_API_PERS`. Verified TLS used the existing system trust
  store; no certificate installation or disabling of verification was needed.
- Actual OAuth exchange and GET models/balance succeeded. The exact requested
  model was listed; observed pre-request Max package balance was **25000000**.
  No purchase, payment-method setup, billing upgrade or PAYG Scope was used.
- **One real model attempt completed**, without retry or fallback. Declared
  returned model: `GigaChat-2-Max:2.0.30.01`; finish reason `stop`.
  Model request elapsed **14.086752800038084 s**; dispatch including local
  checks and account calls **40.98074979998637 s**.
  Observed usage: prompt **2167**, completion **694**, total **2861** tokens,
  precached prompt **3**. Monetary cost remains unknown; a package balance does
  not independently verify tariff or billing cost. No post-request balance call.
- Raw response preserved before parsing, with no credential redaction needed:
  SHA256 `9f132e75de9c17acf5183d72cf3c7c3347dac9018836a7adfc737016544a5b34`.
  Request ID `19cb8fe9-061e-441f-82cd-5574e86a4ef3`; response ID absent.
  A persistent checkout-wide GigaChat attempt reservation prevents another
  dispatch of the same request in another output directory.

## Actual outcome

The API connection works. The answer is **response_invalid**, not an accepted
scientific answer and not a successful abstention.

1. The six-item array contains `sample_handling` twice, once present and once
   ambiguous. `measurement_environment` is absent. The unchanged Reply validator
   rejected it: `DSC reply must account for all six topics exactly once`.
2. Separate offline literal diagnostics found **0/5 unique exact M1 quotations**.
   The response removed line breaks, changed source characters (`◦C`/`°C`,
   `ﬂow`/`flow`), and its temperature-programme quote omitted source wording
   about additional homogenisation. No quote, unit or source text was repaired.
3. The model's `answer_proposal` declaration does not establish completeness or
   truth. Its declared topic coverage and verbatim-copy claims are not accepted.

The sent JSON Schema describes an array of topic-enumerated objects; it does not
encode the Python validator's all-six-topics-exactly-once rule. The response
therefore does not demonstrate that GigaChat ignored JSON Schema. Nor does one
exposed failed case establish general model accuracy.

Tests run:

- Final affected suite: **152 passed**, including **33 new GigaChat cases** and
  the existing DSC context/admission/experiment/dispatch/result/OpenAI tests.
  JUnit: `output/gigachat_affected_20261028_v04.xml`.
- Covered missing permission/key, wrong Scope, model/package-balance admission,
  exact source/offset checks, complete/partial/abstention fixtures, foreign or
  invented evidence, duplicate topics/JSON keys, malformed and nonfinite JSON,
  incomplete/function replies, HTTP/TLS failures, redaction, raw preservation,
  no retries, timeout reservation persistence, stale inputs and postflight drift.
  These tests use constructed transports and are not provider accuracy tests.
- Ruff `app tests scripts`: passed. Mypy `app`: **178 source files**, no issues.
  The additional local offline review script also passed Ruff.
- Initial sandboxed pytest stopped at temporary-directory setup (32 setup errors;
  no test bodies ran). Rerun outside the sandbox passed 32 cases; after the timeout
  test was added the final affected run passed 152. An intermediate regression
  command used an incorrect existing-test filename and ran zero tests; the final
  command uses the verified `tests/unit/test_record_openai.py`.
- Offline postflight reconstructs the frozen source bindings, verifies both
  artifact manifests, inventories all reply topics and compares every quoted
  fragment against exact M1 without normalization. Its script installs a Python
  connect/DNS/sendto guard before application imports. This is not an OS firewall.
- Static HTML QA checked all 11 local links across the two new reviews and the
  copied historical TAC page, all six proposal rows and eight expandable sections
  in the diagnostic review. The copied TAC scope is the one Istomina DSC document,
  with its historical unimplemented Abstract/Conclusions/Terms fields preserved.
  Literal credential scanning found no key in 39 generated/reservation files;
  the GigaChat registry result matches the output result, and the OpenAI attempt
  registry remains absent. Evidence: `output/gigachat_dsc_20261028/qa_v01.json`.

## Artifacts and reproduction

- Protocol: `docs/records/gigachat_dsc_protocol_v0.1.md`.
- Prepared request, contract and exact historical snapshot:
  `output/gigachat_dsc_20261028/prepared_v01/`.
- Original observed response, result, request, account responses, HTML and hashes:
  `output/gigachat_dsc_20261028/live_v01/`.
- Literal diagnostics and searchable HTML with every unchanged proposal, exact M1
  and link to the complete copied historical TAC/PDF review:
  `output/gigachat_dsc_20261028/offline_review_v01/`.
- Offline postflight script:
  `output/gigachat_dsc_20261028/offline_review_v01.py`.
- Model attempt reservation:
  `data/experiments/gigachat_dsc_attempts/c0d95fc74cf990186cbb23ed22ca255c0c73a8fb704ad56b942f81d5fadb1438/`.

Offline reinspection makes no API call:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.records.gigachat_dsc import read_prepared; read_prepared(Path('output/gigachat_dsc_20261028/prepared_v01'))"
```

The smoke CLI is not integrated into the web app. Sending requires the explicit
`send --authorize-gigachat-test` operation, personal credentials and an unused
request slot. Do not delete or reset this experiment's slot to repeat the call.
Historical exports and original PDF inputs remain evidence; retain local ignored
artifacts and the reservation when transferring the workspace.

Limitations:

- One exposed development question. No independent scientific gold, accepted
  answer, comparative accuracy, paid-cost measurement or production integration.
- Quote diagnostics are literal integrity checks; they do not assign scientific
  relations, assess semantic truth or establish the absence of article evidence.
- Account access/model/version/quota observations apply to this run and account.
  Package balance alone is not proof of price. Unknown fields remain unknown.
- Attempt durability is local to this checkout and filesystem; it does not cover
  deleting/rolling back the registry, a different checkout or distributed delivery.
- Full application suite and browser interaction/visual QA are not claimed.

Verdict: **GigaChat access and a real model response verified; the first DSC answer
was rejected by the unchanged integrity contract.** No repeat was sent. A future
separately versioned experiment can use fixed named fields and source-span
selection instead of asking the model to retype PDF characters; it must preserve
this failure and must not weaken exact-source validation.
