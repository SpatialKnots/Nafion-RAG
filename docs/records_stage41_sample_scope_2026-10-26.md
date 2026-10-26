# Records stage41: аудит буквального класса образца

26 октября 2026 года, Asia/Yekaterinburg. Алгоритм `sample_scope_audit_v0.1`.
[Проспективный протокол](records/sample_scope_protocol_v0.1.md).

Changed:

- Добавлен отдельный offline аудит всех 113 исходных co-preservation units
  четырёх frozen stage40 questions. Scope TAC — все десять прежних документов.
  Старый отбор, runtime, БД, PDF, retrieval и provider не менялись.
- Конечный RU/EN inventory различает буквальные упоминания membrane и SEI.
  Каждый hit хранит точный Unicode span, article, region/node, physical page,
  text layer и layer ID. Films, electrodes, Nafion и generic samples сами по
  себе не назначают класс. Переноса класса между группами/статьями нет.
- Неизвестная identity и per-result applicability сохранены во всех группах.
  Literal class не устанавливает релевантность методики, принадлежность
  собственному эксперименту, истинность отрицания или научную связь условий.
- Отдельный CLI поддерживает exclusive prepare/audit/select/export. Каждый
  этап получает свою HTML-проверку и отдельную восьмиколоночную TAC-таблицу.
  Full parents, event states, flags и diagnostics остаются доступны локально.

## Замороженные ожидания и измеренный результат

До нового запуска сохранены 40 assistant development cases: literal state и
retain/defer expectations для всех 18 ранее выбранных units, плюс четыре
no-admission checks. SHA256 файла `development_checks_v01.json`:
`6682897057f14e1b048c5b209d50e1d70e0f126d9fda9009f3016a6ea16d8d77`.
Изучены полные четыре Guo/SEI units, исходные мембранные фрагменты и подготовка.
Это exposed source expectations разработчика, не independent scientific gold.
Оставление membrane units — предосторожность, не положительная научная оценка.

| Literal state | Все исходные units | Ранее выбранные stage40 |
| --- | ---: | ---: |
| target_literal_only | 50 | 8 |
| competing_literal_only | 6 | 4 |
| unknown_no_class | 31 | 0 |
| unsupported_or_ambiguous_query | 26 | 6 |
| Всего | 113 | 18 |

Счётчики относятся к occurrences в четырёх вопросах, не независимым наблюдениям.
Mixed cases в этом реальном scope не встретились; их сохранение покрыто
constructed tests. Query без единственного finite класса остаётся unresolved.
Отсутствие буквального класса не доказывает отсутствие нужного материала.

**22/22 audit checks прошли**: 18 unit states и четыре прежних отказа.
18 selection expectations на этом шаге ещё не оценивались; они проверяются
отдельно в [stage42](records_stage42_sample_selection_2026-10-26.md).
Audit selection не меняет и сохраняет admission **0/4**. Новых запросов к
модели/поиску/БД нет. Общая научная точность и scientific loss не измерены.

## Воспроизводимость и проверки

`baseline_before_run_v02`: 607 source files, fingerprint
`98658bbfefcfd0f0141ab46138245dd6f280b1968f311761d778120991b72ba7`;
missing dependencies и requirement mismatches отсутствуют. Installed snapshot
не является portable lockfile; private PDFs/DB/weights в source archive не входят.
Prepare связал 1064 inherited inputs и 45 code/protocol/test files, получил
четыре вопроса и **0 новых scope outcomes**. Все 40 cases заморожены до audit.

Tests run:

- До commits stages36–40: **214 passed**, один существующий Starlette/httpx
  deprecation warning; Ruff `app tests scripts` и mypy `app` прошли.
- Финальный scope/query-selection прогон: **60 passed**, тот же warning,
  `output/commit_check_20261026/scope_v03.xml`. Проверены unknown/mixed retention,
  source offsets, interleaved/protected groups, oversized units, source/code/PDF
  drift, source-bound references, deterministic exports и HTML escaping.
- Ruff `app tests scripts`: passed. Mypy `app`: no issues, 163 source files.
- Postflight: 317 exact class spans проверены по исходным page/block offsets,
  все 113 units учтены, все 19 baseline Evidence и десять документов сохранены.
  Все четыре parent files на вопрос и `metadata.json` побайтно совпали со stage40.
  Проверены десять PDF paths/hashes; run и оба повторных exports совпали по всем
  25 файлам. Manifest каждого capture/export проверяет 1097 bindings.
- Headless Chrome 156.0.8078.47: четыре question cards, 113 unit rows, поиск 1/0/4,
  раскрытие отдельных source blocks, TAC десять строк/восемь колонок и search/reset
  прошли. JS errors/network requests отсутствуют; проверены 571 PDF-links и
  25 relative links. Screenshots source unit и TAC просмотрены. Поведение PDF
  click в браузере не проверялось; наличие целевых файлов проверено отдельно.

Первая проверка прежних этапов: 74 passed и 140 setup errors — отсутствовал
родитель `--basetemp`; после создания каталога отдельный запуск дал 214 passed.
Первый новый scope run дал 25 passed. Затем расширенный run: 59 passed,
1 failed — новый тест пытался перезаписать JSON через exclusive writer.
Тест исправлен на новые пути; production guards не ослаблялись. Успех 60 tests
относится к отдельному финальному запуску. После исправления теста source snapshot
создан заново до первого реального audit. Полный application suite не запускался.

## Артефакты и повтор

Каталог `output/records_stage41_20261026/`: frozen checks, source baseline,
`prepared_v01`, `run_v01`, `review_v01`, `review_repeat_v01`.
`review.html` содержит все исходные units, exact source blocks и PDF-links,
включая прежние deferred cases; `metadata_review.html` — все десять TAC документов.
Исторические TAC/Terms не пересчитываются и не подтверждаются человеком.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_scope prepare --checks output/records_stage41_20261026/development_checks_v01.json --output-dir output/records_stage41_new_prepared
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_scope audit --source output/records_stage41_new_prepared --output-dir output/records_stage41_new_run
.\.venv\Scripts\python.exe -X utf8 -m scripts.sample_scope export-audit --source output/records_stage41_20261026/run_v01 --output-dir output/records_stage41_new_review
```

Limitations: finite literal classes не решают sample identity, implicit material
aliases, compound/negative query semantics, own-work origin и per-result
applicability. Подготовка в аргоне не становится средой измерения. Неизвестные
случаи сохраняются; independent scientific evaluation не выполнена.

Verdict: инженерный аудит реализован отдельно от отбора и production.
Следующий ограниченный шаг реализован как stage42: whole-unit competing-class
deferral experiment с явной оценкой заданных source expectations.
