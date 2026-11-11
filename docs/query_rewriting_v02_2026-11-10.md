# ARIADNE: выполнены шаги1–2 query rewriting v0.2

10 ноября2026, Asia/Yekaterinburg. User: «Выполняй» после рекомендации начать
с независимой пригодности перевода и проверенного научного названия статьи.

Changed:

- Новый `scripts/query_rewriting_v02.py`, отдельный runner/review/assessment.
  Старые parser/runner/prompts/results/manifests не редактировались. Default app,
  API/DB/PDF/index/retrieval ranking/English adequacy thresholds/answer validators
  не менялись. Шаги3–4 retrieval fusion/completeness не включались в этот тест.
- В wire schema обязателен только `english_question`, `keywords` необязателен;
  generated requirements убраны. Пустые/неправильного типа/слишком длинные/
  повторные/новые числовые/явно противоречащие title keyword entries исключаются
  с отдельным reason/index, без замены scientific текста. Raw response сохранён.
  Canonical requirements=[] явно system diagnostic, не результат LLM.
- Идентификаторы и числовые ограничения основного вопроса всё ещё обязательны;
  missing/invalid translation и обнаруженный chemical/operation drift отклоняются.
  Это конечные guards, не общий scientific identity/entailment validator. Новые
  необоснованные термины/отрицания/значения не гарантированно распознаются:
  сохраняется exposed-agent смысловой review перед подготовкой ответа.
- Scientific title каждого PDF подтверждён unique exact cached page1 span,
  page-text SHA и original PDF SHA. DB labels Satoh2013/Fan2018 не выдаются за
  научные title. Во входе только original question/locked identifiers/verified
  title+identity; нет abstract/results/gold/page hints/previous answers. PDF1 не
  извлекался заново. Title trace/proofs сохранены в input freeze.
- Инструкции различают ethers/esters, di-/triethers и post-charge hold/soak.
  Original question/model answer prompt не заменялся на English question.

Offline replay:

-20 старых native rewrite responses проверены новым parser без model/OAuth/DB.
  Получено16 пригодных translations вместо13 ранее принятых вариантов: Fan03/
 05/08 больше не останавливаются из-за пустых keywords. Четыре прежних chemical/
  operation contradictions отклонены, English text не ремонтировался. Это новая
  оценка на прежних bytes, не переписанная история v0.1.

New bounded run:

- Новый scope max20 rewrite+20answer POST/40OAuth, one attempt/stage/case,
  GigaChat-2-Max/1200 output tokens/120s HTTP, no retry/fallback/continuation.
  All20 native rewrites/code/tests/title contexts frozen до отправок.
-20/20 новых outputs прошли schema/основные guards, против17/20 в v0.1.
  У8 outputs auxiliary normalization diagnostics: пустые keywords не блокируют
  перевод. При agent meaning review приняты19, отклонён Satoh02: diethers/
  triethers заменены на dialkyl/trialkyl ethers. Эта новая ошибка не исправлялась.
  Satoh01/07 ethers и Fan07 hold теперь переведены правильно.
-19 accepted cases подготовлены production service/read-only repeatable-read/
  rollback в fresh processes; все19 reached native boundary. Три native bodies
  точь-в-точь совпали с v0.1: Satoh08, Fan01, Fan06. Старые результаты использованы
  после закрытия scopes; старые slots/output не изменены, new attempts0 для них.
-16 actual ASGI /answer:12 answered,2 model abstentions(Fan02/07),2 HTTP502
  empty-provider outputs(Fan09/10). Эффективно15 answered/20 с учётом3 reuse;
  это12 новых samples, не15 новых вызовов. Satoh02 — один semantic rejection.
- Ровно20 rewrite POST+16 answer POST/36OAuth/36 новых slots. Все36 slots и
  stages закрыты; оставшийся allowance истёк. Reused scopes не открывались.

Comparison:

|Метрика|v0.1|v0.2|
|---|---:|---:|
|Форматно пригодные rewrites|17/20|20/20|
|Приняты после agent meaning review|13/20|19/20|
|Доступные answers|11/20|15/20 (12fresh+3reuse)|
|Model abstentions|1|2|
|API/provider errors|1|2|
|Actual answer POST|13|16|

