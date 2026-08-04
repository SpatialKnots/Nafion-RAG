# Приоритет 3: жизненный цикл векторного индекса

## Статус документа

Это подробный технический план для согласования. Описанные состояния, миграция,
фоновые rebuild-задания, API и новый формат хранения ещё не считаются
реализованными.

План развивает третий этап из
`docs/backend_general_implementation_plan.md` и предполагает завершение
приоритета 2: ingestion должен иметь долговечные задания и worker, в который
можно встроить планирование перестроения индекса. Если приоритет 2 изменит
контракт транзакций, этот документ необходимо сверить с фактической реализацией
до начала работ.

## 1. Цель этапа

После успешного добавления, переобработки или удаления статьи система должна
сама определить, что semantic/hybrid index устарел, безопасно построить новый
индекс и переключить поиск на него без ручной команды и без возможности прочитать
частично записанные артефакты.

Целевая цепочка:

```text
изменение Article/Page/Chunk в PostgreSQL
  -> в той же транзакции увеличивается desired corpus revision
  -> index state становится stale
  -> близкие изменения объединяются debounce-механизмом
  -> worker захватывает rebuild для конкретной collection + model
  -> строит immutable generation во временном каталоге
  -> проверяет manifest, matrix, checksums и corpus revision
  -> атомарно публикует generation через current pointer
  -> index state становится ready
  -> semantic/hybrid используют только полностью проверенную generation
```

Exact retrieval не зависит от векторного индекса и остаётся доступным во время
`stale`, `rebuilding` и `failed`.

## 2. Проверенное текущее состояние

На момент подготовки плана:

- semantic retrieval использует FastEmbed и локальную NumPy matrix;
- выбранная модель по умолчанию — `BAAI/bge-small-en-v1.5`;
- артефакты хранятся в
  `<data_root>/processed/vector_indexes/<safe_model_name>/`;
- рабочими файлами являются `embeddings.npy`, `chunk_ids.json` и
  `manifest.json`;
- manifest schema version равна 2;
- manifest содержит collection, модель, размерность, article checksums, полный
  список chunk metadata, checksum текста и checksum файлов;
- loader строго проверяет schema, model, collection, shape, dtype, finite values,
  нормализацию, порядок chunk ids, metadata и соответствие текущей базе;
- изменение текста, состава или порядка чанков приводит к явной ошибке с
  командой ручного rebuild;
- CLI `python -m app.retrieval.cli build` строит индекс вручную;
- build пишет файлы непосредственно в активный каталог;
- при сбое между записями активный индекс может стать частично перезаписанным;
- lifecycle state в PostgreSQL отсутствует;
- автоматической invalidation после ingestion нет;
- несколько collection с одной моделью используют один каталог и могут
  перезаписать индекс друг друга;
- semantic search загружает и валидирует index при каждом запросе;
- hybrid search намеренно не переключается молча на exact, если semantic
  component недоступен.

Существующая строгая проверка является основой нового lifecycle и не должна быть
ослаблена ради доступности.

## 3. Границы этапа

### Входит в реализацию

- lifecycle по паре `collection + embedding_model`;
- состояния `ready`, `stale`, `rebuilding`, `failed` и вычисляемое `missing`;
- монотонная ревизия корпуса;
- транзакционная invalidation при изменении чанков;
- coalescing нескольких близких изменений;
- фоновый full rebuild через worker;
- immutable generations и атомарный current pointer;
- защита от активации индекса для устаревшего snapshot;
- сохранение предыдущей рабочей generation;
- API и UI состояния индекса;
- ручной операторский rebuild;
- диагностируемый `503` для semantic/hybrid при отсутствии подходящей
  generation;
- миграция со старого layout без удаления legacy artifacts;
- cleanup старых generation и staging-каталогов;
- тесты, evaluation и документация.

### Не входит в реализацию

- инкрементальное добавление отдельных vectors в matrix;
- pgvector, FAISS или внешняя vector database;
- смена embedding model и научное сравнение моделей;
- автоматический fallback hybrid -> exact;
- кэширование matrix между HTTP-запросами;
- memory mapping и performance tuning;
- несколько активных моделей в пользовательском UI;
- распределённая блокировка вне PostgreSQL;
- GPU scheduling;
- изменение RRF, retrieval scoring или top-k;
- изменение chunking/extraction/OCR;
- LLM и генерация ответов.

Кэширование и mmap остаются приоритетом 7. На этом этапе важнее корректность
публикации и воспроизводимость.

## 4. Основные архитектурные решения

### 4.1. PostgreSQL хранит состояние, файловая система — rebuildable artifacts

PostgreSQL остаётся источником истины для:

- какой corpus revision требуется;
- какой lifecycle status наблюдается;
- какая generation активна;
- кто и когда выполняет rebuild;
- какая ошибка произошла.

