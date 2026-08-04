# Приоритет 2: загрузка PDF и фоновые ingestion-задания

## Статус документа

Это подробный технический план для согласования. Описанные API, очередь, worker,
миграция и UI ещё не считаются реализованными.

План развивает второй этап из
`docs/backend_general_implementation_plan.md`. Он предполагает, что приоритет 1
будет завершён и загруженную статью можно будет открыть через безопасный PDF
endpoint. Если приоритет 1 ещё не реализован, приоритет 2 не должен скрыто
реализовывать его вместо отдельного согласования.

## 1. Цель этапа

Пользователь должен иметь возможность загрузить один или несколько PDF через
локальный web-интерфейс или API, получить идентификаторы заданий и наблюдать их
переход до конечного состояния без ручного запуска ingestion CLI.

Целевая цепочка:

```text
multipart upload
  -> потоковая валидация и SHA-256
  -> временный файл в пределах data_root
  -> проверка дубликата
  -> IngestionJob(status=queued)
  -> worker атомарно захватывает задание
  -> существующий extraction/OCR/chunking/classification pipeline
  -> Article + Page + PageTextLayer + Chunk
  -> IngestionJob(status=indexed | duplicate | failed)
  -> удаление только временного upload-файла
```

## 2. Проверенное текущее состояние

На момент подготовки плана:

- `ingest_pdf()` принимает локальный путь и выполняет весь pipeline синхронно;
- CLI поддерживает импорт одного PDF и последовательный импорт папки;
- оригинал копируется в `<data_root>/pdf/` и не изменяется;
- OCR-копия при необходимости создаётся в
  `<data_root>/processed/ocr/`;
- дубликат статьи определяется по уникальному `Article.checksum_sha256`;
- `ingest_pdf()` создаёт `IngestionJob` сразу со статусом `processing`;
- при успехе job получает `indexed`, при исключении — `failed`;
- существующая модель job хранит только `input_path`, `collection_id`, статус,
  сообщение об ошибке и временные отметки;
- job не хранит `article_id`, checksum, имя загруженного файла, размер, параметры
  OCR, worker lease или число попыток;
- worker является placeholder-процессом и только спит по 30 секунд;
- upload API, multipart-зависимость и UI загрузки отсутствуют;
- векторный индекс не обновляется автоматически после изменения корпуса.

Последний пункт является важным ограничением этапа: после успешного ingestion
новая статья сразу доступна exact search, но semantic/hybrid index до приоритета
3 может стать устаревшим и потребовать ручного перестроения.

## 3. Границы этапа

### Входит в реализацию

- multipart API для одного или нескольких PDF;
- потоковая запись upload без загрузки всего файла в память приложения;
- ограничения количества и размера файлов;
- проверка имени, расширения, MIME, PDF signature и структурной читаемости;
- вычисление SHA-256 во время записи;
- обнаружение уже индексированного и уже поставленного в очередь дубликата;
- миграция `ingestion_jobs` для воспроизводимой очереди;
- атомарный захват задания одним worker;
- повторная постановка зависшего задания после истечения lease;
- ограниченное число автоматических попыток;
- API статуса и списка заданий;
- минимальная страница загрузки и наблюдения за заданиями;
- сохранение существующего CLI-поведения;
- тесты, диагностика и эксплуатационная документация.

### Не входит в реализацию

- автоматическое перестроение semantic/vector index;
- распределённая очередь Redis, RabbitMQ, Celery или облачный broker;
- параллельная обработка одного PDF несколькими worker;
- удаление уже проиндексированных статей через upload API;
- редактирование метаданных статьи;
- загрузка по внешнему URL;
- рекурсивный импорт папок через web API;
- распаковка ZIP/RAR;
- антивирусное сканирование;
- аутентификация и многопользовательские квоты;
- изменение extraction, OCR, chunking или classification logic;
- использование LLM.

## 4. Основные решения

### 4.1. PostgreSQL как очередь

Для текущего локального масштаба отдельный broker не требуется. Таблица
`ingestion_jobs` используется как долговечная очередь, а PostgreSQL обеспечивает
атомарный захват через `SELECT ... FOR UPDATE SKIP LOCKED`.

