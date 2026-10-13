# Архитектура и стратегия прав

**Версия:** 1.1. **Дата:** 6 октября 2026 года. **Часовой пояс:** Asia/Yekaterinburg.


## Сохранение задела
Python/FastAPI/PostgreSQL/Alembic, существующий ingestion/retrieval и UI. Новые extraction/review функции — внутри монолита. Model Gateway, graph DB и микросервисы не нужны без измеренной причины.

Начало — versioned sidecar JSON с hashes и ссылками на PDF. Production schema изменяется малыми миграциями после принятия схемы; старые structured_facts остаются отдельным кандидатным слоем.

## Минимальная Scientific Record
record_id; sample_id_local; material_raw и при необходимости normalized; property; transport_species; value_raw; scalar/range/bound; operator; approximate; uncertainty при наличии; units raw/normalized; conditions; method при наличии; data_origin; field_evidence; transformations; extraction_run; status/reasons; reviewer_history.

Обязательные условия зависят от выбранной conductivity. Не создавать видимость сведений, отсутствующих в источнике.

Evidence: document/PDF hash, page/range, source type, selected text layer, exact span/snippet; table row/column identifiers при восстановимой структуре; bbox только если достоверен. Сохранять raw и transformation registry.

## Статусы
candidate → needs_review / machine_checks_passed / rejected.
human_confirmed — только после решения эксперта; исправление создаёт новую ревизию, не переписывает историю.

not_found_in_context означает отсутствие в доступном контексте, не доказанное отсутствие в статье. not_reported требует определения и проверки соответствующей области источника. ambiguous отличается от пустого значения.

## Verification Engine первого года
Ограниченные проверяемые маршруты:
1. Значение/образец явно связаны в предложении либо строке поддерживаемой таблицы.
2. Условие связано с этой записью в пределах выбранного scope; соседнее значение не наследует его автоматически.
3. Unit/value/operator согласованы с заранее выбранным реестром.
4. Data origin классифицирован по явным свидетельствам: experimental, calculated, literature_reference, unknown.
5. Поля и связи обеспечены evidence; неизвестная или неоднозначная обязательная связь блокирует допуск.

Checks возвращают причины, версии и статус. Не считать наличие нужных слов достаточной проверкой связи. Deterministic checks не означают универсальную научную верификацию; поддерживаемые правила и пределы описываются явно.

Противоречия между публикациями, обобщённая confidence calibration и универсальная domain adaptation — stretch/research. Повторная проверка одной моделью может помогать, но не является независимым доказательством.

## Локальная модель
Проверить максимум две кандидатные конфигурации на development/validation, поставить одну. Зафиксировать weights hash, лицензии, quantization, context, prompt, runtime и параметры. Не обещать произвольную 70B и длинный контекст на двух RTX 3090.

## Таблицы
Core: заранее перечисленные простые layouts с явным заголовком, единицами и строками образцов. Сравнить готовый parser на собственных таблицах; не заменять весь pipeline без приёмки. Потери detection учитывать в end-to-end recall. Графики и сложные таблицы вне обязательного scope.

## IP: предложенная схема, не установленные права
До договора нужен snapshot Background: код/история, авторы, лицензии, схемы, данные, ранее созданные gold и документы. Новые результаты — потенциальный Foreground, состав и права определяются договором, а не датой файла автоматически.

Verification Engine — кандидат на know-how. Возможное open-core разделение зависит от авторских прав, ранее опубликованных материалов, лицензий и договорных условий. Нельзя обещать закрытость уже опубликованного содержания или исключительное личное владение результатами.

Юридическое согласование: организация, организатор, допустимость сторонних компонентов, публикации, новые данные, права и коммерциализация. Эта концепция не является правовым заключением.

## Сохранность и эксплуатация
Оригинальные PDF неизменяемы. Схемы, units, chunking, scoring и thresholds не менять молча. Backup перед migration, restore test, pinned dependencies, diagnostics и rollback. Закрытые документы не отправлять внешнему API без разрешённого режима.