Файловая система хранит:

- immutable embeddings;
- ordered chunk ids;
- immutable manifest каждой generation;
- атомарный pointer на активную generation.

Vectors не становятся научным источником истины и могут быть полностью
перестроены из `Chunk.text`.

### 4.2. Отдельный индекс для collection и model

Новый layout включает оба идентификатора:

```text
<data_root>/processed/vector_indexes/
  <safe_collection_name>/
    <safe_model_name>/
      current.json
      generations/
        <generation_id>/
          embeddings.npy
          chunk_ids.json
          manifest.json
      staging/
        <build_id>/
```

Это устраняет текущую коллизию, когда две collection с одной моделью используют
один каталог.

`generation_id` генерируется сервером и включает UUID или UTC timestamp с
достаточной уникальностью. Пользовательские значения collection/model проходят
существующую безопасную нормализацию и отдельные collision-тесты.

### 4.3. Immutable generation + atomic pointer

Builder никогда не перезаписывает файлы активной generation.

Публикация:

1. полностью построить staging generation;
2. записать manifest последним внутри staging;
3. выполнить полную offline-валидацию;
4. переместить каталог в `generations/<generation_id>` на том же filesystem;
5. создать `current.json.tmp` с generation id и manifest checksum;
6. flush/fsync там, где это практически поддерживается;
7. выполнить `os.replace(current.json.tmp, current.json)`;
8. только затем отметить generation активной в PostgreSQL.

Pointer, а не symlink, выбран для одинакового поведения на Windows и Linux.
Содержимое generation после публикации не меняется.

### 4.4. Full rebuild вместо incremental update

На текущем размере корпуса используется полный rebuild. Инкрементальный индекс
создаёт дополнительные риски удаления, изменения текста, ordering и checksum.
Переход к incremental update возможен только после benchmark и отдельного плана.

## 5. Модель состояния индекса

### 5.1. Ключ состояния

Одна строка состояния соответствует:

```text
(collection_id, embedding_model)
```

Пара уникальна. Смена настроенной embedding model создаёт другое состояние и не
переписывает артефакты предыдущей модели.

### 5.2. Состояния

```text
missing     вычисляемое состояние: строка или generation отсутствует
stale       desired_revision новее active_revision либо проверка выявила mismatch
rebuilding worker строит generation для captured target_revision
ready       активная generation проверена и соответствует desired_revision
failed      требуемый rebuild завершился ошибкой, пригодной generation нет
```

`missing` не обязательно хранить как значение БД: API вычисляет его при
отсутствии state/artifacts.

### 5.3. Ревизии

```text
desired_revision   последняя ревизия корпуса, которую требуется индексировать
active_revision    ревизия активной generation или NULL
building_revision  snapshot revision текущего rebuild или NULL
```

`desired_revision` монотонно увеличивается в той же транзакции, которая меняет
набор или содержимое chunks. Он не заменяет manifest checksums: ревизия быстро
сигнализирует invalidation, а fingerprint и chunk checksums подтверждают
фактическое соответствие.

### 5.4. Переходы

```text
missing -> stale -> rebuilding -> ready
ready + corpus mutation -> stale
stale -> rebuilding -> ready
stale -> rebuilding -> stale    если corpus изменился во время build
stale -> rebuilding -> failed   при исчерпании попыток
failed + rebuild request -> stale/rebuilding
ready + optional rebuild failure -> ready с last_error, если active revision всё ещё актуальна
```

Если rebuild не обязателен и существующая generation полностью соответствует
`desired_revision`, ошибка ручного refresh не должна отключать рабочий поиск.
`failed` используется, когда актуальной generation нет.

## 6. Миграция базы данных

Планируется Alembic migration после миграции приоритета 2.

### 6.1. Таблица `vector_index_states`

Предлагаемые поля:

```text
id                         UUID PK
collection_id              UUID NOT NULL FK collections.id ON DELETE CASCADE
embedding_model            TEXT NOT NULL
status                     TEXT NOT NULL
desired_revision           BIGINT NOT NULL DEFAULT 1
active_revision            BIGINT NULL
building_revision          BIGINT NULL
active_generation_id       TEXT NULL
active_manifest_sha256     TEXT NULL
requested_at               TIMESTAMPTZ NULL
started_at                 TIMESTAMPTZ NULL
finished_at                TIMESTAMPTZ NULL
heartbeat_at               TIMESTAMPTZ NULL
worker_id                  TEXT NULL
attempt_count              INTEGER NOT NULL DEFAULT 0
last_error_type            TEXT NULL
last_error_message         TEXT NULL
created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
```

### 6.2. Constraints и индексы