Преимущества:

- используется существующая инфраструктура;
- состояние задания переживает перезапуск API и worker;
- транзакции и диагностика доступны в одной базе;
- не добавляется отдельный сетевой сервис.

Это решение должно быть повторно оценено в приоритете 7, если benchmark покажет,
что PostgreSQL-очередь стала ограничением.

### 4.2. Разделение upload, job и ingestion pipeline

Ответственность разделяется на три слоя:

```text
upload service
  принимает байты, валидирует, вычисляет checksum, создаёт staged file и job

queue service
  захватывает queued job, управляет lease, attempts и конечным статусом

ingestion service
  обрабатывает уже проверенный локальный PDF существующим научным pipeline
```

HTTP-слой не выполняет extraction или OCR. Он завершает запрос после надёжного
сохранения staged file и транзакционной постановки job в очередь.

### 4.3. Сохранение CLI

Существующие команды `ingestion file` и `ingestion folder` должны остаться
синхронными и сохранить текущий JSON-результат. Для этого `ingest_pdf()` следует
разделить на:

- внутреннюю операцию обработки PDF, не создающую второе queue job;
- синхронную CLI-обёртку с текущей семантикой;
- worker-обёртку, работающую с уже существующим job.

Один и тот же PDF не должен проходить через две независимые реализации
extraction/OCR/chunking.

## 5. Модель состояний задания

Разрешённые состояния:

```text
queued      принято и ожидает worker
processing  атомарно захвачено worker
indexed     статья, страницы и чанки успешно сохранены в PostgreSQL
duplicate   статья с тем же checksum уже существует
failed      обработка завершилась ошибкой или исчерпаны попытки
```

Переходы:

```text
upload -> duplicate
upload -> queued -> processing -> indexed
                            \-> duplicate
                            \-> queued      после recoverable error или stale lease
                            \-> failed      после permanent error или лимита attempts
```

Правила:

- `indexed`, `duplicate` и `failed` являются конечными состояниями этапа;
- `processing` устанавливается только в транзакции захвата worker;
- `attempt_count` увеличивается при каждом захвате;
- worker регулярно обновляет heartbeat для долгого OCR;
- stale `processing` можно вернуть в `queued`, если lease истёк и лимит попыток
  не исчерпан;
- после исчерпания попыток stale job становится `failed`;
- состояние нельзя произвольно менять через публичный API;
- `indexed` означает завершение индексирования в PostgreSQL, но не перестроение
  semantic/vector index.

## 6. Миграция базы данных

Планируется новая Alembic migration после `0002_dual_text_layers.py`.

### 6.1. Новые поля `ingestion_jobs`

```text
article_id          UUID NULL, FK articles.id ON DELETE SET NULL
original_filename   TEXT NULL
checksum_sha256     TEXT NULL
file_size_bytes     BIGINT NULL
force_ocr           BOOLEAN NOT NULL DEFAULT false
attempt_count       INTEGER NOT NULL DEFAULT 0
worker_id           TEXT NULL
heartbeat_at        TIMESTAMPTZ NULL
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
error_type          TEXT NULL
```

Существующее `input_path` остаётся внутренним путём staged file. Оно не
возвращается публичным API. Поле остаётся обязательным для совместимости со
старыми job; для немедленного `duplicate` допускается безопасное служебное
значение или, если аудит данных позволяет, поле переводится в nullable. Выбор
фиксируется до написания миграции после проверки реальных записей.

### 6.2. Ограничения и индексы

- check constraint на разрешённые значения `status` после проверки legacy rows;
- check constraint `attempt_count >= 0`;
- check constraint `file_size_bytes >= 0`, если значение задано;
- индекс `(status, created_at)` для FIFO claim;
- индекс по `checksum_sha256`;
- partial unique index активного обычного задания по checksum для состояний
  `queued` и `processing`, чтобы конкурентные upload не создавали две обработки;
- отдельное решение для `force_ocr=true`, чтобы явная OCR-переобработка не
  блокировалась обычным дубликатом.

