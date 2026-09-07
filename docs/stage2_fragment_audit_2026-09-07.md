# Этап 2: аудит fragment-level FAIL и типографских лигатур

Дата: 2026-09-07. HEAD `4958bf0` плюс рабочие изменения этапов 1–2.

## Changed

Класс ошибки: `evaluation_typographic_ligature_mismatch`. Все три оставшихся
FAIL (user_reg_002, 003, 007) вызваны буквальным сравнением `Li-Nafion`
с `Li-Naﬁon`, где `ﬁ` — U+FB01. Это дефект измерения, а не установленная
ошибка ранжирования или границ чанков. Gold и запросы сохранены.

Проверены все страницы и чанки двух источников в локальной БД:

| Источник | DOI | Страниц / чанков | Подходящие чанки в прежней выдаче |
| --- | --- | --- | --- |
| Sanginov 2021 | 10.1016/j.electacta.2021.137914 | 14 / 24 | rank 1: `931a2ad8-abde-4e08-b889-4beae9ff247d`, PDF 12–13; rank 2: `48b38f63-c186-4a95-8473-a3c8fdb667a8`, PDF 1–2 |
| Istomina 2021 | 10.3390/polym13071150 | 14 / 16 | rank 3: `647775a0-3b8d-402d-b17c-ee499e426a1d`, PDF 1–2; rank 4: `3aa22958-5efe-4e30-bd4b-136522d14857`, PDF 2–3 |

Во всех перечисленных чанках слой `original`. Ни один чанк этих статей
не содержит буквальное `Li-Nafion`. После раскрытия только `ﬁ` перечисленные
чанки удовлетворяют всем исходным `text_contains` своего вопроса.
На PDF 1 Sanginov аннотация содержит Li-Naﬁon, EC/SL и ionic conductivity;
на PDF 2 Istomina текст содержит mixing temperature, swelling degree и Li-Naﬁon.
Контекст Istomina прямо связывает исследование набухания с температурой смешения.
Предыдущие записи, называвшие источник вопроса 007 Kayumov 2021, неточны:
его DOI target и название в БД — Istomina 2021.

Оригиналы прочитаны без изменения, SHA-256 совпали с БД:

- `data/pdf/d6744494353ffc88_Sanginov_2021.pdf`:
  `d6744494353ffc88860f3146e17d847bb75111e105c85cae19decd277c84eb8a`.
- `data/pdf/7519b88c1b0a0bf3_Istomina_2021.pdf`:
  `7519b88c1b0a0bf36855c1f881a19965191b72521823bdbafd9736c0c9a32e9f`.

В `app/evaluation/retrieval.py` сравнение keywords и extended text_contains
раскрывает семь латинских типографских лигатур U+FB00–U+FB06 с обеих сторон.
Регистр, как прежде, не учитывается. Общая NFKC-нормализация не применяется:
надстрочные знаки, индексы, минусы и греческие буквы сохраняются. Проверка DOI,
article ID и chunk ID не меняется. Исходный текст и snippets не изменяются.
В settings новых отчётов добавлено `text_matching=lower_latin_ligatures_v1`.
Это явное аддитивное изменение отчёта и правила совпадения; определения метрик
и пороги сохранены. Метрики до/после нельзя выдавать за улучшение поиска.

## Tests run

Команды выполнялись из корня через `.venv/Scripts/python.exe`:

- `-m pytest tests/unit/test_evaluation_ligatures.py -q` до патча:
  2 failed / 5 passed; воспроизведено несовпадение лигатуры в обе стороны.
- `-m pytest -q` после патча и добавления legacy regression: 365 passed,
  одно существующее StarletteDeprecationWarning о httpx.
- `-m ruff check app tests scripts/stage1_smoke.py`: PASS.
- `-m mypy app`: PASS, 68 файлов; первоначальная ошибка аннотации maketrans исправлена.
- `-m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json`:
  match, без добавленных, удалённых или изменённых статей.

Локальная диагностика: `tmp/stage2_fragment_audit.py` →
`tmp/stage2_fragment_audit.json` (полные тексты, страницы, слои, отсутствующие
термины, ranks и проверка хешей). Запуск с `PYTHONPATH=.`.

## Evaluation

Живой повторный запуск неизменных 10 regression вопросов выполнен через
`tmp/stage2_after.py evaluation_questions_user_regression_extended.yaml`,
collection=literature, top_k=10, hybrid_cross_lingual.

| Проверка | До | После |
| --- | --- | --- |
| PASS | 7/10 | 10/10 |
| Article Recall@10 | 1.0 | 1.0 |
| MRR | 0.933333 | 0.933333 |
| nDCG@10 | 0.667230 | 0.667230 |
| Top-1 | 9 | 9 |
| Полнота traceability | true | true |

Для вопросов 002/003/007 chunk Recall@10 изменился с 0 на 1.
Полные `results` (включая порядок, scores и snippets) всех 10 вопросов
совпали с baseline. Before:
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T121210Z.json`.
After: `data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T161943Z.json`.
Этот процесс стартовал после изменения matcher, но до добавления settings.text_matching;
поэтому указанного поля в этом конкретном after-артефакте ещё нет.

Дополнительно выполнен **replay сохранённой выдачи**, без повторного поиска,
с полными текстами из текущей БД: `tmp/stage2_ligature_replay.py` →
`tmp/stage2_ligature_replay.json`. Три baseline: `121210Z`, `121415Z`, `121548Z`
за 20260907 в том же каталоге exports. Regression: 7→10; User: 25→25;
Cross-lingual: 31→31. Проверенные поля passed, article/chunk recall, MRR,
nDCG и traceability изменились только у трёх указанных вопросов (passed и chunk recall).

## Limitations

- 56 дополнительных вопросов проверены replay, а не новым retrieval-запуском.
- PDF проверены по хешам и сохранённому выбранному текстовому слою;
  визуальная проверка страниц в этом шаге не выполнялась.
- Совпадение терминов не доказывает полноту ответа о максимуме проводимости
  или корректность извлечения численных данных.
- Низкое покрытие русских терминов в answer adequacy остаётся отдельным
  ограничением; эта логика не менялась.
- Этап 2 целиком не закрыт: остаются semantic baseline и проверка покрытия
  более широких вопросов и фильтров на едином корпусе.

## Verdict

Исправление evaluator принято: три ложных FAIL устранены, источники и порядок
выдачи сохранены, научные символы не свёрнуты общей Unicode-нормализацией.
Следующий шаг — baseline semantic и сверка оставшихся критериев этапа 2.