- unique `(collection_id, embedding_model)`;
- check status in `ready`, `stale`, `rebuilding`, `failed`;
- check ревизий `>= 0`;
- check `attempt_count >= 0`;
- индекс `(status, requested_at)` для claim;
- consistency checks, где они не мешают recovery:
  `ready` требует active generation/revision;
- embedding model сохраняется как точный идентификатор, а не safe directory name.

### 6.3. Инициализация

Миграция схемы не должна скачивать модель, строить vectors или читать большие
файлы. После migration отдельная idempotent-команда lifecycle init:

- создаёт state для нужной collection/model;
- проверяет legacy v2 index;
- если v2 строго валиден, предлагает или выполняет контролируемую подготовку v3
  generation;
- если v2 отсутствует/невалиден, ставит `stale`;
- не удаляет legacy directory.

### 6.4. Downgrade

Downgrade удаляет только lifecycle table/constraints. Generated v3 artifacts
остаются на диске до отдельной безопасной cleanup-команды. Legacy v2 index
сохраняется для отката приложения.

## 7. Corpus revision и invalidation

### 7.1. Что инвалидирует индекс

Для затронутой collection invalidation обязательна после commit-intent любого
изменения:

- добавление статьи с чанками;
- удаление статьи;
- повторный chunking;
- изменение `Chunk.text`;
- изменение chunk id, порядка, `source_type`, `text_layer`, страниц или
  `char_count`;
- перенос статьи между collections;
- выбор другого text layer, если он пересоздаёт chunks;
- repair/import, изменяющий проиндексированные данные.

Изменение title, DOI или tags само по себе не требует rebuild vectors, но
retrieval evidence получает metadata из PostgreSQL и должно быть отдельно
проверено.

### 7.2. Транзакционная граница

Вызов `mark_vector_index_stale(session, collection_id, reason)` выполняется в той
же DB-транзакции, что и изменение chunks:

- увеличивает `desired_revision` ровно один раз на логическую операцию;
- устанавливает `stale`, если rebuild не идёт;
- если state=`rebuilding`, сохраняет состояние, но увеличивает desired revision;
- обновляет `requested_at` для debounce;
- не запускает embedding model внутри транзакции.

Rollback corpus mutation также откатывает revision, поэтому ложный rebuild не
создаётся.

### 7.3. Точки интеграции

Обязательные вызовы invalidation:

- успешный ingestion worker из приоритета 2;
- синхронный `ingestion file/folder` CLI;
- `reselect-text`;
- `prune-missing-corpus` при фактическом удалении;
- будущие delete/rechunk/admin operations.

Duplicate и failed ingestion без изменения chunks revision не увеличивают.

### 7.4. Защита от обхода service

Прямые SQL-изменения могут обойти invalidation helper. Поэтому loader сохраняет
строгую сверку manifest с текущими chunk ids и checksums. Doctor также вычисляет
corpus fingerprint и сообщает `state says ready, artifacts are stale`.

DB trigger на chunks на этом этапе не рекомендуется: он увеличивал бы revision
для каждой строки массового rechunking. Если дисциплина service окажется
недостаточной, trigger рассматривается отдельным решением.

## 8. Manifest v3

Новый manifest сохраняет все доказательства schema v2 и добавляет lifecycle
metadata.

Обязательные поля:

```text
schema_version: 3
status: built
backend: local_vector_index
collection
collection_id
embedding_model
embedding_dimension
generation_id
build_id
target_revision
corpus_fingerprint_sha256
snapshot_created_at
build_started_at
build_finished_at
build_command
batch_size
software_versions
similarity: cosine
vectors_normalized: true
chunk_count
article_checksums
chunks[]
index_files[]
```

Каждый элемент `chunks[]` сохраняет существующие поля:

- chunk id и article id;
- article checksum;
- chunk index;
- page range;
- source type;
- text layer;
- char count;
- SHA-256 исходного текста.

`corpus_fingerprint_sha256` вычисляется детерминированно из канонически
сериализованных chunk metadata в том же порядке, что embeddings.

### Tracked corpus manifest

`docs/corpus_manifest.json` остаётся evaluation/audit snapshot, но не должен
быть runtime-зависимостью автоматического индекса. Текущее требование совпадения
checksum внешнего документа заменяется внутренним corpus fingerprint. Иначе
каждый upload потребовал бы сначала вручную обновить tracked файл.

Это изменение manifest semantics должно быть явно отражено в schema v3 и
документации; schema v2 не перезаписывается на месте.

## 9. Snapshot и процесс rebuild

### 9.1. Claim

Worker в короткой транзакции:

1. выбирает самый старый `stale` state, у которого прошёл debounce;
2. блокирует строку через `FOR UPDATE SKIP LOCKED`;
3. фиксирует `building_revision = desired_revision`;
4. ставит `rebuilding`, worker id, timestamps и attempt count;
5. commit.

Одна пара collection/model имеет не более одного rebuild одновременно.