До миграции нужно запросить все существующие значения `status` и проверить
наличие job с отсутствующими файлами. Миграция не должна угадывать их состояние.

### 6.3. Downgrade

Downgrade удаляет новые constraints, индексы и поля, не затрагивая статьи и PDF.
Перед downgrade оператор получает предупреждение, что аудит очереди и связь job
с article будут потеряны.

## 7. Хранение временных загрузок

### 7.1. Каталоги

```text
<data_root>/uploads/incoming/<upload_uuid>.part
<data_root>/uploads/queued/<job_uuid>.pdf
```

- `incoming` содержит только незавершённую запись текущего HTTP-запроса;
- после полной проверки файл атомарно переименовывается в `queued`;
- имя генерируется сервером и не зависит от имени пользователя;
- оригинальное пользовательское имя хранится отдельно только как метаданные;
- staged files являются внутренними и не выдаются через static route.

### 7.2. Потоковая запись

Файл читается блоками фиксированного размера. В одном проходе:

- считается число байт;
- обновляется SHA-256;
- проверяется превышение лимита;
- первые байты сохраняются для проверки `%PDF-`;
- данные записываются в `.part`.

После окончания записи:

- поток закрывается;
- проверяется допустимое расширение;
- проверяется заявленный MIME;
- проверяется PDF signature;
- PyMuPDF открывает документ и подтверждает, что он не повреждён, содержит хотя
  бы одну страницу и не требует неизвестного пароля;
- выполняется атомарное перемещение в `queued`.

Проверка структуры на upload-этапе не извлекает и не индексирует текст.

### 7.3. Очистка

- при ошибке валидации удаляется только созданный `.part`;
- при откате транзакции создания job удаляется соответствующий staged file;
- после `indexed` или `duplicate` worker удаляет staged file;
- после `failed` staged file сохраняется ограниченное время для диагностики и
  ручного retry, затем удаляется отдельной документированной cleanup-командой;
- cleanup работает только внутри `<data_root>/uploads` и проверяет resolved path;
- original PDF в `<data_root>/pdf` cleanup никогда не удаляет.

Автоматическая политика retention должна задаваться настройкой, а не скрытой
константой.

## 8. Валидация загрузки

### 8.1. Настройки

Добавить явные параметры в `Settings` и `.env.example`:

```text
UPLOAD_MAX_FILE_SIZE_MB=100
UPLOAD_MAX_FILES_PER_REQUEST=10
UPLOAD_READ_CHUNK_BYTES=1048576
INGESTION_POLL_SECONDS=2
INGESTION_LEASE_SECONDS=1200
INGESTION_HEARTBEAT_SECONDS=30
INGESTION_MAX_ATTEMPTS=3
INGESTION_FAILED_RETENTION_DAYS=7
INGESTION_WORKER_ID=<optional; generated when empty>
```

Фактические defaults должны быть подтверждены перед реализацией. Pydantic
валидация запрещает нулевые и отрицательные лимиты и требует, чтобы heartbeat
был заметно меньше lease.

### 8.2. Проверки файла

Обязательны одновременно:

- непустое имя;
- basename без доверия к директориям из client filename;
- расширение `.pdf` без учёта регистра;
- MIME из документированного списка, например `application/pdf` и безопасный
  fallback `application/octet-stream`;
- размер больше нуля и не выше лимита;
- начало файла `%PDF-`;
- успешное структурное открытие PyMuPDF;
- хотя бы одна страница;
- SHA-256 из 64 hex-символов.

MIME и расширение не считаются доказательством формата без signature и
структурной проверки.

### 8.3. Ограничение HTTP body

Проверка `Content-Length` используется как ранний отказ, но не считается
достаточной, потому что заголовок может отсутствовать или быть неверным.
Фактический лимит проверяется по прочитанным байтам каждого файла. Сервер
остаётся привязанным к `127.0.0.1`; публикация endpoint во внешнюю сеть без
аутентификации и reverse-proxy limits не поддерживается.

## 9. Дедупликация и идемпотентность

### 9.1. Уже индексированная статья

Если `Article.checksum_sha256` уже существует и `force_ocr=false`:

