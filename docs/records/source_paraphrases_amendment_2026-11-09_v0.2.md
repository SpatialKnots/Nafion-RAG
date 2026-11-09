# Дополнение v0.2: guards новых source alternatives

9 ноября 2026. Исходные protocol, freeze_v01, compare_v01, controls_v01.json,
controls_before.xml, controls_after_v01.xml и tests_affected_v01.xml сохраняются.
v0.1 прошла 664 затронутых теста и 81 полное сравнение с baseline, но
последующий отдельный adverse probe выявил 9 constructed false admissions:
по три для префиксов Previous work reported that / For another sample и
неправильного регистра Li / LiPF6 / W. `adverse_v01.xml` содержит 9 failures.
Это недостаток новых ветвей, не эмпирическая частота ошибок на литературе.

До исправления фиксируются дополнительные controls и правила v0.2:

- только для новых alternatives запретить явные previous/prior work/study,
  reported that/according to literature и another/other/different sample,
  material или experiment в проверяемом локальном prefix;
- сохранить точный регистр химических формул Li, O2, LiPF6, EC/DEC и символа W;
  английские слова могут распознаваться без учёта регистра;
- исходные legacy patterns, их guards, extraction и metadata не менять;
- версия активной новой grammar становится `source_paraphrases_v0.2`;
- сохранить девять положительных перефразировок и 36 прежних negatives;
  controls_v02.json добавляет девять negatives, не переписывая controls_v01.json;
- заново выполнить затронутые tests, Ruff/mypy, 81 service comparison и native
  checks. Изменения не настраиваются по новым gold или новым ответам модели.

Prefix guard остаётся конечным и консервативным, не решает общую принадлежность
результата. Могут остаться ложные отказы при длинных/сложных конструкциях.
Scientific ownership/independent evaluation не объявляются завершёнными.
Все live scopes закрыты; новых реальных model/OAuth calls и slots нет.
