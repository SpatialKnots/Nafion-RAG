# ARIADNE: offline-отбор до feature-window cutoff

2 ноября 2026 года, Asia/Yekaterinburg. Продолжение
[retrieval ablation](retrieval_ablation_2026-10-31.md). Итерация завершена;
production ranking/gate не изменены. Полное исправление не достигнуто.

Changed:

- По просьбе пользователя сохранён [query rewriting](query_rewriting_2026-11-02.md)
  как отдельный будущий эксперимент. Ссылки добавлены в roadmap, архитектурную
  память и AGENTS.md. LLM rewriter не реализован и не вызывался.
- До измерения записаны protocol и 22 constructed controls в `docs/records/`.
  Новый `scripts/retrieval_window_selection.py` реализует два offline-only
  source qualifiers в конечной области запроса о зависимости морфологии частиц
  дисперсии Nafion от растворителя. Применимость определяется только исходным
  вопросом, по пяти общим семействам понятий прежнего expansion candidate.
- `body_coverage` требует все пять понятий в raw full_text, без title/snippet.
  `local_relation` дополнительно требует их и dependency cue в одном предложении
  без распознанных negation/future/question/mixed-material cues. Это предложения
  отбора, не научное подтверждение связи, владельца условий или выполнения опыта.
- После существующих legacy ranking/article diversity candidate делает stable
  priority partition до обрезания feature window; тот же приоритет сохраняется
  внутри результата feature scorer. Размеры окон, final top-5 и все дальнейшие
  diversity/evidence selection/adequacy functions остаются прежними. Источники
  не внедряются, результаты/score/raw text не переписываются; reference outcomes,
  article IDs, DOI, названия работ и номера страниц не входят в алгоритм.
- Прогнаны все 76 frozen cases × четыре прежних arms × два qualifiers:
  **608 сравнений**, каждое выполнено дважды (**1216 candidate service executions**).
  Это replay сохранённых каналов, не новые retrieval/DB/embedding вызовы.
  304 полных baseline replay выполнены отдельно. Все новые кандидаты остались
  вне `app/`, рабочее поведение не переключалось.
- Оригинальные `review_v01`/manifest сохранены. Отдельное presentation amendment
  `review_v02` добавляет полные before/after traces и точные вытесненные тексты,
  не повторяя эксперимент и не меняя метрики. Итоговый HTML:
  `output/retrieval_window_selection_20261102/review_v02/review.html`.

Результаты:

| Исходный frozen arm | Original RU, before → body / local | RU paraphrase, before → body / local | EN paraphrase, before → body / local |
| --- | --- | --- | --- |
| baseline | 0 → 0 / 0 | 0 → 0 / 0 | 0 → 0 / 0 |
| ligatures | 0 → 0 / 0 | 0 → 0 / 0 | 3 → 3 / 3 |
| expansion | 0 → 0 / 0 | 0 → 0 / 0 | 0 → 0 / 0 |
| combined | 1 → 4 / 1 | 1 → 4 / 1 | 4 → 4 / 4 |

Это число из восьми прежних exact Kim windows в final generation evidence.
Окна exposed, не независимые эксперименты/эталоны. Для двух RU combined случаев
body возвращает три дополнительных окна: fixed-concentration solvent-ratio
series, constant-ratio concentration control, Figure4 caption. Sample form
сохраняется. Остальные четыре окна не восстановлены; никакой полноты ответа
или сохранения всех научных условий из этого числа не следует. Потерь этих
восьми anchors в данной итерации нет.

Важная новая граница: в обоих RU combined cases прежний gate после нового отбора
меняет `adequate=true` на `false`, boundary становится `insufficient_evidence`
вместо остановки перед generation. Для исходного вопроса coverage падает
с 7/9 до 1/9, matched term остаётся только `nafion`, reason —
`insufficient_distinctive_term_coverage`. Новые selected sources англоязычные;
required concepts/relations для этого вопроса по-прежнему пусты. Значит,
восстановленные anchors ещё не обеспечивают даже допуска к модели. Это
наблюдение cross-lingual lexical gate, не независимая научная оценка ложного
отказа или достаточности всех выбранных источников. Gate не обходился.

`body_coverage` меняет identity/order evidence в четырёх comparisons:
original и RU paraphrase, arms expansion/combined. Expansion заменяет по три
source records, combined — по четыре. У original combined вытеснены четыре
фрагмента двух прежних работ; все их тексты и добавленные фрагменты видны
в review_v02. Их неизвестная релевантность не превращена в negative labels.
Имеющиеся fixture-positive article identities не потеряны, но эти метки
относятся к другим, неизменённым случаям: это не проверка безопасности нового
morphology scope. 584 out-of-scope traces точно совпали с frozen baseline.

