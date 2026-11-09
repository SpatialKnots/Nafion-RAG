# Ограниченный добор контекста условий

Changed:

Пользователь выбрал пункт 3. В `/answer` добавлен
`condition_context_completion_v0.2`: перед generation evidence можно добавить
один неизменённый raw-фрагмент из той же работы, коллекции, source type и
текстового слоя. Применяются исходные SearchFilters, включая библиотеку.
Первое поддержанное семейство — уже распознанная таблица равновесного
набухания/энтальпии Li-Nafion. Для других семейств новый SQL не выполняется.

Выбранная таблица должна однозначно определять работу и слой. Запрос к БД
ограничен двумя предшествующими страницами до начала таблицы, целиком
попадающими в окно chunks, 12 строками и одной контрольной строкой переполнения.
Переполнение, разные методики, другой материал/слой/работа, отрицание или будущее
измерение в распознанной конструкции оставляют контекст unresolved.
Шаблон требует упорядоченные experimental/material/Li-exchange/swelling-method/
initial-water признаки. Это конечная текстовая грамматика, не универсальная
проверка смысла или владельца величины.

Прежние результаты, score, порядок и citation IDs сохранены. Дополнительный
бюджет generation evidence явно равен одному объекту; retrieval top_k остаётся
прежним. Не вытесняются другие условия. Metadata сохраняет кандидатов, причину,
границы, исходные SHA и raw offsets. На этапе выбора citation_id у support
ещё пуст; итоговый evidence связывается через article/chunk/pages, в Q03 — E6.
Ни одно число автоматически не становится условием строки таблицы или другой
операции. Gate thresholds, БД, PDF, индекс и public top-level fields прежние.

В Q03 добавляется прежний chunk PDF2–3. Он содержит experimental context PDF2:
Nafion 115, гравиметрическое измерение набухания и сообщение производителя об
исходной воде в растворителях. Таблица остаётся в E1 PDF3–4. Покрытие исходных
страниц Q03 выросло с [3,4] до [2,3,4]; обе ранее сохранённые reference quotes
остались. Это доступность источника, не научный score. Больше raw текста
увеличивает unsent request с 59029 до 75391 байта; token/cost эффект не измерен.

Tests run:

- 581 тест (544 прежних +37 новых), включая два actual ASGI source-delivery/
  abstention controls и UI source provenance. Все ответы новых controls SYNTHETIC.
  Внешняя сеть запрещена audit guard, denials0. Starlette/httpx deprecation warning.
- 162 actual service frozen-channel executions: пять точных pre-change replays,
  пять новых, два текущих прогона каждого из 76 прежних случаев. Прежние 76
  полных service результатов идентичны; четыре других вопроса trace/native
  байт-в-байт прежние. Индекс/SQL retrieval каналы не переизмерялись в replay.
- Свежий question-only Q03: реальная локальная БД, repeatable-read/read-only,
  rollback. Trace и native bytes совпали с офлайн-прогоном; registry diagnostics,
  external network denials и gold-read denials0. Ровно один simulated OAuth и
  один unsent native boundary в этом процессе; реальных model/OAuth/slots0.
- Ruff десяти изменённых/новых implementation/test/driver файлов, mypy app191
  passed. Финальный verifier отдельно проверяет источники, manifests, JUnit,
  свежие PDF pages и текущие bindings.

Основной обзор: `output/condition_context_completion_20261106/review_final_v02/review.html`.
Полный TAC snapshot33 работ/eight columns/search/исходные PDF ссылки включён;
отсутствующие поля явно помечены. Coverage остальных четырёх случаев в таблице —
server raw parent inventory; новое буквальное попадание в native проверено для Q03.

Сохранены неудачные попытки: freeze_v01 не создал вложенный каталог до записи;
freeze_v02 завершён до app edits. Первый sandbox fresh_v01 не подключился к
localhost:5432 (Permission denied); outside fresh_v02 read-only завершился.
Candidate/review v0.1 не узнал soft-hyphen/newline внутри слов; review_v01
остановился на проверке добавленного support. Amendment v0.2 и отдельные controls
добавляют opt-in joining с raw address mapping; defaults прежних fact recipes
не изменены. review_v02 и fresh_v03 показывают успешную доставку контекста.
После measurement добавлена только type annotation `candidates`, без изменения
выполнения; исходная версия и exact drift map сохранены. Неиспользованные imports
и первый mypy diagnostic сохранены в логе сессии. Final_v01 остановлен Ruff
на длинной строке verifier; лог сохранён, final_v02 отличается переносом строки
проверки scope и текущими bindings, а не новым измерением. Никаких старых guards
не заменяли.

Limitations:

Один ограниченный RU source pattern, не универсальный context completion.
Иные формулировки и формы/методы могут остаться unresolved. Scientific ownership,
полнота таблицы и качество нового ответа модели не подтверждены. Связь с
конкретными числами не установлена автоматически; raw context включает несколько
операций, которые модель должна различать. Browser/PDF visual/full suite,
concurrency/cache-ORM/deployment не проверены. Пункт 4 не входит в эту итерацию.

Verdict:

Доставка недостающего контекста Q03 реализована и проверена офлайн и на локальной
read-only БД. Live результат не измерен; все live бюджеты закрыты. Independent
scientific evaluation остаётся открытой; план качества ответов — 75% работ.