- новый ingestion не запускается;
- создаётся или возвращается диагностируемый результат `duplicate`;
- ответ содержит существующий `article_id`;
- staged file удаляется;
- существующий original PDF не перезаписывается.

### 9.2. Активное задание

Если job с тем же checksum уже находится в `queued` или `processing`:

- новый job не создаётся;
- API возвращает идентификатор существующего активного job;
- вновь загруженный staged file удаляется;
- конкурентная гонка закрывается partial unique index и обработкой конкретного
  `IntegrityError`, а не предварительным `SELECT` в одиночку.

### 9.3. `force_ocr`

`force_ocr=true` является явной операторской переобработкой и не должно
включаться по умолчанию в UI. Необходимо определить одно из двух поведений до
реализации:

1. разрешить одно активное forced-OCR job на checksum;
2. оставить forced OCR только в CLI и не принимать его публичным upload API.

Рекомендуемый вариант для первого релиза — второй: web upload остаётся
идемпотентным, а потенциально дорогая переобработка выполняется через
существующий CLI. Если `force_ocr` всё же включается в API, для него нужны
отдельные тесты гонок и явное подтверждение в интерфейсе.

## 10. Контракты API

### 10.1. Создание заданий

```http
POST /ingestion/uploads
Content-Type: multipart/form-data
```

Поля:

- `files`: от 1 до настроенного максимума PDF;
- `collection`: имя существующей коллекции, по умолчанию `literature`.

Успешный HTTP-статус — `202 Accepted`. Один файл создаёт один результат; batch
не объединяет научную обработку файлов в одну транзакцию.

Предлагаемый ответ:

```json
{
  "items": [
    {
      "job_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "original_filename": "paper.pdf",
      "status": "queued",
      "article_id": null,
      "checksum_sha256": "...",
      "file_size_bytes": 123456,
      "status_url": "/ingestion/jobs/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    }
  ]
}
```

Для уже активной загрузки возвращается существующий `job_id`; для уже
индексированной статьи item имеет `status=duplicate` и существующий
`article_id`.

Рекомендуемая batch-семантика:

- каждый файл валидируется независимо;
- валидные файлы ставятся в очередь;
- невалидные представлены item со статусом `rejected` только в ответе и не
  создают строку job;
- общий HTTP-статус остаётся `202`, если принят хотя бы один файл;
- если не принят ни один файл, вернуть `422` с массивом ошибок;
- порядок items соответствует порядку multipart parts.

`rejected` не является состоянием `IngestionJob`, потому что job для него не
создаётся.

### 10.2. Статус одного задания

```http
GET /ingestion/jobs/{job_id}
```

Предлагаемый ответ:

```json
{
  "job_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "original_filename": "paper.pdf",
  "collection": "literature",
  "status": "indexed",
  "article_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  "checksum_sha256": "...",
  "file_size_bytes": 123456,
  "attempt_count": 1,
  "error": null,
  "created_at": "2026-08-04T10:00:00Z",
  "started_at": "2026-08-04T10:00:02Z",
  "finished_at": "2026-08-04T10:00:11Z"
}
```

Публичный ответ не содержит `input_path`, `worker_id`, абсолютные пути, traceback
или командную строку OCR. Для `failed` поле `error` содержит стабильный code,
тип стадии и безопасное сообщение; полная диагностика остаётся в локальном
журнале и `error_type/error_message` базы.

### 10.3. Список заданий

```http
GET /ingestion/jobs?status=processing&limit=50&offset=0
```

- `status` опционален и принимает только разрешённые состояния;
- `limit` имеет небольшой default и жёсткую верхнюю границу;
- сортировка: новые сначала, с UUID как стабильным вторичным ключом;
- ответ содержит `items`, `limit`, `offset` и общее число подходящих job;
- endpoint предназначен для локальной диагностики и UI.

### 10.4. Повтор неуспешного задания

Рекомендуемый операторский endpoint:

```http
POST /ingestion/jobs/{job_id}/retry
```

Он доступен только для `failed`, только если staged file ещё существует и
находится в разрешённом upload-каталоге. Операция:

