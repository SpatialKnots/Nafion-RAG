# TAC: локальные Authors / Journal / Year

Дата: 12 октября 2026 года. Metadata version: `tac_file_metadata_v0.1`.

## Changed

Реализован отдельный модуль `scripts/tac_metadata.py`, заполняющий метаданные из выбранного текстового слоя первых двух страниц PDF и его вёрстки. Результат сохраняется в проверяемый sidecar JSON, без обновления production Article в PostgreSQL. Это расширение TAC review, не внешняя metadata lookup integration.

- **Authors:** авторские строки после названия или перед affiliation boundary; соседние строки и блоки объединяются. Малые надстрочные обозначения организаций удаляются из отображаемых имён, но остаются в точной исходной цитате. Small capitals, короткие фамилии He/Lee/Ma/Ue, инициалы, дефисы и перенос внутри полного имени сохраняются. Chemical labels в другой колонке и publisher UI не принимаются за byline. Если на странице нет прежнего TAC title, возможен отдельный metadata-only layout anchor; исходный TAC профиль не изменяется.
- **Journal:** printed bibliographic headers/footers, front-matter citation и явно подписанные publisher metadata. Возвращается печатная форма, включая сокращения или слитное извлечение текста; каталог canonical journal aliases отсутствует. Placeholder `J. Name` и publisher/copyright текст отвергаются.
- **Year:** год printed issue/citation имеет приоритет над явной online publication date. Submission/acceptance, download, PDF creation/modification и filename dates не используются. При конфликте одного уровня значение остаётся ambiguous, а кандидаты сохраняются. Для диссертации год берётся из строки «город — год».
- **Тип документа:** у диссертации и явно подписанного ECS Meeting conference abstract Journal помечается `not_applicable`. Это не общий классификатор корпуса.

Поле имеет `value`, `status`, `selected`, `candidates`, `diagnostics`. Ненулевое значение связано с exact-source evidence: PDF checksum/article ID, page, selected layer/layer ID, Unicode offsets, точная цитата и SHA-256 текста страницы. Metadata validator проверяет inventory, типы значений, selection membership и source identity. Эвристическая интерпретация остаётся предложением алгоритма (`needs_metadata_review`), не human-accepted bibliographic gold.

HTML exporter расширен: в Authors показываются первые два имени и число авторов; раскрытие содержит полный список. В Journal/Year раскрытие показывает цитаты, источник и диагностику. Добавлены metadata version/hash и проверка связи metadata JSON с TAC profiles. Прежний формат таблицы и восемь основных колонок сохранены. Старый exporter input с database metadata также поддерживается.

Новая таблица:

`output/tac_metadata_20261012/ARIADNE_TAC_metadata_2026-10-12.html`

## Результат на неизменных 33 документах

| Поле | Заполнено | Не распознано | Не применимо |
|---|---:|---:|---:|
| Authors | 32 | 1 | 0 |
| Journal | 29 | 2 | 2 |
| Year | 30 | 3 | 0 |

Всего **91 ненулевое значение**. Это число предложений, не измеренная точность.

Оставшиеся случаи:

- **Besenhard 2002:** author byline не распознан. Текстовый слой содержит `J¸rgen`, тогда как визуальный PDF показывает корректное имя. Автоматическая подмена повреждённого символа не выполнялась; ручной транскрипции в алгоритмический результат нет.
- **Sasaki 2009 (метка источника):** Authors распознан; документ подписан как ECS Meeting abstract, Journal не применимо. Поддерживаемый publication year на просмотренных страницах не распознан; год из метки/creationDate не использован.
- **Guo 2020 (метка источника):** Authors распознан; Journal/Year не распознаны в рассмотренной области manuscript PDF.
- **Sanginov supplement:** Authors распознан полностью; Journal/Year не перенесены из предполагаемой основной статьи. Подтверждённый work/supplement link этим этапом не реализован.
- **Диссертация:** Authors/Year распознаны, Journal не применимо.

Примеры приоритета источников: Kondo — **2026**, Lin с меткой 2023 — **2024**, Dai — **2017**, Sasaki с меткой 2007 — **2008**. Doi accepted manuscript использует напечатанную citation date **2018**, а не template footer 2013 или miniature journal cover 2017. Разные типы дат не смешиваются автоматически.

Moore сохраняет source suffix `111` с диагностикой возможного повреждения текста; он не исправляется автоматически на визуальный `III`. Остальные metadata proposals также требуют пользовательского review.

## Inputs и воспроизводимость

