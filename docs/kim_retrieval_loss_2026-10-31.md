# ARIADNE: потеря Kim2015 и лексический допуск evidence

31 октября 2026 года, Asia/Yekaterinburg. Продолжение первого внешнего
reference case. Это разбор exposed development case, не новый независимый
тест и не завершение научной оценки.

Changed:

- Добавлены отдельные drivers `scripts/run_kim_retrieval_audit.py`,
  `scripts/expand_kim_retrieval_audit.py`, `scripts/review_kim_retrieval_audit.py`,
  десять unit tests и заранее записанный протокол
  `docs/records/kim_retrieval_audit_protocol_v0.1.md`. Production code, scoring,
  thresholds, glossary, schema, prompt и лимиты не менялись. Существовавшие
  изменения приложения сохранены.
- Повторён вопрос из frozen `preparation_v01/api_request.json`:
  «Как меняется морфология частиц дисперсии Nafion в зависимости от природы
  растворителя?» Сохранены исходные collection, method, top-k и параметры
  ответа. Reference и Kim PDF windows не входили в query/retrieval/evidence.
  Target article определён по checksum PDF после поиска.
- Записаны 17 внутренних наблюдений с parent calls, полными source texts,
  article/chunk IDs, страницами и text layers. PostgreSQL: `REPEATABLE READ,
  READ ONLY`, `SHOW transaction_read_only = on`, rollback. Использован
  существующий offline embedding cache/index. Явное исключение остановило
  выполнение перед генерацией; provider factory запрещён, ответ не создавался.
- Отдельная диагностика расширила только наблюдение исходных каналов до всех
  кандидатов: exact 240 результатов, semantic 619. Production capture не
  переписан и не получил expanded candidates. Первые 50 строк каждого
  expanded канала полностью совпали с исходными; semantic metadata совпали.

## Локализация

**Kim2015 отсутствует уже в обоих исходных top-50 каналов**, до hybrid top-10,
feature window и финального top-5. Полный final trace (`retrieval`, `evidence`,
`metadata`) совпал с frozen preparation 30 октября. Новые внутренние стадии —
воспроизведение, не задним числом восстановленные historical observations.

| Граница | Всего chunks | Kim2015 |
| --- | ---: | --- |
| Original exact output | 50 | отсутствует |
| Original semantic output | 50 | отсутствует |
| Original hybrid output / cross-lingual fusion input | 10 / 10 | отсутствует |
| Feature ranking input/output | 5 / 5 | отсутствует |
| Final retrieval / generation evidence | 5 / 5 | отсутствует |
| Отдельный expanded exact | 240 | 4 chunks: места 155, 216, 222, 223 |
| Отдельный expanded semantic | 619 | все 24 chunks; первое место 179 |

Первые позиции статьи не означают наличие нужного утверждения: четыре exact
Kim rows находятся на PDF с.10–12; ни одно из восьми reference окон в expanded
exact не входит. Все восемь окон присутствуют в DB chunks и expanded semantic;
конкретные exact-window matches имеют semantic позиции 251–514. Ни одна
исходная captured граница их не содержит. Page overlap и exact text presence
считаются раздельно.

Наблюдаемые факторы:

1. `matched_concepts=[]`, единственный variant — исходный русский вопрос.
   RU/EN glossary expansion для этой формулировки не включился. При top-k 5
   variant window равен 10; hybrid multiplier 5 даёт по 50 кандидатов.
   Feature window равен 5. Поздний ranking отсутствующую статью не восстанавливает.
2. SQL ILIKE работает с raw `Chunk.text`. В 20 из 24 Kim chunks ни один query
   term буквально не найден; в четырёх оставшихся найден только `Nafion`.
   После диагностического раскрытия лигатур во всех 24 появляется только
   `Nafion`: исходное `Naﬁon` содержит U+FB01. Эта нормализация не внесена в SQL
   и не добавляет русские термины о морфологии, частицах и растворителе.
3. Semantic model — `BAAI/bge-small-en-v1.5`, dimension 384. Русский query и
   низкие позиции английского источника наблюдаемы; отдельный причинный эффект
   модели/перевода здесь не измерялся.

Не заявляется, что увеличение top-k, нормализация или перевод исправляют
научное покрытие. При равных scores/chunk_index original exact SQL не имеет
уникального дополнительного tie-breaker; приведены позиции данного прогона,
не гарантия стабильного полного порядка ties между процессами.

## Почему evidence было допущено

