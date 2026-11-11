# Группы оставшихся отказов и сохранение исходного контекста

Changed:

По просьбе пользователя «Давай сгруппируем отказы и проработаем их» разобраны
все21 оставшихся отказа. Тип вопроса отделён от причины потери источника.
Требования и33 точных опорных фрагмента составлены implementation agent
по исходным вопросам и свежим PDF, без чтения пользовательских эталонов этим
evaluator. Это post-hoc development annotations, не независимый gold и не
доказательство полноты научного ответа.

| Группа | Вопросов | Все отмеченные сведения в runtime-контексте до | После исправления |
|---|---:|---:|---:|
| Числа, порядок, сравнение режимов | 8 | 6 | 7 |
| Определения, методы, составы, характеристика | 6 | 3 | 4 |
| Объяснение наблюдаемого эффекта | 5 | 4 | 5 |
| Достаточность и границы вывода | 2 | 0 | 0 |
| **Всего** | **21** | **13** | **16** |

Первоначально у13 вопросов все отмеченные сведения уже присутствовали; отказ
был лексическим. У восьми context был неполным: три теряли нужный фрагмент
при дедупликации, четыре — за пределами retrieved top5, один имел обе причины.
В33 source observations найдено22 selected,4 removed_by_deduplication,
7 registered_outside_retrieved_top_k. Все опорные фрагменты есть в зарегистрированном
корпусе; это не означает, что сформирован научно корректный ответ на каждый вопрос.

Найден конкретный дефект: приблизительная дедупликация считала raw chunk PDF2–3
дубликатом PDF2 по пересечению слов и удаляла новый текст страницы3. Старый
алгоритм остаётся на прежнем пути, а новый `evidence_preservation.py` восстанавливает
не доказанно избыточные raw chunks **только для уже отказавшей подготовки** с
однозначной явной single-author/year ссылкой и всеми источниками одной статьи.
В `service.py` сохранён original pre-dedup pool и добавлен этот этап перед trace
observer. Другие прежние app-файлы не изменены. Ранее готовые запросы не входят
в новый путь и сохраняют прежние traces/native bytes.

Восстановление использует только уже найденный request-local pool. Порядок старых
сохранённых источников остаётся, дополнительные источники получают новые E-IDs;
raw text/source_type/text_layer/physical pages не меняются. Полное совпадение
текста с нормализацией только whitespace и доказанное покрытие страниц в том же
work/layer/source_type допускают сохранение прежнего удаления. Похожее множество
слов, другое число, отрицание, новый page range или другой слой таким доказательством
не являются. Количество/символьный объём не превышают прежний pre-dedup pool.

Admission не пересчитывается автоматически: в metadata указаны исходные
`baseline_admission_chunk_ids`, `automatic_reassessment=false`, `admission_changed=false`.
Сохраняются все прежние specialized gates. Три полностью восстановленных случая:
Kondo_07, Kondo_08, Nambu_09; Kondo_09 получил страницу3, но всё ещё требует страницу4.
Количество ready-unsent запросов осталось9/30; все21 отказ пока сохраняются.

Проработка групп:

- Для восьми количественных вопросов выделены конкретные source-bound требования:
  объект/ячейка, показатель, значение/исходная единица, режим/цикл и сравнение.
  Нельзя переносить значения half cell в full cell, интервалы в точки или одну
  концентрацию на все сравниваемые смеси. У Peng_06 Table1 не печатает единицу
  в заголовках; Figure3 визуально показывает /ohm на осях. Автоматическое
  приписывание единицы табличным значениям здесь не выполнено.
- Для шести context-вопросов проверены идентичность материалов, метод, опорное
  состояние, электрод/ячейка и явно указанные условия. У Kondo_02 детали CV,
  у Peng_10 SEM/XPS находятся за текущим top5; у Nambu_09 удалённый caption
  restored. Registered method/figure_caption/table_caption не переклассифицировались.
- Для пяти explanation-вопросов отделены наблюдение, объяснение, направление
  связи и can/may/suggest. После recovery все их отмеченные source spans есть,
  но causal role/epistemic validation не заменяются проверкой наличия существительных.
- Для двух limit-вопросов нужны контрпример, область применимости, отрицание
  достаточности и caveats. Неизвестность и отсутствие поддержки не превращаются
  в доказательство универсальности или отсутствия эффекта.

