# Q03/Q04: устранение потерь контекста в рабочем коде — 2026-11-05

Changed:

- По согласованному [протоколу](records/requested_context_runtime_protocol_2026-11-05_v0.1.md)
  добавлен `app/retrieval/requested_context.py`: два ограниченных класса запросов,
  без IDs вопросов/статей, номеров страниц, названий авторов или ожидаемых значений.
  Исходный runtime из184 bindings сохранён до изменения в
  `output/requested_context_runtime_20261105/freeze_v01`.
- Для Li-Nafion equilibrium swelling + swelling enthalpy сохраняется уже
  найденный фрагмент с таблицей явно обозначенных величин: энтальпия на единицу
  массы и равновесное набухание в процентах. Таблица с одним параметром энергии
  когезии в кДж/моль не получает такой приоритет. Это **отбор контекста**, не
  полноценный parser таблиц/проверка числовых claims.
- Для Li-Nafion EC/SL mixing temperature + heating/cooling + structure
  сохраняются два вида контекста из одной работы: описание uptake/cycles и
  описание plasticised amorphous/crystalline structure. Название статьи не
  заменяет body evidence. Резервируется не более одного chunk на facet;
  совпадения и missing facets помечены как context candidates, не entailment.
- Приоритет применяется **перед original hybrid top-k**, **перед final
  cross-lingual top-k** и после answer evidence selection. Каналы не расширены,
  новые chunks не добавляются, top-k и исходные score/text/page/layer сохраняются.
  За пределами поддержанных семейств либо без matching body порядок и metadata
  остаются прежними. Низкий top-k явно оставляет missing facets.
- В двух существующих app-файлах10 добавленных строк; отдельно новый модуль.
  Порог adequate, prompt, API schema, index, units и output naming не менялись.
  Runtime source drift двух файлов явно сопоставлен с исходными snapshots;
  прежние manifests/guards/native requests/ответы/gold не переписаны.

## Фактический результат

| Случай | Было в конечном evidence | После исправления |
|---|---|---|
| Q03 | Эталонные p3/p4 и обе mapped quotes отсутствуют | **Чернюк2024 p3–4**, полная исходная таблица и сопроводительный контекст. Обе mapped quotes и прежний raw table span сохранены. |
| Q04 | Эталонные p6/p12 и обе mapped quotes отсутствуют | **Istomina p5–6 и p11–12**: полный температурный цикл/60-day context и structural interpretation/conclusions. Обе mapped quotes и два прежних source-note spans сохранены. |
| Q01/Q02/Q05 | Прежний production search | Без изменений; отдельный author/year candidate из предыдущего этапа не интегрирован. |

По всему пяти-вопросному development набору: reference-page retention **0/10→4/10**,
mapped quotes **0/12→4/12**. Важнее, что обе целевые потери Q03/Q04 устранены в
реальной цепочке service, а не только в отдельном diagnostic script. Семь прежних
source notes считаются отдельно: **0/7→3/7**. Экспериментальные условия Q03 наp2
и таблица Q05 наp7 этим патчем не восстановлены. Это не scientific accuracy.

Новые полный [HTML до/после](../output/requested_context_runtime_20261105/review_v01/review.html),
[report](../output/requested_context_runtime_20261105/review_v01/report.json),
[верификация](../output/requested_context_runtime_20261105/verification_v01.json).
TAC содержит все33 работы снимка, восемь колонок, раскрываемые поля и поиск;
81 существующая ссылка на оригинальные PDF/страницы. Missing metadata,
Conclusions/Terms явно помечены; исходный контекст не заменён сводками.

## Достаточность Q01/Q05

Проверен прежний отдельный author/year candidate через текущий production service.
Он всё ещё **не допускает генерацию** Q01/Q05: действующий reason
`insufficient_distinctive_term_coverage`. Два новых regression tests фиксируют,
что наличие авторского совпадения и source quotes не обходит gate.

- Q01: в отдельном кандидате ранее вернулись исходные source quotes Lin p1;
  русская lexical coverage остаётся низкой на английском контексте. Нужна
  отдельная ограниченная проверка полного requested scope / RU–EN соответствий.
  Глобальное добавление алиасов или понижение порога не устанавливает scientific
  adequacy и здесь не внесено.
