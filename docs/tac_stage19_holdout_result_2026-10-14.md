# TAC stage19: новые открытые статьи и исправление v0.9

## Scope и статус оценки

Собраны восемь новых открытых PDF: четыре русских и четыре английских,
138 страниц. Это отдельный offline корпус, без добавления в рабочую БД,
production indexing или retrieval. Состав выбран по доступности источников,
без использования результатов TAC при выборе замены недоступного PDF.

До первого запуска сохранены оригинальные байты, SHA-256, выбранный текст
страниц, копии кода v0.8 и source-bound reference границ T/A/C. Reference
составлен агентом по оригинальным страницам; это не независимый scientific
gold. [Протокол](tac_stage19_holdout_protocol_2026-10-14.md) сохранён без изменений.
После первого запуска корпус использован для разработки v0.9 и имеет статус
development. Результат v0.9 нельзя представлять как held-out accuracy.

| Результат | Первый v0.8 | Исправление v0.9 |
| --- | ---: | ---: |
| Совпадения границ T/A/C с reference | 14/24 | 24/24 |
| Ошибки границ | 8 | 0 |
| Пропуски | 2 | 0 |
| Пропущенные непробельные позиции reference | 3 499 | 0 |
| Лишние непробельные позиции | 19 797 | 0 |

Метрика сравнивает пары `(page, offset)` непробельных символов; это оценка
границ выбранного текста, а не научной корректности, качества OCR, метаданных
или полноты всей статьи. В корпусе нет отрицательных примеров с действительно
отсутствующими Abstract/Conclusions; false-positive rate не установлен.

## Источники и воспроизводимость

| Source key | Документ | Страницы | Проверенный C |
| --- | --- | ---: | --- |
| ru_bunkin_2023 | Адсорбция метиленового синего и аскорбиновой кислоты на Нафионе | 7 | 6–7 |
| ru_kulova_2024 | Нафионовые электролиты для Li/Na аккумуляторов | 16 | 12 |
| ru_kayumov_2023 | Li-Nafion, ДМСО–сульфолан | 10 | 9 |
| ru_safronova_2022 | Растворитель и ультразвуковая обработка дисперсий Nafion | 10 | 8–9 |
| en_schalenbach_2022 | Ion exchange poisoning in PEM water electrolysis | 12 | 12 |
| en_tran_2022 | Informatics-Driven Selection of Polymers for Fuel-Cell Applications | 31 | 18 |
| en_safronova_2023 | Nafion morphology and properties of cast membranes | 15 | 13 |
| en_conductivity_2023 | In-plane conductivity of Nafion membrane | 37 | 17–18 |

Точные названия, авторские выходы, первичные URL, даты загрузки и PDF-хеши
сохранены в [manifest](../output/tac_stage19_20261014/holdout_manifest.json).
Источник источников — сайты издателей, открытый репозиторий и arXiv.
Недоступные ответы HTML/403/challenge диагностированы, обход ограничений
не выполнялся. Два файла sciencejournals.ru имеют префиксы 65 и 67 байт
перед `%PDF`; исходные payload сохранены полностью. MuPDF/Poppler прочли их.

- Corpus SHA-256: `adc77926759e86c87ce93c1aaf12000a7c71874096ea384ed58322e99693d9d0`.
- Reference SHA-256: `dd0f95e44faa21e448c7d93e3d1cd73d93e44aeef6da9a52c0ae91d1e4817d51`.
- Initial profiles SHA-256: `62db0f6354017ff5f2ab82a2731d8fa0b46bd0a54832b196c0eacd7d0b169065`.
- Final profiles SHA-256: `c6e7cb58a47cbbcdf2c3d1912b3a587280f226bd0ffb566ae9d994491629fb7a`.

Два последовательных извлечения v0.9 воспроизвели содержимое profiles.
Время генерации и файловые хеши разных запусков могут отличаться.

## Исправление алгоритма

Изменения общие, без ветвлений по article ID/названию:

- Составные заголовки Discussion and conclusions и русский эквивалент.
- Остановка перед двуязычной библиографией и единственным числом
  «БЛАГОДАРНОСТЬ»; сохранение первичного Abstract в двуязычной статье.
- Сборка абзаца Abstract с первым отступом при прежних ограничениях
  шрифта, колонки, непрерывности и расстояния.
- Исключение библиографической строки/УДК из геометрического Title;
  поддержка сложной строки авторов как TAC-якоря только при границе affiliation.
- Удаление повторного верхнего колонтитула по геометрии и отдельного
  административного абзаца государственного задания из Conclusions.

