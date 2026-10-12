# ARIADNE: TAC feasibility audit and retrieval comparison

Дата: 12 октября 2026, Asia/Yekaterinburg. Статус: development experiment, без production integration.

## Changed

Зафиксирован исходный baseline: `output/baselines/20261012_before_tac/`, **279 файлов**, fingerprint `eed9331e62aee549eb49f643dd65fd6e49c2f7331053b3dd05c2f371c4283488`. Проверка целостности baseline прошла; dependency snapshot не нашёл missing dependencies или requirement mismatches. Новый clean install/wheel build в этом цикле не выполнялся.

Добавлен `scripts/tac_experiment.py`: offline section proposals с точными source spans, детерминированный lexical TAC shortlist и comparison replay на неизменном production hybrid search. Новые проверки находятся в `tests/unit/test_tac_experiment.py`. Код application routes и production search не менялся. RU–EN glossary, OCR, extraction и chunking не обновлялись.

Снимок текущего корпуса сохранён в приватном `data/experiments/tac/20261012_v01/corpus.json`: **33 документа, 493 selected pages, 619 chunks**. Экспорт выполнен в PostgreSQL repeatable-read/read-only transaction. Тексты selected pages совпали с зарегистрированными PageTextLayer. Проверены SHA-256 оригинальных PDF; хеши зарегистрированных source PDFs повторно проверены после сравнения.

Протокол и команды воспроизведения: [tac_experiment_protocol_2026-10-12.md](tac_experiment_protocol_2026-10-12.md). Все source texts, локальные пути, images и query artifacts остаются в ignored `data/experiments/`.

## Распознавание TAC

Итоговый вариант `profiles_v03.json` содержит rule `tac_section_proposals_v0.2`. Он предложил T для **33**, A для **17**, C для **27** документов. Это числа наличия **предложений**, а не число правильно распознанных разделов. Отсутствие предложения не доказывает отсутствие раздела.

Первый text-order прототип захватывал body/references после A/C. До retrieval comparison добавлены ограничения по exact layout blocks и stop headings. Промежуточные `profiles.json` и `profiles_v02.json` сохранены отдельно. Во время итогового сравнения parser, shortlist, gold и правила rescue не менялись; fingerprint кода в `run_started.json` совпадает с кодом завершённого опыта.

MuPDF сообщил layout/content-stream diagnostics; предупреждения сохранены для **17 документов** в итоговых profiles и в `extract_v03.log`. Успешное получение текстового блока не означает, что структура PDF была полностью корректной. Диагностика не подавлялась.

### Визуальная проверка

Poppler отрендерил **14 полных страниц восьми development документов**. Они визуально проверены агентом. После просмотра сохранены 19 source-bound boundary annotations в `boundary_audit.json`; они не подставлялись в retrieval profiles.

| Раздел | Проверено границ | Полный точный текст | Ошибка границы | Пропущен |
|---|---:|---:|---:|---:|
| T | 8 | 5 | 3 | 0 |
| A | 7 | 4 | 1 | 2 |
| C | 4 | 2 | 2 | 0 |

Выборка намеренно содержит сложные layouts; эти отношения не являются corpus-wide accuracy или независимой оценкой. Научные измерения и linking в этом аудите не принимались.

Наблюдения:

- Laporta: summary в верхнем блоке `Full Paper` визуально присутствует, но A detector его не поддерживает. Порядок stored text отличается от визуального порядка страницы.
- Kayumov: A без заголовка правильно предложен по publisher pattern; T усечён. C захватывает блоки финансирования/конфликта интересов.
- Choi: T и C определены в проверенных границах; A визуально присутствует без явного heading и пропущен.
- Ma и Sanginov: проверенные T/A совпали; проверенный C Sanginov совпал.
- Dissertation: institutional line предложена как T; A усечён до первого layout fragment вместо полного текста аннотации.
- Moore/Martin: формула ошибочно предложена как T; C включает acknowledgment/registry material. PDF page 6 также содержит начало другой статьи, что отдельно осложняет article-level interpretation существующей ingestion unit.
- Supplement Sanginov: T проверен. Полное отсутствие A/C во всём supplement не утверждается: визуально проверена только первая страница.

## Tests run

- Целевые synthetic tests: **17 passed in 1.03 s**. Проверены Unicode/exact offsets, inline headings, layout endings, cross-page C, unbounded A refusal, references/methods stop boundaries, source checksum tampering, rescue without gold, отсутствие дубликатов и отказ от перезаписи.
- Полный pytest: **741 passed, 1 warning in 11.03 s**.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Исходный sealed baseline: **279 files verified**, fingerprint совпал.
- Реальные read-only поисковые запросы: **46 вопросов × 2 production retrieval calls**, плюс TAC ranking и offline replay. Это не модельная генерация ответа.
- Проверка inputs/source integrity: article inventory, chunk texts и selected page texts совпали со snapshot до запросов; PDF hashes совпали после полного опыта.