`assess_evidence_adequacy` на пяти настоящих saved evidence воспроизвёл все
поля original metadata. Из девяти distinctive terms найдены семь: `как`,
`меняется`, `дисперсии`, `nafion`, `зависимости`, `природы`, `растворителя`.
`морфология` и `частиц` не найдены ни в одном из пяти полных evidence texts.
Coverage и top_coverage равны 7/9 = 0.7777777777777778.

Все три альтернативных lexical predicates выполнены: два terms и coverage
≥0.6; два top terms и top_coverage ≥0.5; пять terms и два top terms. Для этого
вопроса required concepts и relation requirements пусты. Поэтому aggregate
term coverage допускает ответ без проверки связи «растворитель → морфология
частиц». JSON сохраняет точные raw offsets/text каждого совпадения.

Три assistant-constructed controls также проходят текущий gate:

- текст только о температуре разложения с семью общими terms: 7/9;
- прямое сообщение, что морфология не исследована: 7/9;
- один исходный вопрос в роли заголовка: 9/9.

Это контрпримеры разработки, не независимые gold labels и не новый semantic
validator. Свободный path `service._validate_claims` проверяет непустой claim
и известные citation IDs; bounded source-quote contracts этого вопроса не
касаются. Исторический HTTP200/answered с термосвойством/набуханием и его
отрицательная post-hoc оценка сохранены в прежнем live review. Новый ответ
модели здесь не получен и не имитируется как научное свидетельство.

Tests run:

- **130 tests passed**, включая **10 новых**; JUnit:
  `output/kim_retrieval_audit_20261031/tests_v02.xml`. Проверены exact raw span
  mapping, article presence и exposed gate controls, существующие retrieval-loss,
  cross-lingual, reranking, generation и relation-requirements tests. Первый
  прогон до двух blank-term controls: 128 passed; числа не суммируются.
- Ruff четырёх новых source/test files passed. Начальный E501 исправлен до
  freezing review. `git diff --check` прошёл с существующими LF/CRLF warnings.
- Настоящий offline replay fusion/ranking/evidence прошёл девять boundary
  comparisons и full trace equality. DB connect запрещён, новых embeddings,
  model/OAuth calls в replay нет. Повреждённый ожидаемый порядок финальной
  diversification отклонён точно на соответствующей границе.
- Свежая PDF extraction подтвердила восемь reference windows и девять selected
  pages. Все 33 оригинальных PDF проверены по SHA256. Проверены 279 bindings,
  historical/current manifests.
- Static HTML QA: 33 TAC строки, восемь колонок, полные expandable значения
  имеющихся полей, search handler, 41 существующий PDF/page link и три artifact
  links. Для 28 работ вне исходного capture метаданные явно взяты из архивного
  DB inventory 30 октября; для пяти — из нового capture. Неизвестные поля
  сохранены. Итог: `output/kim_retrieval_audit_20261031/review_v01/review.html`.
- Sandbox capture_v01 не получил доступ к PostgreSQL: `Permission denied
  (0x0000271D/10013)`. Отдельный escalated capture_v02 завершился read-only.
  Первый каталог сохранён. Ошибки пути rg, inspection/schema, console encoding
  и начального Ruff записаны в `failed_attempts.json` как краткие summaries,
  не реконструированные full raw logs. Первый documentation patch не применился
  из-за неверного context; повторный использует реальные строки файла.

Limitations:

- Runtime/ranking/gate не исправлены; alternatives не оценивались как fix.
  Независимая новая разметка не создавалась, пользовательский reference не
  переписан. Kim/topic ранее были известны проекту. General accuracy и
  экспертная приёмка не установлены.
- Browser execution, повторная визуальная PDF проверка, full suite и mypy этой
  итерации не выполнялись. Static link QA не равен открытию PDF браузером.
  Cache/ORM repeated-request defect остаётся открыт.
- Реальные model POST/OAuth и новые slots: **0**. Прежние бюджеты закрыты;
  разрешение этой offline-диагностики не разрешает calls/resends.

Verdict:

Стадия исключения локализована: original candidate retrieval обрезает Kim до
дальнейшего fusion/ranking. Lexical допуск без нужного свойства воспроизведён.
Следующий дизайн — отдельная проверка RU/EN retrieval coverage и raw-text
normalization, затем требуемой научной связи и ложных отказов на наборе шире
этого exposed case. Не продвигать известную статью по ID и не объявлять lexical
cues научным подтверждением. Внешний оценочный набор ещё нужно продолжить.

**Общий прогресс плана: 75% работ; пункт 4 открыт.**
