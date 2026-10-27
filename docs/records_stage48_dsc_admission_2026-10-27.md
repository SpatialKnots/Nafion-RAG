# Records stage48: допуск нового DSC-пакета

27 октября 2026 года, Asia/Yekaterinburg. `dsc_source_admission_v0.1`.
[Протокол](records/dsc_admission_protocol_v0.1.md),
[пакет stage47](records_stage47_dsc_context_2026-10-27.md).

Changed:

- Реализован **пункт 2** согласованного pre-API плана: отдельная проверка нового
  DSC source packet. Старые packets, flags, production gates и scientific
  thresholds не менялись. Новый результат не исправляет исторические 0/4.
- **14/14 source checks прошли; current source blockers — 0.** Пакет получил
  `source_packet_eligible_for_frozen_experiment=true`, статус
  `eligible_for_frozen_experiment_preparation`. Это пригодность входного контекста
  для подготовки ограниченного эксперимента, не научная приёмка или разрешение API.
- Все **12 исторических причин отказа** сохранены отдельно без удаления/repair.
  Они не подменяют текущую проверку нового source packet. Все семь файлов
  stage47, включая wire, source registry, report, TAC HTML и manifest, скопированы
  побайтно в `packet/`; исходный stage47 остался неизменным.

## Что проверено

1. Полная реконструкция stage47 и SourceRegion: live PDF hash, exact source
   pages, citation/source identities, полный methods span и прежние guards.
2. Неизменённый целевой вопрос, пять уникальных citation roles, одна статья/PDF
   и четыре first-page identity anchors.
3. Автор/год только из byline/publication contexts; DSC mention только из M1.
   Повторно использованы существующие finite qualifier parser и token/offset
   matcher. Fake retrieval results, scores и внешние metadata не создавались.
4. В M1 есть source wording DSC calorimeter, measurement-environment statement,
   temperature-range description и temperature-programme introduction.
   После introduction сохранён raw action order heating/cooling/heating.
   Числа, units, flows, rates и durations не интерпретировались и не проверялись
   как научные величины. Finite cue matches не доказывают semantic truth.
5. Полные heading boundaries, исходная mapping diagnostic и terminal punctuation;
   прежние full-page literal/decoded/union guards и 100000-byte ceiling.
   Фактический wire остался **4346 bytes**; provider envelope ещё не существует.
6. Sample identity, per-result applicability и scientific acceptance явно
   сохранены как unknown/unestablished. Их разрешение не требуется для вопроса
   о методике статьи; unsupported scientific assignment при этом не допускается.

Все **10 новых diagnostic source spans** сохраняют citation/region ID, physical
page и абсолютные Unicode offsets; postflight проверил точное совпадение текста.
Источник и его identity остаются exposed development evidence, не независимым gold.

## Что не разрешено этим результатом

`execution.network_ready=false`, `api_calls_authorized=false`.
Три отдельных execution blockers:

- Действующий пользовательский запрет API.
- Frozen experiment contract ещё не подготовлен.
- Provider request для этого пакета ещё не построен и не проверен.

В модуле нет sending capability. Runtime integration, реальная доступность API,
обёртка провайдера/её размер и научное качество ответов не проверялись.
`scientific_acceptance=not_evaluated`. Положительный source admission не отменяет
отказы production pipeline и не объявляет четыре прежних вопроса допустимыми.

## Tests run

- Финальный affected suite по admission, source context и query qualifiers:
  **85 passed**, `output/commit_check_20261026/dsc_admission_v03.xml`.
- Первый новый test file: 15 passed / 1 failed; первый overlapping affected run:
  84 passed / 1 failed. Lifecycle export выявил tuple/list serialization mismatch
  в diagnostic article/PDF identities. Исправлена JSON-представимость списка;
  научная policy/criteria не менялись. До реального run выполнен новый prepare_v02;
  prepare_v01 сохранён как история и не выдан за replay текущего кода.
- Constructed counterexamples: wrong author/year, отрицательный Mars-regolith
  вопрос, byline-role substitution, DSC только в abstract, условия вне M1,
  missing/misordered programme, unknown promotion, unproved mapping, malformed
  quotes, byte guard, input/output drift, exclusive paths, escaping и повторный
  export. Это development tests, не independent scientific accuracy.
- Ruff `app tests scripts`: passed. Mypy `app`: **174 source files**, no issues.
- Postflight: **1377 bindings**, **1359 unchanged parent bindings**, десять exact
  diagnostic spans, 12 сохранённых historical blockers, **7/7 unchanged packet
  files**. Два экспорта: **11/11 файлов byte-identical**.
- CLI два prepares, run и два exports: пять network-evidence файлов, все completed,
  connect/DNS/sendto attempts отсутствуют. Postflight тоже выполнен с запретом
  этих операций, attempts нет. Python audit hook не является OS/native firewall.
- Chrome 156 offline: 14 check rows, раздельные source/network statuses,
  expandable spans/history, search/reset, все review links прошли. Копия пакета
  содержит пять contexts, TAC один документ / восемь колонок; PDF click открыл
  physical page 4. JS errors и remote HTTP requests отсутствуют. Снимки overview,
  programme evidence и historical/current diagnostics просмотрены.

## Артефакты и повтор

`output/records_stage48_20261027/`:

- `prepared_v02`, `run_v01`, `review_v01`, `review_repeat_v01`.
- `review_v01/review.html` — все текущие checks, новый source admission, старые
  отказы и отдельные execution blockers. `report.json` — полный результат.
- `packet/` — byte-identical stage47 со всеми цитатами, sources, исходными PDF
  links и TAC HTML. Scope неизменен: одна Istomina article; missing/unimplemented
  TAC/Terms fields сохранены. XLSX и ручной per-Term workflow не добавлены.
- Browser/postflight JSON, network evidence и screenshots.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.dsc_admission --network-evidence output/stage48_new_network.json export --source output/records_stage48_20261027/run_v01 --output-dir output/stage48_new_review
```

Использовать новые output/evidence paths. Source/code/runtime drift останавливает
replay явно. Generated artifacts и private PDF не входят в Git; установленная
среда записана отдельно и не объявляется portable/transitive lockfile.

Limitations: policy ограничена этим вопросом и finite English source cues.
Нет общей entailment/completeness проверки, независимой научной оценки, полного
application suite, provider-envelope validation, runtime sending или API/model/
retrieval/embedding/DB calls. Unknown не является отсутствием научных данных.

Verdict: пункт 2 выполнен без API. Новый source packet прошёл проверку пригодности
для подготовки frozen-эксперимента. Следующий пункт — зафиксировать experiment
contract: question/context/prompt/model/budget/criteria и сохранение request,
raw response, usage, errors и hashes. Реальные вызовы остаются запрещены.
