# Пункт 4: конечные перефразировки источников, v0.1

Дата: 9 ноября 2026. Статус: протокол до изменения runtime.

Цель: уменьшить ложные отказы на явно эквивалентных английских конструкциях
в трёх source roles двух существующих семейств: синтез Li2O в O2,
электролит EIS и изотермическая выдержка EC/SL. Это ограниченный первый
scope пункта 4, не универсальная semantic entailment и не независимая оценка.

Исходный runtime зафиксировать в `output/source_paraphrases_20261109/freeze_v01`:
снимок всех app Python/YAML файлов с hashes, текущие пять question-only
frozen-channel service traces, их реальные native bodies без отправки,
76 прежних full-service baselines и source windows с raw addresses.
До edits подтвердить точное воспроизведение пяти результатов последнего
condition_context_completion_v0.2 и сохранность их пяти native bodies.
Существующие outputs/manifests не редактировать.

Заранее выбранные альтернативы:

1. Li foils were treated with O2 gas at temperatures from LOW °C to HIGH °C
   for DURATION hours; также between LOW °C and HIGH °C. Явный материал,
   газ, диапазон и продолжительность в одной утверждаемой конструкции.
2. electrolyte containing CONCENTRATION M LiPF6 in EC/DEC (LEFT/RIGHT by volume).
   Молярное M строго отличать от m; соль, растворители и basis обязательны.
3. An isothermal treatment lasting DAYS days was performed/conducted at TEMP ◦C.
   This treatment did not change the measured W values. Оба предложения вместе;
   полученное утверждение остаётся наблюдением, не доказательством необратимости.

Поддерживать только объявленные варианты и нормализацию существующего SourceView.
Не добавлять свободные wildcard-связи, перестановку владельцев или исправление
raw текста. Сохранять прежние patterns; совместные разные значения/разные работы
и неполные роли оставлять неоднозначными. Факт и metadata источника должны
согласованно распознавать новую конструкцию, а поля повторно вычисляться из raw.
Новые ветви помечать отдельной версией grammar и активными ролями; на старых
конструкциях полные traces и native bodies должны остаться неизменными.

Controls строить из точных ранее выбранных Q02/Q04 источников и отдельно
из варьируемых constructed fixtures. Все перефразировки искусственные;
это не новые реальные публикации и не independent gold. Raw originals,
replacement rule, новый полный текст и provenance хранить отдельно.
Положительные варианты должны сохранять числовые/логические поля и unknowns.
Отрицательные: отрицание, будущее, гипотетическое/планируемое действие,
другой материал/газ/соль/растворитель/единица, условия другой операции,
разрыв предложения, отсутствие basis/времени/наблюдения, conflicting candidates,
разные работы. Проверять все F-ID/citation IDs и tampering чисел/полей/текста.

Измерения: исходные expected false refusals до edits; positive/negative controls
после edits; пять текущих вопросов и 76 прежних случаев фактическим service
replay с frozen retrieval channels; actual decoded native content и raw hashes.
Синтетический complete F-ID service/ASGI ответ и abstention явно обозначать.
При изменении контекста на реальных пяти вопросах — отдельная свежая read-only
подготовка/rollback; если контекст и native bytes прежние, новую DB подготовку
не объявлять выполненной или необходимой для неизменившегося контекста.

Критерии: все объявленные positives поддержаны, все negatives не допускают
полный fact bundle; исходные 81 traces и пять native bodies прежние;
source addresses валидны, F-ID recomputation/tamper checks сохранены;
затронутые tests/Ruff/full mypy app и статическая HTML QA выполнены.
Отдельный HTML: исходные цитаты, синтетические варианты, диагностика,
числа successes/refusals с правильными знаменателями, TAC33/eight columns.
Не считать прежние 76 случаев независимой проверкой новых ветвей: activation
учитывать отдельно. Незавершённые/неудачные runs сохранять, критерии задним
числом не менять; исправления scope после измерения версионировать отдельно.

Gate, retrieval, DB/schema/PDF/index, публичные поля, units, thresholds,
бюджет context completion и прежний Q03 не менять. F-ID, серверный renderer,
sample/operation/condition/unit/status checks и explicit unknowns сохраняются.
Реальных model/OAuth calls, новых slots, retries/downloads/deployment нет.
Никакой send mode. Браузер, full suite, concurrency/cache-ORM и независимая
научная оценка не следуют из этих проверок. Отчёт Changed/Tests run/Limitations/Verdict.
