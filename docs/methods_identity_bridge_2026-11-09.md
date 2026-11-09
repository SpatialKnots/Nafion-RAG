# Проверка связи через Methods: read-only результат

9 ноября 2026, Asia/Yekaterinburg.

Changed:

По просьбе пользователя проверены реальные определения Lin2020 и причина
figure_caption. Добавлены только offline diagnostic/test/review scripts.
Все193 app Python files и YAML остались байт-в-байт прежними. Нет изменения
runtime admission, DB/index/PDF, source_type, retrieval/filters или generation.

Найден согласованный конечный кандидат связи:

| Источник | Проверенное содержание |
| --- | --- |
| Abstract, PDF1 |1.2 M LiPF6 в FEC/dimethyl carbonate/HFE,1:1:1 by volume;0.15 M добавки; reported total1.35 M |
| Introduction, PDF1 | Явное определение lithium difluoro(oxalato)borate (LiDFOB) |
| Material Preparation, PDF3 | Явное dimethyl carbonate (DMC); три solvent/ratio entries и три base codes, respectively |
| Base selection, PDF3 | FEC/DMC/HFE1:1:1 соответствует FDH-1.2M-LiPF6 при общей1.2 M LiPF6 |
| Additive series, PDF3 |0.05,0.15,0.3 M LiDFOB separately added to этой базе → FDH-1.25M-LiPD, FDH-1.35M-LiPD, FDH-1.5M-LiPD |
| Conclusion, PDF7 | Явно назван функциональный электролит FDH-1.35M-LiPD; далее CE Li||Cu |

Второй список сопоставлен по порядку элементов. Это **явно объявленное
правило ordered parallel-list pairing** диагностического кандидата. В первом
списке имеется respectively; во втором separately/to obtain. Правило не
выдаётся за универсальное semantic entailment или независимое scientific ownership.

Проверяется весь состав: salt/concentration, все solvent tokens, volume ratio,
additive alias/dose, reported total и literal base/product codes. Alias берётся
только из точного определения источника; chemical dictionary/model не используется.
Цифры внутри code не декодируются. Тест с opaque TGT-999-LiPD сохраняет правильные
source quantities; совместная перестановка списков и coherent изменения чисел
подтверждают отсутствие привязки к benchmark positions/values в parsing logic.

CE в Abstract и Conclusion совпадает по cell/value/unit/cycles/current/areal
capacity. Capacity берётся из Abstract с собственными conditions. Написание
Li||LCoO2 в capacity фразе Conclusion не исправлялось на Li||LiCoO2; сама эта
фраза не подменяла Abstract recipe. Температуры из других операций не переносились.

Каждый шаг имеет exact raw hash/article/chunk/page/span. SourceView распознаёт
слова с переносами, но для code comparison применён raw-span NFKC+whitespace-only:
дефис в FDH-1.2M-\nLiPF6 сохранён. Иначе word dehyphenation теряет структурный
дефис и может создать ложное несовпадение labels. SourceView/runtime не менялся.

Причина source_type установлена:

- В неизменённом Methods parent current classifier воспроизводит figure_caption.
- Trigger: raw offsets5930:5938, строка Figure 2 в конце смешанного чанка.
  Визуально PDF3 действительно содержит и Figure2, и Material Preparation.
- Classifier выбирает caption до проверки методики по любой такой строке.
  Label всего parent не устанавливает роль каждого внутреннего фрагмента.
- Выделенный Material Preparation span current classifier называет formula_block:
 7 из20 непустых строк formula-like, доля0.35 при текущем пороге0.3.
  Поэтому простое вырезание текста не даёт автоматически надёжный method label.
- Никакой source_type не исправлен и не записан обратно. Диагностика scope
  отдельно от классификации остаётся необходимой будущей работой.

Tests run:

-33 новых read-only теста passed, external-network guard denials0.
-29 входов:1 неизменённый real candidate,4 constructed positives и24 negatives.
  Негативы меняют salt/solvents/ratio/basis/aliases/dose/base/product/list order,
  context status/section boundaries/CE cell/value/conditions/work/layer/структурный
  дефис. Положительные separately обозначают joint permutations, opaque code и
  coherent numeric changes. Это не29 научных подтверждений и не independent gold.
