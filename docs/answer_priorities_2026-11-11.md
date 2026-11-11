# ARIADNE: приоритеты после реального прогона

Changed:

Пользователь `Давай выполним эти приоритеты` разрешил офлайн-исправление
ID-протокола и существенных пробелов Kondo04, Nambu10, Peng01. Для независимой
проверки пользователь отдельно выбрал: `Предоставлю отдельный набор вопросов
и эталонов`. Новый набор не создавался и не объявлялся независимым автоматически.

В native JSON Schema пути source-fact добавлены maxItems по числу F-ID,
uniqueItems и ровно один citation_id на выбор. Для singleton F1 допустим
максимум один claim; пустой массив при abstention сохранён. Multi-ID пакеты
сохраняются. Локальные проверки уникальности, полного покрытия и exact citation
не ослаблены; удаления дубликатов или восстановления испорченного ответа нет.
Свободный текст и остальные пути сохраняют свою прежнюю схему.

Три конечных source-bound контракта в answer_completeness.py используют один
полный исходный parent и связывают все запрошенные части:

- Kondo04: три значения и три реакции по alias растворителя, общий salt/ratio/
  ion frame, сопоставление значений между вводным блоком и наблюдениями.
  Сохранены неполное подавление cointercalation для F3MEE и термин
  Li–solvent–graphite. Нет подстановки «соли» вместо растворителя.
- Nambu10: ёмкость, цикл, единица и нормировка на массу катода; возможный
  состав плёнки остаётся `can form`. По этой цитате не заявляется подтверждённая
  химическая идентификация или отсутствие любых исследований во всей статье.
- Peng01: все четыре состава с солью/концентрацией, компонентами, соотношениями
  и mass/volume basis. Шесть полных английских имён привязаны к source aliases;
  русские химические названия не угадываются.

Для этих трёх семейств пакет обязателен: при неполном/противоречивом binding
ответ останавливается, включая неподдержанный provider. Прежние required-concept
и relation gates не обходятся. Общие why/negative/modal ограничения не снимаются;
нет маршрутизации по author/article/QA ID. Более широкие формулировки могут
отказываться; это конечная грамматика, не общий семантический валидатор.

Свежие полные Poppler PDF-страницы Kondo2, Nambu3 и Peng2 визуально проверены.
Два новых SHA-pinned glyph catalogue содержат пять точных операций:
один minus в capacity unit и четыре fl-лигатуры химических имён. Привязаны raw
identity/SHA/offset, PDF offset/page, font/bbox/font-program SHA. Восемь прежних
каталогов, raw/PDF, retrieval/ranking, DB/index, units/thresholds и public API schema
не менялись. В pyproject добавлены два package-data ресурса и dev-only jsonschema.
После sandbox DNS denial jsonschema4.26.0 установлен в .venv вне sandbox;
production dependencies не расширялись.

Tests run:

- 88 focused tests passed, включая семь фактических duplicate-ID outputs,
  multi-ID/abstention, wrong citation/prose, raw/record drift, отрицательный статус,
  несовпадения единиц/циклов/солей/компонентов, section boundaries, cross-parent
  splicing, required-concept/relation gates и запрет free fallback.
- Полный mypy app227 passed. Ruff app/tests/new tools passed; repository Ruff
  сохраняет два прежних E501 в историческом assess_query_rewriting_20261110.py.
- comparison_v01: все30 ready-unsent, retrieval30 exact,27 non-target full
  results exact. Native21 изменились только объявленными schema constraints,
  шесть free-path native побайтно прежние; три новых source-contract native
  изменены отдельно.24fact-cases/99facts/792raw-anchor observations.
- 30 saved-native API executions под текущим кодом:27 полных HTTP/body прежние,
  включая семь первоначальных HTTP502. Три прежних свободных ответа Kondo04/
  Nambu10/Peng01 теперь отклонены как не соответствующие новому F-ID контракту.
  Это counterfactual replay, не новый реальный прогон или оценка доступности.
- 12 SYNTHETIC actual-API controls для трёх новых контрактов: F1/abstention
  HTTP200, prose/wrong-citation HTTP502. Дополнительно каждый из24fact-cases
  проверен synthetic service select/abstain/prose и wrong-citation resolution.
- Историческая регрессия81 full service results exact. У четырёх из пяти
  старых native изменились только schema constraints; один native точен.
- Offline wheel246app/resource files exact; isolated installed app воспроизвёл
  те же30 service preparations/native bytes, без DB/model/OAuth.
- Полный repository pytest:6085passed/0skipped,1762.18s, один прежний
  StarletteDeprecationWarning; network denials0. Итоговый verification_v01
  проверил пять positioned glyph/font bindings,91raw-anchor observations трёх
  новых контрактов, оба UI adapters (6checks),30case/3article HTML rows,
  восемь TAC columns и все10local links. Состав app-патча и ровно три
  объявленных изменения pyproject проверены относительно pre-edit snapshot.

Сохранены промежуточные неудачи: collection v01 без jsonschema; v02 — четыре
ошибки тестовых probes (capitalize изменял solvent code; разрез текста оставлял
целый контракт в одном parent); v03 —79passed; v04 —85pass/3fail из-за забытого
deepcopy import в тесте; начатый fullv01 остановлен. После исправления теста
focusedv05 —88passed. Научная логика ради ошибочных ожиданий не ослаблялась;
добавлен положительный контроль полного parent рядом с неполным. Неудачные
логи/XML и снимки попыток сохранены отдельно.

После compare/history/package менялся только HTML exporter: маркировка
свободного пути и раскрываемые TAC поля. exporter_mapping_v02.json подтверждает
AST-равенство всех остальных функций с сохранённым executed_script.py;
первоначальные результаты и manifests не переписывались.

Limitations:

Новых real model/OAuth/slots0. Все старые30 allowances закрыты, original native
ответы и ошибки прежние. Новые maxItems/uniqueItems проверены локальным
jsonschema; их фактическая поддержка провайдером и новый model compliance
ещё не измерены. Официальная страница structured-output описывает strict schema,
но отдельно эти keywords там не перечислены; это не доказательство их отсутствия.
Источник: [GigaChat structured output](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output).

Это открытые development вопросы/конечные грамматики. Остальные шесть свободных
путей, включая прежние оговорки Nambu03/Peng03, автоматически не исправлялись.
Общая scientific accuracy, независимая приёмка, новые статьи, browser layout,
deployment и новый live-показатель доступности не установлены.

Verdict:

Первые два приоритета реализованы и проверены офлайн. Для третьего готов
протокол docs/records/answer_priorities_independent_v0.1/README.md и пустые
intake templates. Код, ресурсы, конфигурация и документация фиксируются до
получения отдельного набора: output/answer_priorities_20261111/candidate_freeze_v01/version.json.
Итоговая проверка freeze сохраняется отдельно в verification_v02; commit и
candidate version ID — в release_v01.json этого же output каталога.
Независимая оценка остаётся открытой; новый живой scope не создан. План75%.

Итоговый review: output/answer_priorities_20261111/review_v01/review.html.
