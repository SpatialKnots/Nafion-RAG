# Пять вопросов: live-запуск и сравнение — 2026-11-04

Changed:

- После конкретного предложения пяти Q01–Q05 запросов пользователь ответил:
  «Разрешаю отправить запрос. В идеале хочу видеть таблицу сравнения ответов
  моих и программы». Разрешение записано отдельно в
  `output/user_benchmark_live_20261104/approval_v01.json`; scope:
  `docs/records/user_benchmark_live_scope_2026-11-04_v0.1.md`.
- Выполнены пять последовательных fresh-process запусков текущего `/answer`,
  read-only DB/rollback, с проверкой замороженных runtime/source/native bindings.
  Исходные zero-budget preparations и benchmark gold не изменены. Отдельные
  authorized copies разрешали ровно одну попытку OAuth/model на случай.
  Рабочие процессы блокировали чтение gold/intake и других docs/records,
  кроме исходного question-only пакета и разрешённого scope. Данные эталона
  и ожидаемые статьи не передавались в inference.
- Фактически: **4 model POST attempts, 5 OAuth attempts**, без повторов,
  fallback и infrastructure continuation. Все пять append-only slots закрыты;
  неиспользованная model allowance Q01 также закрыта. Настройки:
  GigaChat-2-Max / GIGACHAT_API_PERS / 1200 выходных токенов / 120s per HTTP.
  Модель в четырёх native responses: GigaChat-2-Max:2.0.30.01.
- Новые driver/reviewer — отдельные scripts; app/runtime/gate/prompt/index/
  schema/thresholds/query rewriting не менялись. `data/terms_pipeline_config.json`
  не менялся этой работой. Commit/push не выполнялись.
- Итоговая таблица:
  [review.html](../output/user_benchmark_live_20261104/review_v02/review.html).
  Пять полных исходных эталонов рядом с исходным API answer/error/abstention,
  отдельными post-hoc замечаниями, native responses, citations и полными сырыми
  выбранными страницами. TAC включает все 13 выбранных/эталонных работ,
  восемь колонок, раскрываемые поля, поиск и 51 существующую PDF-ссылку.
  Неполученные ответы не восстановлены ассистентом.

| ID | Фактический исход | Последующее сравнение ассистента |
|---|---|---|
| Q01 | HTTP503, OAuth URLError; model0/OAuth1 | Научного ответа нет. Lin не выбран; модель запроса не получила. |
| Q02 | HTTP502, native finish_reason=blacklist; model1/OAuth1 | Научных claims нет, причина фильтрации неизвестна. Guo выбран p7–8, эталонные p1–2 отсутствуют. |
| Q03 | HTTP200 / answered / stop; model1/OAuth1 | НМП назван верно, но энергия когезии εког таблицы3.3 диссертации выдана за энтальпию набухания. Только2 растворителя вместо5. |
| Q04 | HTTP502; native stop, content=""; model1/OAuth1 | Научного ответа нет. Istomina выбран p1–3, эталонные p6/12 отсутствуют. Причина пустого content неизвестна. |
| Q05 | HTTP200 / insufficient_evidence; native answerable=false; model1/OAuth1 | Научного ответа нет. Laporta не выбран; отказ не доказывает отсутствие ответа в корпусе. |

Q03: программа приводит ДМФА −39.1±2.4 и НМП −57.8±4.4 кДж/моль.
Точный сохранённый E1 содержит эти значения в столбце εког, кДж/моль,
таблицы3.3 «Параметры термодинамического моделирования энтальпии набухания»;
это другая физическая величина, не перевод единиц ΔH набухания из эталона.
Исходный raw evidence span сохранён в `assessment_v01.json` с offsets.
Проверенная ранее и повторно связанная с PDF таблица1 Чернюк2024 p3:
НМП137%/−65.0Дж/г, ДМФА115/−57.8, этанол133/−34.1,
2-пропанол49/−30.1, вода35/−8.9. В ответе нет последних трёх растворителей;
набухание дано как1.15/1.37 без процентов/определения формы величины.
Статья Чернюк2024 выбрана в E3/E4 p5–6/8–9, но таблица p3 и эталонный
сопроводительный контекст p4 не выбраны. Claims ссылаются на диссертацию E1/E2.