-53 raw-anchor observations/51 различных адресов проверены по parent hashes,
  exact slices и свежим PDF-страницам в объявленном диапазоне каждого anchor.
  Повторы не считаются независимыми свидетельствами.
-33 original PDF hashes и3 свежие страницы Lin(PDF1/3/7) проверены. Все три
  страницы визуально просмотрены; копии рендеров сохранены в review.
-193 app Python files плюс YAML неизменны. Прежние81 service baseline и5
  native bodies проверены по сохранённым hashes/manifests, **не запускались
  заново**. Новых service runs/native preparations/DB операций/model/OAuth/
  slots0. Ранее763 tests не выдаются за новый full-suite run.
- Ruff пяти новых diagnostic/control/test/review файлов passed; mypy самого
  diagnostic module passed (1 source file). Новый full mypy app не запускался.
- HTML QA:5 прежних case sections,33 TAC строки/eight columns/57 существующих
  PDF ссылок. Статическая проверка, browser execution не выполнялся.

Сохранённые diagnostics:

1. probe_v01 не разобрал список доз: общий app NUMBER запрещает trailing comma.
   Исходные inputs/script/bindings/failure сохранены. Только локальный audit
   parser использует decimal с явными comma/M delimiters; app NUMBER прежний.
2. tests_v01:1 failed/30 passed. Ожидание main_text для вырезанного Methods
   опровергнуто фактическим formula_block. Classifier не подстраивался.
   Assessment note фиксирует это; tests_v02:33 passed с двумя дополнительными
   coherent positive controls. controls_v01 и прежний failed JUnit сохранены.
3. review_v01 сохранён. В review_v02 только fresh-page matcher ограничен
   declared page_start/page_end anchor вместо всех трёх доступных страниц.
   Candidate, controls/outcomes, raw bindings и53/51 counts неизменны.
4. После tests_v02 исправлен только порядок imports в test module. Финальный
   tests_v03 повторно выполнил все33 проверки:33 passed. review_final_v01
   привязан к этим текущим test inputs и проверяет их hashes; прежние отчёты
   сохранены. Ruff_v03 проверил все пять окончательных файлов.

Limitations:

Одна раскрытая работа; candidate зависит от объявленного сопоставления
упорядоченных списков. Не general identity resolver, не научная приёмка и
не доказательство одинаковых образцов для любых последующих экспериментов.
Неизвестные условия, исходные units и статусы сохраняются.

Runtime source_role_assembly_v0.1 остаётся unresolved на реальном трёх-parent
входе: assembly_source_scope_unresolved. Диагностический mixed-type input
не является разрешением production-сборки и не обходит literal-marker policy.
Новых полных production answers и live результатов нет. Старый full suite,
browser/concurrency/cache-ORM/deployment и независимая оценка не выполнялись.
Все live scopes закрыты; общий пункт4 и прежний75% не закрываются.

Verdict:

В исходнике есть проверяемый кандидат связи Abstract → Methods definition →
код электролита → Conclusion CE при явно объявленном list-pairing правиле.
Причина caption barrier также установлена. Это достаточная основа для отдельного
versioned проекта расширения runtime contract, но не автоматическое разрешение.
Следующий патч должен сохранять registered source_type/filters, проверять
внутренний Methods span и весь witness graph, передавая модели нужные exact
definition quotes. Молчаливое переименование чанка или связь по1.35 M недостаточны.

- [HTML-обзор и страницы](../output/methods_identity_bridge_20261109/review_final_v01/review.html)
- [Полная цепочка и controls](../output/methods_identity_bridge_20261109/review_final_v01/report.json)
- [HTML QA](../output/methods_identity_bridge_20261109/review_final_v01/qa.json)
- [Протокол и assessment notes](records/methods_identity_bridge_protocol_2026-11-09_v0.1.md)
- [Предыдущая runtime-сборка](source_role_assembly_2026-11-09.md)
