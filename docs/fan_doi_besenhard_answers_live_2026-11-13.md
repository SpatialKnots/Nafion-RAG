# ARIADNE: реальные ответы после rewriting, 13 ноября 2026

Changed:

Пользователь `Да, запускай` разрешил предъявленный scope26answerPOST+26OAuth,
по одной попытке, GigaChat-2-Max/1200 output tokens/120s per HTTP operation,
без retry/fallback/continuation. Новый runner отдельно связал разрешение с26
конкретными native SHA и frozen plans; старые dispatch_allowed=false contracts
и исходные native requests не переписывались. Приложение, параметры, prompt,
научные правила, parser/rewriting adapter, PDF/БД/индекс не изменялись.

Выполнены ровно26 actual model POST+26OAuth. Все26 API HTTP200;22answered,
3provider_abstained(F1/F7/D4),1insufficient_confirmation(D10) — модель ответила,
но finite required-fields guard удержал выдачу. Четыре случая F6/B2/B3/B8
остались исходными rewrite rejections без answer call. Всего30registered cases.
Returned model всех26 —GigaChat-2-Max:2.0.30.01, finish_reason stop. Все26новых
slots и allowances закрыты, остатокmodel/OAuth0; повторов/ремонта/дедупликации0.

Доступность не равна правильности. На этом наборе ранее6→26ready-unsent,
теперь получены22выданных ответа; нельзя писать «реальных ответов было6, стало22»,
поскольку baseline6 был только подготовлен, а не отправлен в этом сравнении.

Reported answer usage247371prompt+4345completion=251716total tokens;
precached20998 входят в prompt count. Стоимость неизвестна. Сумма со старым
отдельно закрытым rewriting scope здесь не выдаётся за новые answer calls.

После закрытия выполнена качественная post-hoc сверка30 случаев с исходными
эталонами, исходными/cited контекстами и оригинальными PDF. Оценку выполнил
exposed implementation assistant, не независимый эксперт. Численные баллы0–2
и accuracy не назначались: prospectively agreed scientific acceptance score
для этого прогона отсутствует. Классы — предварительные наблюдения, не шкала
принятия и не утверждение о полной корректности каждого слова:

-11выданных ответов: ядро согласуется с источниками, с отдельно указанными
  оговорками (включая плохое обозначение единицы B1).
-7выданных ответов: неполнота или проблемы формулировок.
-4выданных ответа: существенные расхождения F8/D8/D9/B6.
-3отказа модели,1withheld result,4rewrite rejections показаны отдельно.

Основные source findings:

-F8: F/O10.7/2.4/4.0 относится к катодной CEI на LCP, а не содержанию фтора
  в электролитах. Нужные22/1.8/0M находятся в PDF5 и не попали в выбранный
  контекст; модель ответила на соседнюю величину по PDF7.
-D8: уязвимость TFEE к окислению >4.5В перенесена в объяснение HFE50→67об.%.
  Для HFE источник обсуждает solubility/miscibility,0.73molkg и DMC/Li3.96.
-D9: после50циклов источник даёт186мА·ч/г и93.4%, а ответ сообщает около200
  и не сообщает retention. Абзац186/93.4 отсутствует в выбранном контексте.
-B6: диапазон1.3–1.0В напечатан в PDF3, но raw extraction и actual prompt
  содержат1.3 ±1.0В; ответ воспроизвёл искажение. Это traced glyph/input failure,
  не выдуманный моделью знак. Кроме того,122Ahkg относится к cathode material,
  а сравнение с целой Li-ion батареей в ответе сглаживает basis.
-F1/F7/D4: соответствующие нужные абзацы существуют в PDF9/PDF3/PDF4, но
  locators/целые source windows отсутствуют в selected evidence/actual prompt.
  Эти отказы не доказывают отсутствие ответов в статье.
-F9: правильный порядок DFT выгодности дан, но все четыре запрошенных числа
  отсутствуют. Fig6 визуально подтверждает−2.10/−0.19/−0.28/+0.11эВ.
