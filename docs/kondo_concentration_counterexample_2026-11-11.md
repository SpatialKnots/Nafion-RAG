# ARIADNE: контрпример универсальности концентрации Kondo07

Changed:

Пользователь «Супер. Давай далее» продолжил предложенный Kondo07. Полный
выбранный raw PDF2/3 уже содержит пример и базу отсчёта μ. Новый
concentration_counterexample.py и ветка quantitative_facts связывают два
соль/растворитель мольных отношения с соответствующими значениями μ,
общей печатной единицей, relative reference и modal descriptor conclusion.
Четыре raw-bound facts: limitation, две пары, author interpretation.
Один complete parent/F1 либо отказ, русский текст формирует сервер.

В источнике пороги обратимой интеркаляции Li+ для LiFSI/DEE и LiFSI/F3MEE
составляют1/1.6 и1/4.4 by mol соответственно; μLi+ —23.2 и24.1kJ mol−1
соответственно, названы авторами similar. База μ — LiFSI/DME1/10by mol из
явного reference sentence на PDF2. Порядок respectively, обе записи соли,
три μ-symbol occurrences, Li+, два разных растворителя, разные SI figure
указатели и reference-before-example согласуются. Metal-prefix binding соли
ограничен этим finite monovalent-code grammar, не общей проверкой формул.

Неравенство положительных мольных отношений проверяется точными Fraction
из Decimal: разные записи1/1.6 и2/3.2 не считаются разными концентрациями.
В молярность/массовую долю отношения не переводятся. Новые численные значения
или допуск близости μ не рассчитываются; similar остаётся оценкой авторов,
не независимой оценкой погрешности. Печатная общая kJ mol−1 единица привязана
к обоим числам; can be a descriptor не заменено universal law. Контрпример
не объявляется доказательством отсутствия влияния концентрации вообще.

Вопрос содержит why/negative/universal. Отдельная ветка распознаёт только
точный шаблон «Почему сама по себе концентрация SALT не является универсальным
критерием подавления совместной интеркаляции?». После единственной проверенной
библиографической ссылки и стандартного preamble требуется fullmatch всего
тела. Это не общая отмена negative/why guards; дополнительные условия,
обратная формулировка и иные вопросы не допускаются. Фактический вопрос и
prompt не меняются. Source status guards прежние. Ownership false,
arithmetic null, required-fields guard not_evaluated.

Полные оригинальные PDF2/3 свежо отрендерены Poppler и визуально просмотрены:
база μ и контрпример. Raw остаётся точным, достаточно прежних NFKC/
dehyphenation/whitespace правил; новых glyph aliases/resources/config нет.
SI S7d/S9c сохранены как печатные указатели, supplementary материалы заново
не проверялись. Retrieval/ranking/thresholds/UI/DB/PDF/index/schema прежние.

Tests run:

- Focused59passed с первой попытки; affected1007passed (59 новых), один прежний
  Starlette/httpx warning, network denials0. Synthetic ASGI checks вне sandbox.
- Полный mypy app221 файлов passed; финальный Ruff6 Python-файлов passed.
- Проверены неправильные соли/ионы/μ/ratio/basis, нулевые знаменатели,
  эквивалентные рациональные отношения, одинаковые растворители, shared unit,
  respectively, relative→absolute, can→universal, prior/hypothetical/negative/
  bibliographic scopes, неизвестные query constraints, exact-question boundary,
  cross-parent assembly, ambiguity, record/raw drift и generic source codes.
- Четыре actual experimental API SYNTHETIC контроля: F1→200/answered,
  abstention→200/insufficient, prose→502, wrong citation→502; read-only/
  rollback, guard not_evaluated. Дополнительно три synthetic service исхода.
- All30 actual-service comparison_v01:24→25 ready-unsent, новый Kondo07;
  все30 retrieval traces и остальные29 full results прежние,24 prior native
  exact. Это готовность входов, не25 научно верных ответов модели.
- 81 historical actual-service сценарий сохраняет full results, пять native
  inputs exact. Открытые development данные, не независимая оценка.
- Свежая actual API preparation с настоящим поиском/registry: read-only/
  rollback, trace/native exact, registry diagnostics0, network denials0;
  8976bytes, SHA0db3bd9080b94a84087d05aabde91bcf1daf0e86424b927993dd421324bfc3d8.
  Остановка до transport; реальные model/OAuth/newslots0.
- Exporter проверил40 raw-anchor observations,4facts/pairing/reference/status,
  полные PDF2/3 против raw, source support на PDF3/reference fields на PDF2,
  неизменный PDF SHA через frozen bindings и оба UI adapters. HTML30 case
  rows/4fact details. Initial source probe eligible; провалов тестов не было.

Limitations:

Конечная grammar по открытым development источникам, не общий semantic/causal
или theorem validator. Близость μ не принята независимо, chemical formula
и SI не переоценивались. Новые статьи/реальные F-ID ответы/независимая scientific
accuracy/browser layout/полный repository suite/wheel/deployment не проверены.
Вопросы/prompt/thresholds/UI/DB/PDF/index/resources/config/API schema прежние.
Старые live scopes закрыты; новых нет.

Verdict:

Kondo07 подготовлен через ограниченный source counterexample, с сохранением
мольных отношений, порядка значений, relative basis и can be.25/30
ready-unsent; пять отказов:3explanation,2limits. Следующий отдельный этап —
Kondo09, достаточность FSI-derived SEI для подавления совместной интеркаляции.
Независимая оценка открыта; план75% прежний.

Отчёт: output/kondo_concentration_counterexample_20261111/review_v01/review.html.
