# ARIADNE: Fan / Doi / Besenhard, подготовка проверки 13 ноября 2026

Changed:

Пользователь передал `Ariadne_QA_Fan_Doi_Besenhard_30.md` и разрешил начинать
проверку. В отдельном ответе выбрал существующий корпус с указанием статьи,
как в предыдущей серии. Предложение об отдельных корпусах внутри документа
не применялось автоматически. Оригинальные байты сохранены без правок;
SHA256: `6bffbb42184856f8331fb4c457bb818774a237c22b5ed1f6c019f6ab8f8386c4`.

Зафиксированы30 вопросов F1..F10/D1..D10/B1..B10. Сохранены точные исходные
формулировки/символьные позиции и отдельно объявленный префикс статьи/года.
Эталоны, предложенная шкала0–2 и подсказки источников находятся вне дерева
inference. Реальные worker-процессы ограничены audit hook; эталоны им не переданы.
Implementation assistant прочитал документ до подготовки; слепая проверка не
заявляется. Авторство/метод составления/участие LLM/экспертная проверка не объявлены.
Fan уже использовалась ранее, как прямо отмечает пользовательский файл;
корпус имеет предыдущую development exposure. Независимость источников не заявлена.

Кандидат `dab6dc133dc8bc65b6f3e02e0c4d194b3a5f3160969dc317006ddfe6476aecca`,
commit `270263efcf48c6f6e5381b3126a0a158420c9299`. Все247 app/resource/pyproject
привязок совпали с прежним freeze. Код приложения, ресурсы, промпты, поиск,
нормализация, научная логика, PDF, БД и индекс не менялись. Добавлены только
подготовщик/его явно объявленная коррекция, verifier, синтетические тесты и записи.
Существовавший untracked `data/terms_pipeline_config.json` не изменялся.

Выполнены30 фактических подготовок через `/answer/experimental/required-fields`:
collection literature, hybrid_cross_lingual, top5, claims, русский язык,
отдельный свежий процесс на вопрос, read-only repeatable-read/rollback.

| Статья | Подготовлены к будущей отправке | Отказ до модели |
| --- | ---: | ---: |
| Fan | 2 | 8 |
| Doi | 4 | 6 |
| Besenhard | 0 | 10 |
| Всего | 6 | 24 |

Допущены F3,F9,D2,D3,D6,D7. Шесть точных native requests:164913bytes суммарно,
максимальный35434bytes, каждый ниже100000-byte ceiling. Запросы не отправлялись.
Все30 выбранных evidence-наборов соответствуют указанной статье. У24 отказов
API HTTP200/status insufficient_evidence; причина adequacy —
`insufficient_distinctive_term_coverage`. Это результат фильтра, а не доказательство
отсутствия ответа в самой статье. Вопросы не переформулировались ради допуска.

Tests run:

- 12 focused synthetic tests passed: точные вопросы/позиции, отсутствие private
  text/page hints в question records, неверный порядок/дубли/неполные marker blocks,
  запрет чтения эталонов и узкое разрешение pinned inventory для hash verification.
- Scoped Ruff трёх новых scripts/двух новых tests passed. Полный pytest/mypy не
  запускались; результаты прежнего full suite не выдаются за новую проверку.
- Все30 question spans, API inputs, contracts/manifests/native digests проверены.
  Заново извлечены17 уникальных выбранных PDF-страниц,106 source-page observations;
  точные page text/raw quote/hash совпали. Проверены SHA трёх оригинальных PDF.
- Проверены123 local links HTML review. Browser/layout/PDF visual QA не запускались.
- Все завершённые preparation contracts содержат network/reference denials0.
  Фактических model/OAuth calls/slots0.

Сохранены неудачи:8 initial parser tests passed с PytestCacheWarning; первый
worker F1 остановился на чрезмерном read guard; отдельный execution_overlay_v02
разрешил только hashing pinned source-only inventory, исходный freeze не переписан.
Sandbox SELECT1 получил Windows10013/Permission denied; вне sandbox SELECT1
вернул1. Точные зависшие процессы остановлены; partial artifacts сохранены.
Batch parent затем TimeoutExpired при ожидании D8, хотя D8 уже сохранил полный
контракт/manifest/API-отказ. Причина аномального отрицательного remaining timeout
неизвестна, exit code D8 не восстановлен. D8 не повторялся; продолжены D9..B10.
Итоговая полнота подтверждена30 индивидуальными artifacts, а не вымышленным
успешным исходным batch. Подробности: diagnostics_v01/notes.md в output каталоге.
Прежний StarletteDeprecationWarning при импорте TestClient сохранён.

Limitations:

Нет новых реальных ответов модели, научных баллов, оценки provider compliance
или общего scientific accuracy. Предложенная в файле шкала0–2 сохранена как
данные, acceptance threshold не придуман; отказы/transport failures нужно
показывать отдельно от фактической точности выданных ответов. Продукт не
дорабатывался на этом наборе. Нельзя считать6 ready-unsent шестью верными ответами.

Verdict:

Приёмка и подготовка30 случаев завершены. Основное наблюдаемое препятствие —
24 отказа до модели. Для следующего этапа подготовлен конкретный scope ровно
на F3,F9,D2,D3,D6,D7: не более6 model POST и6 OAuth, по1/1 на вопрос,
GigaChat-2-Max/1200 output tokens/120s per HTTP operation, без повторов,
fallbacks/continuations; стоимость неизвестна. Новый live allowance пока0;
требуется разрешение по п.5 прежнего separate-set acceptance protocol после
фиксации конкретных запросов. Все старые allowances остаются закрытыми.
План75% не изменён.

Материалы:
- `output/fan_doi_besenhard_20261113/review_v01/review.html`
- `output/fan_doi_besenhard_20261113/verification_v01/report.json`
- `output/fan_doi_besenhard_20261113/verification_v01/prospective_live_scope.json`
- `docs/records/fan_doi_besenhard_preparation_2026-11-13_v0.1.md`