- очищает конечную ошибку;
- переводит job в `queued`;
- не обнуляет `attempt_count` без явного решения;
- не создаёт новый original PDF;
- возвращает `409`, если retry невозможен.

Если аутентификация отсутствует, endpoint остаётся только локальным и должен
быть явно отмечен как операторский.

## 11. Worker и конкурентность

### 11.1. Захват задания

Worker выполняет короткую транзакцию:

1. выбирает самый старый `queued` job через `FOR UPDATE SKIP LOCKED`;
2. устанавливает `processing`, `worker_id`, `started_at`, `heartbeat_at`;
3. увеличивает `attempt_count`;
4. commit;
5. обрабатывает PDF уже без удержания блокировки строки.

Два worker не могут получить один job. При отсутствии заданий процесс ждёт
настроенный poll interval без busy loop.

### 11.2. Heartbeat и lease

OCR может выполняться дольше обычного extraction. Worker обновляет
`heartbeat_at` отдельной короткой транзакцией или через контролируемый callback
между стадиями. Lease истекает только если heartbeat отсутствует дольше
`INGESTION_LEASE_SECONDS`.

Нельзя выбирать lease короче максимального периода, в течение которого текущий
pipeline не способен обновить heartbeat. Если OCR-команда блокирует callback,
lease должен учитывать `OCR_TIMEOUT_SECONDS` либо OCR runner должен сообщать
периодический heartbeat.

### 11.3. Восстановление после сбоя

При старте и затем периодически worker:

- находит `processing` job с истёкшим lease;
- проверяет число попыток;
- переводит его в `queued` или `failed`;
- очищает `worker_id`, но сохраняет диагностическое сообщение;
- не удаляет staged file до принятия решения;
- повторно проверяет Article checksum перед обработкой, поэтому успешный commit,
  после которого worker упал до обновления job, становится `duplicate`, а не
  второй статьёй.

### 11.4. Завершение процесса

Worker обрабатывает SIGINT/SIGTERM:

- перестаёт захватывать новые задания;
- даёт текущей операции завершиться в пределах документированного timeout;
- не помечает job успешным до commit статьи;
- при принудительном завершении оставляет lease для последующего recovery.

## 12. Транзакции и файловая согласованность

### 12.1. Постановка в очередь

Операция считается принятой только после двух событий:

1. staged PDF полностью проверен и атомарно перемещён в `queued`;
2. строка `IngestionJob(status=queued)` успешно committed.

Если DB commit не состоялся, staged file удаляется. Если процесс упал между
перемещением и commit, cleanup выявляет orphan по отсутствию job и возрасту.

### 12.2. Успешный ingestion

Article, pages, text layers, chunks, tags и конечное состояние job должны быть
согласованы. Refactor обязан сохранить текущую научную обработку. Если единая
длительная транзакция остаётся практически приемлемой, `indexed` фиксируется в
том же commit. Если pipeline требует промежуточного commit, это выносится на
отдельное согласование с явной схемой компенсации.

### 12.3. Ошибка ingestion

- научные записи текущей попытки откатываются;
- job обновляется до `failed` или повторно `queued` в отдельной короткой
  транзакции после rollback;
- `error_type` и ограниченное `error_message` сохраняются;
- traceback пишется в локальный журнал;
- original PDF, уже скопированный immutable store, не удаляется автоматически;
- staged file обрабатывается по retention policy.

## 13. Классификация ошибок и retry

### Permanent errors

Не повторять автоматически:

- файл перестал быть доступен или вышел за upload root;
- повреждённый/encrypted PDF;
- неизвестная коллекция;
- PDF не содержит страниц;
- OCR завершился, но usable text layer отсутствует;
- нарушение данных или constraint, не связанное с гонкой дубликата.

### Potentially recoverable errors

Допускают ограниченный retry:

- временная недоступность PostgreSQL;
- временный сбой запуска OCR command;
- worker был принудительно остановлен;
- lease истёк без сохранённой permanent error.

Классификация выполняется по конкретным типам исключений и стадиям. Broad
`except Exception` допускается только на внешней границе worker для гарантии
фиксации `failed`; он не должен скрывать traceback или превращать все ошибки в
retryable.

