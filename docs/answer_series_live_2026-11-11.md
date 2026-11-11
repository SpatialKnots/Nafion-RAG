# ARIADNE: реальный прогон после сводного офлайн-аудита

Changed:

Пользователь `давай` разрешил новый ограниченный прогон тех же 30 вопросов
после завершённого аудита. Отдельный scope зафиксирован в
`docs/records/answer_series_live_2026-11-11_v0.1.md`. Прежние разрешения не
переоткрывались. Runtime приложения соответствует коммиту c5a72d3 и source
freeze 8a3740426404b02e4a99a8da2387d67935745f32395992b9e1c443438199a287.
Приложение, промпт, парсер, научные контракты, PDF, индекс и схема БД в ходе
прогона не менялись. Добавлены только отдельные runner/reviewer/assessment,
проверки ограничений и документация.

До отправки все 30 входов подготовлены в отдельных процессах через настоящий
`/answer/experimental/required-fields`: read-only/repeatable-read DB с rollback,
полная трасса и native bytes совпали с аудитом. Входы содержат только прежние
вопросы с зафиксированным контекстом статьи; эталоны в модель не передавались.
Суммарно 409344 bytes, максимум 32172 bytes на запрос, без обрезки контекста.
Сначала зафиксированы все SHA, затем открыты новые exclusive scope-local slots.

Фактический результат:

- **30 model POST и 30 OAuth**, ровно по одной попытке; retries/fallbacks/
  continuations 0. Все 30 allowances закрыты, remaining allowance 0.
- **23 HTTP200/answered**, без abstentions; guard `not_evaluated` для всех 23.
  Это число доставленных ответов, не число научно правильных ответов.
- **7 HTTP502**: Kondo10, Nambu01, Nambu07, Nambu09, Peng02, Peng06, Peng10.
  Все семь native outputs повторили один и тот же F1 с тем же citation_id:
  соответственно 6, 3, 2, 5, 5, 10 и 5 раз. Ошибка API одинакова:
  `Bounded answer must select unique exact source-backed statements`.
  Дубликаты не нормализовались и не принимались; повторной отправки нет.
- Среди 21 source-fact случая: 14 точных ID selections и 7 duplicate-ID
  rejections. Девять ответов прежнего свободного пути доставлены.
- Все ответы: GigaChat-2-Max:2.0.30.01, finish_reason=stop. Это не transport
  timeout/blacklist/обрезка. Причина повторения IDs самой моделью не установлена.
- Usage: input 84418, output 4122, total 88540 tokens; precached input 14543
  является частью input, а не дополнительными токенами. Денежная стоимость
  неизвестна. Postflight hashes у всех 30 verified, registry/network denials 0.

Tests run:

- 57 offline tests passed, включая новые проверки закрытия/неизвестного
  reserved outcome/превышения allowance/остановки после HTTP503/запрета
  повторов/исключения эталонов/native drift. Один прежний Starlette warning.
- Первый запуск тестов в sandbox завис и остановлен; XML успешного v02 и лог
  неудачного v01 сохранены отдельно. В успешных тестах внешняя сеть запрещена,
  model/OAuth calls 0.
- Ruff четырёх новых скриптов и нового тестового модуля passed. Исторические
  результаты полного pytest5979/mypy226 относятся к предыдущему offline freeze;
  полный suite в этом этапе повторно не запускался, app не менялся.
- После закрытия выполнен exact saved-native ASGI replay всех 30 результатов,
  включая семь HTTP502. Совпали HTTP status и полный API body; DB queries и
  новые model/OAuth calls 0. Аннотированный review_v02 повторяет эти 30 replay;
  всего две offline серии, без новых реальных запросов.
- Проверены manifests, request/response hashes, ledger result/closure,
  article scope и неизменность runtime; native и доставленный серверный текст
  сохранены раздельно. Статическая проверка HTML выполняется отдельно.

Post-hoc наблюдения по девяти свободным ответам:

Отдельный assessment содержит 15 точных raw witnesses с SHA/offsets/citation/
article/chunk/pages. Reviewer — implementation assistant, unblinded, после
закрытия; scores и independent scientific accuracy остаются null.

- Kondo04: 0/18.7/41.5 кДж/моль совпали, но пропущена реакция F3MEE с неполным
  подавлением cointercalation. Термин Li–solvent–graphite передан как
  «Li-солевой-графит».
- Nambu02: основные условия, около23% и >99.9% совпали; в русском названии
  спирта есть опечатка «трифтроэтокси».
- Nambu03: основной порядок проницаемостей совпал, но линейность распространена
  на «все» растворители; буквальный source sentence перечисляет три
  фторированных эфира. DEE этой текстовой привязкой не подтверждён.
- Nambu04: порядок вязкости и четыре значения энергий совпали; apparent
  activation energy остаётся авторским определением, не новой физической оценкой.
- Nambu10: около120 мА·ч/г на50-м цикле совпало. Гипотеза `can form` о составе
  плёнки передана как установленное «включает». Вопрос о подтверждённости не
  разрешён корректно.
- Peng01: solvent codes и volume/mass ratios воспроизведены, но пропущен
  1M LiPF6 во всех четырёх составах и искажено полное название TFEE.
- Peng03: основные transport/electrochemical trends отражены, но режим3C
  относится к LCO/Li half-cell; ответ явно не отделяет его от full-cell.
  Авторское suggests/ought to передано как установленная причинность.
- Peng04: все три запрошенных диапазона напряжения совпали.
- Peng09: главный вывод о большем катодном ограничении прямо есть в E1;
  детального разбора EET/CEI нет.

Limitations:

23/30 — доступность на development-exposed серии. Это не scientific accuracy,
не независимая приёмка и не перенос на новые статьи. Успех ID selection
проверяет выбор целого source-bound пакета, не самостоятельное научное
рассуждение модели. Guard not_evaluated не устанавливает корректность ответа.
Post-hoc замечания не заменяют независимые эталоны или эксперта. Browser
layout, deployment, стоимость и повторяемость модели на новом прогоне не
измерены. Приложение/валидаторы не исправлялись после просмотра результатов.

Verdict:

Новый прогон завершён и закрыт: **23 delivered, 7 strict duplicate-ID errors**.
Все результаты и неудачи сохранены. Следующий отдельный offline этап —
исследование единственности F1 в native protocol без ослабления проверки
цитат/сырого источника, а также completeness/epistemic-status gaps свободного
пути. Новые реальные вызовы не разрешены автоматически. План качества 75%.

Итог: `output/answer_series_live_20261111/review_v02/review.html`.
Scope closure: `scope_closed_v01.json`; диагностика: `duplicate_ID_diagnosis_v01.json`;
source observations: `posthoc_source_review_v01.json` в том же каталоге.