Tests run:

- **50 distinct tests passed**: 12 новых budget/approval/no-repeat controls,
  пять новых comparison text/status/escaping controls, 25 прежних input/review
  controls и восемь прежних one-call scope controls. Реального transport в тестах
  нет. JUnit: `output/benchmark_live_checks_20261104/tests_v01.xml` и
  `tests_review_v01.xml`.
- Ruff всех четырёх новых Python-файлов прошёл. `git diff --check` прошёл,
  с существующими CRLF warnings; `git diff --name-only -- app` пуст.
- Пять фактических **offline ASGI replays** воспроизвели полный HTTP status/body,
  включая симуляцию сохранённого OAuth failure Q01, blacklist Q02, обычный
  ответ Q03, пустой content Q04 и abstention Q05. Exact native bytes проверены
  на model boundary; ноль реальных model/OAuth calls и DB connections в review.
- Проверены frozen review/manifests/runtime/prepared bindings, actual/live
  source traces и native bytes, пять global attempt/result slots; 35 свежих
  выбранных PDF-страниц/11 PDF hashes/raw spans и точный Q03 diagnostic span.
- Отдельный `check_user_benchmark_intake --verify-only` прошёл: исходный gold,
  manifests/bindings, 10 свежих эталонных страниц/19 raw spans, прежние
  12 типографических совпадений/два несовпадения сохранены без исправлений.
- Static HTML QA: пять случаев/13 TAC rows/восемь колонок/51 существующая ссылка.
  Полные эталоны и API/native outputs сохранены; ответы не переписывались.

Limitations:

- Q01 первый OAuth не удался: `URLError`, причинная диагностика runtime
  намеренно не раскрывает transport details. Отдельная проверка DNS/TCP/TLS
  ngw.devices.sberbank.ru:9443 и api.giga.chat:443 без ключей/API прошла.
  Это не устанавливает причину первого сбоя. Повторов Q01 не было.
- Провайдер сам сообщил суммарно input34492/output286/total34778 tokens;
  в Q02 blacklist usage — prompt1/output0/total1, сохранено буквально,
  не исправлено по размеру input. Денежная стоимость неизвестна.
- Первый offline review в sandbox задержался после Starlette warning,
  без итогового report. CIM установил точные PID18476/5628; остановлены
  только они. Повтор того же offline reviewer вне sandbox завершился как
  `review_v02`; это не повтор inference. Причина задержки не установлена.
  Starlette/httpx deprecation warning сохранён в терминальном выводе.
- Сравнение — post-hoc анализ ассистента n=5, не слепая независимая экспертная
  оценка. Прежняя тематическая экспозиция, необъявленные reference LLM assistance
  и expert verification сохраняются. Эталоны не исправлялись после ответов.
  Прежнее терминологическое замечание Q04 о physical/chemical crosslinking
  остаётся открытым. Техническая ошибка/abstention не равны научной ошибке;
  единая научная accuracy не назначена.
- Browser execution/новая визуальная проверка PDF/full suite/mypy и long-lived
  cache/ORM/concurrency не проверялись. Полнота corpus retrieval не доказана;
  downstream reference-page diagnostics не локализуют более раннюю потерю.

Verdict:

Разрешённый запуск закончен. Таблица «ваш эталон — исходный ответ программы —
различия — источники» готова. Единственный научный ответ Q03 содержит подмену
величины и неполон; остальные случаи дают три технических/выходных сбоя и один
отказ. Исправление retrieval/runtime не выполнялось. Все live budgets закрыты;
новые вызовы требуют отдельного scope. Независимая оценка и cache/ORM открыты.
**План качества остаётся75% работ; это не оценка точности.**
