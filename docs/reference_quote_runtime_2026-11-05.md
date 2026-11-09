# Q01/Q05: поиск по явной ссылке и ограниченный ответ цитатами — 2026-11-05

Changed:

- В рабочий код добавлены `app/retrieval/source_reference.py` и
  `app/generation/reference_quotes.py`. Исходные185 runtime bindings сохранены
  до изменения в `output/reference_quote_runtime_20261105/freeze_v01`.
  [Первичный протокол](records/reference_quote_runtime_protocol_2026-11-05_v0.1.md),
  [отдельное усиление проверки авторов](records/reference_quote_runtime_protocol_2026-11-05_v0.2.md).
- Единственная явная ссылка автор/год разрешается по зарегистрированным
  title/authors/year **в заданной collection и со всеми исходными filters**:
  article/library/year/tag/type/layer и прочие. Неоднозначность/отсутствие
  оставляет исходную выдачу. Затем chunks читаются только из найденной работы.
  Для составного вопроса сохраняются body roles перед top-k: abstract с
  composition/cycling либо preparation + conductivity table. Числа, авторы,
  IDs работ и страницы эталона не зашиты. Вне explicit reference lookup нет
  дополнительных SQL-запросов. Новый метод имеет явный retrieval_method и
  score0 для незапрошенного semantic scoring; upstream scores не переопределены.
- Для двух ограниченных семейств предусмотрен **только выбор точных цитат**:
  (1) состав fluorinated ether/carbonate electrolyte + результаты двух ячеек,
  буквально указанных в вопросе; (2) ethanol-free Nafion dispersion для указанного
  sample + conductivity comparison с указанной commercial dispersion.
  Дополнительные неподдержанные слова/числовые условия блокируют этот путь.
- Нужны все source roles, границы разделов, unit/header/sample cues и одна
  разрешённая работа. Чужой sample/cell, отсутствующий table/units/footnote,
  явно future/unperformed/hypothesis-only текст остаются blocked. Это finite
  textual guards, не полный semantic/performed/material/value ownership validator.
- Каждый разрешённый claim — атрибутированная **неизменённая** исходная цитата.
  Native enum и локальная проверка запрещают перефразирование/новые числа/
  неправильную ссылку. Q05 обязан выбрать method и table вместе либо отказаться;
  неполный ответ вызывает GenerationOutputError, не объявляется успешным.
  Mini-review для этого контракта также требует все роли, даже из одной работы.
  В native prompt только для нового типа явно предписан выбор всех цитат.
- Новый internal type `reference_quote_derived`, version
  `explicit_reference_quotes_v0.2`, хранит SHA256 raw chunk и точные offsets.
  Source registry явно проверяет hash/span/article/chunk/citation/allowed text,
  а displayed citations остаются исходным текстом и страницами, не JSON.
  Public API fields сохранены; versioned metadata расширена. Общий lexical gate
  и его численные thresholds не менялись. Допуск заменяется только для полного
  quotation-only contract; свободный ответ через него невозможен.

## Измеренный результат

| Случай | После предыдущего этапа | Текущий путь |
|---|---|---|
| Q01 | Production search не выбирал Lin; отдельный кандидат получал lexical refusal | Lin p1 с полным abstract. Named Lin/Zhao и год связаны с первым листом. Контракт допускает только исходную цитату о составе/обеих ячейках; native request подготовлен, **не отправлен**. |
| Q02 | Guo p7–8, эталонные p1–2 отсутствовали | Явная ссылка возвращает Guo p1–2. Старый gate допускает контекст по concept coverage; новый quotation contract здесь не применяется, реального ответа нет. |
| Q03 | Исправлены table/context p3–4 | Сохранено; p2 с экспериментальными оговорками по-прежнему не выбран. |
| Q04 | Исправлены cycle/structure p6/p12 | Сохранено. |
| Q05 | Preparation p2 находился только в отдельном кандидате, table p7 терялась, lexical refusal | В рабочем search сохраняются preparation p2 и conductivity table p7. Контракт требует обе точные цитаты и сохраняет water-content columns/footnote/units; native request подготовлен, **не отправлен**. |

