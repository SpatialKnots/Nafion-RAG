# ARIADNE: read-only карта требований и пробелов

9 ноября 2026, Asia/Yekaterinburg.

Changed:

Реализована первая ограниченная карта требований из архитектурного плана:
`composition_cycling_requirements_v0.1`. Семейство — явная авторская ссылка,
состав электролита с фторированным эфиром и результаты циклирования для двух
различных указанных ячеек. Каталог слов и запросов конечный. Неизвестные
ограничения, другие семейства и неподдержанные вопросы дают `not_applicable`;
они не превращаются в сокращённый вопрос с отброшенными условиями.

Новые явные маршруты:

- `POST /answer/prepare/requirements`;
- `GET /ui/answer/prepare/requirements`;
- `POST /ui/answer/prepare/requirements`.

Они используют прежний валидируемый `PreparationRequest`, тот же read-only
`prepare_api` и остановку до генерации. API возвращает отдельно всю неизменённую
исходную подготовку и карту. Прежние `/answer/prepare` и `/answer`, их решения,
evidence и верхнеуровневые ответы не менялись. В форме подготовки добавлена
ссылка на новый режим с сохранением выбранной библиотеки. Новый GET повторно
использует прежнюю обработку cookie/явного library_source_id. Новые ошибки
целостности карты возвращаются HTTP400; ошибки исходной подготовки сохраняют
прежнюю семантику. Нового запроса модели этот маршрут не строит.

Относительно freeze этого этапа изменены только два прежних app файла:
`app/main.py` (регистрация router) и `app/generation/preparation_routes.py`
(ссылка в форме). Добавлены `answer_requirements.py` и `requirements_routes.py`.
Прежние service/preparation/fact/source grammars/Methods policy, retrieval,
filters/context budget, DB/schema/PDF/index и inference admission неизменны.
Изменения прошлого этапа остаются отдельно связанными с прежними snapshots.

Карта содержит четыре требования: состав, сохранение ёмкости, CE и связь состава
с результатами. Для каждого сохранены основание обязательности в конечном
контракте вопроса, поля, состояние обнаружения, состояние поддержки, кандидаты,
точные source anchors/условия/units/status/unknowns либо непроверенная область,
причина пробела и предложение следующей проверки.

Различаются:

- распознанный шаблон факта;
- несколько разных значений или областей источников;
- упоминание с нераспознанной грамматикой;
- не найдено в просмотренном выбранном контексте;
- непроверенные выбранные источники;
- доступный текстовый контракт связи, условный кандидат либо unresolved identity.

Научная поддержка для всех строк — `not_evaluated`. Совпадение слова, числа,
article_id или концентрации не считается установлением принадлежности. Повторные
совпадающие поля в overlapping chunks группируются как избыточные bindings;
независимые научные свидетельства из них не объявляются. Неизвестные условия
не становятся обязательными полями вопроса автоматически и не заполняются.

Распознавание заново выполняется на зарегистрированных raw chunks выбранных
источников. Derived JSON и source_facts metadata не выдаются за текст PDF.
Для известных fact/quote derived родителей проверяются bindings и восстановление
всего графа, тип/слой Methods — против зарегистрированного raw parent. Повреждение
источника отклоняется видимо; недоступный registry помечается непроверенной
областью. Hash всей исходной подготовки связывает карту также с её вопросом,
метаданными и blockers; `validate_requirements` воспроизводит карту целиком.

Существующие quotation/fact/explicit-label контракты проверяются read-only.
Methods-кандидат отдельно помечен условным: он не включает runtime policy и не
меняет её disabled default. Следующие действия только предлагают просмотр
уже выбранных источников: executed=false, new_source_budget=0, model_call_budget=0.
Нет автоматического retrieval action, генерации или нового допуска.

В UI показаны читаемые состояния, exact фрагменты, PDF-страницы, поля и
предлагаемая проверка. Полная диагностика и оригинальная подготовка доступны
отдельно; её blockers сохраняются даже при найденных текстовых контрактах.

Tests run:

- До app edits: freeze194 app Python/YAML и исходных данных; 81 фактический
  frozen-channel service run и пять unsent native bodies совпали с предыдущим
  baseline. Финальный отдельный compare повторил 81 run: полные результаты
  пяти current +76 old и все пять native bodies побайтно прежние. Всего162
  service executions этого этапа; это известные regression cases, не hidden gold.
- **1077 affected tests passed**, включая **64 новых** теста карты/API/UI,
  source binding, stale parent/map, blockers и actual no-generation boundary.
  Первый new-only probe:58passed; после дополнительных source-registry проверок
  и шести явных blocker/ambiguity controls полный набор прошёл1077. Все новые
  тесты реально выполнялись; весь repository suite не запускался.
- External-network audit denials во всех тестах и export — **0**. Новых model
  POST/OAuth exchanges/slots/DB preparations/ingestion/deployment — **0**.
  Actual preparation/service boundary проверена с synthetic DB/source-registry
  seams и запретом provider factory; это не свежая production DB preparation.
- Ruff девяти новых/затронутых app/test/script файлов passed. Полный mypy app:
  **196 source files**, success. Первые два неиспользованных test imports и две
  mypy diagnostics об inferred object для списка строк исправлены; научная
  логика из-за них не менялась. pytest failures этого этапа не было.
-27 объявленных controls: synthetic preparation с неизменными real Lin raw
  parents,22 прежних constructed split-role controls и4 дополнительных controls.
  25 mapped/2 not_applicable;100 строк:60 recognized pattern,8 grammar unrecognized,
  1 ambiguous candidates,3 not found in inspected context,3 uninspected sources,
  3 textual identity contracts и22 unresolved identities. Это состояния
  конечной диагностики, не precision/recall или доли научно правильных ответов.
-33 original PDF hashes проверены. Для Lin PDF1/3/7 выполнена свежая extraction,
  67 raw-anchor observations/58 уникальных адресов сопоставлены с raw chunks
  и свежими PDF строго в declared page range. Три свежих рендера визуально
  просмотрены; все три копии сохранены в review.
- Статический HTML QA:5 старых case sections,33 TAC works/eight columns,
  57 существующих PDF links. Отдельный preview содержит27 controls/100 requirement
  rows, исходные runtime fragments и явные adapters для минимальных synthetic
  preparations. В preview добавлены только пустая qualifier presentation и
  зарегистрированные ссылки для старого renderer; исходные controls сохранены.
  У synthetic article IDs PDF не выдумываются: неразрешённые ссылки заменены
  явной меткой. Рабочие ссылки на real articles сопоставлены с original PDF.
- Browser layout не проверялся: предыдущий этап установил блокировку file://
  политикой браузера. Новых попыток и обходов этой политики здесь не было.
  `git diff --check` passed; Git показывает обычные LF→CRLF notices.

Limitations:

Один конечный тип вопроса. Данные раскрыты, preparations/DB seams синтетические;
это не независимый научный эталон. Качественные/количественные выводы из источника
и принадлежность величин в общем случае не подтверждены. Для слова без распознанной
грамматики карта не устанавливает ни факт, ни отсутствие научных данных.
Отказы/accuracy/время проверки человеком не улучшены измерением этого этапа.
Новых retrieval actions, версионного постоянного evidence packet/decision log,
model Reviewer и rollout нет. Свежие production DB, browser layout, cache/ORM,
concurrency/deployment и полный repository suite не проверены.

Verdict:

Первый ограниченный этап архитектурного плана реализован offline: карта
объясняет выбранные источники и пробелы, сохраняя исходные решения и запреты.
Новый режим доступен явно через API/UI. Независимая оценка открыта; исходный
план качества ответов остаётся **75% работ**. Следующий отдельный шаг —
версионированный evidence packet и минимальный журнал диагностических решений
поверх этой карты; автоматический сбор контекста этим этапом не разрешается.

- [HTML review](../output/answer_requirements_20261109/review_v01/review.html)
- [Read-only UI preview](../output/answer_requirements_20261109/review_v01/requirements_UI.html)
- [Полный report](../output/answer_requirements_20261109/review_v01/report.json)
- [Протокол](records/answer_requirements_protocol_2026-11-09_v0.1.md)
