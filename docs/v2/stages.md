# ForwardTrace v2 — отчёты этапов

Каждый тикет дописывает строки в раздел своего этапа: первый тикет этапа — план до правок кода, каждый — что сделано и какие тесты добавлены, последний — что осталось открытым и какие умолчания приняты.

## Этап 0. Подготовка

### План (тикет 01, до правок кода)

- Меняются: `progress-backend/app/config.py` (отказ старта с `JWT_SECRET` по умолчанию вне тестов; настройки v2), `app/schemas.py` (`ChangePasswordIn` — проверка 72 байт), `progress-backend/.env.example` (без дублей разделов, переменные v2), `tests/test_app.py` (удаление мёртвого дубля `class TestReminders`), `tests/conftest.py`.
- Удаляется: пустой каталог `progress-backend/app/{services,routers}`.
- Проверяется без правок: дублей полей в `config.py` нет; `generate_vapid_keys.py` не упоминается ни в `config.py`, ни в `.env.example`; правила `*.md` в корневом `.gitignore` нет.

### Сделано (тикет 01)

- Проверено и правок не потребовало: в `config.py` дублей полей нет; `generate_vapid_keys.py` не упоминается ни в `config.py`, ни в `.env.example` (оба называют `python -m app.vapid`); правила `*.md` в корневом `.gitignore` нет — `docs/` и документация в корне попадают в git.
- `config.py`: новое поле `APP_ENV` (`production` по умолчанию). При `JWT_SECRET`, равном значению из кода, и `APP_ENV` ≠ `test` создание `Settings` падает с сообщением, где названа переменная и нет значения. Падает и всё, что читает настройки (alembic, скрипты), — это намеренно.
- `ChangePasswordIn` проверяет ограничение 72 байта, как `RegisterIn` (422).
- `.env.example`: удалены повторные разделы `email` и `push reminders`; комментарий о дневных квотах снова стоит над своими переменными; `LLM_PRICE_*` получили `0` вместо пустых строк (пустое значение числового поля не проходит разбор, и `.env`, скопированный из примера, не стартовал); добавлены `APP_ENV` и все переменные v2.
- Удалены мёртвый дубль `class TestReminders` в `tests/test_app.py` (он импортировал несуществующий `app.services.scheduler` и никогда не запускался) и пустой каталог `progress-backend/app/{services,routers}`.

Тесты (`tests/test_v2_foundation.py`): `TestStartupGuard` (4), `TestChangePassword` (2).

## Этап 1. Модель данных и импорт

### План (тикет 01, до правок кода)

- Создаются: `progress-backend/alembic/versions/0014_v2_core.py`, `app/services/errors.py`, `app/services/events.py`, `app/services/texts.py`, `scripts/import_v1.py`, `tests/test_v2_foundation.py`, этот файл.
- Меняются: `app/models.py` (таблицы `conversations`, `messages`, `facts`, `threads`, `pairs`, `monthly_summaries`, `outreach`; новые поля `users` и `goals`), `app/schemas.py` (схемы v2, `UserOut`/`UserUpdate`), `app/routers/auth.py` (новые поля `PATCH /api/auth/me`, страна по таймзоне), `app/services/accounts.py` (стирание новых таблиц и аудио сообщений), `app/services/costs.py` (места цен `CHAT_MODEL`/`SAFETY_MODEL`/`EMBEDDING_MODEL`, `charge_message`), `tests/conftest.py`, `pytest.ini` (маркер `postgres`).
- Ничего не удаляется: таблицы v1 остаются до этапа 10.

### Сделано (тикет 01)

