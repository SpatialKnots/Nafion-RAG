# ARIADNE: область применимости порога μ в Kondo10

Changed:

Пользователь «Давай далее» продолжил Kondo10. До app edits свежий actual DB
read-only/RR/rollback capture полного пула разрешённых статей воспроизвёл
все30 прежних top5/role metadata. Нужная Conclusion PDF5 отсутствовала в
прежнем top5. Узкая threshold_transfer_limits роль сохраняет неизменённый
объект существующего пула той же статьи; top5/scores/filters/lookup count
прежние. Retention не является admission или scientific ownership.

Новый threshold_scope.py +quantitative_facts/source_reference ветки связывают
шесть facts: generally applicable к различным типам LiFSI-based электролитов,
возможный сдвиг при существенном изменении SEI и четыре исходных контекста:
SEI-forming additives; extremely unstable solvent/salt for reduction;
passivating binders; functional surface coatings. Сохраняются три исходных
типа электролитов и inorganic-rich SEI на graphite negative electrodes.
Все четыре μ-symbol occurrences, три катиона, electrode scope и salt metal
prefix должны согласоваться. Последнее — finite spelling check, не общая
проверка chemical formula. Один contiguous full block/parent, F1 либо отказ.

May be shifted не превращено в обязательный или измеренный сдвиг. Не заданы
численный универсальный порог, знак или величина изменения. Generally
applicable не заменено универсальностью для любых солей. Отрицательный ответ
на proof/universal question опирается на явную авторскую оговорку, а не на
отсутствие найденных сведений. Полный вопрос должен совпасть с finite шаблоном
после single-author/year bibliography/preamble; другие proof/universal/negative
запросы не разблокируются. Status exception — только exact may be shifted
в уже распознанном block. Source/question/prompt не переписываются.

Все values/условия/raw offsets/SHA/type и русский серверный текст
пересчитываются при F1 selection; ownership false, arithmetic null,
required-fields guard not_evaluated. Полная оригинальная PDF5 свежо
отрендерена Poppler и визуально просмотрена. Прежних NFKC/dehyphenation/
whitespace правил достаточно; новых glyph aliases/resources/config нет.

Tests run:

- Focused48passed. Финальный affected_v03:1127passed (48 новых), один прежний
  Starlette/httpx warning, network denials0. Synthetic ASGI checks вне sandbox.
- Финальный полный mypy app223 файлов passed; Ruff8 Python-файлов passed.
- Проверены may→always/cannot, generally→universally, changed→unchanged,
  wrong μ/ion/salt/electrode, loss/replacement of each shift context, reduction
  versus oxidation, currentness/status, extra query requirements, incomplete/
  cross-parent/subsection source, ambiguity, record/raw tampering/generic codes.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- Финальный all30 actual-service comparison_v02:26→27 ready-unsent, только
  Kondo10. Остальные29 full retrieval/service results и26 prior native exact.
  Ranking-only и contract-only отказывают; вместе ready. Все пять выбранных
  строк — неизменённые объекты зарегистрированного article pool.
- Финальная regression_v03:81 historical actual-service сценарий/five native
  exact. Предыдущие v01/v02 сохранены; не используются как final version check.
  Exposed regression, не независимая научная оценка.
- Финальная fresh_api_v02 actual preparation с настоящим поиском/registry:
  read-only/rollback, trace/native exact, registry diagnostics0, network denials0;
  13858bytes, SHA72326bdd159889fc63725475ead94bb18bbf410a19dcc133e1d0f5c663a4a9b3.
  То же native у preliminary fresh_api_v01. Остановка до transport; реальные
  model/OAuth/newslots0.
- Exporter проверил38 raw-anchor observations,6facts/scope/modal/factors,
  полный PDF5 против raw/support, неизменный PDF SHA, pool/top5/ablations,
  оба UI adapters и30caseJSON/27native exact между preliminaryv01/finalv02.
  HTML30 case rows/6fact details.

Сохранённая ошибка типизации:

При initial48/1127passed mypy дал57 diagnostics в quantitative_facts: новый
плоский matches list задал несовместимый inferred type для одноимённого
вложенного списка в последующих ветках. Исходный module, полный mypy log,
driver/fresh-driver snapshots и diagnosis сохранены в typing_attempt_v01.
Имя заменено уникальным threshold_candidates. После отображения этого имени
в matches AST точно совпадает с исходным; научная логика, значения и текст не
менялись. Это подтверждено и byte-exact повтором всех30 cases/27native.

Первая maintenance AST normalization использовала уже существовавшее в другой
ветке имя scope_matches и остановилась с AssertionError до writes. Повторный
старый driver безопасно отказался перезаписывать comparison_v01; intermediate
regression_v02/affected_v02 выполнились на прежнем коде и сохранены. Final
comparison_v02/regression_v03/affected_v03/fresh_api_v02 проверены после
успешного переименования. Historical source hashes сопоставлены со snapshot,
старые manifests не переписывались. Ошибка mypy не выдана за успешную проверку;
провалов pytest не было.

Limitations:

Конечная source grammar по открытым development источникам, не общий proof/
semantic/causal validator. Source caveat не принят как независимое измерение
сдвига. Новые статьи/реальные F-ID ответы/независимая scientific accuracy/
browser layout/полный repository suite/wheel/deployment не проверены.
Вопросы/prompt/thresholds/UI/DB/PDF/index/resources/config/API schema прежние;
ranking изменён указанной узкой ролью. Старые live scopes закрыты; новых нет.

Verdict:

Kondo10 подготовлен с сохранением generally/may и границ LiFSI-based scope.
27/30 ready-unsent; остаются три explanation refusals Nambu05/07/08.
Следующий отдельный этап — Nambu05, молярная концентрация чистого растворителя
и связь с плотностью/молярной массой. Независимая оценка открыта; план75% прежний.

Отчёт: output/kondo_threshold_scope_20261111/review_v01/review.html.