Для пяти оставшихся runtime gaps (Kondo_02/09/10, Peng_07/10) подобраны конкретные
same-work/original-layer chunks, покрывающие missing annotated spans. Выполнено
по одному добавлению в **отдельные diagnostic offline packets**, а не в обычный
поиск/API: extra source≤1, extra chars≤14000, total chars≤60000. Все21 пакета
теперь содержат все33 отмеченных source spans. Selection направлялась post-hoc
аннотациями;21/21 не новая retrieval accuracy и не scientific sufficiency.
Это подготовленные материалы для следующего semantic/field admission шага,
без разрешения генерации и без automatic continuation.

Tests run:

- **341 passed**, включая17 новых controls: потеря новой страницы, числа/negation,
  точное и whitespace containment, page/source_type/layer provenance, foreign work,
  unknown layer, неправильная reference и сломанная raw/display пара. Actual service
  controls подтверждают восстановление при отказе/provider0 и прежний ready путь.
  Первые17 также прошли отдельно. Ruff9 Python files passed; full app mypy210
  Python files passed. Полный repository suite не запускался.
-30 actual old/new frozen-source service comparisons реконструировали старый
  baseline целиком; все девять ready traces/native inputs точны. Все additions
  равны зарегистрированным raw chunks; retrieval objects не изменены.
  Все81 старых service-channel результата и пять native inputs сохранены.
- Capture:3 articles/18 registered pages/28 chunks; REPEATABLE READ READ ONLY,
  rollback. Hash каждого original PDF проверен. Все18 registered page texts
  совпали со свежим PyMuPDF extraction.14 релевантных страниц отрендерены Poppler
  и просмотрены полностью, включая таблицу и подписи. Browser layout не проверялся.
- Два fresh real experimental API read-only/rollback checks (Kondo_08, Nambu_09)
  вернули HTTP200/insufficient_evidence с точным predicted trace/body и восстановленной
  страницей3. Provider не вызывался. Реальные model POST/OAuth/new slots0;
  external-network denials0. Offline packet completion не делал DB/retrieval calls.

Диагностика: первый anchor reader остановился на line-break hyphen в Kondo_02.
Отдельный сохранённый anchor_probe_v01 нашёл три неуникальных/неподходящих
локатора; заменены только границы цитат, все33 final spans проверены. Старые
аннотации/probe сохранены. Один E501 в уже frozen capture script исправлен только
переносом строки; AST before/after идентичен, original executed script сохранён
как capture_script_v01.py и явно сопоставлен в verifier. Исходный review_v01/
reviewer_v01.py сохранён до offline packets; review_v02 включает их. Отдельный
review_v03 исправляет E501 только в форматировании exporter, HTML/report данные
сверяются побайтно с review_v02; исходный reviewer_v02.py сохранён.
FastAPI/Starlette TestClient deprecation warning сохранён; dependency не менялась.

Limitations:

Проработаны источники и требования всех четырёх групп, реализовано безопасное
сохранение потерянного уже найденного контекста. Общий numeric/causal/status
admission и автоматический добор outside-top5 здесь не реализованы. Не введён
широкий перевод или новый lexical threshold. Все21 отказы остаются; новые
LLM answers/scientific accuracy/стоимость и token usage не измерялись. Corpus
и вопросы уже development-exposed. Наличие source spans и assistant context
review не независимая scientific acceptance. Deployment/server reload не проверялись.

Verdict:

Есть проверенная21-row карта причин и воспроизводимое исправление реальной
потери информации:13→16 runtime source-complete по отмеченным требованиям.
Пять диагностических добавлений подготовили недостающие source packets;
production readiness остаётся9/30. Следующий общий шаг — проверка source-bound
полей/ролей/условий и модальности, начиная с восьми quantitative вопросов.
Новых live calls автоматически нет. План качества остаётся75%, не accuracy.

[Все21 вопроса, группы, источники и действия](../output/refusal_groups_20261110/review_v03/review.html) ·
[Полный отчёт](../output/refusal_groups_20261110/review_v03/report.json) ·
[21 диагностический пакет](../output/refusal_groups_20261110/diagnostic_packets_v01/summary.json) ·
[Численные результаты сравнения](../output/refusal_groups_20261110/comparison_v01/result.json)
