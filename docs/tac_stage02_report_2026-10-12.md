# TAC stage 02: границы секций и HTML-проверка

Дата: 12 октября 2026 года. Изолированный эксперимент ARIADNE; production integration отсутствует.

## Changed

В `scripts/tac_experiment.py` реализована версия `tac_section_proposals_v0.3`:

- Заголовки объединяются через соседние layout blocks с совместимыми размером шрифта и геометрией. Область поиска ограничена до поддерживаемого начала основной части; добавлены исключения для institutional/publisher lines и зона названия диссертации между автором и специальностью.
- Поддержан publisher label `Full Paper:`. Явная аннотация собирается из соседних блоков совместимого оформления; переход к другой колонке или стилю останавливает объединение.
- Добавлен отдельный эвристический кандидат для аннотации без heading: narrative prose, расположение после названия, верхняя область страницы и переход к более узкой основной колонке. Неоднозначные кандидаты отвергаются. Соседние фрагменты одного оформления объединяются до проверки narrative trigger: это восстановило начало аннотации Kondo.
- Conclusions останавливаются перед singular/plural acknowledgment, финансированием, конфликтом интересов и registry material.
- Добавлены проверка профилей по точным source offsets/layer/hash и offline replay сохранённых production candidates. Параметры, lexical scoring, rescue rule и evaluator не менялись.

`scripts/tac_review_html.py` — воспроизводимый HTML-only exporter. Основные колонки: Title, Authors, Journal, Year, Abstract, Conclusions, Terms, hyperlink to original file. Все 33 документа включены. Тексты разворачиваются полностью; есть поиск, ссылки на оригинал/страницу, offsets, selected text layer, hash и диагностика. HTML экранирует исходный текст и показывает управляющие символы как `⟦U+XXXX⟧`. Отсутствующие поля обозначены явно. Перезапись результата запрещена. XLSX на этом этапе не создавался.

Таблица для пользователя:

`output/tac_stage02_20261012/ARIADNE_TAC_stage02_final_2026-10-12.html`

Согласованный HTML review workflow сохранён в `AGENTS.md`. Исходные PDF и `app/` не изменены этим этапом; изменений production database/schema, OCR, chunking, glossary или retrieval scoring нет.

## Inputs и воспроизводимость

- Неизменный корпус: `data/experiments/tac/20261012_v01/corpus.json`, 33 документа, 493 выбранные страницы, 619 chunks.
- Snapshot SHA-256: `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Финальные предложения: `data/experiments/tac/20261012_stage02/profiles_final_v02.json`. Их hash/code hash записаны в профилях, HTML и `source_integrity.json`.
- Предложены T для 32, A для 21, C для 27 документов. Это наличие кандидата, не число правильно распознанных секций. Прежняя версия предлагала T/A/C для 33/17/27 документов.
- Authors, Journal, Year отсутствуют в сохранённых метаданных всех 33 документов. Не выводились из filenames или визуальной догадки. Terms/RU–EN admission пока не реализованы.
- Frozen baseline перед этапом: `output/baselines/20261012_before_tac_stage02/`, 283 файла, fingerprint `cee8fa4bdcdffcd2300d37c98ec192e2e72fce3aa88312b47667c019affbd052`.
- Baseline после этапа: `output/baselines/20261012_after_tac_stage02/`. Итоговый manifest содержит inventory/hash исходников и runtime dependencies. Закрытые PDF не включаются в source baseline.

Команды финального прогона из корня репозитория:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment extract --snapshot data/experiments/tac/20261012_v01/corpus.json --output data/experiments/tac/20261012_stage02/profiles_final_v02.json
.\.venv\Scripts\python.exe -m scripts.tac_experiment replay --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage02/profiles_final_v02.json --baseline-report data/experiments/tac/20261012_v01/comparison/report.json --questions docs/evaluation_questions_extended.yaml --output data/experiments/tac/20261012_stage02/comparison_final
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage02/profiles_final_v02.json --metadata data/experiments/tac/20261012_v01/table_metadata.json --output output/tac_stage02_20261012/ARIADNE_TAC_stage02_final_2026-10-12.html --source-root .
```

Для нового прогона нужны новые output paths: существующие артефакты не перезаписываются. Source recipes сохранены в `data/experiments/tac/20261012_stage02/recipes/`. Предварительные profiles, comparison и HTML этого этапа оставлены отдельно; итоговый отчёт относится только к `profiles_final_v02.json` и `comparison_final/report.json`.

## Tests run