### 9.2. Снимок корпуса

Builder читает ordered rows существующим правилом:

```text
Article.checksum_sha256, Chunk.chunk_index, Chunk.id
```

Из БД материализуются только необходимые immutable значения и тексты. Длинная
транзакция не удерживается во время embedding. Snapshot получает:

- target revision;
- ordered chunk records;
- corpus fingerprint;
- collection/model configuration.

Если корпус пуст, создаётся валидная matrix shape `(0, dimension)` при известной
размерности модели.

### 9.3. Построение staging generation

- staging directory создаётся внутри того же model root;
- embeddings вычисляются batch-ами существующим FastEmbed provider;
- проверяются count, dimension, dtype, finite values, zero vectors;
- vectors нормализуются для cosine;
- `embeddings.npy` и `chunk_ids.json` записываются только в staging;
- их SHA-256 добавляются в manifest;
- manifest пишется последним;
- builder не читает и не изменяет current generation.

### 9.4. Проверка перед активацией

После построения:

- generation загружается тем же validator, который использует search, но против
  сохранённого snapshot;
- проверяются все checksums и matrix invariants;
- повторно читается state под row lock;
- `desired_revision` сравнивается с `building_revision`;
- текущий corpus fingerprint сверяется со snapshot;
- если revision/fingerprint изменились, generation не активируется, state снова
  становится `stale`, а новый rebuild объединяет все изменения.

### 9.5. Атомарная активация

Под короткой блокировкой state row:

1. ещё раз подтвердить target revision;
2. переместить staging в immutable generations;
3. атомарно заменить `current.json`;
4. записать `active_generation_id`, manifest checksum и active revision;
5. поставить `ready`;
6. очистить building/worker/error fields;
7. commit.

Файловая система и PostgreSQL не имеют общей транзакции. Порядок pointer-first,
DB-second выбран намеренно:

- crash до pointer оставляет state rebuilding и старый current;
- crash после pointer, но до DB commit обнаруживается recovery-проверкой;
- DB никогда не сообщает ready для generation, pointer на которую ещё не
  опубликован.

### 9.6. Recovery после частичной активации

При старте worker:

- проверить stale `rebuilding` states;
- прочитать current pointer;
- если pointer указывает на полностью валидную generation с target revision,
  завершить state как ready;
- иначе вернуть state в stale или failed согласно attempts;
- удалить только старые staging directories после проверки, что они не
  referenced;
- не менять active generation без полной валидации.

## 10. Coalescing и debounce

Несколько ingestion commits не должны запускать отдельный full rebuild каждый.

Правила:

- каждое логическое изменение увеличивает desired revision;
- `requested_at` обновляется последним изменением;
- worker ждёт `VECTOR_REBUILD_DEBOUNCE_SECONDS` после последнего изменения;
- все изменения до claim входят в один snapshot;
- изменение во время build не отменяет процесс принудительно, но запрещает
  активацию устаревшей generation;
- после завершения такого build worker строит только последнюю desired revision;
- число пропущенных промежуточных revisions видно в диагностике.

Рекомендуемый начальный debounce: 10 секунд. Значение фиксируется настройкой и
проверяется на реальном batch upload.

## 11. Worker и retries

### 11.1. Роль worker

После приоритета 2 поддержать режимы:

```text
python -m app.workers.worker --role ingestion
python -m app.workers.worker --role vector
python -m app.workers.worker --role all
```

Для локального запуска достаточно `all`. Отдельная роль `vector` позволяет не
блокировать ingestion долгим rebuild без внедрения внешней очереди.

### 11.2. Heartbeat и lease

Vector rebuild обновляет heartbeat между embedding batches. Lease должен быть
дольше максимального ожидаемого batch, но не всего rebuild. Зависший state
восстанавливается так же явно, как ingestion job.

### 11.3. Ошибки

Permanent до изменения конфигурации/данных:

- неизвестная collection/model;
- inconsistent embedding dimensions;
- NaN, infinity или zero vectors;
- повреждение snapshot metadata;
- недостаток обязательных manifest fields.

Potentially recoverable:

- временная ошибка чтения БД;
- временная ошибка runtime/model cache;
- процесс был остановлен;
- временная ошибка записи staging filesystem.

Недостаток места на диске фиксируется отдельно и не должен приводить к удалению
active generation.

### 11.4. Ограничение попыток

После `VECTOR_REBUILD_MAX_ATTEMPTS` обязательный rebuild становится `failed`.
Новый corpus mutation или ручной rebuild может создать новую серию попыток.
Автоматический бесконечный retry запрещён.

## 12. Поведение retrieval

### 12.1. Exact

Exact search не читает lifecycle state и продолжает работать во всех состояниях.

### 12.2. Semantic

Semantic search обслуживается только если:

- state существует;
- active generation существует;
- active revision равна desired revision;
- current pointer совпадает с state;
- manifest и артефакты проходят строгую проверку;
- corpus fingerprint/metadata соответствуют текущей DB snapshot.

При невыполнении условий возвращается специализированная
`VectorIndexUnavailableError`, а API преобразует её в `503 Service Unavailable`.

Пример безопасного ответа:

```json
{
  "detail": {
    "code": "vector_index_not_ready",
    "collection": "literature",
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "status": "rebuilding",
    "exact_search_available": true
  }
}
```

Внутренние пути и traceback не возвращаются.

### 12.3. Hybrid

Hybrid сохраняет текущую строгую семантику: если semantic component недоступен,
метод не выдаёт exact-only результат под именем hybrid. API возвращает тот же
диагностируемый `503`, а UI предлагает пользователю явно выбрать exact.

### 12.4. Предыдущая generation

Предыдущая generation сохраняется физически до cleanup:

- при rebuild без изменения корпуса она может оставаться обслуживаемой до
  успешного переключения;
- после corpus mutation она не соответствует desired revision и не обслуживает
  semantic/hybrid;
- при failed rebuild она остаётся rollback-артефактом, но не выдаётся как
  актуальная;
- ручное возвращение к ней разрешено только если её manifest снова строго
  соответствует текущему корпусу.

## 13. API lifecycle

### 13.1. Список индексов

```http
GET /retrieval/indexes
```

Предлагаемые поля:

```json
{
  "items": [
    {
      "collection": "literature",
      "embedding_model": "BAAI/bge-small-en-v1.5",
      "status": "ready",
      "desired_revision": 12,
      "active_revision": 12,
      "active_generation_id": "20260804T120000Z_abcd1234",
      "chunk_count": 420,
      "requested_at": "2026-08-04T11:59:40Z",
      "started_at": "2026-08-04T11:59:51Z",
      "finished_at": "2026-08-04T12:00:15Z",
      "last_error": null
    }
  ]
}
```

Не возвращаются filesystem paths, worker id и traceback.

### 13.2. Один индекс

```http
GET /retrieval/indexes/status?collection=literature&embedding_model=BAAI%2Fbge-small-en-v1.5
```

Query parameter для model предпочтительнее path segment, потому что model id
может содержать `/`.

Дополнительно вернуть:

- building revision;
- active manifest SHA-256;
- attempts;
- `semantic_available` и `exact_available`;
- безопасную последнюю ошибку;
- рекомендуемое следующее действие.

### 13.3. Ручной rebuild

```http
POST /retrieval/indexes/rebuild
Content-Type: application/json

{
  "collection": "literature",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "reason": "operator_request"
}
```

Операция не строит индекс в HTTP request. Она:

- создаёт state, если его нет;
- ставит stale/requested;
- coalesce с уже ожидающим или выполняющимся rebuild;
- возвращает `202` и текущее состояние;
- не увеличивает corpus revision, если данные не изменились;
- не позволяет передать filesystem path или backend через API.

Без аутентификации endpoint остаётся локальным операторским действием.

## 14. CLI

Сохранить ручной контроль и добавить lifecycle-aware команды:

```powershell
python -m app.retrieval.cli status --collection literature
python -m app.retrieval.cli request-rebuild --collection literature
python -m app.retrieval.cli rebuild-now --collection literature
python -m app.retrieval.cli validate --collection literature
python -m app.retrieval.cli cleanup --collection literature --dry-run
```

Правила:

- `request-rebuild` только ставит запрос worker;
- `rebuild-now` использует тот же builder и locking, что worker;
- два `rebuild-now` не работают одновременно для одной пары;
- `validate` ничего не изменяет;
- `cleanup` по умолчанию dry-run;
- legacy `build` либо становится совместимой alias, либо сохраняется на один
  переходный релиз с предупреждением;
- команды возвращают структурированный JSON, пригодный для diagnostics.

## 15. UI

Добавить компактный блок Vector Index на dashboard или отдельной странице:

- collection и embedding model;
- status с нейтральной цветовой индикацией;
- desired/active revision;
- chunk count текущей generation;
- время запроса, начала и завершения;
- progress вида `embedded_chunks / total_chunks`, если worker его хранит;
- безопасная последняя ошибка;
- кнопка rebuild с подтверждением;
- ссылка переключения на exact search при stale/rebuilding/failed.

UI не обещает процент завершения, если pipeline не может измерить его точно.
Анимация/опрос прекращается после конечного состояния и использует умеренный
interval.

## 16. Настройки

Добавить в `Settings` и `.env.example`:

```text
VECTOR_AUTO_REBUILD_ENABLED=true
VECTOR_REBUILD_DEBOUNCE_SECONDS=10
VECTOR_REBUILD_POLL_SECONDS=2
VECTOR_REBUILD_LEASE_SECONDS=1800
VECTOR_REBUILD_HEARTBEAT_SECONDS=30
VECTOR_REBUILD_MAX_ATTEMPTS=3
VECTOR_REBUILD_BATCH_SIZE=64
VECTOR_INDEX_KEEP_GENERATIONS=2
VECTOR_STAGING_RETENTION_HOURS=24
```

Точные defaults подтверждаются benchmark текущего корпуса. Валидация требует:

- положительные интервалы;
- heartbeat меньше lease;
- keep generations не меньше 1;
- batch size положительный;
- max attempts положительный.

`VECTOR_AUTO_REBUILD_ENABLED=false` запрещает автоматический claim, но manual
rebuild и status остаются доступными. Invalidation продолжает ставить `stale`.

## 17. Cleanup и хранение generation

Cleanup запускается только после успешной активации или отдельной командой.

Правила:

- никогда не удалять generation из current pointer;
- никогда не удалять generation, указанную в DB state;
- сохранить active и минимум одну предыдущую валидную generation;
- не удалять staging моложе retention;
- проверять resolved path внутри конкретного collection/model root;
- сначала dry-run report, затем `--apply`;
- удалить только generated artifacts, не PDF, corpus manifest или model cache;
- при ошибке чтения pointer прекратить cleanup, а не угадывать active directory.

## 18. Doctor и диагностика

`doctor` должен отдельно проверять:

- наличие state для configured collection/model;
- согласованность status и revisions;
- существование/валидность current pointer;
- существование generation directory;
- manifest schema/model/collection/revision;
- checksums artifacts;
- matrix shape/dtype/normalization;
- DB chunk ids и text checksums;
- доступность записи в staging root;
- наличие embedding runtime/model cache;
- stale lease;
- свободное место как предупреждение, если его можно получить переносимо.

Диагностика разделяет:

```text
PASS     индекс готов и соответствует корпусу
WARN     exact доступен, index stale/rebuilding или остались cleanup artifacts
FAIL     повреждение active generation, state/pointer mismatch или model unavailable
```

Doctor ничего не исправляет автоматически без отдельного repair/rebuild действия.

## 19. План изменений по файлам

Ожидаемый набор:

```text
alembic/versions/0004_vector_index_lifecycle.py
app/core/config.py
app/db/models.py
app/ingestion/service.py
app/ingestion/cli.py
app/retrieval/vector_index.py
app/retrieval/index_lifecycle.py
app/retrieval/cli.py
app/retrieval/search.py
app/main.py
app/ui.py
app/workers/worker.py
app/diagnostics/doctor.py
tests/unit/test_vector_index_manifest.py
tests/unit/test_vector_index_lifecycle.py
tests/unit/test_vector_index_worker.py
tests/unit/test_retrieval_search.py
tests/unit/test_api_search.py
tests/unit/test_api_vector_indexes.py
tests/unit/test_ingestion_cli.py
tests/unit/test_ui_routes.py
.env.example
README.md
docs/architecture.md
docs/data_model.md
docs/operations.md
docs/phase3_storage_decision.md
```

Номер migration уточняется по фактическому Alembic head после завершения
приоритета 2.

## 20. Пошаговая реализация

### Шаг 1. Зафиксировать baseline

- сохранить `git status`, не затрагивая пользовательские изменения;
- выполнить полный `pytest`, Ruff и mypy;
- проверить Alembic head;
- проверить corpus manifest;
- выполнить exact/semantic/hybrid evaluation;
- сохранить manifest SHA-256 и checksums текущего v2 index;
- измерить время и размер текущего rebuild;
- проверить фактические collections и configured model.

### Шаг 2. Добавить schema v3 и новый layout без переключения search

- отделить snapshot/build/validate/publish operations;
- добавить collection в directory layout;
- реализовать immutable staging generation;
- реализовать deterministic corpus fingerprint;
- записывать manifest v3;
- сохранить v2 loader без изменений на переходном шаге;
- покрыть новый builder unit-тестами.

### Шаг 3. Добавить lifecycle migration и state service

- создать `vector_index_states`;
- добавить ORM model и status constants;
- реализовать get/create state;
- реализовать транзакционную invalidation;
- реализовать claim, heartbeat, success, stale-again и failure transitions;
- проверить upgrade/downgrade/upgrade.

### Шаг 4. Интегрировать invalidation с corpus mutations

- ingestion worker success;
- синхронный CLI ingestion;
- reselect text;
- prune/delete operations;
- добавить тест: rollback corpus mutation не увеличивает revision;
- добавить тест: duplicate/failed не инвалидируют index.

### Шаг 5. Реализовать worker rebuild

- debounce и claim;
- snapshot target revision;
- batched embedding и heartbeat;
- staging build;
- offline validation;
- pre-activation revision/fingerprint check;
- atomic pointer swap;
- state commit;
- crash recovery и bounded retry.

