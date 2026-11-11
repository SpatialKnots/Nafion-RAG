# ARIADNE: query rewriting на20 Satoh/Fan вопросах

10 ноября2026, Asia/Yekaterinburg.

Changed:

- По прямому запросу пользователя проведён отдельный development experiment:
  максимум20 rewrite+20 answer POST/40 OAuth, по одной попытке на stage/case,
  без retries/fallback/continuation. Предыдущие scopes не открывались.
- Добавлен экспериментальный CLI adapter, без изменений default app/runtime,
  API/schema/DB/index/PDF/thresholds.20 question-only запросов зафиксированы до
  вызовов. Rewriter видел исходный вопрос, article label и locked identifiers;
  исходных статей, эталонов, page hints и старых ответов в его входах нет.
- LLM вернула English question/keywords/requirements. Из20 outputs17 прошли
  автоматическую schema/identity/numeric проверку,3 отклонены из-за пустых
  keyword slots: Fan03/05 —12 пустых строк, Fan08 —3 пустых из12. Никаких repairs
  или повторных отправок. После exposed-agent смыслового review дополнительно
  отклонены Satoh01/02/07 (ether→ester, di-/triether→di-/triester) и Fan07
  (post-charge hold→soak, неоднозначная операция). Приняты13, rejected7 остаются
  в знаменателе20. Многие принятые keywords/requirements избыточны; отмечены
  в review, сохранены без pruning. Requirements diagnostic only, не gate.
- В13 случаях English question+keywords участвуют в existing source-reference
  rank_context и evidence selection внутри той же uniquely resolved статьи.
  Top_k5/first-chunk retention/raw sources/layers/filters/dedup/budgets сохранены.
  Adequacy использует прежние thresholds на English question, сохраняет исходные
  required-concept/relation vetoes и baseline diagnosis. Это явно изменённая
  экспериментальная admission policy, не semantic entailment. Итоговая модель
  получает исходный русский вопрос и прежним способом оформленные raw evidence.
- Все13 preparations достигли native boundary, потом actual ASGI /answer:
  11 answered, Fan02 provider abstention, Fan09 HTTP502. Fan09 native message
  имеет пустой content и не содержит role=assistant; прежний validator правильно
  отклонил output. Native/API сохранены, повтор не делался. Все33 responses
  returned GigaChat-2-Max:2.0.30.01/finish_reason=stop; stop не гарантирует schema.
- Ровно20 rewrite POST+13 answer POST и33 OAuth/new slots. Лимиты обоих stages
  и всех33 slots закрыты, неиспользованные7 answer allowances истекли. Native
  reuse предусмотрен для exact duplicate input, фактически0 cases. Перед13
  answer POST actual trace/sources/articles/native совпали с frozen preparations.

Tests run:

-36 distinct focused tests:35 в основном final run+1 reader regression,
  включая12 новых. Ruff7 final files passed. Первый запуск25 passed/10 tmpdir
  setup errors из-за отсутствующего parent; original JUnit сохранён.
- Canonical meaning-map reader ошибочно требовал insertion order, несмотря на
  sort_keys serialization. Initial freeze и один prepare worker остановились
  до поиска; старые runner/freeze/outputs не менялись. Separate v02 reader
  собирает список по frozen IDs, собственный source hash включён в plan freeze;
 20 новых read-only preparations/rollback в fresh processes, failures/logs v01
  сохранены. Regression проверяет порядок и unchanged plan hashes.
-20 original questions/case IDs совпадают с baseline; declared old/new input
  bindings/manifests и target PDF scopes verified.203 app Python/9 YAML не
  менялись. Actual docs glossary сейчас byte-identical frozen packaged copy;
  manifest — declared bindings, не весь environment/historical authenticity.
-33 native response SHA/current ledgers/slot closures/20 rewrite request hashes,
 13 exact ASGI trace/source/article/native replays verified. Network denials0;
  child workers forbidden reference/prior output access0. Это не live retry.
-20 HTML sections/112 links checked;8 raw source anchors с hash/offsets.
  Все46 selected raw chunks и8 anchors присутствуют в13 actual prompts после
  existing whitespace-only cleaning. Первоначальный multiline literal test
  дал0/8, поскольку runtime collapses whitespace; original diagnostic сохранён,
  separate verification_v02 содержит точный raw→prompt span mapping8/8.
