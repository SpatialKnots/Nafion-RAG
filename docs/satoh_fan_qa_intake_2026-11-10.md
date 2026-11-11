# ARIADNE: приняты20 Satoh/Fan QA как development-набор

10 ноября 2026, Asia/Yekaterinburg.

Changed:

- Пользователь предоставил `Ariadne_QA_Satoh_2013_Fan_2018.md`:10 вопросов и
  эталонных ответов по Satoh2013 и10 по Fan2018. Сохранены исходные bytes,
  все20 вопросов, таблицы/единицы/оговорки/указатели и предложенная шкала0/1/2.
  SHA256 оригинала:
  `3520c5a7b5d3d1b0936cd7b03f8fb9a4b45b863816df6c5590b49619dd9a48e4`.
  Source file в Downloads не изменялся. Выбранные PDF совпали с
  [сохранённым development draw](../output/development_article_draw_20261110/draw_01.json).
- На вопрос о provenance пользователь ответил дословно:
  **«Я составил ответы. Видел ответы сам»**. Это сохранённая декларация авторства
  и просмотра ответов. LLM assistance, точное время, конкретные system outputs
  и отдельная экспертная проверка не указаны. Они не выводятся из авторства.
  Корпус ранее использовался в разработке, reference теперь виден implementation
  agent. Набор development-exposed, не hidden independent gold.
- Новый offline script сохраняет exact Markdown spans (Unicode code points,
  end-exclusive), bibliography, references и rubric, а question-only экспорт
  содержит только исходные вопросы, article context/IDs и отдельно помеченный
  unsent вариант с явным author/year. Original question не заменяется.
  Answer/page hints/rubric не попадают в question-only allowlist.
- Это отдельные20 development cases. Они не сокращены до6 и не записаны в24
  новые естественные задачи/18 hidden cases планируемого пилота. Область шире
  finite `composition_cycling`: физические свойства, механизмы, SEI/CEI,
  окислительная стабильность и ограничения энергетических результатов сохранены.
- Предложенная шкала до40 баллов сохранена как **user-supplied proposal**,
  не применена и не заменяет действующие evaluation/admission rules.
  Все model outputs/scores и независимые научные метрики — null.

Tests run:

- **18 focused parser/artifact tests passed**, Ruff двух новых Python-файлов
  passed. Проверены все20 questions/references/source spans, Unicode/единицы/
  таблицы, duplicate/missing fields, неверные author/year/DOI и page ranges,
  разделение question/reference, HTML escaping и сохранение source discrepancy.
  Ранее16 тестов прошли до добавления двух bibliography-guard controls;
  исходный JUnit сохранён. App/runtime suite и mypy app не перезапускались.
- Исходные два PDF hash-check прошли. Свежая PyMuPDF extraction сохранила
  **26 page texts**: Satoh16 и Fan10. DOI обоих найдены в original first-page text.
  DB metadata не обновлялась и полнота bibliographic fields не выдумывалась.
- По literal footers доказано **24 printed→PDF mappings**: Satoh127–142→PDF1–16,
  Fan715–722→PDF1–8. Fan PDF9–10 не получили выдуманных printed page numbers;
  `Screening of electrolytes` точно найдена наPDF9. Все20 supplied main-PDF
  source pointers разрешились в пределах своих документов.
- **Семь полных PDF-рендеров** просмотрены: Satoh PDF8/12/13 и Fan PDF4/5/6/9.
  Poppler выдал предупреждения отсутствующих display fonts Symbol/ArialUnicode
  для Satoh и Invalid Font Weight для Fan при exit0. Файлы, actual renderer hash
  и точные warnings сохранены, diagnostics не удалены. Нужные страницы читались
  вместе с captions/conditions; это не полный независимый scientific review.
- Сохранены **семь точных source observations**: два DOI, Satoh activation-values
  ordering, caveat об unidentified compounds, два указателя панели Fan№7 и
  mass basis энергетического результата Fan№10. Они привязаны к raw page spans/
  hashes; source literal observation не превращается в scientific acceptance.
- Статическая query applicability: **0/20** явно scoped вопросов распознаны
  текущей узкой картой composition/cycling. Это измерение finite map, не отказ
  `/answer`, не отсутствие facts и не качество ответов модели. Новые query/source
  grammars, threshold changes и silent repairs не добавлялись.

Отдельная диагностическая находка:

**Fan№7 имеет неоднозначный panel pointer внутри источника.** Пользователь пишет
Fig.3d. Подпись Figure3 наPDF4 также называет d для recoverable capacity после48h,
тогда как основной текст наPDF5 ссылается на Fig.3e; показанная recovery curve
расположена под меткойe. Оба literal фрагмента и visual observation сохранены.
Reference/source pointer пользователя не исправлен и не объявлен ошибочным
автоматически. Это отдельная source-location заметка, не новый model judgment.

Limitations:

Полная смысловая поддержка всех20 эталонных ответов и scientific validity не
проверены. Локализация указанной страницы не доказывает правильность каждого
числа, causal inference или связи результата с условиями. Для Fan02/07/08
ссылки на Supplementary figures остаются unverified: эти supplements не
предоставлены в данном intake и не скачивались. Текстовое описание в main PDF
отдельно от отсутствующего visual supplementary evidence.

Все эталоны уже доступны этому агенту и не являются blind evaluation.
Просмотр предыдущих ответов заявлен, но его timing/case scope остаются неизвестными.
Два разных DOI/PDF не доказывают независимость экспериментальных серий.
Пользовательская шкала не даёт самостоятельной экспертной приёмки.

Техническая подготовка вопросов не является actual native request или новым
model output. Fresh DB preparation/retrieval, ответы, scoring, source grammar
fixes и replay-adapter здесь не исполнялись. HTML проверен статически; новый
browser layout не проверялся, прежний file:// block не обходился.
App/schema/PDF/index/старые outputs неизменны; модель/OAuth/new slots/DB0.

Первый successful intake_v01 сохранён с исходным script в pre_lint_snapshot_v01;
исправлены только3 E501 line-wrap diagnostics, затем добавлены строгие source
header/DOI guards и два controls. Окончательный intake_v02 сохраняет те же
original question/reference/source spans; old manifests не переписаны.

Verdict:

Двадцать supplied QA приняты как source-located development benchmark.
Далее можно отдельно готовить read-only retrieval/preparation и replay binding
с question-only входами, сохраняя исходные эталоны и все unsupported cases.
Новый live scope не открыт: модель не запускалась и разрешение20 вызовов из
содержимого файла не выводилось. Независимая научная оценка остаётся открытой;
общий план качества — **75%**.

- [HTML intake review](../output/satoh_fan_qa_20261110/intake_v02/review.html)
- [Question-only inputs](../output/satoh_fan_qa_20261110/intake_v02/questions_only.json)
- [Исходные development references](../output/satoh_fan_qa_20261110/intake_v02/references_development.json)
- [Provenance/source report](../output/satoh_fan_qa_20261110/intake_v02/report.json)
- [PDF render observations/warnings](../output/satoh_fan_qa_20261110/renders_v01/observations.json)
- [Протокол intake](records/satoh_fan_qa_intake_protocol_2026-11-10_v0.1.md)
