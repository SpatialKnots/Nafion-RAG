# ARIADNE: основной answer runtime переведён на GigaChat

29 октября 2026 года, Asia/Yekaterinburg.
Пользователь: «Давай изменим текущий выбор нейросети полностью на gigachat».

Changed:

- Основной answer factory теперь принимает только `gigachat`, модель по
  умолчанию `GigaChat-2-Max`. `RAG_PROVIDER=openai` отклоняется явно; fallback
  к OpenAI и автоматических retries нет. Новый runtime adapter находится в
  `app/generation/gigachat.py`; `/answer` и Answer UI используют его через
  существующий `build_answer_provider`.
- Добавлен native GigaChat transport: OAuth Basic authorization + RqUID + scope,
  затем Bearer `POST https://api.giga.chat/v1/chat/completions`. Токен получается
  заново для каждой генерации и не сохраняется. Endpoint фиксирован; redirects
  и environment proxies отключены. TLS verification обязательна, необязательный
  `GIGACHAT_CA_BUNDLE_FILE` добавляет PEM trust к системному.
- Сохранены scientific system prompt, формирование claims/mini-review evidence,
  языковые инструкции, adequacy gates и проверка citation IDs. Новый adapter
  использует native `response_format.schema`, без OpenAI-specific wrapper или
  reasoning settings. Sampling остаётся provider default; эквивалентность
  прежнему OpenAI `temperature=0` не заявляется.
- Строгий локальный разбор отклоняет duplicate JSON keys, nonfinite constants,
  лишние/неверно типизированные answer fields, несовместимые answerable/claims,
  несколько choices, incomplete/filtered/function/refusal responses. Ошибки
  транспорта/формата не объявляются научным отсутствием данных. HTTP/network
  diagnostics не содержат тела ответа, ключа или OAuth-токена.
- Обновлены Settings, `.env.example`, локальная ignored `.env`, UI error hint,
  README, AGENTS.md, дорожная карта и память архитектурного решения. Реальная
  загрузка `.env` подтвердила `gigachat`, `GigaChat-2-Max`, наличие ключа и scope
  `GIGACHAT_API_PERS`. Ключ не печатался и не включён в этот отчёт.
- Прежний численный лимит основного answer path сохранён явно:
  `RAG_GIGACHAT_MAX_TOKENS=1200`, timeout 120 s на каждый HTTP request. Это не
  изменение лимита отдельных DSC-экспериментов и не денежный лимит.
- Исходные PDF, БД, OCR, retrieval scoring, локальные embedding-модели/индексы и
  Terms алгоритмы не менялись. Прежний OpenAI class и frozen records CLI/contracts
  сохраняют историческую идентичность; их нельзя выдавать за GigaChat runs.
  Старые `RAG_OPENAI_*` настройки не управляют новым answer runtime.

Tests run:

- Полный unit suite: **2672 passed**, failures/errors/skipped = 0. JUnit:
  `output/gigachat_runtime_unit_20261029_v02.xml`. Длительность 2918.76 s;
  одна существующая FastAPI/Starlette TestClient deprecation warning. Это
  финальная регрессия текущего кода; counts не складываются с affected suite.
- Affected suite: **149 passed**, в том числе **62** constructed GigaChat runtime
  cases и существующие generation/UI/API/evaluation cases. JUnit:
  `output/gigachat_runtime_tests_20261029_v01.xml`. Одна deprecation warning от
  существующего FastAPI/Starlette TestClient; ошибок и падений нет.
- Проверены OAuth/native payload, scopes, verified TLS и additive CA, missing
  credentials/CA, отсутствие сети без evidence, language/mini-review, HTTP/TLS/
  timeout/incomplete-read failures без retry/fallback/утечки ключей, invalid
  envelopes/JSON, truncated/filtered/function responses, правильные citations и
  отклонение unknown citation IDs через настоящий answer service с fake search
  и fake transport. Реальные sockets в новых тестах запрещены.
- Ruff `app tests scripts`: passed. Mypy `app`: **180 source files**, no issues.
  `git diff --check`: passed. Это завершённые проверки, не live provider validation.
- Отдельный offline configuration check установил CPython network guard до
  application imports, загрузил текущие настройки и создал основной provider.
  Сверены **73 output hashes** пяти исторических manifests, оба занятых GigaChat
  request slots и совпадение registry results с сохранёнными live results.
  OpenAI attempt registry по-прежнему отсутствует. Network events: `[]`.
  Script/report: `output/gigachat_runtime_20261029/offline_configuration_v01.py`
  и соответствующий `.json`. Скрипт также прошёл Ruff.
- Read-only проверка процессов не обнаружила запущенный `python`/`uvicorn
  app.main:app`; существующий сервер не останавливался и не перезапускался.

Limitations:

- В рамках переключения **0 новых model/API calls**. Два реальных DSC-ответа
  28 октября относятся к отдельным frozen experiments; их результат нельзя
  переносить на новый claims/mini-review runtime. Live end-to-end работа нового
  пути, scientific acceptance и независимая accuracy не проверялись.
- Генерация использует внешний GigaChat API и настроенный scope. Денежная
  стоимость и тариф в этом шаге не проверялись. Один answer может выполнить
  OAuth request и model request; timeout применяется отдельно к каждому.
- Прежние manifests не переписывались под изменённый checkout. Проверка старых
  current-code/source bindings может выявить drift после этой смены; сохранённые
  snapshots и исходные guards остаются доказательством, не обходятся.
- CPython network guard offline check — не OS firewall. Браузерный live smoke,
  независимая научная оценка и PostgreSQL integration suite здесь не заявляются.
- Settings кэшируются процессом; уже запущенные экземпляры требуют перезапуска
  после смены `.env`. Новые запуски выбирают GigaChat.

Verdict: основной выбор генерации и локальные настройки переведены на
**GigaChat-2-Max**, без OpenAI fallback; offline transport/service checks пройдены.
Независимая научная приёмка остаётся отдельной задачей.

API contract checked against official documentation:
[OAuth](https://developers.sber.ru/docs/ru/gigachat/quickstart/ind-using-api),
[structured output](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output).
