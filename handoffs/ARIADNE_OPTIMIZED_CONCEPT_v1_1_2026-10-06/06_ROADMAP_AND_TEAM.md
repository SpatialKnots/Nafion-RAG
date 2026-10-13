# Дорожная карта и команда

**Версия:** 1.1. **Дата:** 6 октября 2026 года. **Часовой пояс:** Asia/Yekaterinburg.


## Люди и ресурс
Пользователь — химик, самостоятельно кодить не умеет, планирует Codex Pro и 20–30 ч/неделю. Напарник — к.х.н.; его ресурс и роль требуют согласия.
Плановая основа пользователя: 25 ч × 46 недель = 1150 часов, включая 150 часов резерва. При 20 ч/неделю — 920 часов; сокращаются stretch, дополнительные свойства и расширение корпуса.

Предложены 4–6 ч/неделю напарника и периодическое инженерное сопровождение порядка 100–160 часов за год. Это оценки, не договорённости. Научная разметка и проверка — ответственность химиков; миграции, восстановление и release требуют компетентного инженерного review.

## До подачи/договора
Организация/руководитель; один conductivity scenario; 6–8 интервью; ручной baseline; 10–15 pilot papers; один end-to-end record; background snapshot; ресурс/benchmark; предварительная смета и вопросы по IP/оборудованию. Это предложенные действия, не выполненные результаты.

## Первый месяц
- Неделя 1: inventory без reset/clean, воспроизводимый baseline, схема и annotation manual, выбранные 10–15 статей.
- Неделя 2: sidecar extractor, один полный текстовый маршрут, evidence, ranges/bounds/approximate/data origin и отрицательные случаи.
- Неделя 3: review/edit/confirm/reject, history/export, восстановление sidecar после перезапуска.
- Неделя 4: малое B/C сравнение на development, полный ручной timing, failure report, demo 3–5 источников и решение о scope.

Gate: если связи ненадёжны либо review не экономит время, остаётся review-first режим и переработка основного workflow. Не наращивать функции ради демонстрации.

## Месяцы 1–2
Фиксация schema/scope, baseline, pilot-gold и annotations. Один локальный extractor для явного текста.

## Месяцы 3–4
Полная текстовая запись, reasons/checks, field evidence, review UI, история, CSV/JSON.

Gate: оценка стоимости исправления. Если она съедает выигрыш, исправлять extractor/schema/review, а не начинать второй домен.

## Месяцы 5–6
Поддерживаемые простые таблицы, row/sample mapping, units/conditions/data origin, negative cases.
Gate: определить layouts и exclusions до окончательного gold; потери обнаружения не скрывать.

## Месяцы 7–8
Gold 60, независимая разметка test без раскрытия predictions, validation model/threshold selection, ablations. Clean install, backup/restore; предварительный offline прогон.

## Месяцы 9–10
Пилотная таблица, сбалансированный timing, feedback. Финальная заморозка extractor/parser/model/rules/thresholds до untouched test. Test не используется для настройки.

## Месяцы 11–12
Final test, интервалы и counts, сетевой offline acceptance, повторяемый deployment, эксплуатационные документы, materials по результатам/IP и контролируемое демо. Достигнутое и недостигнутое раздельно.

## Контроль разработки
Одна задача Codex — один проверяемый результат; acceptance examples до кода; небольшие патчи; рабочую копию не откатывать; исходные PDF не изменять; критические миграции/release с review; unit tests не заменяют scientific acceptance. Для повторных заявлений после tuning по раскрытому test нужен новый holdout.