- Assessment v01/Ruff2 long-line diagnostics сохранены; separate v02 меняет
  только wrapping/path. Summary/cases/anchors identical, source/manifest bindings
  обеих версий verified. Новых модельных вызовов при review/verification0.

Measured results:

|Показатель|До|Эксперимент|
|---|---:|---:|
|Выданных ответов, все20 cases|4|11|
|Новые ответы относительно baseline|—|8|
|Ранее answered, теперь недоступен|—|Fan09, пустой provider output|
|Вызовов модели ответа|5|13|
|Вызовов query rewriting|0|20|
|Приёмка перевода после schema+agent review|—|13/20|
|Reference-page range gaps среди тех же13 accepted cases|10|6|

Offline ablation на accepted13, **только диагностический gate, не новые service
answers**: baseline5; только English ranking6; только English adequacy11;
ranking+English adequacy13. Основной прирост допуска связан с устранением
межъязыкового lexical mismatch; ranking дополнительно влияет. Это не изолированная
causal оценка качества ответов. Baseline использует ранее сохранённые model samples.

Предварительная exposed-assistant сверка: восстановлены численные ответы Satoh03/
05/08 и Fan04; Satoh06/10 передают основные эффекты с пропусками условий/сравнения;
Fan06 добавляет F/O comparison, но не всю composition/thickness информацию.
Satoh04 по-прежнему не включает страницы10–11 с основным механизмом, Fan01
неточно называет HFE/распределяет функции и теряет Methods9, Fan10 пропускает
знаменатель энергии total cathode/anode masses даже при наличии его в cited E4.
Fan02 теряет PDF2: actual prompt не содержит5.1/10.3 и модель отказывается.
11 answered не означает11 scientifically correct. Score/independent accuracy null.

Reported usage: rewrite2869+4519=7388 tokens, answer114247+1468=115715, всего123103.
Precaching отдельно:2056/7334 reported tokens; реальная стоимость неизвестна.
Суммы записанных timers:rewrite118.72s/answer215.70s. Они исключают process startup/
preflight hashing, не являются измерением production user latency.

Limitations:

- Это exposed20-case development cohort, не independent/new24-task pilot. Agent
  видел эталоны раньше, выполнил meaning review до ответов и post-hoc сравнение
  после закрытия scopes. Эксперимент не проверяет unattended rewriting.
- Tested intervention — translation+keyword ranking+English lexical admission;
  LLM requirements не проверяют completeness, semantic support или scientific
  validity. Entity/numeric validator не обнаруживает все смысловые подмены.
- Page-range overlap не доказывает quote presence/support. Все46 prompt chunks
  проверены отдельно. Полная экспертная проверка всех новых утверждений отсутствует.
- Fan02/07/08 supplements отсутствуют/Fan07 panel discrepancy сохранена.
  Fresh PDF extraction/visual/browser layout/full app suite/mypy не запускались;
  app default code не менялся, deployment/rollout нет.

Verdict:

Гипотеза поддержана для доступности ответов в этом bounded development experiment:
4→11 при13 принятых переводах. Одновременно выявлена необходимость semantic
контроля переписывания, улучшения ranking и контроля полноты итогового ответа.
Автоматическое включение не обосновано. Следующее улучшение — сузить rewrite
schema/лишние keyword expansions, использовать проверенный title/chemical context
для снятия ether/ester ambiguity, сохранив отдельную оценку и старый baseline.
Это будущий scope, текущие переводы/ответы не исправлялись. Общий план75%.

- [Все20 сравнений/переводы/raw native и API](../output/query_rewriting_20261110/review_v01/review.html)
- [Предварительное содержательное сравнение](../output/query_rewriting_20261110/assessment_v02/assessment.md)
- [Protocol](records/query_rewriting_experiment_2026-11-10_v0.1.md)
- [Canonical reader diagnostic](records/query_rewriting_reader_note_2026-11-10.md)
- [Raw→actual prompt verification](../output/query_rewriting_20261110/verification_v02/result.json)