- Q05: прежний кандидат возвращает способ получения дисперсии, но теряет
  conductivity table. При этом полный составной вопрос остаётся непокрытым;
  author match не исправляет этот пробел. Отказ нельзя автоматически считать
  ложным. Author-scoped completeness и selection conductivity table остаются
  открытыми, а не объявлены решёнными этим патчем.

## Проверки

Tests run:

- **96 distinct tests passed**:26 новых (22 constructed context controls +4
  actual-service frozen-channel checks),70 существующих generation/selection/
  reranking/labels/comparison tests. JUnit:
  `output/requested_context_runtime_20261105/tests_final_v01.xml`.
- Controls: RU/EN, чужой материал, title-only, cohesion versus swelling units,
  недостаточный контекст, cross-article joins, top-k=1, raw identity, observed
  null и сохранение прежнего отказа Q01/Q05. Это software controls, не gold для
  научной оценки. Модель/real transport в тестах не использовались.
- **162 фактических offline service executions**: пять новых +76 старых случаев
  × baseline/repaired. Baseline со строго отключённым только новым retention
  точно воспроизвёл81 исходную полную трассу и старые ranking boundaries.
  Все76 старых repaired full traces идентичны baseline; потерь размеченных IDs
  и изменений gate boolean нет. **Активаций query family в этих76 —0**:
  это проверка изоляции вне области, не валидация активной ветви на независимых
  данных. Displaced raw fragments и literal condition surfaces сохранены.
- **Две fresh-process проверки через реальную локальную БД и локальный semantic
  search**, Q03/Q04: transaction read-only/repeatable-read, завершение rollback,
  original question-only packet и gold-read guard. Каждый fresh полный trace
  точно совпал по всем JSON-значениям с offline repaired trace. Новый provider
  не создавался; остановка до generation. Внешние model/OAuth/native requests/
  downloads/slots —0. Corpus619 chunks/33 работы.
- 319 report bindings,33 PDF hashes,48 selected raw evidence records,
  **10 свежих reference pages/19 точных raw spans** проверены. HTML static QA
  passed:5 sections/33 TAC rows/eight columns/81 существующая ссылка.
- Ruff всех восьми затронутых Python-файлов прошёл. **Полный `mypy app` прошёл,
  184 source files**. `git diff --check` прошёл с CRLF warnings.
- Первый общий test run:91 passed/one fixture setup error из-за pytest default
  temporary directory в sandbox. Старый JUnit сохранён; workspace `--basetemp`
  дал92 passed, а финальный расширенный run96 passed. Первые lint/type diagnostics
  (B009/F821/type mismatch) исправлены до измерения. Reviewer затем получил
  только перенос длинной строки E501: старый snapshot/manifest сохранены,
  текущий SHA и исходный SHA отдельно сопоставлены; AST обоих файлов точно
  идентичны. Selection logic и результаты после измерения не менялись.

Limitations:

- Q01/Q05 admission и author/year integration **не исправлены**. Технические
  OAuth/blacklist/empty content сбои не повторялись и не исправлялись.
- В Q03 правильная таблица теперь доступна модели, но semantic ownership /
  единицы каждого будущего claim не валидируются этим модулем. В evidence всё
  ещё могут оставаться другие работы; отсутствие подмены εког/ΔH новым ответом
  пока не проверено. Нельзя заявлять исправление научного ответа без его оценки.
- Finite lexical facets не подтверждают material/value ownership, performed
  status или причинный вывод. Richness tie-break не является проверкой полноты
  таблицы; unsupported formulations не входят в эти две query families.
- Это два активированных раскрытых development случая; независимая оценка
  остаётся открытой. Q04 physical/chemical crosslink source terminology caveat
  сохраняется; gold/source не редактировались.
- Browser/new PDF visual QA/full suite, работа уже запущенного сервера и
  cache/ORM/concurrency не проверялись. Новых модельных ответов/latency/cost нет.

Verdict:

**Потери Q03/Q04 исправлены в рабочем коде и подтверждены реальным локальным
поиском**, при сохранении старых внеобластных трасс. Глобальный gate не ослаблен.
Это завершённый bounded retrieval repair, не закрытие всех пяти вопросов или
научная приёмка ответов. Q01/Q05 и claim-level quantity validation остаются
открытыми. Все live budgets закрыты, повторные вызовы автоматически не выполняются.
Независимая оценка/cache-ORM открыты; прежний план качества остаётся75% работ.
