# Records stage46: каких доказательств не хватает

27 октября 2026 года, Asia/Yekaterinburg. `evidence_gap_audit_v0.2`.
[План](records_stage46_evidence_gaps_plan_2026-10-27.md),
[журнал грилла](records_stage46_evidence_gaps_review_log_2026-10-27.md),
[протокол v0.1](records/evidence_gaps_protocol_v0.1.md),
[поправка v0.2](records/evidence_gaps_protocol_v0.2.md).

Changed:

- Отдельный offline аудит сохранил четыре исходных вопроса, stage45, selection,
  model-facing wires, metadata, отказы и admission. Mars-regolith — отрицательный
  development-контроль, не сообщение о научном измерении.
- Неизменённый ingestion extractor прочитал полный original text layer десяти
  прежних PDF и отдельно зарегистрированной Istomina 2021: **11 PDF / 273 страницы**.
  Новые capture/layer IDs явно локальные, не выданы за записи БД. Для исторически
  зарегистрированных страниц сохранены layer IDs и проверены exact text hashes.
- Перед исходами заморожены registration, четыре exposed checks прежних отказов,
  code/protocol, родители и installed direct-dependency versions. Все 1280 parent
  bindings прошли preflight; новая подготовка содержит 1282 input bindings.
  Это installed snapshot, не portable/transitive lockfile.
- Для каждого question/document scope есть checklist исходных признаков,
  недоказанная связь, необходимое доказательство и следующее действие.
  Sample/table abstentions и condition/origin diagnostics доступны без исправления.
  Научная связь из соседства, общего метода или совпадения cues не устанавливается.

## Практический результат

| Вопрос | Что показала проверка | Что нужно дальше |
| --- | --- | --- |
| conductivity_protocol | В Kayumov, физическая стр. 3, есть методика импедансного измерения и критерий термического равновесия. Три прежних row candidates не стали доказанной sample identity/applicability. | Явная область применения методики к конкретным образцам/строкам/результатам; не копировать общий метод на каждую строку. |
| dsc_protocol | В прежнем scope были Choi, Yu и диссертация Чернюк. Локальный Istomina PDF подтверждён pinned first-page title/byline/publication/DOI anchors. На физической стр. 4 раздел 2.4 Thermal Analysis содержит условия и температурную программу DSC. Это пробел отбора, а не доказанное отсутствие методики в статье. | Отдельно подготовить source-bound контекст запрошенной статьи с полным разделом 2.4 и прежними guards. Старый packet, selection и admission пока не менялись. |
| preparation_atmosphere | В Kayumov, стр. 3, аргон относится к подготовке электродов и сборке ячеек. Эта фраза не доказывает среду во время измерения. | Прямое source statement среды измерения или её сохранения после сборки; иначе measurement environment unknown. |
| absent_material | В полном проверенном тексте трёх PDF его scope конечные Mars/regolith patterns не нашли matches. | Сохранить неподдержанную предпосылку/отказ и границы поиска. Не изобретать измерение и не заявлять отсутствие во всём корпусе. |

Эта таблица — интерпретация помощника по exposed development-источникам,
**не independent scientific gold**. `source_review_v01.json/html` хранит её
отдельно от детерминированного алгоритма, с exact quotations/offsets и provenance.
Она не повышает автоматически научные состояния. Физические страницы Istomina
1 и 4, Kayumov 3 просмотрены целиком; для Istomina 4 также просмотрен независимый
Poppler render. Остальные страницы не объявлены визуально проверенными.
Текст двухколоночного Kayumov не переставлялся и не ремонтировался.

## Состояния и границы

Все **2158 matching blocks / 6657 literal spans** сохранены с offsets, полным
текстом блока, page/layer/PDF identities и доступным bbox. Это lexical candidates,
включая возможные citations/negations/bibliography, а не научные измерения.
В текущих 273 страницах нет empty-text/unproven-block-mapping cases; полнота
визуального/OCR содержания из этого не следует. Новый OCR не запускался.

| Checklist state | Question/document/requirement occurrences |
| --- | ---: |
| supported_in_packet | 6 |
| found_outside_packet | 17 |
| not_found_in_inspected_scope | 9 |
| source_identity_unresolved | 6 |

`supported_in_packet` означает только точное присутствие буквального текста
в прежнем selected block, при совпадении article/PDF/page/layer и offsets.
Это не научная поддержка утверждения. Шесть identity-unresolved entries относятся
к трём чужим для Istomina DSC document scopes. Их cues не подставляются вместо
запрошенной статьи. 13 document/question relation entries остались
`relation_unresolved`: это состояние алгоритма, не доказательство невозможности
установить связь в источнике. **Admission остаётся 0/4.**