-D10: native в основном правильно связывает784Whkg с NCM523 cathode и называет
  volatility/1.52molkg. Guard отмечает source_support_not_established_by_finite_grammar,
  а не установленную научную ошибку. Интегрирование кривых и точная mass basis
  всё ещё не разъяснены. Исходный native сохранён отдельно от невыданного ответа.
-D2: число310mPa·s подтверждено на PDF6. Исходный user reference page hint
  PDF3–4 неполон для этого значения; эталон и исходный файл не редактировались.

Tests run:

-12 новых synthetic scope/read-guard controls passed, Scoped Ruff четырёх новых
  scripts/одного test passed. Старые full suite/59/5 tests не заявляются новым run.
-26actual saved-native API replays в свежих процессах полностью воспроизвели
  HTTP status/body и точные native bytes, без реальных model/OAuth/DB queries.
-104 live-vs-prepared byte comparisons:26trace/sources/articles/request sets
  точны. Проверены26unique actual attempt slots, result/ledger/closure/input
  manifests; все модели/OAuth по1на случай, постпроверки input hashes verified,
  network/reference denials0.
-25оригинальных PDF-страниц извлечены для post-hoc source cache;34точных
  raw-span witnesses привязаны к PDF SHA/page-text SHA/offsets и наличию locator/
  whole quote в selected/cited evidence/actual prompt. Такое присутствие не
  объявляется автоматическим scientific entailment validator.
-6полных source pages визуально просмотрены: BesenhardPDF3, DoiPDF4–7,
  FanPDF6. Poppler images и оригинальные тексты сохранены, originals неизменны.
-199local links/images в основном и assessment HTML существуют. Browser
  execution/layout не проверялись. Final verification имеет отдельные bindings.

Diagnostics retained:

Один initial E501 в первичном review exporter исправлен до export. В assessment
первый locator F5 ожидал знак% непосредственно после20, хотя source использует
общую единицу после списка20/80/60–85/95%; D2 locator не учитывал буквальный Li+.
Первоначальный script сохранён assessment_attempt_v01.py; поправлены только
locators.29E501 в длинных notes исправлены переносом строк с проверенным полным
AST equality; сами notes и функции не менялись. Финальные locators/Ruff прошли.
Ни приложение, ни ответы, ни старые manifests ради этого не ремонтировались.

MuPDF выдавал content-stream/colorspace diagnostics при широком Doi text probe;
они остались в terminal evidence. Отдельный PDF6 probe сохранён в
mupdf_page6_all_streams.txt и сам этих ошибок не воспроизвёл. Пустой
mupdf_extract_stderr.txt не доказывает отсутствие warnings: часть шла в stdout.
Poppler stderr сохранены: Doi Symbol/ArialUnicode display-font diagnostics,
Fan Invalid Font Weight warnings. PNG созданы с exit0 и визуально проверены;
«PDF без ошибок» или general extraction fidelity не заявляется.

Limitations:

Это exposed development comparison по3известным статьям, не независимая
экспертная scientific acceptance/общая accuracy. Source witnesses/сравнение
с эталонами не доказывают полноту всей литературы. Fullpytest/mypy/browser/
deployment не запускались. Native/API/refs/отказы сохранены без ремонта.
Новых вызовов сверх26answer+26OAuth не было; rewrite scope30/30 остаётся прежним
закрытым scope. Все дальнейшие live вызовы требуют нового отдельно заданного scope.

Verdict:

Разрешённая серия26ответов и содержательная сверка завершены. Rewriting улучшил
допуск, но остаются потеря нужных source paragraphs, подмена quantity/condition/
solvent frames и искажение PDF symbols. Следующая обоснованная работа — отдельный
офлайн-разбор этих слоёв, не автоматический новый live trial. План75%, accuracy null.

Итоговая содержательная сверка:
`output/fan_doi_besenhard_answer_live_20261113/assessment_v01/review.html`.
Полные исходные ответы/эталоны:
`output/fan_doi_besenhard_answer_live_20261113/review_v01/review.html`.
Контроль закрытия/replay/links:
`output/fan_doi_besenhard_answer_live_20261113/final_verification_v01/report.json`.
