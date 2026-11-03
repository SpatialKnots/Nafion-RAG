# ARIADNE: offline-сравнение лигатур и RU/EN expansion

31 октября 2026 года, Asia/Yekaterinburg. Продолжение
`kim_retrieval_loss_2026-10-31.md`. Эксперимент завершён; полноценное исправление
научного покрытия не подтверждено. Production runtime не изменён.

Changed:

- Добавлены offline candidates и drivers: `scripts/retrieval_ablation.py`,
  `scripts/run_retrieval_ablation.py`, `scripts/review_retrieval_ablation.py`.
  Отдельный исправленный оценщик: `scripts/retrieval_ablation_labels.py`.
  Протокол и case recipe заморожены до измерения в `docs/records/`.
- Сравнены четыре arms: baseline, ligatures, expansion, combined. Ligatures
  раскрывает только пять существующих fi/fl/ff/ffi/ffl mappings в SQL matching/
  scoring view. Raw source text, PDF, query processing и embedding index не
  изменены; NFKC, stemming, dehyphenation и преобразования единиц не добавлены.
- Expansion требует совместных query cues Nafion, dispersion, particle,
  morphology/shape и solvent; добавляет две общие RU/EN lexical variants.
  Ни article IDs, ни Kim, ни формы частиц/размеры/названия конкретных
  растворителей из reference в кандидат не передаются. Существующие glossary
  variants сохранены; новый concept не подменяет частицы дисперсии мембраной.
- Для каждого вопроса использованы baseline variant top-k и feature window,
  одинаковые во всех arms; final top-k равен пяти. Окна не увеличивались ради
  известного источника. Дополнительные каналы expansion посчитаны отдельно.
- Выполнены **304 service preparations: 76 cases × 4 arms**, 67 уникальных
  queries. В наборе 24 baseline и 46 extended fixtures, три дословных прежних
  пользовательских вопроса, исходный morphology case и две заранее записанные
  RU/EN development paraphrases. Это exposed, частично перекрывающийся набор,
  не независимая научная оценка. Опечатка «пре переходе» сохранена.
- PostgreSQL: `REPEATABLE READ, READ ONLY`, проверено `on`, завершение rollback.
  Corpus: 619 исходных chunks, 33 работы. Все source-bearing rows сохраняют
  article/chunk IDs, страницы, source type, text layer и проверяемый raw text.
  Provider factory запрещён; явное исключение останавливает допущенные случаи
  перед генерацией. При отказе сохраняется настоящий pre-provider статус.
  Новые модельные ответы, native requests и live slots не создавались.

## Существующие article labels и изменения evidence

Final accounting использует существующие parser/matcher из
`app/evaluation/retrieval.py`, версия sidecar metric
`retrieval_ablation_article_labels_v0.2`. Считается попадание хотя бы одной
ожидаемой статьи в top-5, отдельно — потеря любой matched article identity.
Это не измерение полноты научных связей или корректности ответа.

| Arm | Existing article hits@5 | Потери matched identities | Изменён порядок top-5 | Изменён source identity/order evidence | Изменены полные evidence records | Exact channel calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 62/62 | 0 | 0 | 0 | 0 | 168 |
| ligatures | 62/62 | 0 | 39 | 35 | 57 | 168 |
| expansion | 62/62 | 0 | 3 | 3 | 3 | 174 |
| combined | 62/62 | 0 | 40 | 36 | 57 | 174 |

Исходный поиск уже достигает потолка этой ограниченной article-hit метрики;
62/62 нельзя выдавать за научную accuracy. Контрольные вопросы перекрываются.
Для expansion внутри finite scope находятся только исходный exposed case и
две development paraphrases; остальные 73 случая его не активируют. Поэтому
отсутствие article-level потерь не доказывает безопасность внутри всей семьи
morphology-вопросов или сохранность научных условий в изменённых evidence.

Два разных определения изменений явно разделены:

- Source identity/order — упорядоченные `(article_id, chunk_id, SHA256(text))`.
  Это основной счётчик `evidence_changed_cases` в report.json: 35 и 36.
- Full record comparison учитывает также score/metadata и другие поля Evidence:
  57 в обоих normalization arms. Предварительное сообщение о 57 изменениях
  относилось к полным записям; оно не означает 57 новых source texts.

Adequacy boolean не изменился ни в одном из 76 случаев. У трёх старых
пользовательских вопросов сохранились q1 `complete_supported_table_4_5`, q2
`conductivity_optimum_not_verified_for_comparable_scope` с отказом, q3
`bounded_source_quote_candidates`. Это сохранение bounded решений подготовки,
не новые ответы GigaChat.

Сохранено также существующее противоречие с fixture label: qext044
`absent_neutron_radiography` помечен `answerable=false`, но во всех четырёх
arms проходит gate до явной остановки перед генерацией. Семь остальных
declared-negative fixtures отказывают. Это конфликт подготовки с прежней
разметкой, не установленная независимой экспертизой scientific false-answer
rate; модель не вызывалась. Кандидаты его не исправляют и не создают заново.

## Восемь точных source windows Kim

Окна взяты из прежнего source check, не поступают в retrieval и не считаются
независимым gold. Считается полное exact raw text containment с подходящими
article/page; одно окно не равно одному независимому эксперименту.

| Question | baseline | ligatures | expansion | combined |
| --- | ---: | ---: | ---: | ---: |
| Исходный пользовательский RU вопрос | 0/8 | 0/8 | 0/8 | 1/8 |
| Заранее записанная RU paraphrase | 0/8 | 0/8 | 0/8 | 1/8 |
| Заранее записанная EN paraphrase | 0/8 | 3/8 | 0/8 | 4/8 |