- Модели и миграция `0014_v2_core`: таблицы `conversations`, `messages`, `facts`, `threads`, `pairs`, `monthly_summaries`, `outreach`; поля `users` (`skill`, `country`, `outreach_channel`, `telegram_chat_id`, `telegram_link_token` — unique, `outreach_unanswered`, `plus_until`, `first_conversation_done`) и `goals` (`why_message_id`, `finish_line`, `finish_set_on`, `baseline_message_id`). Unique: `(user_id, local_date)`, `(then_fact_id, now_fact_id)`, `(user_id, month)`. Индексы: `messages (conversation_id, created_at)`, `facts (user_id, local_date)`, `(user_id, type)`, `threads (user_id, status)`. FK на `users.id` — `CASCADE`; ссылки факта на сообщение и нить, нити на факты, цели на сообщения, outreach на разговор/сообщение/нить — `SET NULL`; пары на факты и сообщения на разговор — `CASCADE`. Цикл `facts.thread_id` ↔ `threads.*_fact_id` разорван `use_alter`, в миграции — отдельными `create_foreign_key`.
- Pydantic: `TextSegment`/`QuoteSegment`/`Segment`, `MessageOut`, `LimitOut`, `ConversationOut`, `ThreadBrief`, `DayOut`, `ThreadOut`, `ThreadUpdate`, `FactOut` (`flagged` из `flagged_at`), `PairOut`, `GoalPatch`, `MemoryOut`, `MonthlyContentOut`, `MonthlySummaryOut`, `ProgressOut`, `RatingIn`, `SearchHitOut`, `CalendarDayOut`, `PaywallClickOut`, `TelegramLinkOut`. `GoalOut` дополнен `finish_line`, `finish_set_on` (одна схема для v1 и v2 до этапа 10). `UserOut` дополнен `skill`, `country`, `outreach_channel`, `telegram_linked`, `plus_until`, `first_conversation_done`; `UserUpdate` принимает `skill` (≤120), `country` (две латинские буквы, приводится к верхнему регистру), `outreach_channel` (`push|telegram|none`).
- `users.country` при регистрации и при смене таймзоны — из таблицы частых зон (`accounts.country_for_timezone`); при смене таймзоны страна меняется, только если она пустая или совпадает со страной старой зоны.
- `services/errors.py` (`api_error` и константы кодов), `services/events.py` (`log_event`, `day_number`), `services/texts.py` (`t`, `quick`, `month_name`; ключи первого разговора, тем outreach, безопасности, сводки, Telegram; ru на «вы»).
- `costs.py`: цены `CHAT_*`, `SAFETY_*` (применяются, когда модель отличается от `OPENAI_MODEL`), `EMBEDDING_PRICE_PER_1M`, все `0`; `record_embedding`, `missing_prices()` (для предупреждения при старте), `charge_message`.
- `accounts.erase` удаляет строки всех новых таблиц и файлы `messages.audio_path`.
- `scripts/import_v1.py` по шагам 1–5 брифа.
- Тест миграций на Postgres выполнен локально (Docker Desktop, временный контейнер `postgres:16`, удалён после прогона): чистая база 0001 → head, откат на 0013 и снова head, `main._check_schema` проходит; база на 0013 с данными v1 → 0014 → импорт (1 разговор, 1 сообщение, 3 факта, 1 отброшенная цитата), повторный импорт — ноль новых строк, таблицы v1 и `why_text` целы. `alembic check` по новым таблицам расхождений не показал, кроме `created_at`/`updated_at`/`sent_at`, которые в миграции допускают NULL при `server_default` — так же, как во всех таблицах v1.

Тесты (`tests/test_v2_foundation.py`): `TestApiError` (1), `TestTexts` (6), `TestLogEvent` (2), `TestProfileV2` (10), `TestSchemasV2` (1), `TestErasureV2` (1), `TestCostsV2` (4), `TestImportV1` (2), `TestMigrationsOnPostgres` (2, маркер `postgres`, нужен `TEST_POSTGRES_URL`, без него пропускаются). Общие фикстуры `fresh_db`, `client`, помощники `register`, `parse_sse` — в `tests/conftest.py`.

### Открыто

- Цены `CHAT_MODEL`, `SAFETY_MODEL`, `EMBEDDING_MODEL` (и `OPENAI_MODEL`) — `0`, заполняет владелец. `costs.missing_prices()` готов; вызов предупреждения из `lifespan` в `main.py` — вне зоны тикета 01.
- `SAFETY_RESOURCES = {}`, `EMBEDDING_MODEL` и `TELEGRAM_*` пусты — заполняет владелец.
- Сервер ещё не дополняет события `POST /api/events` полями `day_number`/`language`/`channel` (`routers/admin.py`, этап 9).

### Принятые умолчания

- Открытые решения владельца — по умолчанию брифа: PWA — основной интерфейс, Telegram — канал сообщений ИИ первым; токены в `localStorage`; модель разговора — `OPENAI_MODEL`; эмбеддинги не заданы (поиск по дате); функциональный дизайн; подтверждение почты как в v1; контакты помощи пустые.
- Тестовое окружение определяется `APP_ENV=test` (ставит `conftest.py`).
- `day_number`: день регистрации по локальной дате человека = 1.
- Импорт: разговоры получают `counts_for_limit = true` и `memory_extracted_at` = время импорта (их факты уже перенесены, повторное извлечение моделью стоило бы денег); человек с импортированной историей и активной целью получает `first_conversation_done = true` и `skill` = название цели, чтобы не проходить онбординг заново; цели не меняются; дубли фактов ищутся по нормализованной цитате внутри сообщения; записи с пустым `raw_transcript` пропускаются.
- `outreach.conversation_id` — `SET NULL`: строка outreach остаётся для аналитики после удаления разговора.