## 14. Изменения UI

Добавить локальную страницу, например `/ui/ingestion`:

- выбор одного или нескольких PDF;
- выбор коллекции из базы, а не свободный ввод;
- видимые лимиты числа и размера файлов;
- кнопка запуска загрузки;
- состояние загрузки каждого файла;
- таблица последних job со статусом, именем, attempts, временем и ошибкой;
- ссылка на статью и PDF после `indexed` или `duplicate`;
- автоматическое умеренное обновление только пока есть `queued/processing`;
- действие retry только для доступного failed job после явного подтверждения.

UI не должен показывать абсолютный `input_path` или server traceback. Ошибки
экранируются существующим `_html`.

## 15. План изменений по файлам

Ожидаемый набор:

```text
alembic/versions/0003_ingestion_queue.py
app/core/config.py
app/db/models.py
app/ingestion/service.py
app/ingestion/upload.py
app/ingestion/queue.py
app/ingestion/schemas.py
app/main.py
app/ui.py
app/workers/worker.py
tests/unit/test_upload_validation.py
tests/unit/test_ingestion_queue.py
tests/unit/test_ingestion_worker.py
tests/unit/test_api_ingestion.py
tests/unit/test_ingestion_cli.py
tests/unit/test_ui_routes.py
.env.example
pyproject.toml
README.md
docs/architecture.md
docs/data_model.md
docs/operations.md
```

Для FastAPI multipart parsing потребуется явная зависимость
`python-multipart`. Новые тяжёлые queue-фреймворки не планируются.

## 16. Пошаговая реализация

### Шаг 1. Зафиксировать baseline

- сохранить `git status` и не затрагивать пользовательские файлы;
- выполнить текущие тесты, Ruff и mypy;
- проверить Alembic head;
- получить распределение существующих `ingestion_jobs.status`;
- проверить существующие job paths и конечные состояния;
- выполнить один синхронный CLI ingestion на тестовом PDF;
- зафиксировать corpus manifest и retrieval baseline.

### Шаг 2. Согласовать и применить миграцию

- добавить новые nullable/default поля;
- backfill только значений, которые однозначно выводятся;
- добавить constraints после аудита legacy rows;
- добавить queue и dedup indexes;
- выполнить upgrade, schema inspection и downgrade/upgrade test на тестовой БД;
- не менять таблицы статей, страниц и чанков.

### Шаг 3. Добавить настройки и upload storage

- добавить валидируемые limits и worker settings;
- создать helper разрешённых upload-каталогов;
- реализовать безопасное серверное имя;
- реализовать потоковую запись, checksum и cleanup;
- запретить выход из `data_root/uploads`.

### Шаг 4. Реализовать валидацию PDF

- проверить число файлов и ранний Content-Length;
- проверить фактический размер при чтении;
- проверить extension, MIME, signature и PyMuPDF structure;
- классифицировать каждую ошибку стабильным code;
- гарантировать удаление `.part` после отказа.

### Шаг 5. Реализовать постановку job и дедупликацию

- проверить существующую Article по checksum;
- проверить active job;
- атомарно переместить staged file и создать queued row;
- обработать конкурентный `IntegrityError`;
- удалить лишний staged file;
- вернуть детерминированный item для каждого upload.

### Шаг 6. Разделить ingestion pipeline и управление job

- выделить общую операцию обработки без создания вложенного job;
- сохранить синхронный CLI wrapper;
- добавить worker wrapper для существующего queued job;
- передавать фактический `article_id` в job;
- сохранить текущие extraction/OCR/chunking/classification правила;
- добавить регрессионные тесты CLI и service.

### Шаг 7. Реализовать PostgreSQL worker

- реализовать FIFO claim через `SKIP LOCKED`;
- добавить worker identity, attempts и heartbeat;
- добавить stale lease recovery;
- классифицировать retryable/permanent errors;
- добавить graceful shutdown;
- удалить staged file только в документированных состояниях.

### Шаг 8. Добавить API