### Шаг 6. Перенести текущий индекс

- строго проверить legacy v2 artifacts;
- построить v3 generation тем же model и corpus;
- не изменять v2 files;
- сравнить embeddings shape и retrieval evaluation;
- опубликовать v3 pointer;
- отметить state ready;
- сохранить v2 как rollback до завершения этапа.

### Шаг 7. Переключить semantic/hybrid loader

- читать lifecycle state и current pointer;
- загружать только immutable generation;
- сохранить строгие manifest/chunk checks;
- ввести специализированную unavailable error;
- map error в API `503`;
- сохранить отсутствие silent hybrid fallback;
- включить lifecycle metadata в search diagnostics.

### Шаг 8. Добавить API, CLI и UI

- status list/detail;
- asynchronous rebuild request;
- lifecycle-aware CLI;
- dashboard status и rebuild action;
- exact-search guidance при недоступном vector index;
- не раскрывать filesystem paths.

### Шаг 9. Добавить cleanup и doctor checks

- generation retention;
- orphan staging detection;
- stale lease detection;
- state/pointer/artifact consistency checks;
- dry-run cleanup;
- recovery tests для каждой точки сбоя публикации.

### Шаг 10. Полная проверка

- выполнить целевые unit/integration tests;
- полный `pytest`, Ruff и mypy;
- migration upgrade/downgrade/upgrade;
- запустить API и worker;
- загрузить новый PDF через приоритет 2;
- подтвердить stale -> rebuilding -> ready;
- проверить exact во время rebuild;
- проверить диагностируемый semantic/hybrid `503`;
- проверить новый документ semantic/hybrid после ready;
- запустить exact/semantic/hybrid evaluation;
- проверить UI desktop/mobile;
- проверить `git diff --check` и итоговый diff.

## 21. Тестовая матрица

### 21.1. Layout и path safety

- разные collections с одной model имеют разные roots;
- разные models одной collection имеют разные roots;
- unsafe collection/model names нормализуются;
- collision safe names обнаруживается, а не приводит к перезаписи;
- staging/generation/current остаются внутри data root;
- symlink/path traversal не позволяет cleanup или publish выйти наружу.

### 21.2. Manifest v3

- записаны все обязательные lifecycle/evidence fields;
- fingerprint детерминирован при одинаковом ordered corpus;
- изменение текста/metadata меняет fingerprint;
- chunk order совпадает с embeddings order;
- checksum каждого файла проверяется;
- неверная schema/model/collection/revision отклоняется;
- NaN/infinity/zero/non-normalized vectors отклоняются;
- пустой corpus создаёт корректную matrix.

### 21.3. Invalidation

- новый indexed article увеличивает desired revision;
- duplicate/failed ingestion не увеличивает revision;
- reselect/delete инвалидируют правильную collection;
- изменение другой collection не инвалидирует текущую;
- несколько изменений coalesce в один ожидающий rebuild;
- rollback не оставляет ложный stale state;
- mutation во время rebuilding увеличивает desired revision без второго claim.

### 21.4. Claim и worker

- один state захватывается одним worker;
- `SKIP LOCKED` позволяет взять другой state;
- debounce соблюдается;
- heartbeat обновляется между batches;
- stale lease восстанавливается;
- retries ограничены;
- выключенный auto rebuild не захватывает state;
- manual rebuild использует тот же lock.

### 21.5. Atomic publish

- active artifacts не меняются во время staging build;
- ошибка embedding оставляет current pointer прежним;
- ошибка записи manifest оставляет current прежним;
- invalid staging generation не публикуется;
- corpus mutation перед активацией возвращает state в stale;
- pointer заменяется атомарно;
- crash до pointer восстанавливается;
- crash после pointer до DB commit восстанавливается;
- DB никогда не сообщает ready на отсутствующую generation;
- предыдущая generation сохраняется.

### 21.6. Retrieval

- ready index обслуживает semantic и hybrid;
- missing/stale/rebuilding/failed дают semantic/hybrid `503`;
- exact работает во всех lifecycle states;
- hybrid не маскируется под exact;
- state/pointer mismatch отклоняется;
- chunk checksum mismatch отклоняется;
- search metadata содержит generation/revision/manifest checksum;
- ranking на неизменном corpus не регрессирует.

### 21.7. API и UI

- status list/detail корректно сериализуют каждое состояние;
- model id с `/` безопасно передаётся query parameter;
- rebuild request coalesce;
- неизвестная collection возвращает `404` или согласованный `400`;
- API не возвращает paths/tracebacks/worker id;
- dashboard показывает state и timestamps;
- exact action виден при недоступном index;
- UI polling прекращается после ready/failed;
- длинные model/error strings не ломают layout.

### 21.8. Cleanup