Полная регрессия выполнялась вне sandbox, поскольку в этой сессии ранее наблюдались ограничения temporary files:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/tac_full_20261012
```

Единственное предупреждение — существующий `StarletteDeprecationWarning` об использовании `httpx` с `starlette.testclient`.

## Сравнение поиска

Неизменный набор `evaluation_questions_extended.yaml`: **46 вопросов — 38 answerable, 8 unanswerable**. Использован существующий extended evaluator. Критерии/разметка/denominators не менялись. Все числа ниже относятся к этому development набору.

| Вариант | PASS / 46 | Mean article Recall | Mean chunk Recall | MRR |
|---|---:|---:|---:|---:|
| Текущий hybrid_cross_lingual, top-10 | **46** | 1.000000 | 1.000000 | 0.934211 |
| TAC-only, до 5 статей | **41** | 0.947368 | 0.769231* | 0.800439 |
| Expanded-pool control, top-10 из top-20 | **46** | 1.000000 | 1.000000 | 0.932018 |
| TAC-deep replay | **44** | 0.947368 | 1.000000 | 0.899123 |
| TAC-deep replay с добором | **45** | 0.973684 | 1.000000 | 0.902882 |

*Для TAC-only это совпадение текстовых targets внутри section proposals, а не подтверждённое измерение и не production chunk retrieval. Метрика не доказывает извлечение научной записи.

Все восемь unanswerable controls прошли существующую adequacy check во всех вариантах. Это свойство этих controls и эвристики, не доказательство общей надёжности отказов.

Дополнительные hits не имеют исчерпывающей независимой relevance разметки. Сохранённый `judged_hit_fraction` нельзя интерпретировать как измеренную долю нерелевантных статей; TAC-only выдаёт статьи, остальные варианты — chunks.

### Разбор потерь

- TAC-only потерял PASS на qext007 (Laporta), qext015 (Cho), qext024/qext025 (Sanginov supplement) и qext031 (Kayumov diglyme). Потери бывают как на уровне статьи, так и на уровне конкретного текстового target.
- Строгий TAC-deep потерял qext025 и qext031. Добор восстановил qext031, но qext025 остался потерян.
- Для qext025 ожидаемый supplement не вошёл в пять TAC-кандидатов. Title supplement не содержит искомые `M05-2X/TZVP/SMD/dielectric constant`, а A/C detector не предлагает его экспериментальные appendix regions. Production baseline и expanded-pool control находят нужный документ.
- При qext025 после TAC-фильтра уже есть десять фрагментов других выбранных работ. Rescue по правилу «добрать, если меньше десяти» не запускается, хотя необходимый источник отсутствует. Количество evidence не является проверкой полноты ответа.
- Expanded-pool control не потерял PASS, поэтому две strict-stage регрессии связаны с TAC gating в этом опыте; увеличение окна само по себе не объясняет их.

Детальные результаты и исходные выдачи: `data/experiments/tac/20261012_v01/comparison/report.json`, individual `qext*.json`, копия questions и `run_started.json`. Исторические эксперименты и gold не переписаны.

## Limitations

1. Это lexical TAC prototype на предложенных границах, без отдельного semantic TAC index или проверенного научного профиля.
2. Глубокий этап выполнен как replay глобального expanded production pool. Реальный поиск внутри shortlist ещё не реализован; ускорение, масштабирование и interactive responsiveness не доказаны.
3. Component timings последовательны и зависят от cache/runtime state. Нулевой evaluator elapsed_ms для replay — placeholder, не измеренная нулевая стоимость. Сравнение latency не является controlled benchmark.
4. Independent relevance labels, scientific records, measurement-level recall и accuracy отсутствуют. Question set — исторический development regression set.
5. Визуально проверена часть корпуса; число правильно распознанных TAC во всех 33 документах не установлено. Гипотеза «80–90% нужных сведений покрываются TAC» не проверена этим опытом.
6. RU–EN extraction/admission не реализованы. Неразрешённые boundaries, author metadata, acknowledgments и формулы могут загрязнить автоматически извлечённый словарь.

## Verdict

Изолированный baseline, TAC prototype, визуальный boundary audit и retrieval comparison выполнены. **Жёсткий TAC gate не принят**: он теряет источники, а простой добор по числу фрагментов не восстанавливает полноту.

Следующий bounded cycle:

1. Исправить title/abstract/conclusion boundaries по отдельно версионированному development набору; добавить новые layouts для проверки обобщения, сохранить этот failed baseline.
2. Установить проверяемые work/supplement links и исследовать full-text safety channel, который не зависит только от количества найденных фрагментов. Не использовать expected answers как runtime trigger.
3. Повторить comparison на неизменном development gold и новом независимо размеченном наборе; измерять article и evidence losses отдельно.
4. После достаточного качества boundaries добавить терминологические предложения с source evidence. Научный review Li-Nafion records сохраняется как отдельная задача.

До этих проверок TAC допустим как экспериментальный сигнал приоритета. Production retrieval, scientific admission и текущий словарь остаются прежними.