- `POST /ingestion/uploads`;
- `GET /ingestion/jobs/{job_id}`;
- `GET /ingestion/jobs`;
- после отдельного решения — `POST /ingestion/jobs/{job_id}/retry`;
- добавить Pydantic response models;
- не возвращать внутренние пути и tracebacks.

### Шаг 9. Добавить UI

- форму multiple upload;
- список коллекций;
- per-file validation/status;
- таблицу job;
- ссылки на результат после завершения;
- ограниченный polling без постоянной нагрузки.

### Шаг 10. Обновить диагностику и документацию

- doctor проверяет upload directories, write access и worker settings;
- operations описывает запуск одного worker, recovery и cleanup;
- architecture описывает queue flow и транзакционные границы;
- data model документирует новые поля и статусы;
- README содержит команды запуска и API-примеры;
- явно описать ручное перестроение vector index до приоритета 3.

### Шаг 11. Полная проверка

- выполнить целевые unit/integration tests;
- выполнить полный `pytest`;
- выполнить Ruff и mypy;
- проверить migration upgrade/downgrade/upgrade;
- запустить API и worker как отдельные процессы;
- загрузить реальный text PDF и проверить exact search;
- при наличии OCRmyPDF загрузить реальный scan и проверить OCR path;
- остановить worker во время job и проверить lease recovery;
- выполнить corpus manifest comparison и retrieval evaluation;
- проверить UI на desktop/mobile;
- проверить `git diff --check` и итоговый diff.

## 17. Тестовая матрица

### 17.1. Upload validation

- пустой файл отклоняется;
- файл выше лимита отклоняется во время чтения;
- превышение числа файлов отклоняется;
- `.txt` с PDF MIME отклоняется;
- `.pdf` без `%PDF-` отклоняется;
- PDF signature с повреждённой структурой отклоняется;
- encrypted PDF без пароля отклоняется с понятным code;
- mixed-case `.PDF` принимается;
- клиентский путь `../../paper.pdf` используется только как basename metadata;
- SHA-256 совпадает с независимым вычислением;
- `.part` удаляется после каждой ошибки.

### 17.2. Queue creation

- валидный PDF создаёт ровно один queued job и staged file;
- неизвестная collection не создаёт job;
- DB rollback удаляет staged file;
- уже индексированный checksum возвращает duplicate с article id;
- активный checksum возвращает существующий job id;
- два конкурентных upload не создают два активных job;
- response не раскрывает input path;
- batch сохраняет порядок items и изолирует ошибки файлов.

### 17.3. Worker claim

- worker получает самый старый queued job;
- `SKIP LOCKED` исключает двойной claim;
- claim устанавливает timestamps, worker id и увеличивает attempts;
- пустая очередь не создаёт busy loop;
- второй worker может взять другой job;
- graceful shutdown не захватывает новую работу.

### 17.4. Processing

- успешный text PDF создаёт article/pages/chunks и indexed job;
- OCR-required PDF вызывает существующий OCR pipeline;
- duplicate между upload и processing заканчивается duplicate;
- ошибка extraction откатывает научные записи и фиксирует failed job;
- CLI не создаёт вложенный job и сохраняет прежний контракт;
- original PDF checksum после обработки совпадает с upload checksum;
- staged file удаляется после success/duplicate;
- original store не удаляется после failed.

### 17.5. Lease и retry

- свежий heartbeat не восстанавливается;
- stale processing с оставшимися attempts возвращается в queued;
- stale processing на последней попытке становится failed;
- успешный article commit перед crash превращает повтор в duplicate;
- retry невозможен без staged file;
- permanent error не повторяется автоматически;
- recoverable error не превышает max attempts.

### 17.6. API

- multipart single и multiple uploads возвращают ожидаемые items;
- отсутствующий `files` возвращает `422`;
- неизвестный job возвращает `404`;
- status filter валидируется;
- pagination limits соблюдаются;
- timestamps сериализуются с timezone;
- error payload безопасен;
- публичные ответы не содержат абсолютных путей и traceback.

### 17.7. UI

