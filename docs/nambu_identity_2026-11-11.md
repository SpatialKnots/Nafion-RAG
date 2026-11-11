# ARIADNE: химические идентичности Nambu01

Changed:

По просьбе «Давай далее» выполнен следующий context case Nambu01. Полная
оригинальная PDF1 свежо отрендерена Poppler и визуально просмотрена. Первая
страница явно содержит три полных названия/обозначения, затем список степеней
фторирования в другом порядке. Новый контракт связывает списки по обозначению,
не по позиции в первом перечне: FETFEE — tetrafluorinated, ETFEE — trifluorinated,
EFEE — monofluorinated. Основание DEE отдельно привязано к явному определению
1,2-diethoxyethane / ethylene glycol diethyl ether в той же исходной странице.

Новый `ether_identity.py` и узкая ветка quantitative_facts. Нет фиксированных
целевых aliases/авторов/QA IDs или полных имён трёх ответных веществ в логике.
Грамматика намеренно ограничена1-arm-2-arm ethane: ethoxy либо фторированный
ethoxy с явными локантами. Проверяются длина списка локантов/fluoro-приставка,
поддерживаемые позиции1,2 и локальное число замещений ethoxy. Число F из этой
ограниченной записи должно совпадать с явным source-declared mono/di/tri/...
классом. Это проверка согласованности конечной номенклатуры, не общий molecular
graph/стереохимический validator или независимое подтверждение структур.

Требуются три разных обозначения и одинаковые полные множества aliases между
перечнем имён и классификацией. Повторное имя/identity не считается новым
соединением. Для этого конкретного симметричного основания также учитывается
эквивалентность двух концов центрального1,2-ethane: перестановка двух одинаковых
ethoxy arms не создаёт другую identity. Локанты внутри arms сохраняются;
различающиеся позиции фторирования не объявляются взаимозаменяемыми.

Три source-declared identity facts: полное английское название, обозначение,
степень фторирования, reference base/его определение, explicit item count и
correspondence relation имеют отдельные точные raw anchors/SHA. Names и classes
не являются численными измерениями; unit=null, name numeric_value=null,
scientific_ownership_verified=false. Условие item_count3 берётся из явного
source word three с прежним правилом word-number interpretation.

Полные названия не переводятся автоматически. Прежняя NFKC/dehyphenation
нормализация раскрывает ﬂ и переносы; удаление оставшихся пробелов внутри
химического имени отмечено отдельно в normalization. Исходные строки, включая
перенос после chemical hyphen, остаются в raw quote. Локанты, скобки, дефисы,
стем ether/ethoxy и все химические буквы не заменяются. Новые glyph aliases,
конверсии, resources/config, retrieval/ranking, вопрос/prompt/UI, DB/PDF/index,
threshold или внешняя API schema не менялись. App patch: один новый module и
quantitative_facts.py. Один полный F1 либо отказ, record и текст вычисляются
снова из raw перед выбором. Синтез всех трёх веществ в этой работе не заявляется.

Tests run:

- Финальный affected651passed,44 новых проверки; focused_v02 —114passed.
  Один прежний Starlette/httpx warning. Audit hook запрещал внешнюю сеть,
  network_denials0. ASGI проверки вне sandbox с синтетическим транспортом/БД.
- Полный mypy app215 файлов passed. Финальный Ruff6 Python-файлов passed.
- Проверены перестановка/дубликат/подмена aliases, несовпадение degree с именем,
  лишние/неверные локанты, methoxy/ethoxy и ether/ester, число объектов, неверный
  reference base, symmetric-end duplicate, unknown query requirements,
  prior/hypothetical/negative/bibliography scope, metadata, raw/record/normalization
  drift. Generic aliases/base и difluorinated constructed case исключают
  привязку только к исходным ответным буквам/трём классам.
- Три actual experimental API SYNTHETIC исхода: F1→200/answered,
  abstention→200/insufficient, unbound prose→502, read-only/rollback.
  Existing required-fields guard not_evaluated; это не ответы реальной модели.
- All30 actual-service comparison_v01:18→19 ready-unsent, новый толькоNambu01;
  остальные29 full results/retrieval и18 старых ready traces/native точны.
  Дополнительно три synthetic service исхода нового случая.
- 81 исторический actual-service сценарий сохраняет все full results;
  пять native inputs точны. Это прежняя development regression, не независимость.
- Свежая actual API preparation read-only/rollback: trace/native exact,
  registry diagnostics0/network denials0,6992bytes,
  SHA68b2c20ba2272c9962bd03c1d900aa5528bdcefa88025ff05e81e4d7d18cf5ea.
  Реальные model/OAuth/newslots0, остановка до внешнего transport.
- Exporter перепроверил27 raw-anchor observations, все три alias/degree связи,
  full names/explicit normalization, полную свежую PDF1 extraction/support
  против выбранного raw и неизменный PDF SHA, оба UI adapters. HTML содержит
  три identity строки и30 сравнительных строк.

Сохранённые ошибки и исправления:

Первый focused_v01:112passed/1failed — inline References marker перед
перечнем не блокировал контракт, потому что исходный generic bibliography
guard ожидал заголовок в начале строки. Отдельный agent-constructed adverse
probe также показал ложный допуск symmetric-end duplicate: разные записи имён
одних и тех же двух arms воспринимались как разные compounds. App/tests source
snapshots и точный probe сохранены в attempt_v01, JUnit v01 не переписан.

Добавлен локальный bibliography lead guard только для нового семейства и
ограниченная arm-site signature с симметрией этого ethane scaffold. После
исправления focused114 и affected651 прошли. Первый Ruff нового fresh driver
нашёл порядок импортов; исправлен до его исполнения. Ни один первоначальный
неудачный контроль не объявлен успешным научным результатом.

Limitations:

Конечное exposed source-declared identity семейство, не независимая научная
оценка или общий nomenclature/structure toolkit. Проверка arms/locants/prefix
покрывает только описанную грамматику и простую end symmetry, не все изомеры,
стереохимию, аналитическое подтверждение чистоты/структуры или химическую
валидность произвольных названий. Явный перечень статьи и agent visual review
не равны независимой экспертной приёмке. Полные English names сохранены для
проверки; другая номенклатура может оставаться неподдержанной.
Реальные ответы модели/F-ID compliance, scientific accuracy, natural transfer,
browser layout, полный suite, wheel и deployment не проверены.

Verdict:

Nambu01 готов к отправке с тремя полными названиями и source-declared
соответствием степеней фторирования.19/30 — готовые входы, не19 правильных
ответов. Остаются11 отказов:4 context,5 explanation,2 limits. Реальные вызовы
модели/OAuth отсутствуют, старые scopes закрыты; план качества75% прежний.
Следующий context case — Kondo02: метод определения μLi+ и reference zero.

[Отчёт](../output/nambu_identity_20261111/review_v01/review.html) ·
[Проверка](../output/nambu_identity_20261111/review_v01/report.json) ·
[Сравнение30](../output/nambu_identity_20261111/comparison_v01/result.json) ·
[Свежая API подготовка](../output/nambu_identity_20261111/fresh_api_v01/Nambu_01/result.json)
