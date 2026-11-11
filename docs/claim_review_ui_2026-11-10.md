# ARIADNE: явный просмотр утверждений рядом с evidence

10 ноября 2026, Asia/Yekaterinburg. Продолжение после offline claim checks.
[Протокол v0.1](records/claim_review_ui_protocol_2026-11-10_v0.1.md) зафиксирован
до изменений app. Сохранён snapshot фактического dirty working tree; прежняя
незакоммиченная работа и все предыдущие outputs сохранены.

Changed:

- Два новых app-модуля: `claim_review.py`, `claim_review_routes.py`.
  Отдельный API `POST /answer/prepare/requirements/packet/checks` и UI
  `/ui/answer/prepare/requirements/packet/checks`. Из старых app-файлов изменены
  только регистрация router в main и ссылка с сохранением library ID в navigation
  preparation. Старый checker, source recipes, inference, preparation decisions,
  admission, retrieval, context budgets, DB/PDF/index не менялись.
- UI сначала явно готовит snapshot через существующий read-only packet путь.
  Каталог показывает записи источников и raw quotes; автоматически утверждения
  не создаются и не проверяются. В отдельной расширенной форме пользователь
  передаёт явный JSON-массив structured assertions и pinned packet ID.
  Сохраняются question, collection, top_k, method, answer_style/language, library.
  GET учитывает выбранную библиотеку и preference cookie; некорректный cookie
  не превращается в evidence.
- При проверке сервер повторно готовит текущий packet. Если его ID изменился —
  **HTTP409**, без автоматического rebasing/retry/continuation. Client packet,
  parent, sources, report, file path и научное решение не принимаются. API имеет
  strict claim schemas, уникальные IDs и старый canonical claim budget256000 bytes/
  64 assertions. Дополнительный транспортный лимит нового UI/API — **300000 bytes**,
  включая JSON или URL-encoded request body; multipart/file uploads не поддержаны.
  Duplicate JSON/form keys, NaN/Infinity, malformed и extra fields отклоняются.
- В карточке слева показано заявленное значение с ячейкой, единицами, условиями,
  approximation status и unknowns; справа — название из существующей evidence
  записи, точная цитата, PDF range/layer и expandable полный raw с выделенным span.
  Отдельно показаны field diff, identity/ambiguity/uninspected diagnostics.
  Четыре статуса literal / finite semantic contract / arithmetic / scientific
  validity сохранены раздельно. Научная достоверность всегда не оценена.
- Exact page link появляется только при доказанном packet page mapping; иначе
  ссылка явно открывает начало диапазона, а точная страница остаётся неустановленной.
  OCR PDF и original PDF различены; совпадение OCR-текста с original не выводится
  из общей нумерации страниц. Используются существующие article PDF routes,
  embedded PDF paths не открываются. Неизвестный title остаётся неизвестным.
- Отдельная canonical capsule `claim_evidence_review_v0.1` связывает полный
  unchanged packet, исходный report, assertions и hashes двух UI-модулей.
  Validator полностью восстанавливает её по текущему доверенному packet/claims
  и pinned IDs. API/кнопка скачивания возвращают canonical JSON attachment.
  На сервере capsule не сохраняется; human reviews=[], writable decisions,
  actor attribution, scientific acceptance и постоянная revision history не добавлены.
  Журнал остаётся deterministic system observations с прежними blockers.

Tests run:

- Финальный `tests_affected_v03.xml`: **1306 passed**, 0 failures/errors/skipped,
  включая **39 новых** тестов. New-only до последнего rendering-исправления:
  38 passed. Два предыдущих affected прогона дали по1305 passed; это повторные
  проверки одних тестов, не независимые подтверждения. Audit guard внешней сети: denials=0.
  TestClient запускался вне sandbox из-за ранее установленного зависания;
  прежний `StarletteDeprecationWarning` сохранён.
- Ruff **9 Python-файлов** passed; полный mypy app — **203 source files**,
  success. `git diff --check` без whitespace errors; CRLF warnings относятся
  к существующим файлам рабочего дерева.
- Baseline freeze и три сравнения: **324 actual frozen-channel service executions**.
  Все **81 полных результата и пять native bodies** каждого прогона совпали.
  Ни одного native request не отправлялось. Source checker и прежний inference
  не дрейфовали; два старых app drift явно описаны в review/report.json.
- **27 canonical capsules**, **27 catalogs**, **284 claim cards** экспортированы
  и воспроизведены; **311 событий** отдельно проверены по sequence/root/input/
  output/event hashes, отдельно пересчитан capsule ID. Сохранены runtime HTML
  fragments и link inventory. Assertions constructed из известных tuples;
  это не реальные ответы модели и не независимые scientific labels.
- API/UI controls покрывают полные/mismatch/ambiguous/no-claims входы, unknowns,
  точный/missing page registry, original/OCR ссылки, escaping title/raw/assertion/
  attributes, все request options, library cookie, stale409 без retry, инъекцию
  parent/packet/report/path, schema/input budgets, duplicate keys/IDs и ошибки.
  Providers/context actions запрещены в seams. Реального SQL/DB preparation нет.
