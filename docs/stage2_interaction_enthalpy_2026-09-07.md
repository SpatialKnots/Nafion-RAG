# Stage 2: сохранение энтальпии взаимодействия в межъязычном запросе

Дата: 2026-09-07. Исходная ревизия `4958bf0`, рабочие изменения этапов 1–2.

## Changed

Класс ошибки: `property_confusion`. Запрос `What is the enthalpy of interaction
of lithiated Nafion with aqueous alcohol solutions?` не находил Чернюк 2024
в top-10. Переведённые варианты содержали понятия воды и литиевой формы,
но теряли требуемую энтальпию взаимодействия. Первым результатом была диссертация;
её релевантность не опровергнута, принудительное продвижение статьи не применяется.

Источник: `data/pdf/de0c55db3994c9a6_Чернюк_2024.pdf`, SHA-256
`de0c55db3994c9a6c2a2e3f0939d3b28b907fe3ac0c6ca867050be02bc53f182`.
Страница PDF 1, печатная 378, выбранный слой `original`. Заголовок содержит
«ЭНТАЛЬПИЯ ВЗАИМОДЕЙСТВИЯ ЛИТИРОВАННОЙ МЕМБРАНЫ NAFION С ВОДНЫМИ РАСТВОРАМИ
СПИРТОВ И ПОЛЯРНЫМИ АПРОТОННЫМИ РАСТВОРИТЕЛЯМИ». Аннотация подтверждает
исследование этанола, 2-пропанола, водно-спиртовых смесей и микрокалориметрию.

В `docs/cross_lingual_glossary.yaml` добавлено одно понятие `interaction_enthalpy`:
две английские фразы и две русские формы. Запрос и целевая статья в gold сохранены;
добавлена классификация ошибки и regression guard. Формулы scoring не менялись.
Словарь не содержит article IDs, DOI или условий для конкретного запроса.

## Tests run

- `.venv/Scripts/python.exe -m pytest tests/unit/test_interaction_enthalpy_glossary.py -q`:
  до дополнения словаря 3 FAIL / 2 PASS; после — 5 PASS.
- `.venv/Scripts/python.exe -m pytest -q`: 357 PASS, одно существующее предупреждение
  Starlette о deprecated использовании httpx в TestClient.
- `.venv/Scripts/python.exe -m ruff check app tests scripts/stage1_smoke.py`: PASS.
- `.venv/Scripts/python.exe -m mypy app`: PASS, 68 файлов.
- `git diff --check`: PASS, предупреждения Windows о нормализации LF/CRLF.
- Локальный API перезапущен. HTTP `/search` с целевым запросом подтвердил
  `interaction_enthalpy` в диагностике и Чернюк 2024 на местах 2–3
  (страницы 1–2 и 2–3); ответ сохранён в `tmp/stage2_http_enthalpy.json`.

## Evaluation

Три baseline выполнены до изменения словаря; пути и метрики приведены в
[аудите gold](stage2_gold_audit_2026-09-07.md). Повторная оценка выполняется
на тех же вопросах, collection=literature, top_k=10, hybrid_cross_lingual.
Корпус соответствует snapshot `data/exports/corpus_manifest_stage1_20260907.json`;
исторический `docs/corpus_manifest.json` не заменялся.

| Набор | PASS до → после | Recall@10 | MRR | Top-1 | nDCG@10 |
| --- | --- | --- | --- | --- | --- |
| Cross-lingual 31 | 30 → 31 | 0.967742 → 1.0 | 0.772849 → 0.788978 | 21 → 21 | 0.779477 → 0.791956 |
| User 25 | 25 → 25 | 1.0 → 1.0 | 0.836 → 0.836 | 19 → 19 | 0.876185 → 0.876185 |
| Regression 10 | 7 → 7 | 1.0 → 1.0 | 0.933333 → 0.933333 | 9 → 9 | 0.667230 → 0.667230 |

After-отчёты в том же порядке:
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T121548Z.json`,
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T121415Z.json`,
`data/exports/retrieval_eval_extended_hybrid_cross_lingual_20260907T121210Z.json`.

Целевой запрос: статья вне top-10 → rank 2, MRR 0 → 0.5. Для остальных
65 запросов метрики и полный порядок chunk IDs совпадают. Сравнение сохранено
в `tmp/stage2_enthalpy_comparison.json`. `evidence_trace_complete=true` во всех
наборах до и после. Mean rank: 1.733333 → 1.741935 в наборе 31, потому что
теперь учитывается ранее пропущенный вопрос; ранги прежних найденных статей
не ухудшились. В других наборах mean rank остался 1.6 и 1.2.
Классификация целевого gold добавлена после baseline, поэтому before-группа
`unspecified` и after-группа `property_confusion` сопоставляются по ID вопроса.

Повторные `doctor` и `corpus-manifest --check
data/exports/corpus_manifest_stage1_20260907.json` завершились PASS / match.

## Limitations

- Найденная статья не доказывает полноту научного ответа или правильность чисел.
- Три baseline FAIL в user_regression_extended связаны с отсутствующими ожидаемыми
  чанками: 002/003 (Li-Nafion, EC/SL, conductivity в Sanginov 2021) и 007
  (mixing temperature, swelling degree, Li-Nafion в Kayumov 2021).
  Требуется отдельный аудит исходного текста и границ чанков; gold не ослаблялся.
- Диагностика adequacy этих запросов также отмечает низкое буквальное покрытие
  русских терминов; это не самостоятельное доказательство нерелевантности
  англоязычной статьи. Для answerable PASS evaluator проверяет ожидаемые статьи
  и чанки, а не adequacy.
- Параллельные повторные прогоны не используются для сравнения latency с
  последовательным baseline.

## Verdict

Исправление принято по retrieval error fixing policy: целевой пропуск устранён,
Recall не снизился, остальные запросы и traceability сохранены. Этап 2 целиком
не закрыт: три случая ожидаемых чанков требуют отдельного исходного аудита.
