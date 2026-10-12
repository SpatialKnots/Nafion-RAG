# ARIADNE: выполнение S01 и начало S02/S03

Дата: 9 октября 2026 года, Asia/Yekaterinburg.

## Результат

Создан инструмент фиксации локального baseline; пакет установлен и проверен в новой Python-среде. Исправлены два обнаруженных дефекта wheel: отсутствующие PNG и зависимость от glossary вне пакета. Выполнен read-only профиль Li-Nafion, создан schema/annotation draft.

Пользователь выбрал проводимость литиевой формы с точным авторским названием свойства; подтверждение Li-ion отмечается отдельно. Обязательные условия admission, окончательный supported scope и gold ещё требуют scientific review.

## Changed

- [freeze_baseline.py](../scripts/freeze_baseline.py): explicit inclusion rules, SHA-256, Git status, dependency closure, version snapshot, source.zip, inventory/checksum verification. Не читает `.env`, не копирует corpus/review/model data, не обращается к БД.
- [profile_li_nafion.py](../scripts/profile_li_nafion.py): transaction READ ONLY, проверка оригиналов, multilingual/ligature anchors, точные spans, chunk/page/layer provenance. Co-occurrence не является scientific linkage.
- `pyproject.toml`: PNG и glossary package data; явные dev dependencies httpx/packaging.
- `cross_lingual.py`: checkout читает прежний glossary из docs; установленный wheel при его отсутствии читает побайтово идентичный packaged YAML. Содержание словаря и scoring не изменены.
- `.gitignore`: private experimental data и generated baseline artifacts исключены из Git.
- Новые тесты: escaping paths, checksum tampering, незаявленный `.env`, точность multilingual/ligature anchors, совпадение glossary copies.

Рабочая `.venv`, production schema/facts и PDF не модифицировались. Существующие незакоммиченные изменения сохранены; автоматический коммит не выполнялся.

## Комплект baseline

Итоговый каталог: `output/baselines/20261009_s01_final/`.

| Artifact | Назначение |
|---|---|
| manifest.json | File hashes, selected Git status, runtime, inclusion/exclusion policy |
| source.zip и source/ | Sealed source комплект; tests/build выполнять в отдельной копии |
| requirements-observed.txt | Наблюдавшаяся dependency closure, проверенная в новой среде |
| environment.json | Package versions и requirement diagnostics |
| wheels/ariadne-0.1.0-py3-none-any.whl | Проверенный installed package |
| resources.json | Index pointers/manifests, known model-file hashes, OCR tools |
| verification.json / artifact_checksums.json | Фактические результаты и integrity дополнительных artifacts |

Промежуточные v1/v2/v3 сохранены как история. v1 source использовался напрямую для build/tests и получил generated files: это не sealed release. Далее source отделён от build-input; final source проверяется отдельно. Source archive содержит научные test fixtures; это локальный комплект, а не очищенный публичный релиз. Закрытые PDF, `.env`, ключи, БД и review history в нём отсутствуют.

Installed dependency snapshot не является универсальным hash-locked комплектом для всех платформ. Build backend устанавливался pip в build isolation; полный build lock пока открыт. Migrations/config/evaluation datasets находятся в source комплекте, не в wheel.

## Tests run

| Проверка | Фактический результат |
|---|---|
| Первые целевые baseline/profile tests | 13 passed |
| Ligature/profile/glossary cases | 8 passed |
| Full suite в новой среде, до packaging fixes | 603 passed |
| Full suite после новых profile/glossary tests | 609 passed |
| Итоговый full suite | **611 passed, 1 warning in 6.11 s** |
| Ruff app/tests/scripts | All checks passed |
| mypy app | Success: no issues found in 74 source files |
| pip check новой среды | No broken requirements found |
| Installed wheel, Python -I, вне source | 3 PNG; 20 glossary concepts; /health 200, status=ok |
| Doctor installed wheel | Все 11 категорий PASS; head 0005; 2 ready индекса; 33 originals present |
| Original integrity | SHA-256 всех 33 оригиналов совпали с БД |
| Manifest v3 после build в отдельной копии | 253 source files verified |

