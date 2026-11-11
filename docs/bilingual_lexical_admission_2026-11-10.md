# Двуязычная проверка лексического допуска

Changed:

Пользователь поручил устранить необоснованные лексические отказы. Добавлен
`app/generation/bilingual_lexical.py`, версия `bilingual_field_mention_coverage_v0.2`,
и один дополнительный путь в общем `answer_question` (`/answer` и экспериментальный
маршрут используют эту функцию). Из прежнего service сохранена полная копия;
проверка hashes подтверждает, что других прежних app-файлов эта итерация не меняет.
Новый runner/reviewer/read-only preflight и46 constructed controls обслуживают
проверку. Старые незакоммиченные изменения не откатывались.

Первоначальная проверка сравнивает слова исходного русского вопроса напрямую
с английскими фрагментами. Новый путь использует конечный словарь эквивалентов
синтез/выход/чистота/очистка и вязкость/энергия активации, с дополнительными
признаками порядка и класса ethers. В app-логике нет имён авторов, case/article IDs,
эталонных значений, страниц или ожидаемых результатов этих30 вопросов.

Допуск возможен только при прежнем lexical refusal, одной точно разрешённой
ссылке с одной фамилией/годом и всех evidence из этой статьи. Требуются минимум
два разных основных понятия, покрытие всех содержательных слов/названных
идентификаторов и всех запрошенных полей в одном исходном фрагменте. Для
названного вещества его literal identifier также требуется в локальном
предложении каждого основного поля. Неизвестные слова, методы, числа/условия,
причинные/эпистемические/отрицательные вопросы не превращаются в разрешение.
Для запрошенного количества упорядоченных объектов требуется исходная цепочка
идентификаторов с нужным количеством элементов. Число не подставляется из эталона.

Каждое совпадение содержит raw quote/offset/context/hash/citation/chunk/article.
Поле scientific_support остаётся not_evaluated. Локальные явно отрицательные,
предположительные, previous-work и bibliography контексты исключены конечными
правилами. Registered source_type остаётся прежним: страницы Nambu записаны
как method и figure_caption, хотя содержат полные экспериментальные/results
абзацы; новый лексический путь допускает эти типы и main_text без переклассификации.
Специализированные required-concept/relation, quote/fact/fidelity/superlative/
Methods и output validators продолжают работать после/вместе с этого пути.

Пороги исходной проверки, retrieval/ranking/filters/top_k/context budget,
исходные вопросы, generation prompts, PDF/index/DB schema не менялись.
Baseline metrics сохраняются отдельно. Новые model/OAuth allowances не создавались.

Tests run:

- **324 passed**, включая46 новых constructed controls: разные имена/вещества/
  значения, inflections/ligatures, отсутствие каждого поля/идентификатора,
  substring traps, другой article/reference, split phrases/fragments,
  неизвестные условия/методы/числа, negative/status/causal requests,
  wrong product, previous work и неверный item count. Actual service controls
  проверяют допуск до provider, сохранение provider abstention и substance veto.
  Полный app mypy:209 Python files passed. Ruff шести затронутых Python files passed.
  Полный repository suite не запускался. FastAPI/Starlette сообщил предупреждение
  о deprecated httpx TestClient, без новых runtime dependency изменений.
- Сравнение30 actual old/new service preparations на тех же frozen retrieval
  objects: baseline полностью реконструирует старые traces/native/refusals;
  после исправления **9 ready-unsent вместо7**. Новые: Nambu_02 (синтез/выход/
  чистота/очистка) и Nambu_04 (порядок вязкости/энергия активации). Все30 исходных
  selections/raw texts сохранены, семь прежних ready traces/native inputs точны.
  Остальные21 lexical refusals не объявлены научно обоснованными.
- Три проверки81 прежнего service-channel case (243 executions) сохранили все
  полные результаты и пять native inputs, включая финальный regression_v03.
  Это повторная регрессия, не243 независимых научных задач.