- **33 PDF hashes** и **58 прежних raw/PDF audit bindings** перепроверены.
  Свежая PDF extraction/визуальное чтение PDF не выполнялись; missing registry
  не дополнен задним числом. Статический HTML QA проверил27 новых cases/284 cards,
  пять архивных секций, **33 TAC/eight columns** и существование PDF links.
  Архивное сравнение контекста явно отделено от новых UI-контролей.
- Через CUA открыт **новый HTTP UI** на127.0.0.1:8766 в отдельном FastAPI test app
  с реальным новым router и synthetic preparation на раскрытом Lin raw.
  В браузере выполнены GET→prepare catalog→explicit wrong-cell assertion.
  Наблюдались exact quote, число84 при WRONG_CELL_CONSTRUCTED, field mismatch,
  четыре отдельных статуса и сохранённый page-registry blocker.
  Проверено расположение утверждения и цитаты рядом на desktop.
  helper v02 записал3 подготовки: один seed и два UI POST, network denials0,
  model/OAuth/DB0; после теста сервер штатно остановлен.

Сохранённые находки и исправления:

- Первый new-only прогон: **15 failed/22 passed/2 errors**. Fixture ошибочно
  смешивал question constructed-пакета и real-raw parent; исправлена только
  тестовая предпосылка. Длинный автоматически созданный pytest-ID для300001-byte
  body превысил Windows environment limit; назначены короткие явные IDs.
  Исходный JUnit не переписан. Первые lint/type diagnostics исправлены до финала.
- Browser показал реальный CSS дефект: общий flex-style формы сжимал question
  textarea. Добавлены scoped styles новой формы; после перезапуска/нового GET
  повторно визуально проверена полная ширина question и карточка результата.
  Helper сначала не монтировал branding assets; исправлено только test app.
  Первый preview и passing pre-CSS tests/comparison сохранены отдельно.
- Финальный replay первоначального review_v01 обнаружил изменение HTML после
  canonical JSON load: порядок полей утверждения и JSON-подробностей зависел от
  insertion order. Сохранены исходный renderer/script, capsule и actual rebuilt
  fragment в `pre_render_roundtrip_fix_v01`; первая разница на позиции1866.
  Вывод полей теперь имеет фиксированный порядок, JSON-подробности sort_keys=True.
  Добавлен отдельный regression test и повторён affected набор:1306 passed.
  Новый review_v02 проверяет canonical rendering всех27 capsules и catalogs;
  все27 исходных diagnostic reports остаются byte-identical с review_v01.
  Capsule IDs изменились из-за нового UI code hash; старые outputs не переписаны.
  После этого финального изменения порядка полей браузер повторно не запускался:
  визуальное наблюдение относится к сохранённой предшествующей версии, а полный
  canonical HTML replay — к окончательному renderer.
- Первая browser tab исчезла; восстановлена новой вкладкой того же IAB по
  документированному recovery. Старый tab.reload не обновил отображение после
  перезапуска; новый GET и повторный submit показали текущую форму и результат.
- Sandbox запретил loopback socket при остановке helper. Тот же ограниченный
  shutdown POST вне sandbox вернул200; сервер10584 завершился штатно.
  Это не внешняя модельная попытка и не сетевой denial внутри audit guard.

Limitations:

UI предназначен для явных structured assertions. Удобный редактор произвольного
ответа и автоматическое извлечение его утверждений не реализованы. Научная
достоверность, general entailment, ownership, human decisions, сравнение постоянных
ревизий и независимая оценка остаются открытыми. Копирование source tuple в
assertion не доказывает пригодность ответа на исходный вопрос.

В браузере просмотрен один constructed mismatch на desktop с synthetic preparation.
Mobile/responsive behavior, реальная БД, running production server, PDF navigation
через production document resolver, full repo suite, concurrency/cache/ORM и
deployment не проверены. Старый file:// HTML review не открывался повторно и
его прежний policy block не обходился; новый HTTP app — отдельный проверенный
объект. Скриншоты наблюдались в чате; отдельные PNG/JPEG артефакты не сохранялись.

Integrity не равна authenticity или актуальности источника. Navigation hash
меняет актуальность старых code-bound packets: архивы сохранены без миграции
и не объявляются текущими. Повторный явный UI/API request повторяет read-only
preparation; persistent ledger/cache не добавлен. Все реальные model/OAuth/slots/
fresh DB preparation/ingestion/deployment — **0**.

Verdict:

Ограниченный явный claim/evidence viewer реализован и проверен. Это bounded часть
архитектурного этапа5, без автоматического научного принятия и включения в inference.
Следующий отдельный scope — протокол измеряемого пилота на новых статьях либо
объявленное улучшение ввода assertions. Независимую оценку не заменяют exposed
regression cases и constructed controls. Общий план качества остаётся **75%**,
все предыдущие live scopes закрыты.

- [HTML review](../output/claim_review_ui_20261110/review_v02/review.html)
- [Полный итог и bindings](../output/claim_review_ui_20261110/review_v02/report.json)
- [Статический QA](../output/claim_review_ui_20261110/review_v02/qa.json)
- [Финальный JUnit](../output/claim_review_ui_20261110/tests_affected_v03.xml)
- [HTTP browser helper](../output/claim_review_ui_20261110/browser_probe_v02/result.json)
- [Финальное сравнение](../output/claim_review_ui_20261110/comparison_v03/summary.json)