Итоговый suite выполнялся из отдельного build-input с актуальными profile/test files, в новой среде `output/baselines/20261009_s01_v1/clean-env/`, Python 3.12.7. При isolated smoke app импортирован из site-packages, не из checkout. Подтверждение соответствия final code этому test input фиксируется в verification.json.

Doctor использовал новую Python-среду с **существующей** `.env`, PostgreSQL и корпусом из рабочего каталога. Это не fresh DB setup, не новый OCR/recovery/offline прогон. Doctor создаёт служебные write probes.

External tools: Tesseract v5.5.0.20241111; leptonica 1.85.0; Ghostscript 10.07.1; OCRmyPDF package 17.7.1. Они не упакованы в wheel. Bge cache files идентифицированы SHA-256. Полный multilingual query-model cache в просмотренном расположении не установлен как готовый ресурс; ready index не доказывает переносимость model cache.

## Сбои и исправления

- Первый targeted pytest в sandbox: 6 setup errors из-за недоступного tmp directory. Повтор с новым basetemp вне sandbox прошёл.
- Venv/ensurepip в sandbox завершился ошибкой; повтор вне sandbox прошёл.
- В рабочей среде отсутствует installed metadata ariadne; setuptools/wheel также не установлены. Новый wheel устанавливался только в отдельную среду.
- Первый wheel не содержал PNG; добавлены package data.
- Installed API import упал с FileNotFoundError для site-packages/docs/cross_lingual_glossary.yaml. Добавлен точный packaged fallback; итоговый smoke прошёл.
- Sandbox pip install сообщал о невозможности очистить временные каталоги; финальная переустановка вне sandbox прошла. Произвольная очистка не выполнялась.
- Starlette/httpx deprecation warning сохранён, не подавлен.

## S02: profile, не gold

Отчёт: [li_nafion_20261009_v3.json](../data/experiments/records/profiles/li_nafion_20261009_v3.json).

33 originals verified; **6 документов с lexical anchors**, **5 с conductivity co-occurrence в chunk**. Повторения, overlapping chunks, references, оглавления и supplement не считаются независимыми experimental records. Первоначальный профиль дал 4/3; source-text inspection основной статьи Sanginov 2021 выявил пропуск PDF-лигатуры Naﬁon. После исправления matcher сохраняет raw text/spans; stored text не менялся.

Шесть документов не означают шесть независимых подходящих работ. Для pilot на 10–15 публикациях научная пригодность и расширение корпуса ещё открыты. Main/supplement и связанные публикации/диссертация требуют work grouping до split.

Schema/annotation draft: [li_nafion_schema_draft_2026-10-09.md](records/li_nafion_schema_draft_2026-10-09.md). Runtime full-record extractor/validator ещё не реализован.

## Повторение проверки

```powershell
.\.venv\Scripts\python.exe scripts\freeze_baseline.py --output output\baselines\NEW_UNIQUE_NAME
.\.venv\Scripts\python.exe scripts\freeze_baseline.py --verify output\baselines\NEW_UNIQUE_NAME
```

Builder требует новый output directory и не перезаписывает snapshot. Для воспроизведения: новая Python 3.12 Windows среда → requirements-observed → supplied wheel с --no-deps → pip check → isolated import/health → pytest из копии source с отдельным basetemp. Затем собственная конфигурация PostgreSQL/DATA_ROOT/OCR/models и doctor по JSON categories. Исходная `.env` не поставляется; migrations новой БД и full offline/restore — отдельные setup/S16 проверки.

## Статус и следующий шаг

S01: source baseline, dependency snapshot, новая Python-установка, installed wheel и текущая конфигурация проверены. Portable build lock/new DB/offline/restore ещё открыты. S02: scope и технический profile готовы, научный shortlist/обязательные условия впереди. S03: draft готов; scientific schema/validator впереди.

Следующий шаг — versioned experimental schema/validator и source region adapter после определения обязательных условий. Химик независимо размечает первые две подходящие статьи; автоматический profile эту работу не заменяет.

Limitations: scientific record pipeline, independent gold, автономная поставка и научная точность ещё не доказаны.

Verdict: начальный инженерный рубеж выполнен; экспериментальная разработка может продолжаться по выбранному scope.