После exposed v0.1 run обнаружено использование broad sample/membrane inventory
для named Nafion qualifier отрицательного контроля. В проспективной поправке
v0.2 введён отдельный Nafion/Naﬁon/Нафион pattern. Generic membrane больше не
считается этим именованным признаком. Также parent manifest скопирован побайтно
для рабочей ссылки из исторического HTML. Новый prepare/run отделён;
`prepared_v01`, `prepared_v02`, `run_v01`, `review_v01` сохранены как история.
Старые результаты не перезаписаны и не выдаются за новый runtime replay.

## Tests run

- Финальный affected suite: **90 passed**, один существующий Starlette/httpx
  deprecation warning; `output/commit_check_20261026/evidence_gaps_v06.xml`.
  До поправки overlapping run: 89 passed; после поправки новый test file:
  18 passed. Эти прогоны не складываются как unique tests.
- Проверены exact Unicode offsets, foreign article/PDF/layer, changed source
  text/ranges, unselected blocks, outside-packet evidence, wrong/ambiguous header
  identity, negation/negative control, generic membrane без Nafion, missing links
  при повторных sample IDs, preparation-versus-measurement atmosphere,
  empty/uninspected source, input drift, exclusive paths и HTML escaping.
- Первый pytest: 14 passed / 3 temp-directory setup errors из-за sandbox;
  повтор разрешён с локальным basetemp. Технические ошибки tuple/list coordinates
  при replay и тестовой записи в exclusive JSON исправлены до финального run.
- Первый helper регистрации избыточно блокировал локальный socket.gethostname
  при импорте SQLAlchemy/platform. Сетевого/model запроса не было; сохранён
  исходный helper, новый использует список connect/DNS/sendto events, как CLI.
  Первая browser QA остановилась на неоднозначном nested-summary locator;
  исправлен локатор теста. Неуспешные запуски не считались passes.
- Ruff `app tests scripts`: passed. Mypy `app`: **171 source files**, no issues.
- Postflight: **1346 bindings**, 11 PDF hashes, 273 page hashes, все 2158 blocks /
  6657 literal spans и три source-review quote occurrences проверены.
  Все **47 historical files**, включая manifest, и metadata побайтно совпали.
  Два финальных экспорта: все **55 файлов** побайтно одинаковы.
- Chrome 156 headless: четыре question cards, DSC с четырьмя document scopes,
  expandable exact quote, search/reset, все review links, TAC 11 строк / восемь
  согласованных колонок прошли. Реальный клик открыл application/pdf на стр. 4.
  Отдельная source-summary HTML также проверена. JS errors и remote HTTP requests
  отсутствуют; browser context offline, HTTP блокирован. Снимки DSC quote, TAC
  supplement и source summary просмотрены.
- Восемь prepare/run/export network-evidence файлов завершены без запрещённых
  CPython socket/DNS attempts; postflight также без attempts. Это Python audit
  guard, не OS firewall или контроль networking native libraries.

## Артефакты и повтор

`output/records_stage46_20261027/`:

- `prepared_v03`, `run_v02`, `review_v02`, `review_repeat_v02` — финальный v0.2.
- `source_review_v01.html/json` — краткая source-based сводка четырёх вопросов,
  отдельная assistant interpretation с проверенными exact quote spans.
- `review_v02/review.html` — полный алгоритмический аудит;
  `metadata_review.html` — все 11 документов. Исторические TAC десяти документов
  сохранены; для нового supplement доступны raw identity anchors и полный
  first-page text. Abstract/Conclusions/Terms явно unimplemented, не выдуманы.
- Registration/checks, source-review manifest, network evidence, renders,
  postflight_v01.json, browser_qa_v02.json, source_notes_qa_v01.json.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.evidence_gaps --network-evidence output/stage46_new_network.json export --source output/records_stage46_20261027/run_v02 --output-dir output/stage46_new_review
```

Нужны новые output/evidence paths. Изменение bound code/source/PDF/runtime
останавливает replay явно. Private corpus и generated artifacts в Git не входят;
локальные пути и installed snapshot не являются автономной переносимой поставкой.

Limitations: конечные lexical inventories не определяют научную релевантность,
coreference, figure/table semantics или applicability. Нет нового retrieval/DB/
embedding/model/API исполнения, изменения runtime/thresholds/selection, полного
application suite, independent quality evaluation или cross-model review.
Unknown и отрицательный контроль не превращаются в отсутствие научных данных.

Verdict: согласованный stage46 выполнен без API. Следующий bounded шаг — отдельный
контекст Istomina для исходного DSC-вопроса с полным source разделом и прежними
guards; это пока предложение, не выполненная интеграция.