Original pre-rewrite baseline был4/20 answered. V0.2 добавила к v0.1 пять
доступных ответов(Satoh01/07,Fan03/05/08), потеряла Fan10 из-за empty-provider
output; net+4. Эффект складывается из parser policy, title/prompt, коротких
keywords и новых stochastic samples, не изолирует одну причину.

Content findings:

- Satoh04 теперь получил E4/PDF9–10 и восстановил основное donor ability/
  solvation/dissociation объяснение. Satoh05 potentials/conditions сохранены,
  Fan03 CE values и Fan04 retention сохранены, Fan08 methods/DSC появились.
- Существенные source-faithfulness errors: Satoh07 пишет identified, хотя cited
  raw/prompt прямо says not been identified/possible; Fan05 переносит cathode CEI
  на SEI. Satoh01 искажает полные химические названия при правильных short IDs.
  Эти вновь доступные ответы нельзя объявлять научно корректными.
- Satoh03 стал менее полным: не называет requested TFEME density, которую v0.1
  называла. Satoh06/09/10 пропускают некоторые conditions/comparison/caveats.
  Fan01/06 reuse сохраняют прежние недостатки. Fan02/07 всё ещё теряют нужные
  страницы. More answered не означает better correctness; score/accuracy null.

Tests run:

-65 distinct focused tests passed:62 основной suite+3 reuse proof controls,
 29 новых относительно36 prior tests. Ruff6 новых files passed. Один initial
  report line-length diagnostic исправлен до первого export; неожиданных internal
  exceptions0, два provider/API failures сохранены как результаты.
-20 exact original questions и prior manifests/bindings unchanged; verified2
  title spans/PDF hashes, source app203py+9yaml unchanged. Actual docs glossary
  включён в новые input bindings. Manifest — declared files, не полный environment.
-36 new native request/response SHA/ledger/closed slots+3 byte-identical prior
  results verified.16 live trace/sources/articles/native exact to frozen.
  Native returned model2.0.30.01/stop for all36, включая2 invalid empty replies.
-20 HTML sections/182 links/65 full raw chunks after unchanged whitespace
  cleaning in19 effective native prompts checked.4 exact cited raw→actual prompt
  witnesses для scientific cautions/method improvement. Source ranges не выдаются
  за exact single-page semantic support. Network/reference denials0.
- Tokens reported:rewrite6447+1301=7748; fresh answer141661+1971=143632;
  total151380, reused usage не пересчитана как новая. Precaching3368/9553 отдельно;
  cost unknown. Review/verification model calls0. Свежих PDF extraction/visual,
  browser layout/full app suite/mypy/deployment не было.

Limitations:

- Exposed development cohort, manual agent meaning filter, не independent gold
  и не autonomous rewriting benchmark. User references ранее видел agent;
  exact provenance timing/LLM assistance/expert review не установлены.
- Title/finite guards не гарантируют scientific equivalence. Особые guards
  ether/ester/hold/soak не распознали dialkyl/trialkyl error, её отклонил agent.
- Supplementary Fan02/07/08 не предоставлены, Fan07 panel ambiguity сохранена.
  Никаких retries/ручного semantic repair/подмены native/API output не было.

Verdict:

Шаги1–2 выполнены: optional-field отказы устранены на этом наборе, semantic
acceptance13→19. Доступность4→11→15 не доказывает рост scientific accuracy.
Перед расширением/включением нужны шаги3–4: source coverage и обязательные
role/status/condition checks. Особенно важно не пропускать identified-vs-suggested
и SEI-vs-CEI errors. Default rollout не выполнен/не обоснован; общий план75%.

- [Все20 сравнений](../output/query_rewriting_v02_20261110/review_v01/review.html)
- [Содержательная сверка](../output/query_rewriting_v02_20261110/assessment_v01/assessment.md)
- [Offline replay](../output/query_rewriting_v02_20261110/offline_replay_v01/report.json)
- [Verification](../output/query_rewriting_v02_20261110/verification_v01/result.json)
- [Protocol](records/query_rewriting_v02_2026-11-10.md)
