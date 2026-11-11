# ARIADNE: наблюдения LSV и float-test Peng02

Changed:

Пользователь «Давай дальше» продолжил предложенный Peng02. Оба метода,
определения составов и результаты уже были в выбранном полном raw PDF2/3
фрагменте. Новый oxidation_comparison.py и ветка quantitative_facts связывают
базовый EE с его EC/EMC составом и FFT с FEC/FEMC/TFEE, сохраняют одинаковую
явную концентрацию соли и разные основания соотношений: по объёму/по массе.
Названия составов/значения/коды/режимы читаются из raw, QA IDs/эталоны не
используются. Perfluorinated передаётся как обозначение авторов, не отдельная
проверка химической структуры.

Float-test: LCO/Li, три pre-cycles при0.1C, затем4.6V относительно Li+/Li,
20h; авторская трактовка заметного тока утечки EE сохраняет suggesting,
а введение фторированных растворителей описано как сопровождающееся меньшим
током утечки. LSV:5mV s−1, Pt working electrode, Li counter/reference; EE
показывает рост окислительного тока примерно с5.5V, FFT описан как устойчивый
примерно до6.4V. Оба знака приближения сохранены; numeric delta и токи утечки
не рассчитываются. Предел LSV не объявляется рабочим напряжением полной
ячейки. Изолированный причинный вклад каждого растворителя не определяется.
Комнатная температура измерения вязкости не переносится на LSV/float-test.

Семь raw-bound записей: два состава, float-режим, LSV-метод, сравнительное
наблюдение утечек и два LSV-наблюдения. Полный F1 либо отказ, русский текст
строит сервер. Поля/условия/соль/коды/единицы/approximation/status пересчитываются
по точному исходному raw. Неоднозначные/противоречивые label/salt/dose/reference/
voltage/figure/ratio, неположительные значения, отсутствующие единицы/tilde,
неизвестные условия/общие why/negative вопросы и prior/hypothetical/bibliographic
контекст отказывают. Межфрагментная сборка не применяется. Ownership false,
arithmetic null; required-fields guard not_evaluated.

Оригинальные полные PDF2/3 свежо отрендерены Poppler и визуально просмотрены.
Отдельный reviewed_oxidation_glyph_aliases_v01.json содержит10 наблюдений одного
точного raw-parent: один U+0001→minus в скорости LSV, два U+0003→tilde, семь
U+E104/U+E103→fl/fi в методе и результатах. Привязки article/chunk/page/type,
полный raw SHA, PDF offset/font/bbox/font-program SHA и оригинальный PDF SHA.
Это визуальные интерпретации агента, не автоматическая семантика имени шрифта
и не независимое принятие. Старые catalogues/raw/PDF не менялись. Добавлена
только одна package-data строка нового ресурса с сохранением исходных байтов
окончаний строк. Wheel не собирался.

Tests run:

- Focused79passed с первой попытки; affected822passed (79 новых). Один прежний
  Starlette/httpx warning. ASGI проверки вне sandbox с synthetic transport,
  audit hook запрещает внешнюю сеть; network denials0.
- Полный mypy app218 файлов passed; финальный Ruff7 Python-файлов passed.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- All30 actual-service comparison_v01:21→22 ready-unsent, только Peng02;
  все30 retrieval traces прежние, остальные29 полных результатов и21 прежний
  native input exact. Это готовность входов, не22 корректных ответа модели.
- 81 historical actual-service сценарий сохраняет full results, пять native
  inputs exact. Открытые development данные, не независимая оценка.
- Свежая actual API preparation с настоящим поиском/registry: read-only/
  rollback, trace/native exact, registry diagnostics0, network denials0;
  11863bytes, SHA9497a234e8efe8ae3ebd6dc31bd9c129708d9afef05808a9c9673b7a9896ceb1.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter перепроверил61 raw-anchor observations, семь facts,10 glyph
  positions/font programs/bboxes, полные PDF pages против raw, неизменный
  оригинальный PDF SHA и оба существующих UI adapters. HTML содержит30
  сравнительных строк и семь подробных записей.

Сохранённые диагностики: начальный source-only locator использовал неверный
Unicode code point U+E084 вместо фактического U+E104 и остановился до извлечения
или правок app. Исправлен после чтения фактических code points. Генератор
унаследовал неточный module docstring; исправлена только документация, исходный
script/hash/snapshot/mapping сохранены в generator_docstring_v01, non-docstring
AST точен. Text write при исправлении docstring создал лишние пустые строки
и Ruff I001: восстановлены исходные CRLF-байты, intermediate script/старый
review script/review_v01 сохранены. Итоговые mapping generator_docstring_v02
и review_v02. Неудачная maintenance here-string остановилась с SyntaxError до
мутаций; последующий старый exporter отказался перезаписывать review_v01.
Диагностика сохранена в export_diagnostics_v01.json. Ресурс не регенерировался,
исходные manifests не переписывались.
Начальный Ruff E501 в driver исправлен до его выполнения.

Limitations:

Конечная grammar и source-specific glyph repair на открытых development
источниках; не общий causal validator. Новые статьи/реальное поведение F-ID
модели/независимая scientific accuracy/browser layout/полный repository suite/
wheel/deployment не проверены. Retrieval/ranking/вопросы/prompt/thresholds/UI/
DB/PDF/index/API schema не менялись. Старые live scopes закрыты; новых нет.

Verdict:

Peng02 подготовлен с разделением методов, сохранённой приблизительностью
LSV и осторожной трактовкой тока утечки.22/30 ready-unsent; восемь отказов:
1context (Peng10),5explanation,2limits. Следующий source-bound этап — Peng10:
наблюдения морфологии LCO и состава поверхностной плёнки после cycling в FFT.
Независимая оценка открыта; план75% прежний.

Отчёт: output/peng_oxidation_20261111/review_v02/review.html.
