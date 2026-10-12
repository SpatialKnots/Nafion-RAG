# ARIADNE: проверка предыдущей сессии и подготовка продолжения

Дата: 12 октября 2026, Asia/Yekaterinburg. Рабочая копия: `D:\Nafion-RAG`.

## Changed

Сверены исходники, отчёты от 9 октября, сохранённые экспериментальные результаты и последние сообщения чата «Найти заявку Центрального университ՞». Последний коммит рабочей копии — `bbffc25` от 9 сентября; новые модули `app/records/` и отчёты октябрьского цикла находятся в незакоммиченном дереве. HEAD не воспроизводит текущую реализацию.

Подтверждены следующие результаты предыдущего цикла:

- S01: фиксация source baseline, dependency snapshot и проверка установленного wheel описаны в `ariadne_s01_s02_execution_2026-10-09.md`. Историческую установку в чистой среде сегодня не повторяли.
- S02–S05: профиль Li-Nafion, draft experimental record contract, source regions, manifests, completeness diagnostics и offline worksheets присутствуют в исходниках. Ручные кандидаты и proposed work grouping не являются независимым gold.
- S06: локальный smoke harness, два single-field формата, предварительный эталон на 3 случая / 30 полей, source-bound offline comparison. Сохранённые ответы двух моделей доступны для воспроизведения проверки.

Сегодня повторно выполнен `app.records.cli compare` по прежнему эталону и двум matched batch. Новый результат: `data/experiments/records/comparisons/session_review_20261012/report.json` и `report.md`. Исторические эксперименты не перезаписаны.

Подготовлен приватный пакет `data/experiments/records/review/session_20261012/`:

- `reference_review.md`: 30 полей и 9 измерений связи, точные evidence и пустые решения рецензента; раскрывает предложения агента и предназначен для review/adjudication.
- `source_only_annotation.md`: все сохранённые регионы с source identity и точным текстом, без предложенных ответов и результатов моделей; предназначен для независимой разметки выбранных development contexts. Это не полный корпус и не held-out набор.
- `reference.json`: побайтовая копия исходного эталона, SHA-256 `9f05e608e24903bc5f03948385748c9ae4dd9d64a9d996b3534315674c2f42a6`.

Рецепт подготовки: `tmp/prepare_session_review_20261012.py`. Это одноразовый генератор локальных worksheets, не новый production adapter. Автоматические human decisions не создавались. Application source в этой сессии не менялся.

## Tests run

- Полный текущий pytest: **724 passed, 1 warning in 10.62 s**.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Offline comparison: Qwen2.5-1.5B — **3/30 literal valid, 3/30 reference agreements**; Qwen2.5-3B — **11/30 literal valid, 3/30 reference agreements**. Все reference agreements — отказы. Это воспроизведённая проверка сохранённых ответов, не новые inference requests.
- Пакет review: проверены идентичность копии эталона, 39 разделов / 39 пустых решений, точное сохранение всех source-region quotes и отсутствие разделов предложенных ответов в source-only worksheet.

Первый sandbox pytest задержался после пяти тестов и был прерван; успешный результат к нему не относится. Повтор вне sandbox выполнен с новым basetemp:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/session_review_unrestricted_20261012
```

Предупреждение: `StarletteDeprecationWarning` об использовании `httpx` с `starlette.testclient`. Причина задержки первого запуска не установлена; успешный повтор вне sandbox не доказывает конкретную причину.

## Limitations

Сегодня не запускались модели, живой retrieval benchmark, doctor, новый clean install или live verification PDF/БД. Исторические показатели 33 статей и 46/46 retrieval вопросов не являются повторным измерением сегодняшнего состояния.

Независимая научная проверка эталона, sample/condition/origin linkage, work-level split и quality acceptance S06 остаются открытыми. Machine integrity и совпадение с агентским эталоном не равны научной точности. Полные записи из модельных ответов не собраны и не приняты.

## Verdict

Текущая инженерная регрессия проходит; слабое место выбранного эксперимента — ненулевые поля и их научное связывание. Следующий ограниченный цикл:

1. Проверить эталон по source-only разметке, затем adjudication: sample identity, 20 °C по сноске, initial-plasticiser composition, применимость общей методики и происхождение цитируемого результата.
2. Зафиксировать отдельный контракт extraction adapter: поиск exact evidence отдельно от предложения связи полей; поддерживаемая структура таблиц/сносок задана явно; отсутствие и противоречия диагностируются.
3. Начать S07 с proposed records, сохранённых входов/ответов и обязательного review. Не превращать независимые single-field ответы в принятую запись автоматически; не переносить метод текущей статьи на цитируемый результат.

Изменения production extraction, database schema или расширение модели не следуют автоматически из этой проверки. Научное admission требует решений рецензента.