- Две **свежие read-only/rollback подготовки через реальный experimental API**
  с текущей локальной PostgreSQL подтвердили predicted traces/native byte-for-byte:
  Nambu_02:20818bytes SHA `4c9592dd822317e53d25faa89e8b142367435e84ec1b3a31f4413c61bc4e372d`;
  Nambu_04:20862bytes SHA `7b018d3afeb9478d67f9bc2d23c4c8084c7fcc2081491c8e15cd33ec1433a305`.
  Они остановлены на provider boundary до внешней отправки; реальные model POST/
  OAuth0, slots0, network denials0. Сравнение frozen corpus отдельно не обращалось
  к БД. Свежего поиска остальных28 вопросов здесь не заявляется.
- Проверены исходные PDF hashes3 работ, hashes11 сохранённых страниц и10 точных
  page anchors в двух новых допусках. Свежего PDF extraction/rendering/browser
  layout не было. Native buffers и prior results сохранены как есть.

Диагностика и версии:

Начальные41 controls прошли. Два последующих adverse constructed probes выявили
ошибки v0.1: фамилии Yield/Purity считались полями, а never measured давало
совпадение purity. v0.1 implementation/comparison/probes сохранены. Отдельный
v0.2 маскирует bibliographic span перед анализом и исключает явные no/not/never/
without контексты. Финальное ограничение одной фамилией защищает от неподтверждённых
дополнительных соавторов, которых прежний resolver сам не проверяет. Предыдущие
comparison_v01/v02 и implementation_v01/v02 не переписаны; финальный comparison_v03.

Сводный sandbox pytest остановился на ASGI, не считался успешным. CIM inspection
потребовал выход из sandbox; завершены только точно определённые PID23388/25444.
Следующие guarded тесты вне sandbox прошли323, затем финальные324 после добавления
coauthor control. Исправлены отдельные lint E501/E731 до финальной проверки;
две диагностические terminal команды имели encoding/comprehension ошибки и не
выполнили изменений. Ни одного неуспешного реального model attempt не было,
поскольку реальный transport вообще не вызывался.

Limitations:

Это конечный двуязычный словарь прямых field questions. Он не решает все
русско-английские вопросы и не устанавливает научную обоснованность оставшихся
21 отказа. Наличие полей/локальных идентификаторов/цепочки не доказывает
принадлежность каждого значения эксперименту, полноту ответа, причинность,
эпистемический статус или научную истинность. Прежние допуски не пересмотрены.
Неизвестная грамматика — ограничение parser, а не отсутствие данных в статье.
Текущие30 вопросов уже раскрыты; independent scientific evaluation остаётся
открытой. Качество новых model answers, цена/токены, deployment/server reload
и перенос на другие языки/семейства не измерялись.

Verdict:

Два ранее проверенных ложных lexical refusals сняты общим source-bound правилом,
с подтверждением фактической API-подготовки и сохранением старой регрессии.
9/30 — доступность подготовки, не научная accuracy и не9 полученных ответов.
Общее устранение всех ложных отказов остаётся открытым; следующему расширению
нужны отдельные смысловые проверки оставшихся классов, а не снижение порога.
Все live scopes закрыты; новых автоматических отправок нет. План качества75%
по-прежнему относится к работе по плану, а не к правильности проекта.

[Сравнительная таблица30 вопросов и точные фразы](../output/bilingual_lexical_admission_20261110/review_v02/review.html) ·
[Полный отчёт](../output/bilingual_lexical_admission_20261110/review_v02/report.json) ·
[Контрпримеры v0.1](../output/bilingual_lexical_admission_20261110/adverse_v01.json) ·
[Свежая API-подготовка Nambu_02](../output/bilingual_lexical_admission_20261110/fresh_api_v01/Nambu_02/result.json) ·
[Свежая API-подготовка Nambu_04](../output/bilingual_lexical_admission_20261110/fresh_api_v01/Nambu_04/result.json)
