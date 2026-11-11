# ARIADNE: проверка20 Satoh/Fan вопросов

10 ноября2026, Asia/Yekaterinburg.

Changed:

- По прямому запросу пользователя «Начинаем проверку?» открыт отдельный однократный
  scope, максимум20 model POST/20 OAuth, без retries/fallback/continuation. Это
  авторизация из сообщения, не из загруженного QA. Все прошлые scopes сохранены.
- До отправок зафиксированы20 question-only входов,212 app assets/203 Python,
  runner/tests/protocol/pyproject, trace/source/PDF/index/cache bindings. Wrapper
  `По статье Satoh (2013): ...` / `Fan (2018)` добавляет только исходный контекст
  статьи в формат существующей citation grammar. Original questions отдельны;
  эталонов, page hints и rubric во входах модели нет. Новых app changes0.
-20 actual production-service preparations в fresh processes/read-only repeatable
  read/rollback.15 штатных insufficient_evidence из-за
  insufficient_distinctive_term_coverage; модель для них не вызывается.
  Эти ответы service сохранены, не выдаются за15 фактических ASGI HTTP запросов.
-5 eligible actual ASGI /answer calls: Satoh04/08/09, Fan06/09. Все5 HTTP200,
  GigaChat-2-Max:2.0.30.01,1200 output tokens/120s per HTTP.4 answered,
  Satoh08 provider abstention. Ровно5 model POST+5 OAuth/5 append-only slots,
  retries/fallback/continuations0. Перед model POST trace/sources/articles/native
  совпадают с freeze; после исполнения frozen input hashes verified. Все20
  allowances и5 slots закрыты; неиспользованные15 не переносятся.
- Usage:37689 prompt+659 completion=38348 tokens, cost unknown/null. Credentials
  и OAuth tokens не сохранялись. Network/reference-read denials0.
- Отдельное post-hoc сравнение после закрытия отправок: Satoh04 объясняет
  снижение проводимости только вязкостью/размером, пропускает механизм
  donor ability→solvation→dissociation; Satoh09 правильно даёт направления,
  но пропускает оговорки и ошибочно относит TFEMEE к диэфирам; Fan06 даёт CEI/
  толщину, пропускает CFx/POxFy и численное сравнение F/O; Fan09 сохраняет
  основные три результата окислительной стабильности. Это предварительное
  exposed-assistant сравнение, не независимая научная оценка. Баллы0/1/2 не
  применялись; score/independent_accuracy null.
- У15/20 cases хотя бы одна declared reference PDF page вне selected chunk
  ranges. Это наблюдение о диапазонах, не проверка полного присутствия страницы
  или entailment. Satoh08: четыре числа есть в замороженном PDF8, но selected
  ranges1–5 не включают страницу8; отказ не доказывает отсутствие ответа в статье.

Tests run:

-24 focused tests:17 новых runner controls+7 existing smoke tests, passed.
  Проверены question-only allowlist, identity, foreign evidence stop, gold/prior
  output file guard, offline boundary, закрытый scope, отсутствие авторизации,
  exclusive attempt slots, interrupted outcome unknown. Первый sandbox run:
  14 passed/10 tmpdir setup errors; исходный JUnit сохранён. Повтор вне sandbox
  с отдельным basetemp:24 passed. Ruff4 новых/связанных файлов passed.
-20 frozen preparations/manifests/input hashes и5 фактических native/API/ledger
  bindings проверены.20 selected evidence scopes/PDF originals совпали с целевыми
  статьями;60 original question/reference/pointer spans exact.130 existing HTML
  file links checked;79 review bindings.6 exact literal source witnesses из ранее
  замороженных текстов PDF с page hashes/offsets, не fresh extraction.
- Отдельная финальная проверка:20 HTML sections/150 links (130 файлов+20 anchors),
  все5 native response SHA совпадают с observed/stored SHA, все5 finish_reason=stop,
  returned model2.0.30.01, manifests/frozen inputs verified. Результат отдельно
  `output/satoh_fan_qa_run_20261110/verification_v01/result.json`, новых вызовов0.
- Сохранены initial review v01 и отдельный assessment v01, исходные ответы,
  native responses, failures/denials/usage. Fresh PDF extraction/visual/browser
  layout/full app pytest/mypy не выполнялись. Product code frozen и unchanged.

Limitations:

- Development-exposed корпус/эталоны, user provenance «Я составил ответы. Видел
  ответы сам»; exact timing/LLM/expert review undeclared. File guard не устраняет
  прежнее знание эталонов агентом. Это не новый24-task pilot и не independent gold.
-4 technical answers/20 — availability, не4 scientifically correct.15 pre-model
  refusals не являются scientific negatives. Для полных semantic ownership/
  validity/всех эталонов независимая экспертная оценка отсутствует.
- Fan02/07/08 supplements unprovided; Fan07 caption/body panel discrepancy
  сохранена. Новых downloads/DB writes/ingestion/deployment/automatic context
  completion/threshold or grammar changes не было.

Verdict:

Проверка завершена. Основные измеренные проблемы: отбор страниц указанной статьи,
межъязыковая adequacy, причинные объяснения и полнота сравнений. Исправления —
отдельный следующий scope. Общий план75%, independent evaluation открыт.

- [Все20 случаев и raw artifacts](../output/satoh_fan_qa_run_20261110/review_v01/review.html)
- [Предварительное сравнение с эталонами](../output/satoh_fan_qa_run_20261110/assessment_v01/assessment.md)
- [Scope closure](../output/satoh_fan_qa_run_20261110/scope_closed_v01.json)
- [Scope protocol](records/satoh_fan_qa_run_scope_2026-11-10_v0.1.md)