- форма принимает multiple PDF;
- не-PDF получает локально понятную ошибку, подтверждённую сервером;
- queued/processing обновляются без перезагрузки всего приложения;
- indexed/duplicate дают ссылку на статью;
- failed показывает безопасную диагностику;
- длинные имена файлов не ломают layout;
- HTML metadata экранируется.

### 17.8. Migration

- upgrade сохраняет существующие job;
- legacy statuses проходят согласованный backfill/constraint;
- defaults применяются к новым строкам;
- indexes присутствуют;
- downgrade возвращает исходную схему;
- повторный upgrade проходит;
- migration не меняет articles/pages/chunks/PDF.

## 18. Критерии приёмки

Этап считается завершённым только при выполнении всех условий:

- один или несколько PDF можно загрузить через API и UI;
- upload request не ждёт завершения extraction/OCR;
- валидный файл получает долговечный queued job;
- worker обрабатывает job существующим ingestion pipeline;
- статусы `queued`, `processing`, `indexed`, `duplicate`, `failed` наблюдаемы;
- status response содержит article id после успеха или дубликата;
- повторная загрузка того же PDF не создаёт вторую статью;
- конкурентная загрузка не создаёт два активных job одного checksum;
- сбой worker не теряет job и восстанавливается через lease;
- invalid/corrupt/oversized файлы не попадают в corpus;
- временные файлы очищаются по документированным правилам;
- original PDF остаётся неизменным;
- CLI ingestion сохраняет прежнее поведение;
- полный test suite, Ruff и mypy проходит;
- миграция проверена upgrade/downgrade/upgrade;
- exact search находит новую статью после indexed;
- ограничение semantic/hybrid до приоритета 3 явно показано пользователю;
- документация соответствует реализации.

## 19. Риски и решения

### Долгий OCR превышает lease

Lease согласуется с OCR timeout, а worker обновляет heartbeat между стадиями или
во время внешнего процесса. Тест имитирует долгую обработку.

### Worker падает после commit статьи, но до обновления job

Повтор проверяет `Article.checksum_sha256` и завершает job как duplicate с
существующим `article_id`.

### DB commit падает после сохранения staged file

HTTP-слой удаляет файл при известном rollback. Периодический cleanup удаляет
старые orphan files, только если для них нет job.

### Большой multipart body исчерпывает диск

Используются ранний Content-Length check, фактический потоковый лимит, предел
числа файлов и локальная привязка сервера. Внешняя публикация без reverse proxy
не поддерживается.

### Рефакторинг меняет научную обработку

Общая функция сохраняет extraction/OCR/chunking/classification logic. Corpus
manifest и retrieval evaluation сравниваются до и после.

### Новый PDF делает vector index устаревшим

`indexed` на этом этапе означает PostgreSQL. UI и operations показывают, что
semantic/hybrid требуют ручного rebuild до реализации приоритета 3. Exact search
остаётся доступным.

### Ошибка раскрывает локальный путь

Внутренние пути и tracebacks остаются в локальном журнале. API использует
стабильные error codes и безопасные сообщения.

## 20. Откат

Откат приложения:

- остановить worker;
- запретить новые upload requests;
- дождаться или явно завершить active job;
- удалить новые API/UI routes и queue logic;
- вернуть синхронный CLI wrapper;
- выполнить Alembic downgrade только после экспорта job diagnostics.

Откат не удаляет статьи, страницы, чанки, original PDF или OCR PDF, созданные
успешными job. Временные staged files очищаются отдельной безопасной командой
внутри upload root.

## 21. Контрольная точка согласования

До начала реализации необходимо согласовать:

1. PostgreSQL как очередь без Redis/Celery;
2. маршруты `POST /ingestion/uploads`, `GET /ingestion/jobs/{job_id}` и
   `GET /ingestion/jobs`;
3. batch-семантику с независимым результатом каждого файла;
4. состав миграции `ingestion_jobs`;
5. lease, heartbeat и максимум попыток;
6. рекомендуемое отсутствие `force_ocr` в первом web API;
7. retention failed staged files;
8. значение `indexed` как готовность данных PostgreSQL, но не vector index;
9. минимальный upload/status UI;
10. отдельное согласование retry endpoint перед его реализацией.