Source retention в фактическом inference evidence (для derived — **только
разрешённые raw quote spans**, не весь родительский chunk): reference pages
**4/10→9/10**, ранее mapped quotes **4/12→12/12**. Прежние семь source notes —
отдельный знаменатель **3/7→6/7**. Два исходных unmapped quote не исправлялись;
их source-note alternatives сохранены отдельно. Это не scientific accuracy:
развёрнутых модельных ответов здесь не получали.

Все76 старых repaired full traces идентичны baseline; labelled article losses и
gate boolean changes0. В этих76 explicit-reference parser activation0, поэтому
это изоляция вне ветви, не независимая научная оценка нового admission.
Q01/Q05 — два раскрытых development случая. Ни IDs/страницы/gold, ни expected
values не передавались в worker/native request; question-only selection завершена
до первого чтения эталонов оценщиком.

## Артефакты и native boundaries

- Итоговая [таблица и синтетические примеры](../output/reference_quote_runtime_20261105/review_final_v02/review.html).
  **SYNTHETIC_EXACT_SELECTION — не ответ реальной модели.** Детерминированный
  тест выбрал все допустимые цитаты через настоящий service; нативная схема и
  ответ service проверены. Они отдельно помечены в HTML; предыдущие реальные
  ответы benchmark не переписаны и не подменены.
- [Полный report](../output/reference_quote_runtime_20261105/review_final_v02/report.json),
  [верификация](../output/reference_quote_runtime_20261105/review_final_v02/verification.json),
  [JUnit262](../output/reference_quote_runtime_20261105/tests_final_v01.xml),
  [финальная проверка55](../output/reference_quote_runtime_20261105/tests_typefix_v01.xml).
- Две фактические fresh-process подготовки Q01/Q05: read-only/repeatable-read
  DB/local semantic search, rollback, gold-read/network guards, real service and
  native serializer. Внешний `_post` заменён: по одному simulated OAuth boundary
  и одному captured native boundary, **реальные model/OAuth/slots0**.
  Оба полных trace точно совпали с offline repaired; source registry diagnostics0.
- Q01 request **5258 bytes**, SHA256
  `821446de48ea4256d654923a4679eb3ed2cfa60ada9d97bfb1606139c14fc2eb`;
  Q05 **6533 bytes**, SHA256
  `f264b28d85dbbad9800811149dc44deb38e781b45bb748a603b4a34c4c218d63`.
  v0.1/v0.2/synthetic-boundary/fresh native bytes идентичны для каждого случая.
  GigaChat-2-Max /1200 output tokens/120s; monetary cost не измерялась.
  Prepared contracts имеют максимум0 реальных calls, не резервируют слоты и не
  являются live authorization. Отправок/повторов/fallback не было.
- TAC: все33 работы, восемь колонок, раскрываемые missing/не реализованные поля,
  поиск,72 существующие ссылки на исходные PDF/страницы. Static HTML QA passed;
  browser execution не проводился.

## Усиление после adverse control

Сохранённый `adverse_author_guard_v01.json` — **constructed software control**:
вопрос Smith/Jones, источник Smith/Brown. v0.1 допускал точные цитаты, поскольку
первый автор/год совпадал, а явно названный соавтор не проверялся. Это не
scientific false-answer rate; реальной модели на этом кейсе не было.

Отдельно до нового измерения зафиксирован v0.2: все явно названные фамилии должны
находиться whole-word в first-page front matter до Abstract/Introduction/section
body, год — на этом исходном первом листе. Поздняя bibliography/metadata не
заменяет guard. Et al. не выдумывает неизвестных фамилий. Новые constructed
negatives для автора/года/первой страницы проходят; v0.1 report/source snapshot
и adverse результат неизменны. Это необходимая буквальная связь, не независимая
экспертная библиографическая идентификация.

Tests run:

- **262 distinct tests passed**, включая55 новых:37 quotation controls,10
  reference/filter controls,8 actual service/native controls. Остальные207 —
  предыдущие generation/evidence/reranking/labels/transport/retention/replay tests.
  После финального mypy-only переименования55 затронутых tests повторены и прошли;
  они также подтвердили байтовую идентичность native bodies с frozen v0.2.
