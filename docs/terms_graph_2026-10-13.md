# Terms Atlas: интерактивный граф источников, 13 октября 2026

Пользователь запросил граф множеств Terms с выбором группы/термина,
прослеживанием источника и размером кругов по размеру подмножества.
Реализован дополнительный read-only exporter `tac_terms_graph_v0.1`.
Это визуализация frozen stage09/10, не завершение научной классификации этапа 3.

## Результат и область данных

Итоговый файл:
`output/terms_graph_20261013/ARIADNE_Terms_Atlas_final_v03_2026-10-13.html`.
Один автономный HTML содержит данные, CSS и JavaScript; сетевых библиотек нет.
Пути к исходным PDF абсолютные: при переносе корпуса экспорт нужно повторить.

Scope: все 33 документа development snapshot, 2 266 article-local candidates,
4 195 mentions/uses и 98 frozen TAC page contexts. Одинаковые labels в разных
статьях не объединяются и не объявляются одним научным понятием.

Первый экран показывает множества статей. Выбор статьи открывает её T/A/C
подмножества. Клик на круг или кнопку раздела фильтрует список Terms; клик на
term показывает все его T/A/C memberships, точные вхождения, полные отдельные
контексты, оригинальный PDF на нужной странице и PDF выбранного OCR-слоя,
если он отличается. Источники включают IDs, hashes, offsets, method и boundary
status. Переносы строк сохранены; подсветка учитывает Unicode code points.
Лексические вложения доступны как навигация между кандидатами с явной оговоркой
об отсутствии утверждения научной связи.

Подмножества допускают пересечения. Размер группы — число DISTINCT локальных
term IDs, не число упоминаний. Площадь каждого круга пропорциональна этому числу
в пределах текущего вида (`radius = scale * sqrt(count)`). Масштаб между обзором
статей и отдельной статьёй меняется для вписывания; сравнивать площади разных
экранов нельзя. Поиск уменьшает только список, не меняет состав/площадь групп.
Нулевой count имеет нулевую площадь; группа остаётся доступной кнопкой.
Отсутствие сохранённого контекста помечается явно, status не придумывается.
Центральный узел term/TAC служит навигации и не кодирует размер множества.

Координаты кругов — детерминированное размещение для читаемости, без semantic
distance или scientific similarity. Есть масштабирование, перемещение,
вписывание, клавиатурный выбор и адаптация к узкому экрану.

Ссылка «Таблица TAC» ведёт к отдельному полному review stage10 со всеми
33 документами и согласованными восемью колонками. Эта таблица и прошлые
артефакты не переписаны; graph не заменяет TAC review.

## Входы и воспроизводимость

| Input | SHA256 |
| --- | --- |
| `20261012_v01/corpus.json` | `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a` |
| `20261013_stage08/profiles_final_v02.json` | `1523a30e45197d664a906c450eacac01b6e8c94b581f05082d430800951e0885` |
| `20261013_stage09/terms_final.json` | `a7d3504a7741a0dffce02d58ff469c596193f4d3ea6611421012dcc7bafeddee` |
| `20261013_stage10/contexts_final.json` | `98bbc65104c25e00859739d2ef9c05d6481a8c595c7ce803ee15b3a48d1ea517` |

Exporter сначала валидирует profiles/inventory/contexts против frozen sources,
проверяет input hashes и physical hashes оригинальных/выбранных PDF. Затем
строит только структурное отображение. Отказ при повреждении входов или
существующем output явный. JSON в HTML защищён от script terminators;
динамический текст вставляется через DOM textContent. UI не записывает
исправлений/решений в исходные данные, файлы PDF или БД.

Команда из корня репозитория (PowerShell; output должен быть новым):

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_graph `
  --snapshot data/experiments/tac/20261012_v01/corpus.json `
  --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json `
  --inventory data/experiments/tac/20261013_stage09/terms_final.json `
  --contexts data/experiments/tac/20261013_stage10/contexts_final.json `
  --source-root . `
  --review output/tac_stage10_20261013/ARIADNE_TAC_stage10_contexts_final_2026-10-13.html `
  --output output/terms_graph_20261013/reproduced_atlas.html
```

Input/asset hashes, timestamp, версия и pending human confirmation встроены в
раздел «Снимок и версия». Timestamp делает HTML bytes нового экспорта отличными;
source membership, labels, quotes и круговые counts детерминированы.

До правок сохранён baseline `output/baselines/20261013_before_terms_graph`:
315 файлов, fingerprint
`dd5682afeea0df1ba8c6c5240ccdf320962faa6436fe244b094d84532497ea15`.
Итоговые manifests находятся в `data/experiments/tac/20261013_terms_graph`.
Assets HTML/CSS/JS не входят в прежние extension rules freeze_baseline;
они отдельно включены в `source_graph.zip` и artifact inventory.
Прежние незакоммиченные изменения сохранены.

## Проверки

6 новых pytest cases проверяют distinct counts при повторных occurrences,
пересечение T/A/C, нулевую группу, сохранение раздельных IDs дубликатов,
точные source fields, безопасную сериализацию HTML и границы PDF-путей.
Целевой запуск с context tests: **27 passed**.
Полный regression: **919 passed, 1 warning**, 8.34 s; warning относится к
существующему Starlette/httpx deprecation. Ruff для `app`, exporter и новых
tests: **All checks passed**. Mypy в этом изменении не запускался: `app` не менялся.

Начальные pytest запуски не прошли setup из-за прав стандартного temp/cache.
После переноса test temp/cache в отдельные каталоги проекта выполнены проверки
выше. Ошибка synthetic fixture с отсутствующим optional `section_status`
исправлена явным null projection; отсутствие status не представляется как pass.

Headless Edge audit использует реальный frozen корпус и проверяет:

- 33 article circles, отсутствие перекрытий кругов обзора;
- точный состав всех 99 T/A/C-групп, включая пустые;
- все 2 266 выбора Terms, 4 195 exact mention quotes и 2 926 полных context cards;
- степень membership edges каждого term и постоянство `radius²/count`;
- реальные клики по кругам/группам, поиск, zoom/fit, lexical navigation, клавиатуру;
- 70 различных local links с существующими targets;
- ширину 390 px без горизонтального overflow; screenshots осмотрены;
- отсутствие page errors и external requests.

Browser recipe:
`data/experiments/tac/20261013_terms_graph/recipes/verify_graph.cjs`.
Результаты и screenshots: `output/terms_graph_20261013`.
Это engineering/source-integrity audit, не независимая scientific acceptance.

## Changed / Tests run / Limitations / Verdict

Changed: добавлены exporter, автономные UI assets, 6 unit tests и документация.
Frozen inputs, existing production app, extraction/ranking/retrieval/DB schemas
не изменены. Исходные PDF проверены read-only; их содержимое не переписано.

Tests run: 27 targeted и 919 full pytest passed; Ruff passed; browser audit всего
scope, точных источников, групп, площадей и интерактивности прошёл.

Limitations: группы отражают статью и TAC-раздел, научные категории/roles ещё
не назначены. Источники относятся к frozen snapshot; живая БД не запрашивается.
Выбор одного активного term, review persistence отсутствует. Качество исходных
кандидатов, границ и PDF-глифов не исправляется визуализацией.

Verdict: source-traceable граф доступен для просмотра и пользовательского review.
Этап 3 классификации остаётся открытым; конкурентное преимущество не измерено.
