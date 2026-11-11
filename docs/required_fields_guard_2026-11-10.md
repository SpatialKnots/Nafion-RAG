# Экспериментальная защита выдачи и фиксация версии

10 ноября 2026. User «Давай» после предложения подключить finite checks к
экспериментальной выдаче, проверить offline и зафиксировать версию для новых
вопросов. На отдельный provenance-вопрос пользователь ответил: «Я подготовлю
эталоны заранее». Новые вопросы/эталоны ещё не получены, модель на них не запускалась.

Changed:

- `RequiredFieldsGuardProvider` вызывает один переданный provider, затем
  применяет существующую карту/check. При mapped unresolved requirements
  возвращает whole-answer abstention; исходный parsed result, evidence и
  причину передаёт отдельному обязательному review collector. Без retry,
  редактирования, частичной выдачи или изменения native результата.
- Явные причины: отсутствующий ожидаемый literal, нераспознанная формулировка/
  привязка, неоднозначные source candidates, неустановленная finite source
  связь. Ни одна из них не выдаётся за доказанную научную ошибку/отсутствие в
  литературе. Unsupported families сохраняют прежний ответ и статус
  `not_evaluated`; заполненные поля не становятся semantic acceptance.
- Новый API **POST `/answer/experimental/required-fields`** принимает прежние
  query/collection/top_k/method/style/language/library options. Использует
  прежний service/retrieval/filters/admission с explicit requirement-guided
  provider и guard, read-only repeatable-read transaction + rollback.
  Клиент не может подставить evidence/native result/gold/path.
- Страница **`/ui/answer/experimental/required-fields`**: явная кнопка одной
  генерации, статус «Недостаточно подтверждений», отдельно разворачиваются
  причины и исходный ответ с меткой «не допущен». JSON/API response хранит
  review для вызывающей стороны. Нового серверного архива/persistence нет.
- В `app/main.py` добавлены только импорт и регистрация router. Обычный
  `/answer`, factory, prompt/schema/thresholds/index/PDF/DB не переписаны.
  Исторический main сохранён до изменения; ровно одна old-source mapping
  проверяет прежний hash по `pre_edit_v01/main.py`. Старые manifests/results
  не исправлялись, остальные прежние app assets совпали.

Tests run:

- **555 passed**, в том числе33 новых guard/API/UI controls; Ruff6/full mypy
  app208 passed. Один прежний Starlette/httpx deprecation warning сохранён.
- Реальный ASGI TestClient с synthetic search/session/provider проверил
  withholding, full field retention, unknown wording, native abstention,
  preprovider refusal, errors/no retry, request filters/library scope,
  transaction rollback, client extras422, escaping/UI GET0 generation и
  прежний `/answer` без включения guard. Это не live model/DB test.
- Unit controls: сохранность native, one-call/language forwarding, callback
  tampering/storage failure, invalid contracts/citations, missing/ambiguous/
  unknown field reasons. Native collector errors не скрываются и не повторяются.
- Initial16 unit tests passed. Первый full run551passed/1failed: `731Wh/kg`
  ошибочно классифицировалось как не найденное число вместо unknown wording.
  Исправлена только причина диагностики; withholding не менялся. Старый JUnit
  и source before-fix сохранены. Добавлены три numeric-unit controls. Import
  ordering и B023 lint diagnostics исправлены до финального555-test run.
- Offline replay пяти saved native: Satoh07/Satoh06/Fan10/Satoh03 сохранены;
  Fan05 удержан за unresolved causal mechanism. Native result/text/claims
  прежние. Это **не четыре научно правильных ответа**, не новые API/model
  outputs и не гарантия отсутствия ложных удержаний.
- Новый статус удержания виден в сохранённых fragments фактического renderer.
  HTML15 details checked; browser layout визуально не проверялся. Проверены
  source/version/parent/old-main mappings, source/default-route text unchanged
  кроме двух router lines, old native5, deterministic review replay.
- Real model/OAuth/DB calls0, новых attempt slots0; external-network denials0.
  Все прежние live scopes остаются закрыты. Full repository suite, production
  DB, fresh PDF/browser visual/deployment/running-server reload не выполнялись.

Фиксация для новых вопросов:

- Freeze ID: `27def498b8580a6922808d8eca08b0a5c6fb76f0eaa46657fc1cc279deacedd3`.
  Snapshot включает app208 Python files +YAML, guard tests/runner/protocol,
  transfer guide/template, pyproject, actual selected package versions и
  nonsecret provider settings. Это локальная версия dirty workspace, не git
  release или полный environment lock.
- Пользователь подготовит эталоны **до просмотра новых ответов**, отдельно от
  общего рабочего каталога. Публично нужны вопросы и статьи, private reference
  SHA256/author/provenance commitment до inference, без содержания эталонов.
  Hash не доказывает научную правильность/авторство, отдельное хранение не
  является проверенной ACL. Само обещание не считается полученным эталоном.
- [Руководство](records/guard_transfer_v0.1/README.md) и
  [пустая регистрация](records/guard_transfer_v0.1/registration_template.json)
  готовы. Registered questions0/reference contents0/model budget0. Этот transfer
  check не подменяет прежний отдельный24-task pilot и не объявлен независимой
  оценкой без cohort/commitment/assessment.
- До новых outputs зафиксировать весь cohort. Оценивать raw answers и guarded
  delivery на одном model draw, все refusals/unsupported scopes в denominator.
  Корректные ответы, удержанные из-за unknown wording, учитываются как false
  holds по человеческому эталону. Не настраивать код по новым test cases до
  окончания оценки. Новая статья и новый вопрос к известной статье различаются.

Limitations:

Конечная грамматика может удержать корректную альтернативную формулировку;
unknown label этого риска не отменяет. Связи вне map не проверены. В частности,
сохранение четырёх текущих результатов не подтверждает causal/synthesis claims
в них. Новые научные показатели/обобщение на проект пока не измерены.

Verdict:

Экспериментальный путь выдачи подключён и проверен offline. Default route
сохранён, исходные ответы доступны отдельно от решения guard. Версия
зафиксирована; проверка на новых вопросах ожидает пользовательских вопросов/
источников и заранее подготовленных частных эталонов. План75%/independent
evaluation остаются без изменения, автоматических новых вызовов нет.

- [Пять результатов после защиты и исходные тексты](../output/required_fields_guard_20261110/review_v01/review.html)
- [Replay report](../output/required_fields_guard_20261110/review_v01/report.json)
- [Зафиксированная версия](../output/required_fields_guard_20261110/freeze_v01/version.json)
- [Проверка integrity](../output/required_fields_guard_20261110/verification_v01/result.json)
- [Протокол](records/required_fields_guard_2026-11-10_v0.1.md)
