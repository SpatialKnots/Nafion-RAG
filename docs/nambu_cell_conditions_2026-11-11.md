# ARIADNE: условия растворов Nambu09

Changed:

Пользователь «далее давай» продолжил предложенный Nambu09. В прежнем выбранном
E4 уже находились оба эксперимента. Новый cell_solution_conditions.py и ветка
quantitative_facts связывают четыре эквимолярные бинарные смеси с концентрациями
LiPF6: EC–FETFEE, EC–EFEE, EC–DEE — 1 mol dm−3; EC–ETFEE — 0.5 mol dm−3.
Циклирование Li/LiCoO2 относится к25°C, рис.3(b). Отдельная запись проводимости
сохраняет1 mol dm−3 LiPF6 в FETFEE/EFEE/ETFEE, концентрацию при25°C и диапазон
268.15–333.15K (−5–60°C), рис.3(a). K/°C не пересчитываются; эквимолярность
не переименовывается в объёмную долю. Все значения/коды получены из raw.

Распознаётся только точный методологический хвост вопроса «и почему важно не
смешивать эти условия?». Он разрешает оговорку о разных условиях и запрете
переноса одной концентрации на все смеси. Иные причинные вопросы, неизвестные
условия и отрицания не отбрасываются. Отдельные причинные вклады концентрации
и растворителя этим контрактом не устанавливаются. Фактический вопрос модели
не переписывается. Полный F1 либо отказ; сервер формирует русский текст.

Полные оригинальные PDF2/3 свежо отрендерены Poppler и визуально просмотрены.
В новом отдельном SHA-pinned glyph catalogue шесть наблюдений одного точного
raw-parent: пять U+00B9→minus (экспоненты концентраций/нижняя температура) и
один U+00AB→вертикальный разделитель ячейки. Связаны article/chunk/page/type,
полный raw SHA, PDF offset/font/bbox/font-program SHA и оригинальный PDF SHA.
Это визуальная интерпретация агента, не автоматическое значение имени шрифта
и не независимое принятие. Прежние glyph catalogues не менялись. Добавлена
одна package-data строка для нового ресурса; wheel не собирался.

В PDF text order подпись рисунка расположена после библиографии. Для неё
применена полная caption grammar (a)/(b), локальная проверка статуса и
согласование с body по соли/номеру рисунка/концентрации/трём растворителям.
Body по-прежнему не принимается после References. Неполные/дублированные
caption/body, неверные ячейки/соли/единицы/смеси/диапазоны и одинаковые
концентрации двух групп отказывают; межфрагментная сборка не допускается.
Все пять facts имеют точные raw anchors, ownership false, arithmetic null.

Tests run:

- Focused41passed; итоговый affected743passed (41 новый). Один существующий
  Starlette/httpx warning. Синтетический транспорт, network denials0.
- Полный mypy app217 файлов passed; финальный Ruff7 Python-файлов passed.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- All30 actual-service comparison_v01:20→21 ready-unsent, новый Nambu09.
  Все30 retrieval traces прежние; остальные29 полных результатов и20 прежних
  подготовленных native exact. Реальных ответов модели нет.
- 81 historical actual-service сценарий сохраняет full results, пять native
  inputs exact. Открытые development данные, не независимая оценка.
- Свежая actual API preparation с настоящим поиском/registry: read-only/
  rollback, trace/native exact, registry diagnostics0, network denials0;
  9120bytes, SHA7f4505bf6dc431b3468e5a2479374d8a094a2938c90ac3de5b6ee8527b2db551.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter независимо проверил57 raw-anchor observations, пять facts,
  все шесть glyph positions/font programs/bboxes, полные PDF pages против
  исходного raw, оригинальный PDF SHA и оба существующих UI adapters.
  HTML содержит30 сравнительных строк и пять подробных записей.

Первый comparison preflight остановился до создания comparison outputs:
pyproject hash изменился после добавления ресурса. Второй preflight выявил
нормализацию смешанных окончаний строк при text write. Точные первоначальные
байты восстановлены с проверкой прежнего SHA68da74e2… и сохранены отдельно;
окончания строк возвращены, добавлена только одна строка. Старые manifests
не изменялись. Диагностика обеих остановок сохранена. Начальные Ruff formatting
диагностики исправлены; не выдаются за научные ошибки или ответы модели.

Limitations:

Конечная grammar и source-specific glyph repair на открытых development
источниках. Новые статьи/реальное поведение модели/независимая scientific
accuracy/browser layout/полный repository suite/wheel/deployment не проверены.
Retrieval/ranking/вопросы/prompt/thresholds/UI/DB/PDF/index/schema не менялись.
Guard остаётся not_evaluated. Старые live scopes закрыты; новых нет.

Verdict:

Nambu09 подготовлен без переноса концентраций между смесями и экспериментами.
21/30 ready-unsent, девять отказов:2context (Peng02/Peng10),5explanation,
2limits. Следующий source-bound этап — Peng02: сначала проверить содержание
вопроса и источники, не переносить методологическое исключение на причинный
ответ. Независимая оценка открыта; план75% прежний.

Отчёт: output/nambu_cell_conditions_20261111/review_v01/review.html.
