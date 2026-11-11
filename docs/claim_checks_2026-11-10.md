# ARIADNE: отдельные offline-проверки утверждений

10 ноября 2026, Asia/Yekaterinburg. Продолжение после bounded context action:
ограниченный детерминированный проверяющий слой, без дополнительной LLM.
[Протокол v0.1](records/claim_checks_protocol_2026-11-10_v0.1.md) зафиксирован
до реализации; сохранён snapshot фактического рабочего дерева с прежними
незакоммиченными изменениями. Ни один старый app-файл в этом этапе не менялся.

Changed:

- Новый `app/generation/claim_checks.py`, версия `offline_claim_checks_v0.1`.
  Принимает существующий canonical evidence packet v0.1, отдельно доверенный
  текущий requirement-preparation parent, pinned packet ID и явные structured
  assertions. Полный packet восстанавливается прежним validator перед проверкой.
  Context-action capsule не является допустимым input packet.
- Три типа: точная цитата по anchor ID; полный tuple факта по fact ID; сумма
  по transformation ID. Свободный текст не разбирается. Утверждения здесь —
  caller-supplied диагностические входы, не сгенерированные ответы или human review.
- Цитата сравнивается со всем raw anchor без исправления Unicode/whitespace.
  Несовпадение относится к конкретному адресу, не доказывает отсутствие в статье.
  Для факта отдельно показаны raw surfaces и нормализация; сравниваются property,
  sample/value/unit/method, operation, conditions, numeric interpretation,
  epistemic status и unknowns. Совпадение с одним конечным рецептом не снимает
  конфликт альтернатив, uninspected sources и unresolved role identity.
- Сумма пересчитывается через `Fraction` по десятичным строкам, независимо от
  precision контекста `Decimal`. Порядок/написание operands и unit должны совпасть
  с source recipe; result сравнивается точно численно, исходное написание сохранено.
  Нет unit conversion, ratios, новых joins или присвоения научного владельца.
- Каждый результат разделяет literal presence, finite semantic contract,
  arithmetic и scientific validity. Последнее всегда `not_evaluated`; цитата
  сама по себе не получает смысловой поддержки. Diff полей не объявляется научным
  противоречием. Общего approved/confidence показателя нет.
- Лимиты: 64 assertions, 256000 canonical input bytes, 8000 символов цитаты,
  1024 на value/key, 32 conditions/unknowns, 16 operands/80 символов decimal.
  Strict extra-forbid схемы; duplicate IDs/foreign refs/неполные tuples/неверные
  числа/превышение лимита отклоняются. Пустой список даёт `no_claims`, не одобрение.
- Отдельный canonical report сохраняет assertions/refs, source/page/layer,
  unresolved page mapping, parent/packet hashes и прежний stop/blockers. Журнал
  продолжает packet root, содержит проверяемые input/output/event hashes.
  Проверка по текущим trusted inputs/code и pinned report ID обнаруживает дрейф.
  Локальные save/load — exclusive-create, без перезаписи или чтения embedded PDF paths.
- CLI: `python -m scripts.check_answer_claims --packet ... --parent ... --claims ...
  --packet-id ... --output ...`. Canonical входы для первого случая находятся в
  `output/claim_checks_20261110/review_v01/checks/{packet,parent,claims}_000.json`;
  pinned ID — поле packet_id в packet. `--output` должен указывать новый файл.
  API/UI продукта, `/answer`, preparation, source recipes, retrieval, admission,
  DB/PDF/index и существующие code-bound packet контракты не менялись.

Tests run:

- Финальный затронутый набор: **1267 passed**, 0 failures/errors/skipped,
  включая **57 новых** тестов. Guard внешней сети: denials=0. TestClient выполнялся
  вне sandbox из-за ранее установленного зависания; сохранён прежний
  `StarletteDeprecationWarning`. Отдельный new-only прогон: 57 passed.
- Ruff: шесть новых Python-файлов passed; полный mypy app: **201 source files**,
  success. `git diff --check` без whitespace errors; предупреждения о CRLF
  относятся к существовавшим изменениям.
