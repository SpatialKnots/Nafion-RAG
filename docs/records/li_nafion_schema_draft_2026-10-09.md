# Li-Nafion Scientific Record: схема и инструкция pilot, черновик

Статус: S03.1, проект для научного review, 9 октября 2026 года. Пользователь выбрал **литий-ионную проводимость Li-Nafion**. Обязательные условия сравнимости и окончательный supported scope ещё не утверждены. Production schema и данные не меняются.

Согласовано пользователем: pilot включает **проводимость литиевой формы с сохранением авторского названия свойства; подтверждение Li-ion отмечается отдельно**. Total ionic conductivity не переименовывается в Li-ion conductivity. Авторское утверждение и отдельно подкреплённое evidence о Li-ion характере различаются; окончательные labels уточнить в schema review.

## Единица разметки

Одна запись связывает один определённый образец с одним значением/диапазоном/границей проводимости в одном наборе условий. Каждая точка температуры и каждый образец таблицы — отдельная запись. Одинаковые числа в разных экспериментах не объединять. Повтор текста или перекрытие chunks не создают новую измерительную точку.

Название Li-Nafion не доказывает, что reported conductivity является отдельно измеренной Li-ion conductivity. Записывать формулировку свойства автора: ionic/total conductivity, Li-ion conductivity, electronic conductivity или unclear. Не заменять total conductivity на Li-ion conductivity без evidence. Transference number — отдельное свойство; расчёт компоненты проводимости возможен только как отдельная производная с утверждённым правилом и обоими источниками.

## Структура предлагаемой записи

| Поле/группа | Representation | Основание |
|---|---|---|
| source_identity | article_id, PDF SHA-256, work_group_id, schema/run IDs | Не смешивать supplement, основную статью и повтор в диссертации как независимые работы |
| sample | original label, Nafion grade/form, Li-form evidence, preparation/treatment | Sample IDs локальны внутри работы; aliases только с подтверждением |
| property | verbatim name, interpreted kind, uncertainty of kind | Interpretation с source fragment; unknown допустим |
| value | raw lexeme и raw unit; scalar/range/bound; approximation, uncertainty | Исходный текст неизменен; parsed decimal отдельно |
| temperature | raw text/unit; representation либо explicit missingness | Room temperature не превращать автоматически в 25 °C |
| medium | Solvent/electrolyte components и composition basis | Массовые/мольные/объёмные доли не подменять друг другом |
| conditioning | Hydration/RH, swelling/plasticisation, drying/pretreatment, при наличии | Не выводить из марки материала или названия solvent |
| method | Reported technique и условия измерения, если есть | Method для одного опыта не переносить на соседние записи без связи |
| data_origin | experimental/calculated/reference/unknown | Цитирование чужой работы не становится собственным экспериментом |
| field_evidence | page/layer, exact text/span/hash, role; отдельные fragments для нескольких страниц | Страница chunk range не является точной страницей occurrence |
| linkage_evidence | sample↔value, property↔value, conditions↔measurement | Близость слов сама по себе не проверяет связь |
| review | machine state и отдельный human state/revision | Автодопуск не равен подтверждению химиком |

Это научный проект схемы. Техническая реализация части полей и source integrity checks появилась в `app/records/`; её точные границы описаны в [experimental contract](experimental_record_contract.md). Production API, scientific admission, normalized quantities и полный record lifecycle не реализованы.

## Состояния отсутствия и сложности

- `not_found_in_context`: поле отсутствует в просмотренном region; статья целиком ещё не проверена.
- `not_reported`: после полного заранее определённого просмотра источник не сообщает поле; для одного абзаца такой вывод обычно недоступен.
- `ambiguous`: несколько возможных связей, неизвестный basis, роль числа или неустановленный sample.
- `unsupported`: layout/representation выходит за фиксированный supported scope. Причина сохраняется; статус не должен скрывать ошибки внутри supported scope.

Пользователь выбрал обязательные условия для первой сравнительной таблицы: **образец, температура, состав среды и метод**. Неполные записи остаются на review. Технический checker v0.1 перечисляет недостающие observations/linkage proposals; даже комплектный кандидат не получает автоматическое научное одобрение. Записи с отсутствующими условиями сохраняются как proposals с явной missingness и без подтверждённой сравнимости.

## Порядок работы химика с одной статьёй

1. Проверить original PDF, article identity и принадлежность к work group. Убедиться, что metadata title не принимается за проверенную библиографию.
2. Найти методы, определения образцов, таблицы/абзацы проводимости и сноски. Отмечать просмотренные regions и общий scope.
3. Разметить все подходящие случаи внутри scope, включая не найденные системой. Отдельно фиксировать неподдерживаемые случаи.
4. Связать значение с исходным sample label; сохранить headers, captions и необходимые context fragments.
5. Переписать raw value/unit без нормализации. Затем отдельно указать scalar/range/bound/approximation/uncertainty.
6. Зафиксировать reported property kind, температуру, medium/composition basis, conditioning и method по фактическому evidence.
7. Указать experimental/calculated/reference origin. Библиография и оглавление — полезные detection counterexamples, не самостоятельные records.
8. Записать ambiguous/missingness и время работы. Независимый reviewer размечает свою часть до просмотра outputs extractor.

## Первые development cases

Shortlist строится из read-only профиля, не является gold. Уже просмотренные текстовые примеры показали: Li-Nafion может встречаться в библиографии Каюмова 2021, оглавлении диссертации и разделе electrochemical stability supplement. Эти упоминания не доказывают наличия conductivity record в выбранном region.

Использовать их как естественные контрпримеры detection/linkage. Положительные records выбрать отдельно по реальному PDF. Main article/supplement и связанные публикации/диссертация требуют проверки work grouping до split.

## Решения для научного review

- Как отдельно представить авторское утверждение и подтверждение Li-ion характера? Включение проводимости литиевой формы с авторским названием уже согласовано.
- Как проверять согласованные обязательные условия — образец, температура, состав среды и метод — и их связь с измерением? Conditioning сохраняется отдельно; его обязательность ещё не установлена.
- Какие диапазоны, inequalities и uncertainty representations войдут в первый supported scope?
- Как фиксировать авторское room temperature без неподтверждённой нормализации?
- Считать ли диссертацию и supplement development-only источниками; какие связанные работы сгруппировать?

До этих решений: source adapter и schema proposal допустимы, финальный admission policy и scientific KPI не объявляются согласованными.