- Целевые тесты TAC и HTML: **33 passed in 1.24 s**. Добавлены проверки сложных границ, fragmented layout, ambiguous abstention, escaped HTML, source integrity и оригинальных ссылок; synthetic fixtures обозначены как synthetic.
- Полный pytest: **757 passed, 1 warning in 12.25 s**. Финальный запуск вне sandbox: `--basetemp D:/Nafion-RAG/tmp/tac_stage02_full_unrestricted`; лог `data/experiments/tac/20261012_stage02/pytest_full_unrestricted.log`. Предыдущий sandbox запуск завис без вывода, был остановлен и успешным не считается.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Контрольный replay старых профилей полностью воспроизвёл прежний summary для всех пяти методов, включая PASS и метрики. Evidence: `control_verification.json` и `control_replay/report.json`.
- Все **33 PDF hashes** совпали со snapshot; **88 файлов app/** совпали с baseline перед этапом. Evidence: `source_integrity.json`.
- HTML проверен headless Edge/Playwright: **33 строки, 8 колонок, 33 original links**, полное совпадение Abstract/Conclusions с профилями, работа поиска/expand/collapse, отсутствие page errors. Локальные PDF проверены exporter и hash audit. Evidence: `output/tac_stage02_20261012/browser_verification.json`, `preview.png`, `preview_sections.png`; оба скриншота визуально просмотрены. Начальный browser launch в sandbox завершился ошибкой доступа к временному профилю; повтор вне sandbox успешен.

Предупреждение pytest — существующий StarletteDeprecationWarning об использовании httpx с starlette.testclient. PDF layout warnings не скрывались: предупреждения сохранены для 17 документов; extraction stderr оставлен в логах.

## Boundary audit

Прежние 19 agent-authored development annotations не редактировались. Проверялось совпадение точной исходной цитаты после удаления внешнего whitespace:

| Вид | Прежние совпадения | Финальная версия |
|---|---:|---:|
| T | 5/8 | 8/8 |
| A | 4/7 | 7/7 |
| C | 2/4 | 4/4 |
| Всего | 11/19 | 19/19 |

Evidence: `boundary_audit_final.json`, hash неизменных annotations включён. Эти cases использованы при разработке. **19/19 не является независимой точностью и не переносится на весь корпус.**

Дополнительно просмотрены пять полных первых страниц оригиналов: Nambu, Fan, Kondo, Peng, Sasaki 2007. Nambu/Fan: предложенные T/A визуально полны; Kondo: T полон, A сначала был обрезан до последнего фрагмента, после общего объединения блоков содержит все три фрагмента (1066 Unicode codepoints). Peng: T распознан, визуально присутствующая A пропущена. Sasaki 2007: визуально присутствующие T/A пропущены. Это дополнительная проверка разработки, включая один исправленный случай, не held-out gold. Conclusions этих пяти документов не принимались. Evidence: `additional_visual_review.json`, `visual_audit/render_manifest.json`, PNG и stderr.

## Retrieval replay

Неизменные 46 development вопросов: 38 answerable и 8 unanswerable. Использованы сохранённые исходные production выдачи top-20; article_k=5, top_k=10. Production и expanded-pool controls скопированы без изменения. Новый поиск к БД на этом этапе не выполнялся; latency не измерялась.

| Метод | Прежний PASS | Финальный PASS | Mean article Recall | Mean chunk Recall | MRR |
|---|---:|---:|---:|---:|---:|
| Production top-10 | 46/46 | 46/46 | 1.000000 | 1.000000 | 0.934211 |
| TAC-only | 41/46 | 42/46 | 0.947368 | 0.769231* | 0.859649 |
| Expanded-pool control | 46/46 | 46/46 | 1.000000 | 1.000000 | 0.932018 |
| TAC-deep strict replay | 44/46 | 44/46 | 0.947368 | 0.923077 | 0.916667 |
| TAC-deep + прежний добор | 45/46 | 45/46 | 0.973684 | 1.000000 | 0.919591 |

*Для TAC-only chunk recall — lexical target coverage в предложениях секций, не извлечение измерений. Метрики и denominators существующего evaluator не изменялись.

Все восемь unanswerable controls сохранили PASS; это не доказательство общей надёжности отказов. Unjudged hits не считаются установленно нерелевантными.

Финальный strict replay теряет qext024 и qext025, оба по Sanginov supplement. Добор восстанавливает qext024; qext025 остаётся потерян. qext031 по Kayumov теперь проходит strict replay. При полном A Kondo меняются лексические top-5 tie/ranks; улучшение корректности границ не гарантирует монотонного улучшения shortlist. Предварительная версия с неполным A Kondo давала strict 45/46; она не принята как итоговая.

Итог: **полнота глубокого поиска на этом development наборе не улучшилась**, strict chunk recall снизился; MRR вырос. Требуется safety channel и связь article/supplement, а не выбор ошибочных границ ради более высокого PASS. Evidence: `comparison_final/report.json`.

## Limitations

- Не все layouts поддержаны. Пропуски Peng/Sasaki и неверные/усечённые кандидаты вне проверенной части корпуса остаются возможными.
- Ни визуальное наличие A/C в 80–90% корпуса, ни покрытие ответов этими секциями не установлены. Отсутствие кандидата не равно отсутствию секции в статье.
- Нет независимого boundary/relevance gold, проверки научных зависимостей или measurement-level acceptance. Human review HTML ещё не выполнен.
- TAC index, реальный restricted deep search, work/supplement links и full-text safety channel не реализованы этим этапом. Replay не доказывает ускорение.
- Metadata extraction, Terms и автоматический RU–EN admission остаются следующими отдельными задачами. Словарь production не пополнялся.
- HTML рассчитан на локальные PDF paths этого компьютера. Снимок и review содержат закрытые source fragments; не являются публичным пакетом.

## Verdict

Этап разработки границ и воспроизводимого HTML-review выполнен. TAC остаётся экспериментом; **жёсткий gate не принят**. Следующий этап: разбор пользовательского HTML-review, независимые boundary cases и безопасный full-text канал с проверяемыми article/supplement связями. Затем — source-bound Terms candidates и отдельно RU–EN соответствия. Этот результат не закрывает scientific acceptance других этапов ARIADNE.
