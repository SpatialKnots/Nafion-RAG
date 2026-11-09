# Пять question-only входов — 2026-11-03

Changed:

- По запросу «подготовь входы» выполнена фактическая локальная подготовка пяти
  вопросов через текущий ASGI `/answer`. Для каждого — отдельный процесс,
  read-only REPEATABLE READ DB/rollback, существующий локальный индекс и модель
  embeddings. Внешняя сеть и известные файлы benchmark gold заблокированы.
- Перед исполнением заморожены 190 bindings текущего app/helpers/tests/протокола
  и точного question-only JSON. SHA256 пакета:
  `d0d3ed5983b9e8b2a2bca6f26f1853232a6e7fa76035ae8e5c87fc8ab6c0609a`.
  В рабочий процесс не загружаются исходный benchmark, эталоны, цитаты, ожидаемые
  статьи или заметки приёмки. API body содержит ровно question/collection/method/
  top_k/answer_style/answer_language; ID остаётся снаружи. Вопросы дословные.
- Сохранены все реальные retrieval/evidence/adequacy/qualifier traces, source
  registry и пять точных неотправленных native bodies. Все пять дошли до границы
  генерации, 100000-byte review cap не превышен; gate не обходился.
  Настройки: GigaChat-2-Max, 1200 выходных токенов, timeout120s; claims/auto,
  текущие defaults retrieval/collection/top-k. Снимки и contract сохраняют детали.
- Provider transport заменён отдельной offline-функцией: пять OAuth placeholder
  boundaries и пять захватов native bytes. Это не реальные OAuth/model calls.
  Нет режима send, реальных вызовов, новых slots или разрешения отправки.
- Итоговый review: `output/user_benchmark_inputs_20261103/review_v01/review.html`.
  Чистый пакет API: `output/user_benchmark_inputs_20261103/inputs_v01/api_inputs.json`.
  В этой же папке отдельные API JSON/native bodies, побайтные копии успешных
  подготовок, manifest и parent bindings. ID/обёртка batch не входят в `/answer` body.

| ID | Native bytes | SHA256 неотправленного body |
|---|---:|---|
| Q01 | 69584 | `30d3867ec90294b8063a7b1a5bce41985eea3a248906b6bd57ad6fa1f4521382` |
| Q02 | 71206 | `ec8a976259f6aad915510dc56eb03d516224cb9fc6b42bedc5b5247ac784c40a` |
| Q03 | 57286 | `7a3928500f2168461c6516305cda16614e91ea5d5658154b99cb6d849800470b` |
| Q04 | 59882 | `e6fea5072dba879bc7d6a86f13b527f222f98aaa7bd7924112008539b1ba7f8c` |
| Q05 | 68993 | `35d12bebb82f6a5f3e82eb97bcf2f9f5e6a8109d4cb8a8c359a11e731e360f91` |

Tests run:

- 47 distinct tests passed: 25 новых question-only/transport/native/review
  контролей и 22 прежних intake/user-question preparation теста. Включены отказ
  от лишних gold/expected-article полей, повреждённого hash/порядка/authorization,
  запрет чтения benchmark-файлов, сохранение исходного вопроса, восстановление
  helper scope, fake transport без реальной отправки, blocked/oversized режимы,
  повреждённые native bytes/model/limits/question/roles и HTML escaping.
- Ruff четырёх новых Python-файлов прошёл; `git diff --check` прошёл.
  `git diff --name-only -- app` пуст: runtime/app не менялся.
- Review выполнялся без DB/сети/чтения gold: проверены 279 общих bindings,
  пять prepared manifests, точные API/native hashes/размеры/исходные вопросы,
  11 PDF hashes, 35 свежих полных страниц и raw quote offsets/text.
- Static HTML QA: все 11 фактически выбранных TAC работ, восемь колонок,
  раскрываемые полные метаданные/сырой контекст, поиск, 58 существующих PDF-ссылок.
  Conclusions/Terms/другие отсутствующие поля не придуманы.
- Точные копии API/native bytes и итоговый bundle manifest прошли проверку.

Limitations:

- Первый sandbox-запуск Q01 сохранил только `api_request.json` и не вернул trace.
  По полной командной строке установлены PID21720/22248, остановлены только они.
  CIM inventory в sandbox был запрещён; повторён вне sandbox. Все последующие
  подготовки вне sandbox завершились. Причина исходной задержки не установлена.
  Q01 `prepared_v01` сохранён; успешный `prepared_v02` указан в неизменяемом
  `prepared_selection_v01.json`. Нет reroll по содержимому и отброшенных успешных
  подготовок. Это инфраструктурное повторение без real provider call.
- Первый pytest: 24 passed/15 fixture setup errors из-за отсутствующего parent
  basetemp. После создания каталога:39 passed; с дополнительными review controls:
  47 passed. Все три JUnit сохранены в `output/benchmark_inputs_checks_20261103`.
  Два E501 в новом renderer исправлены до freeze review. Нативное предупреждение
  Starlette о deprecated httpx сохранено в терминальном выводе.
- Допуск внутреннего gate не доказывает научную достаточность, попадание нужной
  статьи или правильность будущего ответа. Gold comparison не выполнялся; ответов
  модели, оценок, provider token usage/latency/cost пока нет.
- Fresh-process preparation не проверяет long-lived cache/ORM. Browser execution,
  визуальная проверка PDF в этой итерации, full suite и mypy не выполнялись.
  Происхождение эталонов/неизвестные LLM assistance и expert verification,
  прежняя тематическая экспозиция остаются как в паспорте приёмки.
- Не менялись runtime/prompt/gate/index/schema/thresholds; нет query rewriting,
  rebuild/model downloads, реальных model/OAuth calls или новых reservations.
  Запрос пользователя и протокол разрешают подготовку, не live dispatch.

Verdict:

Пять входов подготовлены, проверены и сохранены без отправки. Следующая возможная
операция — отдельный ограниченный live scope на этих exact bytes, только после
явного разрешения пользователя; ничего автоматически не отправляется. Научное
сравнение ещё не выполнено. Независимая оценка и cache/ORM открыты.
**План качества:75% работ, не оценка точности.**