- Covered: RU/EN supported forms; unknown constraints; wrong cells/material/sample;
  author/year ambiguity/boundaries; title/body-only identity; all SQL filters;
  missing preparation/table/unit/footnote/section boundary; future/negative cues;
  cross-article joins; partial selection, additions, wrong citations, abstention,
  tampered hash/span/claim/parent; raw characters/conditions/units unchanged.
- По164 actual offline service runs в v0.1/v0.2:81 cases×2 +2 synthetic selections.
  Baseline воспроизвёл81 прежнюю полную трассу/границы при явно выключенной только
  новой ветви. Inactive source reference не открывает БД. Модель в этих runs
  отсутствует; Engine.connect в replay запрещён.
- Проверены314 report bindings (с явным mapping ниже),33 PDF hashes,
  10 свежих эталонных страниц/19 raw spans и15 конечных evidence records.
  У derived отдельно проверены exact source spans/parent hashes/citation IDs.
- **Полный mypy app:186 source files passed. Ruff15 Python files passed.**
  `git diff --check` прошёл с CRLF warnings.
- Два старых исторических test fixtures сохранены до адаптации в
  `historical_test_snapshot_v01`. Старый replay теперь явно выключает новую
  ветвь для замороженных прежних boundaries; проверка непринятия неподтверждённой
  author metadata ожидает новый более строгий reason. Assertions не ослаблены;
  новые реальные service tests отдельно проверяют активную ветвь. Старые
  manifest hashes не переписаны.
- Первые Ruff unused/line-length и mypy annotation diagnostics исправлены.
  Финальный mypy нашёл reuse локального `words` как set и list после author
  guard; имя author_words изменено **без изменения логики**. Исходный v0.2
  snapshot/SHA сохранён; verifier допускает только это точное переименование.
  Финальные55 tests подтвердили прежние native bytes.
- Q01 fresh capture записал полный валидный manifest/contract, но процесс
  завершился UnicodeEncodeError при печати символа‖ в cp1251 после записи.
  Артефакты проверены без нового DB/model запуска. Driver stdout переведён в
  JSON ensure_ascii=True; его исходный SHA/source snapshot отдельно сохранён
  и сопоставлен. Q05 со скорректированным stdout завершился успешно. Ни ошибка
  печати, ни проверка сохранённых файлов не являются дополнительной inference.

Limitations:

- **Реального нового model answer нет.** Provider enum support, точность
  посимвольного копирования/лигатур, output budget и actual model abstention
  остаются live-непроверенными. OAuth/blacklist/empty content не исправлены.
- Поддержаны только две finite query families с ограниченным словарём/границами
  разделов. Это вывод исходных цитат, не русскоязычный пересказ, свободный обзор,
  количественное сравнение с вычислением отношения или полный catalogue.
- Unit interpretation/конверсия не производится; например, исходная PDF/OCR
  запись единицы в таблице сохраняется буквально. Sample/material/value owners
  и performed/scientific truth не объявлены экспертно подтверждёнными.
- Q03 claim-level εког/ΔH validation остаётся открытой: правильная таблица уже
  в evidence, но свободный новый ответ ещё не проверен. Не хватает одной из10
  reference pages — experimental caveats Q03 p2. Q04 terminology caveat сохранён.
- Independent evaluation, browser/PDF visual/full suite/running-server deployment,
  cache/ORM/concurrency и latency/cost не проверены. Пять exposed cases не дают
  независимой научной метрики.

Verdict:

**Рабочий путь Q01/Q05 теперь находит необходимые части и допускает только их
точное атрибутированное цитирование**, при сохранении отказа/блокировки неполного
или неподдержанного выбора. Общий threshold не ослаблен. Положительный service
output проверен синтетически, native запросы подготовлены и не отправлены.
Измерено улучшение source retention, не scientific answer accuracy. Все live
budgets закрыты; независимая оценка/cache-ORM открыты, прежний план75% работ.