Пороги, область применения и ограничения описаны в
[контракте v0.9](tac_boundary_cleanup_contract_v0.9.md).
Метаданные авторов не исправлялись matching-view преобразованиями TAC.
Original PDFs, page text, OCR, chunking и retrieval scoring не изменены.

## Terms, метаданные и прежний корпус

Частный автоматический pipeline восьми документов создал 462 article-local
Terms, 849 uses и 27 contexts; 75 уникальных Terms имеют предложения type.
Состояния proposed/unclassified/unresolved остаются явными. Это количество
выходов, не научная precision/recall и не доказательство правильности subsets.
Ручное разрешение контекстов пользователем не включено.

Заполнено 13/24 полей Authors/Journal/Year; заполнение не означает correctness.
В Guo часть авторских имён слита. Неизвестные поля и эта ошибка сохранены
в таблице без ручной подмены. Metadata parser требует отдельного этапа.

Для прежних 33 документов повторное извлечение v0.9 сохранило все 99 полей
T/A/C, включая source spans/methods, и 91 заполненное значение метаданных.
Хеши оригинальных PDF сохранены. Эти входы используются для обновления
рабочего автоматического pipeline; новые восемь статей остаются отдельно.
На этом этапе retrieval benchmark не запускался, преимущество в поиске
или ответах не измерялось.

Рабочий v0.9 snapshot:
`121c961fc71f79222dadc430a182f2f426ec786d9d75fb85854676d7025ca97a`.
Его 2 154 Terms / 3 976 uses, context records и classification assignments
совпадают с предыдущим stage18. Содержимое предложений/диагностики связей
также совпадает; relation IDs изменились по существующему контракту, который
включает хеши входов и сортирует по этим IDs. Обе версии IDs проверены
по формуле в исходниках, без изменения relation algorithm.

Loopback API подтвердил automatic mode, отсутствие manual decisions/events
и problems; оригинальный Lin PDF вернул HTTP 200 и `%PDF`. Watcher восстановлен
с интервалом 30 секунд; первый цикл подтвердил `state: unchanged`.
Логи и [live verification](../output/tac_stage19_20261014/working_live_verification.json)
сохранены. Конфигурация: `data/terms_pipeline_config.json`.

## Проверки и артефакты

- 114 targeted tests passed, включая 17 новых случаев: 6.01 s.
- Полный pytest: 1 039 passed, одно предупреждение Starlette/httpx, 86.59 s.
  Первый запуск завис без вывода и роста CPU более семи минут; прерванные
  процессы проверены по command line. Успешным считается только повтор.
  Причина зависания не установлена.
- Ruff `app tests scripts`: passed; mypy: 94 app files, passed.
- Bundled Node `--check` HTML script: passed.
- Exact source quotes, PDF hashes, воспроизводимость profiles и regression33:
  passed; результаты сохранены отдельными JSON.
- Browser QA: восемь строк, восемь основных колонок, десять изменённых полей;
  раскрыты все 16 A/C и восемь Terms-контейнеров, русский/английский поиск
  возвращает одну подходящую строку. Все 30 local file targets существуют;
  открытие каждой `file://` ссылки в браузере не заявляется.

[Итоговая HTML-таблица](../output/tac_stage19_20261014/final_v09/ARIADNE_TAC_stage19.html)
содержит полный expandable TAC, все Terms, прежние изменённые тексты,
источники/диагностику и ссылки на оригинальные PDF. Отдельно сохранены
[первый v0.8](../output/tac_stage19_20261014/initial_v08/ARIADNE_TAC_initial_v08.html),
[initial report](../output/tac_stage19_20261014/initial_v08/report.json),
[final report](../output/tac_stage19_20261014/final_v09/report.json),
[regression33](../output/tac_stage19_20261014/regression33_verification.json) и
[browser QA](../output/tac_stage19_20261014/browser_verification.json).

## Changed / Tests run / Limitations / Verdict

Changed: новый source-preserving corpus, pre-output reference, TAC v0.9,
17 regression cases, отдельная HTML-таблица и automatic Terms snapshot.

Tests run: 114 targeted / 1 039 full tests, Ruff, mypy, JS syntax,
точные источники/хеши, повторное извлечение, old33 regression, browser QA.
Рабочая публикация, loopback API и watcher также проверены.

Limitations: development corpus и assistant reference; неизвестна независимая
точность, metadata содержит ошибки/пропуски, retrieval efficacy не измерена.

Verdict: выявленные ошибки границ исправлены и воспроизведены; прежние
результаты сохранены. Следующая научная проверка требует нового корпуса,
который не использовался для разработки v0.9.
