# ARIADNE: SEM/XPS поверхности LCO в Peng10

Changed:

Пользователь «Давай дальше работать» продолжил предложенный Peng10. До app
edits свежий actual DB read-only/RR/rollback capture полного пула разрешённых
статей воспроизвёл все30 прежних top5 и role metadata. Нужный полный raw
PDF6/7 parent отсутствовал в прежнем top5. Узкая cycled_cathode_surface роль
сохраняет неизменённый объект существующего пула статьи с нужным электродом,
SEM microcracks и XPS cathode paragraph. Top5/filters/scores/число lookup/
вопрос прежние; ownership не устанавливается одним retention.

Новый cathode_surface.py +quantitative_facts/source_reference ветки. Конечная
grammar связывает frame cycled full cell, SEM по LCO, XPS по LCO и подпись
XPS рисунка. Все повторные владельцы электрода, обозначения четырёх составов,
SEM figure references и XPS figure/caption должны согласоваться. Шесть facts:
fresh surface, SEM trend, C1s assignment, O1s group comparison, F1s comparison,
CEI author interpretation. Один complete parent/F1 либо отказ, русский текст
строит сервер; поля/anchors/status/текст пересчитываются из точного raw.

Сохраняется исходная сила наблюдений: микротрещины FFT «почти исчезают», не
«полностью отсутствуют». C–O/C=O связываются авторами с органическими/
неорганическими продуктами разложения. Усиление O1s Li2CO3 относится в
предложении к группе двух FEC-содержащих электролитов. Отдельное членство FFT
не выводится из имени состава и не собирается из внешнего preparation chunk;
oxygen fact не содержит label/caption_label, unknown named formulations
явен. F1s снижение LixPOyFz у FET/FFT относительно EE явно принадлежит LCO.
Источник трактует его через suggesting; общий вывод об изменении CEI сохраняет
suggest. LiF/SEI/total F из соседнего MCMB paragraph не переносятся на LCO.
Количественные доли/толщина отсутствуют в этих абзацах, не придумываются.
100cycles/4.45V из других страниц не приписаны отдельным SEM/XPS observations.
Ownership false, arithmetic null, guard not_evaluated.

Свежо отрендерены и визуально просмотрены полные Poppler PDF5/6/7: исходный
SEM Fig6, XPS Fig7 и текст наблюдений. Это не независимое переизмерение
микрофотографий/спектров или подтверждение назначения пиков. Новый отдельный
reviewed_surface_glyph_aliases_v02.json:6 наблюдений одного точного raw-parent —
ft, три fi, fl и C]O→C=O. Связаны article/chunk/page/type/full raw SHA,
PDF offset/font/bbox/font-program SHA и оригинальный PDF SHA. Визуальная
интерпретация агента, не автоматическая семантика имени шрифта. Старые
catalogues/raw/PDF прежние; package-data добавляет ровно одну строку v02.

Tests run:

- Focused66passed с первой попытки; affected888passed (66 новых), один прежний
  Starlette/httpx warning, network denials0. ASGI synthetic tests вне sandbox.
- Полный mypy app219 файлов passed; финальный Ruff9 Python-файлов passed.
- Adverse controls: неправильные владельцы LCO/MCMB, label/figure/caption,
  partial/almost→complete, lower→higher, suggest→prove, FEC group/origin,
  некорректный carbonyl, prior/hypothetical/negative/bibliographic scope,
  неизвестные числовые/causal запросы, record/raw tampering, cross-chunk
  assembly и лишние MCMB LiF/total-F данные. Generic source codes не зашиты.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- All30 actual-service comparison_v01:22→23 ready-unsent, только Peng10;
  остальные29 полных retrieval/service outcomes и22 прежних native exact.
  Это не23 научно верных ответа модели.
- Ranking-only и contract-only сохраняют отказ; вместе ready-unsent.
  Все пять выбранных строк — исходные неизменённые объекты full article pool.
- 81 historical actual-service сценарий сохраняет full results, пять native
  inputs exact. Открытые development данные, не независимая оценка.
- Свежая actual API preparation с настоящим поиском/registry: read-only/
  rollback, trace/native exact, registry diagnostics0, network denials0;
  14578bytes, SHA0c74b96d07fd3281921e297c045c8a60f6bd47256ce4376fabefedad40caf764.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter проверил66 raw-anchor observations,6facts/6glyph positions/
  fonts/bboxes/font programs, полные source PDF pages против raw, неизменный
  PDF SHA, source objects/top5/ablations и оба существующих UI adapters.
  HTML содержит30 сравнительных строк и шесть подробных записей.

Сохранённые диагностики до тестов: первый glyph catalogue пропустил U+E09D
из-за ошибочного U+E0DD в mapping. Пять ops/v01, старый generator и hash mapping
сохранены; неиспользованный ресурс перемещён из app/resources в
unused_catalogue_v01. Финальный v02 содержит6ops; исходные manifests не
переписывались. Первый source-binding probe отказал: line wrap после slash
в extraction/insertion и generic negative-token veto на точном O1s comparator
«than those without it». Source snapshots/diagnosis сохранены. Разрешены только
slash whitespace и уже распознанный точный comparator; source/question/raw
не меняются, другие status guards прежние. Начальные Ruff E501 исправлены до
выполнения driver. Провалов тестов в этой итерации не было.

Limitations:

Конечная source grammar/source-specific glyph repair по открытым development
источникам. Не общий semantic/causal validator; O1s group не получает
недоказанного индивидуального назначения. Новые статьи/реальные F-ID ответы/
независимая scientific accuracy/browser layout/полный repository suite/wheel/
deployment не проверены. Вопросы/prompt/thresholds/UI/DB/PDF/index/API schema
прежние; ranking изменён только указанной узкой ролью. Live scopes закрыты.

Verdict:

Peng10 подготовлен с разделением морфологии, XPS assignments и авторской
CEI interpretation.23/30 ready-unsent; семь отказов:5explanation,2limits.
Следующий отдельный этап — Kondo03: проверить source-bound направления
изменений и статус объяснения ионного спаривания, без автоматического causal
допуска. Независимая оценка открыта; план75% прежний.

Отчёт: output/peng_surface_20261111/review_v01/review.html.