Проверяемая отдельная post-hoc source observation: в original combined/body
финальные E3 и E5 имеют разные article IDs, один DOI `10.1021/mz3005204`,
PDF pages3–4 и одинаковый SHA256 raw evidence:
`718049d3562ea6f3a8817c6910f498393d31c750775db385b373a309899ad908`.
Один зарегистрирован под title `priority3_e2e_upload`; само это имя не означает
искусственный scientific text. Raw text содержит статью Welch; его не заменяли.
Все 33 PDF hashes различны. Это точный повтор текста в выдаче, не доказанное
тождество PDF-файлов; дедупликация по источникам здесь не реализована.

`local_relation` не квалифицирует ни один raw candidate в 12 scoped frozen
query/arm inputs; final evidence нигде не меняет. Контрольные примеры показывают
цену ограничений:

| Qualifier | Qualified positive controls | False qualifications | False refusals |
| --- | ---: | ---: | ---: |
| body_coverage | 7 | 11 | 0 |
| local_relation | 5 | 2 | 2 |

Всего controls22, positives7/negatives15, authored by assistant до нового
измерения. Local пропускает анафору/implicit relation, но принимает
нераспознанный другой материал и absence cue `Evidence is lacking`.
Это development observations, не scientific false-answer rates.
Finite blacklist нельзя считать общим распознаванием отрицаний/материалов.
Неизменённый конфликт qext044 declared-negative gate admission сохранён;
новый алгоритм его не исправляет. Новых ответов модели нет.

Tests run:

- **199 affected tests passed** (34 новых) в `tests_v01.xml`; отдельно
  **2 новых accounting tests passed** в `tests_accounting_v01.xml`.
  Итого201 различных тестов,36 новых. Preflight34 не прибавляется повторно.
- Ruff шести новых source/test/QA files passed. 304 baseline full-trace /
  recorded-boundary replay совпали;608 candidates совпали каждый со своим
  действительным повторным выполнением. Corrupted raw source и corrupted
  diversification boundary отклонены ожидаемыми проверками.
- Проверены33 original PDF SHA256 и8 anchors свежей PyMuPDF extraction;
  296 bindings экспериментального пакета и299 bindings итогового presentation
  report совпали. Старые manifests/hashes не переписывались, pdftoppm не запускался.
- Static HTML QA:33 TAC rows,8 согласованных колонок,41 существующий PDF/page
  link к33 оригиналам, full expandable TAC/before/after/diagnostics и search
  implementation. Неизвестные поля сохранены. QA: `qa_v01.json`.
- Ранний тест ошибочно пытался менять frozen SearchResult:1 failed/33 passed;
  fixture исправлен через dataclasses.replace, алгоритм не менялся.
  Начальные10 E501 устранены форматированием до измерения. Read-only rg path
  errors и эти failures отдельно сохранены в `failed_attempts_v01.json`.

Limitations:

- Всё — exposed development на прежнем snapshot, а не независимая оценка.
  Scientific acceptance/accuracy остаются not_established/null; HTTP/model
  поведение и полезность будущих ответов не измерены.
- Исследована конечная семья morphology questions. Общий H/Li/температурный/
  composition ownership validator не реализован. Same-sentence cues и chunk
  co-location не устанавливают принадлежность свойств/условий. Abbreviations,
  cross-sentence context и неявные связи могут оставаться unresolved.
- Корпусные каналы не искались заново: это сравнение выбора на frozen candidates,
  не новое измерение search recall или unbiased latency benchmark.
- Browser execution, новая визуальная проверка PDF, full suite и mypy не
  выполнялись. Static search checks не объявляются browser verification.
- App/runtime/index/PDF/prompt/public schema/thresholds не изменены. Реальные
  DB/search/embedding/model/OAuth calls, native requests и новые slots:0.
  Cache/ORM repeated-request defect и rollout остаются открытыми.

Verdict:

Отдельный эксперимент завершён. Перенос source-cue priority до cutoff может
вернуть часть известных фрагментов при неизменных окнах, но слабый кандидат
даёт ложные qualifications на controls, вытесняет другие источники и приводит
RU combined к pre-provider refusal. Строгий кандидат недостаточно полон и тоже
не обеспечивает семантическую безопасность. **Ни один вариант не внедрять.**

Следующая разработка — отдельный frozen offline дизайн cross-lingual
requested-relation/adequacy проверки: сохранять исходные требования и проверять
их по RU/EN source-local evidence, с scope/ownership/negation, false-refusal
controls и exact-source redundancy diagnostics. Не снижать threshold, не
добавлять только Nafion как достаточный сигнал и не обходить gate ради Kim.
Query rewriting остаётся отдельным последующим экспериментом.

Независимая научная оценка по решению пользователя остаётся открытой до новых
эталонов. **План качества ответов:75% работ.** Все live budgets закрыты;
автоматического resend/new call нет.
