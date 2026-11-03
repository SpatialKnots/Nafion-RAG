# ARIADNE: доступный внешний эталон и границы независимой оценки

31 октября 2026 года, Asia/Yekaterinburg.

Changed:

- Пользователь выбрал именно независимую научную оценку из пункта4 исходного
  плана. О происхождении исходного эталона Kim сообщил дословно «я составил»;
  о наличии новых случаев — «Пока есть только эталон Kim».
- Эти сведения сохранены отдельной поздней декларацией. Исходный reference,
  исходные четыре пункта ответа, старые null metadata, реальные request/API/
  native response и consumed slot не переписаны. Составление без LLM,
  квалификация автора, метод разметки, отдельная научная проверка и знакомство
  с outputs при исходной разметке из этих слов не выводятся.
- Подготовлен конкретный ретроспективный пакет n=1:
  `output/independent_answer_review_20261031/review_v01/review.html`.
  Содержит оригинальный вопрос/reference, исходный HTTP200/answered и два claims,
  источники, отдельные source caveats и прежнее сравнение ассистента. В прежнем
  сравнении все четыре reference items отмечены not_addressed; это сохраняется
  как assistant post-hoc assessment, не превращается в независимую экспертизу.
- Новый driver `scripts/prepare_independent_answer_review.py` выполняет только
  повторную проверку файлов/источников и упаковку. App/runtime не менялись;
  новых model/OAuth/DB calls, requests и slots —0. Исторический вызов не повторялся.

Tests run:

- Ruff нового driver passed. Оригинальные preparation/authorized/live/source/
  live-review manifests совпали; original user-reference bytes одинаковы в
  preparation, authorized inputs и новом пакете. Native request/response SHA256
  и полный original API body совпали с историческими.
- Fresh PyMuPDF extraction подтвердила8 exact Kim windows и9 selected pages;
  проверены SHA256 четырёх scoped original PDF. Проверены274 текущие привязки.
- Static HTML QA: четыре TAC rows, восемь согласованных колонок,17 существующих
  local links; неизвестные поля не дополнены догадками. Browser execution и
  новая визуальная проверка PDF не выполнялись. Новые unit tests для обратимой
  упаковки не писались; прежние165 tests здесь не объявляются повторно запущенными.

Limitations:

- Обнаружен реальный historical input drift: `pdftoppm.exe` имеет current SHA256
  `8a7c0aa1cb5b4da26a922938693a87a6f9b5ee589aaeca705b8d44a42aac1eb7`
  вместо `f473853a5a1a08ad1b10708cb65ba98aa04276b42dbdd7cfd01625ba1e72784d`.
  Причина неизвестна; review этот binary не менял и не выполняет. Первый запуск
  корректно остановился на старом guard. Все остальные268 historical bindings
  совпали. Отдельный drift record требует именно эти old/current hashes; старые
  manifests/expected hashes сохранены. Original historical rendering не
  воспроизведён; archived PNG manifests совпали, текст проверен свежим PyMuPDF.
- Один exposed case не содержит контрольных отказов. Другого внешнего набора
  сейчас не предоставлено. Размер и критерий закрытия общего этапа заранее не
  ограничены одним случаем. Минимальное число случаев здесь не выдумывается.
- Позднее указание авторства не подтверждает retrospective blindness или
  независимую научную проверку. Independent scientific metrics/acceptance
  остаются null/not_established; общая accuracy не измерена.

Verdict:

Доступный случай полностью сохранён и повторно проверен; готов конкретный
single-case review. По исходному
`docs/records/user_reference_preparation_protocol_v0.1.md` один candidate сам
по себе не означает100% плана. После подготовки review пользователь явно
выбрал: **«Оставить этап открытым до новых эталонов»**. Решение сохранено в
`docs/records/independent_answer_review_user_decision_v0.1.json`; исходный frozen
пакет с состоянием до этого решения не переписан. Пункт4 остаётся открытым,
**прогресс75% работ**, single-case pilot не объявлен полным этапом.
Никакое решение об объёме не должно означать general accuracy или научную
приёмку системы; отрицательный результат модели сохраняется в любом случае.
