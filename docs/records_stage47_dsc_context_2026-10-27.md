# Records stage47: отдельный DSC-пакет Istomina

27 октября 2026 года, Asia/Yekaterinburg. `istomina_dsc_context_v0.1`.
[Протокол](records/dsc_context_protocol_v0.1.md),
[предыдущий stage46](records_stage46_evidence_gaps_2026-10-27.md).

Changed:

- Реализован **пункт 1** согласованного плана до API: отдельный source-bound
  контекст для неизменённого вопроса `For Istomina 2021, what conditions and
  temperature programme were used for DSC measurements?`.
- В wire включены пять цитат: B1–B4 — title, полный byline, publication quote и
  DOI context физической страницы 1; M1 — полный раздел `2.4. Thermal Analysis`
  физической страницы 4, до заголовка 2.5, который исключён. Соседние WAXD/AC
  разделы не включены как методика DSC. Каждый контекст имеет отдельную роль.
- M1 содержит **644 Unicode characters**, absolute page span **[502, 1146)**,
  SHA256 `7e0a47e0b98b448393e26956f9477db2b6edfa2f6ce14c34efe3eb647e0d38d5`.
  Полный методический текст, включая условия и последовательность программы,
  сохранён дословно: знаки, units, ligatures и переносы строк не нормализованы.
  Численные величины не интерпретировались и не преобразовывались.
- Фактический `wire.json` занимает **4346 UTF-8 bytes**, с учётом indent/newline.
  Исторический ceiling 100000 bytes не менялся. Сработали существующие literal/
  decoded full-page и interval-union guards; complete source pages в wire — 0.
  Это инварианты сборки источников, не новая оценка допуска к API.
- Отдельный `sources.json` содержит пять валидных SourceRegion с точными quotes,
  offsets, article/PDF/page/layer IDs и полным локальным page text. Локальные PDF
  paths и полные страницы не включены в wire. Геометрия пересекающихся исходных
  блоков доступна в report/HTML. Capture IDs остаются локальными, не записями БД.

## Источник и воспроизводимость

Использован только отдельно зарегистрированный Istomina PDF из stage46:
`data/pdf/7519b88c1b0a0bf3_Istomina_2021.pdf`.
Original PDF SHA256:
`7519b88c1b0a0bf36855c1f881a19965191b72521823bdbafd9736c0c9a32e9f`.
Stage46 first-page identity anchors проверены заново, обе страницы повторно
извлечены неизменённым ingestion extractor и точно совпали с frozen source.
Номера страниц физические; выбор заголовков задан для этого exposed development
источника и не является универсальным извлекателем разделов.

Prepare заморозил source declaration, expected full-methods hash, текущие code/
protocol и installed direct-dependency snapshot до сборки wire. Run/export
проверяют родителя, исходный PDF и точную реконструкцию. Missing/ambiguous/reordered
headings, неполные цитаты, code/source/PDF/runtime drift и перезапись output явно
останавливают выполнение; context clipping и скрытый repair не применяются.
Installed snapshot не является portable/transitive lockfile.

Все **1346 parent bindings** сохранены; новый run проверяет **1359 bindings**.
Stage46, четыре прежних вопроса/пакета, metadata, старые отказы, thresholds,
original PDF, extraction/OCR/retrieval/runtime не изменены. Старые DSC blockers
показаны отдельно как история. В новом пакете `network_ready=false`, admission
`not_evaluated_in_source_packet_stage`; снятия запрета API и повышения допуска нет.
Sample identity, per-result applicability и scientific acceptance остаются unknown.

## Tests run

- Новый test file: **19 passed**, затем affected suite по DSC context, прежним
  full-page guards и evidence gaps: **59 passed**;
  `output/commit_check_20261026/dsc_context_v02.xml`. Прогоны пересекаются и не
  складываются в unique count. Ошибок в этих прогонах не было.
- Проверены полная section boundary, отсутствие соседних методик, question/
  article/page/layer/PDF/quote drift, missing/repeated/reordered headings и identity
  anchors, усечение полного раздела, full-page union, byte ceiling, изменённый
  исходный PDF/wire, exclusive outputs, deterministic export и HTML escaping.
- Ruff `app tests scripts`: passed. Mypy `app`: **172 source files**, no issues.
- Postflight: все пять exact regions и полный M1 span/hash совпали; original PDF
  hash и parent bindings неизменны. Два экспорта: **7/7 файлов byte-identical**.
- CLI prepare/run/два exports: четыре network-evidence файла, completed=true,
  запрещённых CPython connect/DNS/sendto attempts нет. Postflight также запрещает
  эти операции и не зарегистрировал attempts. Это не OS/native-network firewall.
- Физические PDF страницы 1 и 4 заново отрендерены и целиком просмотрены.
- Chrome 156 offline: пять context rows, полный раскрываемый M1, сохранённые raw
  source values/signs, search/reset, все review links, TAC один документ / восемь
  колонок прошли. Реальный клик открыл исходный PDF на physical page 4. JS errors
  и remote HTTP requests отсутствуют. Снимки methods и metadata просмотрены.

## HTML и повтор

`output/records_stage47_20261027/`:

- `prepared_v01`, `run_v01`, `review_v01`, `review_repeat_v01`.
- `review_v01/review.html` — все пять полных цитат, JSON wire, локальный source
  registry, геометрия, текущие ограничения и исторические отказы.
- `metadata_review.html` — Title, Authors, Journal, Year, Abstract, Conclusions,
  Terms, Original file для единственного документа scope. Identity значения —
  raw source-header proposals; Abstract/Conclusions явно unimplemented в этой
  стадии, Terms не пересчитывались. Полный first-page source раскрывается отдельно
  и не выдаётся за готовую TAC-разметку. Ручной per-Term workflow не вводился.
- Source renders, browser_qa_v01.json, postflight_v01.json, network evidence.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.dsc_context --network-evidence output/stage47_new_network.json export --source output/records_stage47_20261027/run_v01 --output-dir output/stage47_new_review
```

Выбирать новые output/evidence paths. Private PDF и generated artifacts не входят
в Git; локальные paths/installed snapshot не доказывают автономную переносимость.

Limitations: не выполнялись независимая научная оценка, полный application suite,
проверка достаточности/допуска, provider request construction, runtime integration,
API/model/embedding/retrieval/DB calls или новые OCR/metadata lookup. Пакет описывает
методику статьи, не создаёт measurement records и не назначает условия образцам.

Verdict: пункт 1 выполнен без API. Следующий пункт — отдельная проверка допуска
нового пакета; в этой стадии она не реализована и не объявлена пройденной.