- active generation никогда не удаляется;
- DB-referenced generation не удаляется;
- предыдущая generation сохраняется по retention;
- свежий staging не удаляется;
- orphan старше retention попадает в dry-run;
- повреждённый pointer блокирует cleanup;
- `--apply` удаляет только перечисленные generated paths.

### 21.9. Migration и legacy

- migration сохраняет corpus и v2 artifacts;
- lifecycle init idempotent;
- валидный v2 остаётся доступен до controlled switch;
- невалидный v2 не помечается ready;
- v3 build не перезаписывает v2;
- downgrade удаляет только state table;
- rollback приложения может использовать сохранённый v2 layout.

### 21.10. End-to-end

1. начать с ready generation;
2. загрузить несколько PDF подряд;
3. подтвердить один coalesced rebuild;
4. во время rebuild выполнить exact search успешно;
5. получить semantic/hybrid not-ready diagnostic;
6. дождаться ready;
7. найти новые статьи semantic и hybrid;
8. проверить article/page/chunk traceability;
9. повторить duplicate upload без нового rebuild;
10. сравнить retrieval evaluation с baseline.

## 22. Критерии приёмки

Этап считается завершённым только при выполнении всех условий:

- corpus mutation автоматически переводит нужный index в stale;
- несколько близких изменений объединяются в один rebuild;
- worker строит generation без изменения active artifacts;
- частично построенный индекс никогда не обслуживает запросы;
- generation активируется только для неизменившейся target revision;
- pointer заменяется атомарно и проверяется вместе с DB state;
- предыдущая generation сохраняется;
- exact search доступен во время stale/rebuilding/failed;
- semantic/hybrid не выполняют silent fallback и дают безопасный `503`;
- после ready новые статьи доступны semantic/hybrid;
- две collections не перезаписывают индексы друг друга;
- duplicate/failed ingestion не запускают лишний rebuild;
- crash worker и частичная публикация восстанавливаются;
- original PDF и научные записи не изменяются lifecycle cleanup;
- migration и legacy transition проверены;
- exact/semantic/hybrid evaluation не показывает неприемлемой регрессии;
- полный test suite, Ruff и mypy проходит;
- документация соответствует реализации.

## 23. Риски и решения

### Corpus меняется во время долгого build

Builder фиксирует target revision и snapshot fingerprint. Перед публикацией оба
значения проверяются под lock. Устаревшая generation не активируется.

### Сбой между filesystem pointer и DB commit

Pointer публикуется до ready commit. Recovery валидирует generation и либо
завершает commit состояния, либо возвращает stale. DB не обещает несуществующий
active index.

### Один model directory обслуживает разные collections

Новый layout включает safe collection name. Дополнительно manifest проверяет
точные collection name/id.

### Частичная перезапись активного v2 index

V3 builder пишет только новую staging generation. Current pointer заменяется
одной операцией; immutable active files не перезаписываются.

### Автоматический rebuild постоянно отстаёт от ingestion

Debounce объединяет batch, а desired revision не позволяет активировать
промежуточный snapshot. При непрерывной загрузке UI показывает stale/rebuilding;
оператор может запустить отдельный vector worker.

### Model runtime недоступен

State становится failed с безопасной диагностикой. Exact остаётся рабочим;
active generation не удаляется.

### Semantic downtime после каждого upload

Строгий режим не обслуживает stale vectors под видом актуальных. Для текущего
локального корпуса full rebuild должен быть измерен. Снижение downtime через
incremental index возможно только после benchmark в приоритете 7.

### Несогласованное прямое изменение БД

Revision helper является основным механизмом, но loader и doctor дополнительно
проверяют fingerprint, chunk ids и text checksums.

## 24. Откат

Порядок отката:

1. отключить auto rebuild;
2. остановить vector worker;
3. убедиться, что нет publishing operation;
4. переключить приложение на сохранённый v2 loader/layout;
5. выполнить downgrade lifecycle migration при необходимости;
6. оставить v3 generations на диске для диагностики;
7. не удалять PDF, chunks или embedding model cache.

Изменение retrieval scoring и corpus в этом приоритете не планируется, поэтому
откат не требует re-ingestion.

## 25. Контрольная точка согласования

До начала реализации необходимо согласовать:

1. lifecycle state в PostgreSQL по паре collection + embedding model;
2. full rebuild вместо incremental update;
3. manifest schema v3 и отказ от runtime-зависимости на tracked corpus manifest;
4. immutable generations и атомарный `current.json` pointer;
5. запрет обслуживания stale generation;
6. `503` для semantic/hybrid без silent fallback;
7. coalescing через desired revision и debounce;
8. worker roles `ingestion`, `vector`, `all`;
9. хранение active и минимум одной предыдущей generation;
10. переход с v2 без удаления legacy artifacts.