- Корпус: `data/experiments/tac/20261012_v01/corpus.json`.
- Snapshot SHA-256: `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Неизменный TAC: `data/experiments/tac/20261012_stage02/profiles_final_v02.json` (`tac_section_proposals_v0.3`).
- Финальные метаданные: `data/experiments/tac/20261012_metadata/metadata_final.json`; raw input/code hashes включены в JSON и HTML.
- До изменений: `output/baselines/20261012_before_tac_metadata/`, 286 файлов, fingerprint `95f0ae1846113ffd0ef0d1aa52b5de9601151bece5cf9309fe2f7c9b5bdaacfb`.
- После изменений: `output/baselines/20261012_after_tac_metadata/`; итоговые hashes и inventory находятся в manifest.
- Source recipes и inventory: `data/experiments/tac/20261012_metadata/recipes/`, `artifact_inventory.json`.

Запуск из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_metadata --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage02/profiles_final_v02.json --output data/experiments/tac/20261012_metadata/metadata_final.json
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage02/profiles_final_v02.json --metadata data/experiments/tac/20261012_metadata/metadata_final.json --output output/tac_metadata_20261012/ARIADNE_TAC_metadata_2026-10-12.html --source-root .
```

При повторе используйте новые output paths: перезапись артефактов запрещена. Промежуточные версии v01–v06 сохранены отдельно; отчёт относится только к `metadata_final.json`. Первоначальный failed synthetic thesis fixture не имел layout_warnings; исправлена fixture, а не обработка ошибок в production code.

## Tests run

- Целевые metadata/HTML tests: **30 passed in 1.33 s** (25 новых metadata tests и пять существующих HTML tests). Проверены короткие имена, инициалы, small capitals/superscripts, fragmented author names, отказ от figure labels/template/reference dates, конфликт дат, точные Unicode offsets, schema/source tampering и HTML escaping.
- Полный pytest: **782 passed, 1 warning in 9.60 s**. Лог `data/experiments/tac/20261012_metadata/pytest_full.log`; запуск вне sandbox с `--basetemp D:/Nafion-RAG/tmp/tac_metadata_full` из-за прежнего зависания полного набора в sandbox. Warning — существующий StarletteDeprecationWarning.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Browser QA в headless Edge: 33 строки / 8 колонок / 33 original PDF links, точное совпадение всех 91 metadata values с JSON, поиск по авторам, раскрытие полного списка и TAC texts, отсутствие page errors. Abstract/Conclusions полностью совпали с прежними профилями. Скриншоты `preview.png`, `preview_authors.png` визуально просмотрены. Evidence: `output/tac_metadata_20261012/browser_verification.json`.
- Source integrity: **33 PDF hashes** совпали со snapshot; **88 app files и прежний TAC detector** совпали с baseline до metadata. Evidence: `source_integrity.json`. Production database migrations, retrieval scoring, OCR/chunking и glossary не менялись.
- Read-only visual QA: шесть полных оригинальных страниц для Besenhard, Doi (две), Cho, Sasaki и Mohammadi. Проверены printing dates, manuscript boilerplate и сложные bylines. Это выборочная проверка разработки, не independent accuracy audit. PNG, stderr и source hashes находятся в `visual_audit/`.

Retrieval comparison не повторялся: TAC sections и retrieval runtime не менялись. Нового XLSX нет. PDF warnings сохранены в логах и metadata JSON; они не подавлялись.

## Limitations

1. Первые две страницы, exact mapped PDF text/layout и эвристики не покрывают все издания, имена, glyph encodings или необычные bylines. Остальные страницы не используются для библиографического заполнения.
2. Journal возвращается в source form, без автоматического раскрытия всех сокращений/исправления склейки слов. Корректность full author list на всём корпусе не подтверждена независимым gold.
3. External DOI lookup, OCR repair, human corrections, work/supplement inheritance и автоматическое заполнение production Article при ingestion отсутствуют в этом этапе.
4. Метаданные не считаются принятыми без пользовательского review. Пустое поле означает отсутствие поддержанного кандидата в проверенной области, а не отсутствие метаданных в документе вообще.
5. Private JSON/HTML содержат исходные фрагменты литературы и локальные paths; это не публичный пакет.

## Verdict

Автоматическое заполнение трёх колонок и проверяемый HTML-review реализованы. Текущий результат — 91 source-bound proposal. Следующий шаг: пользовательская проверка, отдельный учёт исправлений и поддержка повреждённых/нестандартных источников; затем — metadata admission/ingestion integration по отдельному scope. Terms extraction и безопасный full-text search channel остаются самостоятельными задачами.