Здесь приведены окна в **generation evidence**, не только найденная статья.
В обоих RU cases единственное combined окно — **Sample form**, описание
подготовки Na-формы. Ни одно из остальных семи проверяемых окон в их evidence
не вернулось. Это не доказательство отсутствия любого morphology-сведения во
всём корпусе или других выбранных работах; проверяются конкретные старые anchors.

Для исходного RU вопроса expansion возвращает шесть exact windows в fusion
input, но ни одно в feature input из пяти chunks; final evidence остаётся 0/8.
Combined также имеет шесть окон в fusion input и ноль в feature input. Затем
cross-language presence вставляет Kim с позиции 6 на позицию 5: chunk PDF с.1–2
с Sample form. При этом `query_intents=[]`; отдельный morphology ranking bonus
не появился. Увеличение candidate coverage не обеспечило покрытия требуемого
содержания после отбора.

У EN paraphrase normalization возвращает три других окна: fixed-concentration
solvent-ratio series, constant-ratio concentration control, Figure4 caption.
Combined добавляет к ним Sample form. Эффект языка наблюдаем, но отдельный
причинный эффект изменения semantic модели/перевода не измерялся. Все arms
используют прежний `BAAI/bge-small-en-v1.5`; English semantic channel для
добавленной variant не вводился.

## Исправления диагностического процесса

Первая попытка `capture_v01` явно остановлена после 14 arm files из-за стоимости
повторных одинаковых SQL-запросов. Она не является завершённым сравнением.
Сохранены partial outputs, исходные runner/protocol snapshots, interruption
record и manifest. В replacement `capture_v02` добавлен deep-copy exact-response
cache по normalization state/query/collection/top-k/filters. Все 14 прежних
полных traces и всех их boundaries совпали с replacement. Кандидат, case set,
scoring, thresholds и окна после наблюдения результатов не подбирались.

Completed capture: 218 actual exact SQL calls +466 cache hits; 67 actual local
semantic calls +237 cache hits. Это счётчики завершённой replacement attempt,
не суммарный benchmark всех предварительных работ. Ordered/cached timings не
используются как независимое измерение latency или исправление cache/ORM.

Первый capture counter ошибочно не учитывал nested checksum/title/identity
targets в девяти extended fixtures и давал denominator 53. Исправленный
отдельный v0.2 evaluator воспроизвёл существующий repository fixture parser/
matcher на неизменных saved retrieval rows и восстановил denominator 62.
Оригинальные capture counters не переписаны; final review сохраняет их как
legacy рядом с исправленными. Подробности:
`docs/records/retrieval_ablation_label_accounting_v0.2.md`. Семь regression tests
добавлены; labels/queries/scientific evidence не менялись.

Tests run:

- **165 affected tests passed, 29 новых**, JUnit
  `output/retrieval_ablation_20261031/tests_v04.xml`. Проверены query scope и
  отсутствие reference outcomes в generic variants, SQL entity/filter/limit
  preservation, fixture identities, частичная потеря expected article,
  повреждение raw source и существующие retrieval/ranking/generation/relations.
  Ранние preflight/156/158 runs сохранены; числа не суммируются.
- Ruff восьми новых source/test/QA files прошёл. Initial B023 исправлен до
  первой попытки измерения. Ошибки rg path, CIM inventory и неверного пути
  inspection записаны в `failed_attempts_v01.json` / `failed_attempts_v02.json`.
- **304 реальных offline arm replays** с настоящими fusion/ranking/evidence
  functions воспроизвели девять внутренних границ и полные final traces каждый.
  DB connect запрещён; новых SQL/model/OAuth/embedding calls в replay нет.
  Повреждённая финальная diversification отклонена на ожидаемой границе.
- Original morphology baseline trace и оба исходных channel prefixes полностью
  совпали с frozen Kim audit. Проверены 293 report input bindings и manifests,
  восемь exact windows свежей PDF extraction, все 33 original PDF SHA256.
- Static HTML QA: 33 TAC rows, восемь согласованных колонок, полные expandable
  имеющиеся поля, search handler, 41 существующий PDF/page link и три artifact
  links. Даны полные actual generation evidence для morphology cases и точные
  source notes; отсутствующие метаданные/Conclusions/Terms не выдумывались.
  Итог: `output/retrieval_ablation_20261031/review_v01/review.html`.

Limitations:

- Нет независимых новых аннотаций или новых model answers. Article hits, exact
  anchors и совпавший replay не устанавливают научную достаточность, ownership,
  полноту всех источников или качество будущего ответа.
- SQL при ties не имеет уникального final tie-breaker; зафиксирован конкретный
  исходный порядок. Cache/ORM repeated-request defect и unbiased performance
  benchmark не проверялись и не объявлены исправленными.
- Browser execution, повторная визуальная PDF проверка, full suite и mypy не
  выполнялись. Static links QA не равен открытию PDF браузером.
- App, index, PDF, public schema, prompt, scientific thresholds и generation
  runtime не менялись. Реальные model/OAuth/новые slots: **0**; все прежние
  бюджеты закрыты, автоматического live запуска или resend нет.

Verdict:

Сравнение выполнено, но автоматический rollout кандидата не обоснован. Общая
normalization помогает некоторым EN source windows; generic expansion улучшает
candidate coverage исходного RU вопроса, которое далее теряется при ranking/
feature-window/evidence selection. Вернувшаяся статья не заменяет требуемую
научную связь. Следующий offline шаг — изучить ранжирование и отбор на уже
сохранённых кандидатах, отдельно проверить requested-relation gate и ложные
отказы. Не продвигать Kim по ID, не увеличивать окно ради известной страницы
и не считать lexical cues научным подтверждением. Independent evaluation
остаётся отдельным открытым этапом.

**Общий прогресс плана: 75% работ; пункт 4 открыт.**