- До реализации и после: **162 actual frozen-channel service executions**,
  все **81 полных результата и пять native bodies** совпали в обоих прогонах.
  Native bodies не отправлялись; это регрессия на раскрытых случаях.
- 27 прежних preparations → **284 явных assertions**, **311 событий**,
  независимо проверенных по sequence/parent-root/input/output/event/report hashes.
  Canonical export/load воспроизведён для каждого отчёта. Четыре пустых входа
  явно остановились без assertions. Все исходные packet/blockers сохранены.
- В этой демонстрации: 105 совпадений конечного source tuple, 89 tuple differences,
  2 ambiguous candidates, 88 semantic not_evaluated. Это контрольные статусы,
  не scientific positives/negatives или доли качества. Есть exact/wrong quotes,
  чужая ячейка/единица/ток/статус при том же числе, потеря unknowns и неверные суммы.
  Отдельные tests проверяют incomplete registry, malformed inputs, budgets,
  tampering/code/parent/pins, overwrite refusal и действительный CLI round trip.
- **33 PDF hashes** и **58 прежних raw/PDF audit bindings** перепроверены.
  Свежая PDF extraction/новый визуальный просмотр не выполнялись: использован
  явно указанный неизменный предыдущий аудит. Missing page registry не дополнен.
- Статический HTML QA: **27 новых cases/284 rows**, пять архивных case sections,
  **33 TAC/eight columns/57 существующих PDF links**. Архивное сравнение контекста
  явно отделено от новых assertions; полный исходный TAC сохранён.

Первый new-only прогон сохранён: **3 failed/51 passed**. Два сбоя — неверные
тестовые предпосылки: первый реальный CE tuple не имел unknowns, а missing-registry
fixture не имел ни одного факта. Контроли исправлены с явным выбором Conclusion
и отдельным частично недоступным registry. Третий сбой обнаружил реальный дефект:
порядок conditions менялся при canonical JSON round trip. Поля literal-check
теперь упорядочиваются; добавлена отдельная проверка key-order invariance.
Исходные JUnit/inputs не перезаписывались. Все изменения сделаны до финальных
tests/comparison/review; measured behavior не корректировалось после отчёта.

Limitations:

Это offline CLI и библиотечный слой для явных структурированных assertions.
Извлечение утверждений из произвольных ответов, общий semantic entailment,
научная достоверность, связь результатов разных ролей, human review и независимая
оценка не реализованы этой доработкой. Все adverse assertions constructed;
единственный exposed real raw пакет имеет synthetic preparation, он не hidden gold.
Нового естественного ответа или снижения отказов не установлено.

Replay требует trusted current parent/code: integrity не равна authenticity,
актуальности БД/PDF или научной приёмке. Browser layout не проверен из-за прежнего
file:// policy block; новых попыток/обходов нет. Product integration, running
server, full repo suite, cache/ORM/concurrency/deployment и новый pilot не проверены.
Реальные model/OAuth/slots/fresh DB preparation/ingestion/deployment — **0**.

Verdict:

Ограниченный offline per-claim слой реализован и проверен. Разделение literal /
finite semantic contract / scientific validity сохранено; старый допуск не меняется.
Это bounded часть архитектурного этапа 4, не завершение общей научной оценки.
Следующий отдельный scope — рабочее место просмотра утверждений/evidence и
диагностик либо отдельно объявленное расширение контрактов. Автоматическое
включение в генерацию не выполнялось. Общий план качества остаётся **75%**;
независимая оценка открыта, все прежние live scopes закрыты.

- [HTML review](../output/claim_checks_20261110/review_v01/review.html)
- [Итог и исходы](../output/claim_checks_20261110/review_v01/report.json)
- [Статический QA](../output/claim_checks_20261110/review_v01/qa.json)
- [Финальный JUnit](../output/claim_checks_20261110/tests_affected_v01.xml)
- [Финальное сравнение](../output/claim_checks_20261110/comparison_v01/summary.json)
