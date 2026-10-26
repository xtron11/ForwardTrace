# ForwardTrace — техническая документация (v2)

Справочник по коду ветки `v2`: что где лежит, как устроено и как запускается. Где этот
файл расходится с кодом, верен код. Отчёты этапов сборки, принятые умолчания и открытые
места — в [docs/v2/stages.md](docs/v2/stages.md).

---

# 1. Что это

Разговорный дневник прогресса. Каждый календарный день человека (по его часовому поясу) —
один разговор голосом или текстом. ИИ отвечает сразу, потоком, и ссылается на прошлое
только дословными цитатами из сообщений человека, с датами; цитаты подставляет код.

* **Факты** (`achievement` / `struggle` / `learned` / `level`) извлекаются из разговора в
  фоне. Факт без цитаты, найденной в его сообщении, не сохраняется.
* **Нити** — трудности, которые человек назвал; живут, пока он не скажет, что справился.
* **Пары «было → стало»** — ранняя трудность и поздний успех (по закрытию нити, по
  сходству смысла или из первого разговора, «по вашим воспоминаниям»).
* **ИИ пишет первым** раз в день в час человека — push или Telegram.
* **Первый разговор** — онбординг: навык → мотивация → финиш → точка старта → час
  сообщений.
* **Месячная сводка** 1-го числа; **«Кажется, я стою на месте»** — ответ с доказательствами.
* **Безопасность**: каждое сообщение человека проверяется (уровни 0–3).
* **Лимит**: первые `FREE_TRIAL_DAYS` (7) дней без ограничений, потом
  `FREE_CONVERSATIONS_PER_WEEK` (3) разговора в неделю; «Plus» — фейковая дверь, дающая
  `PLUS_BETA_DAYS` (30) дней безлимита.

В v2 нет недельных отчётов, критериев, задач-намерений, шага проверки расшифровки,
нескольких целей одновременно и процентов «пройдено к финишу». Всё это удалено вместе с
таблицами v1 (миграция `0015_drop_v1`).

---

# 2. Архитектура

```
браузер (PWA, Next.js)  ──HTTPS/JSON, SSE──▶  FastAPI (один воркер)
                                               ├─ роутеры: auth, conversations, progress, me, telegram, push, admin, adminui
                                               ├─ services/: разговор, память, безопасность, outreach, прогресс…
                                               ├─ фоновые циклы в lifespan (asyncio)
                                               └─ PostgreSQL 16 (Alembic) · аудио на диске (AUDIO_DIR)
внешние сервисы: OpenAI (Chat Completions, эмбеддинги) · Deepgram (STT) · Web Push · Telegram Bot API · Resend
```

* Всё состояние фоновой работы — в БД (`memory_extracted_at`, `last_reminded_on`,
  `monthly_summaries`…), поэтому рестарт ничего не теряет и ничего не дублирует.
* Ответ в разговоре генерируется отдельной `asyncio`-задачей со своей сессией БД и
  пишет события в очередь; HTTP-поток читает очередь. Закрытая вкладка не обрывает
  ответ — он дописывается и сохраняется.
* Процесс один (`--workers 1`): ограничитель перебора, «ответ уже идёт», семафоры
  провайдеров и циклы живут в памяти процесса.

---

# 3. Структура проекта

```
progress-backend/
├── app/
│   ├── main.py          lifespan (проверка схемы, циклы), роутеры, /health
│   ├── config.py        все настройки (pydantic-settings, .env)
│   ├── db.py            async engine, SessionLocal, Base
│   ├── deps.py          CurrentUser, AdminUser, admin_from_cookie
│   ├── models.py        таблицы
│   ├── schemas.py       Pydantic: вход/выход API
│   ├── security.py      bcrypt, JWT (access/refresh/verify/restore)
│   ├── time_utils.py    valid_timezone, tz_of, local_today
│   ├── vapid.py         python -m app.vapid — ключи для push
│   ├── templates/       Jinja2-админка (обзор, люди, человек, разговор, события)
│   ├── routers/
│   │   ├── auth.py          регистрация, вход, почта, профиль, удаление/восстановление
│   │   ├── conversations.py разговор дня (SSE), лента, поиск, аудио, оценки, флажки, нити, память, календарь
│   │   ├── progress.py      прогресс, месячная сводка, скрыть пару, PATCH цели
│   │   ├── me.py            пейволл, выгрузка, «сообщение ИИ открыто»
│   │   ├── telegram.py      привязка и вебхук
│   │   ├── push.py          подписка, тестовое уведомление, час и вкл/выкл
│   │   ├── admin.py         POST /api/events, JSON-админка
│   │   └── adminui.py       HTML-админка /admin
│   └── services/
│       ├── conversation.py      prepare_message, stream_reply, ReplyRenderer, контекст, правила ответа
│       ├── first_conversation.py шаги онбординга
│       ├── memory.py            извлечение фактов и нитей, пары, циклы памяти и закрытия дня
│       ├── safety.py            проверка 0–3, ресурсы помощи, совет специалисту
│       ├── limits.py            недельный лимит, пробный период, Plus
│       ├── outreach.py          ИИ пишет первым: отбор, паузы, тема, текст, доставка
│       ├── progress.py          экран «Прогресс», месячная сводка и её цикл
│       ├── telegram.py          Bot API через httpx
│       ├── push.py              Web Push (pywebpush)
│       ├── llm.py               complete_json, complete_json_with, stream_chat, embed
│       ├── stt.py               Deepgram / faster-whisper, слова с таймкодами
│       ├── prompts.py           промпты (англ.) и JSON-схемы
│       ├── verify.py            normalize, quote_supported — проверка цитат
│       ├── texts.py             все серверные строки ru/en (ru — на «вы»)
│       ├── audio.py             MIME, размер, AUDIO_DIR/<user>/<message>.<ext>
│       ├── events.py            log_event — исследовательский журнал
│       ├── errors.py            api_error → {"detail": {"code", "message"}}
│       ├── costs.py             цены и учёт стоимости вызовов
│       ├── retry.py             повтор при 429/5xx/обрыве
│       ├── accounts.py          удаление, восстановление, стирание, цикл стирания
│       ├── mail.py              письма Resend (подтверждение, удаление аккаунта)
│       ├── ratelimit.py         защита от перебора
│       └── adminstats.py        метрики админки
├── alembic/versions/    0001 … 0013 (v1), 0014_v2_core, 0015_drop_v1
├── scripts/             make_account.py, diagnose_stt.py, eval_dialogs.py
├── tests/               conftest.py, test_app.py, test_v2_*.py, eval/dialogs.yaml
└── Dockerfile, docker-entrypoint.sh, docker-compose(.prod).yml, Caddyfile, DEPLOY.md, RAILWAY.md

progress-frontend/
├── app/                 маршруты; (app)/ — экраны после входа под AppShell
├── components/          экраны и компоненты (TodayScreen, ChatThread, PairCard, …)
├── lib/                 api.ts (+ SSE), types.ts, i18n.ts, useT.ts, dates.ts, push.ts, pwa.ts, theme.ts, useRecorder.ts
└── public/              sw.js, manifest.json, иконки, landing/ (лендинг)
```

---

# 4. Стек

| Слой | Что |
|---|---|
| Бэкенд | Python 3.12 (Docker; локально 3.11+), FastAPI 0.115, SQLAlchemy 2 async (asyncpg), Alembic, Pydantic v2, httpx |
| База | PostgreSQL 16; тесты — SQLite (aiosqlite) через `create_all` |
| Модель | OpenAI Chat Completions: structured outputs (JSON-схемы), поток (`stream: true`), эмбеддинги `/embeddings`. Без SDK — `httpx` |
| Речь | Deepgram Nova-3 (`STT_PROVIDER=deepgram`) или faster-whisper локально (`local`) |
| Доставка | Web Push (pywebpush, VAPID), Telegram Bot API (httpx), Resend (письма) |
| Фронтенд | Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind v4 (CSS-first, токены в `app/tokens.css`) |
| Наблюдаемость | Sentry (если задан `SENTRY_DSN`), журнал `events`, `/admin` |

---

# 5. Функциональность

### 5.1 Аккаунт
Регистрация, вход, JWT (access 30 мин, refresh 60 дней, отзыв через `token_version`),
подтверждение почты (если задан `RESEND_API_KEY`; без него аккаунт сразу подтверждён),
смена пароля (8 символов – 72 байта), удаление с восстановлением по письму в течение
`ACCOUNT_RESTORE_DAYS` (30), затем полное стирание всех строк и аудио. Профиль: имя,
пояс, язык (`en`/`ru`), навык, страна (по умолчанию из пояса), канал сообщений ИИ
(`push`/`telegram`/`none`), час.

### 5.2 Разговор дня
`GET /api/conversations/today` создаёт день при первом обращении (первый разговор, если
человек ещё не прошёл онбординг). `POST /api/conversations/today/messages` — JSON `{text}`
или multipart с `audio` (или `text`). До потока — обычные JSON-ошибки: 403
`email_not_verified`, 402 `limit_reached`, 409 `reply_in_progress`, 413/415/400 для аудио,
422 `empty_text`/`text_too_long`. Дальше — SSE:

| Событие | Данные |
|---|---|
| `user_message` | сохранённое сообщение человека (с расшифровкой для голоса) |
| `delta` | кусок текста ответа |
| `quote` | сегмент-цитата `{fact_id, quote, local_date, recalled?, audio_start_ms?, audio_end_ms?, message_id?}` |
| `done` | итоговое сообщение ассистента (`MessageOut`), быстрые ответы |
| `error` | `{code}`: `no_speech`, `stt_failed`, `llm_failed` |

Модель пишет `{{quote:<fact_id>}}` только для фактов, которые ей дали в контексте;
`ReplyRenderer` подставляет цитату из БД и молча выбрасывает незнакомый id. После
`<<<META>>>` модель отдаёт JSON (быстрые ответы, `intent`) — он не стримится. Правила
ответа (длина `REPLY_MAX_WORDS`, один вопрос, `BANNED` — похвала и диагнозы) проверяются
после потока, нарушение пишется событием `reply_rule_violation`.

Контекст ответа: навык, мотивация, финиш, до `CONTEXT_FACTS` фактов (по смыслу через
эмбеддинги, без `EMBEDDING_MODEL` — по дате; флажок «неточно» исключает факт навсегда),
`CONTEXT_THREADS` открытых нитей, выжимки `CONTEXT_DAYS` дней.

### 5.3 Первый разговор
Шаги в `conversations.state`: `skill → motivation → finish → baseline → schedule → done`.
Тексты вопросов — из `texts.py`, модель только читает ответ (`on_topic`, название навыка,
цитата мотивации, варианты финиша, пары «тогда → сейчас»). Один мягкий повтор на
пустой/посторонний ответ. Незавершённый онбординг продолжается на следующий день с того же
шага. По завершении — `first_conversation_done`, события `onboarding_completed` и др.

### 5.4 Память
`memory_loop` раз в `MEMORY_TICK_MINUTES` берёт разговоры, затихшие на
`MEMORY_IDLE_MINUTES`; `close_day_loop` закрывает день в `CLOSE_DAY_HOUR` по местному
времени. `extract_memory` в одной транзакции: факты (цитата проверена по своему сообщению,
отброшенные считаются в событии `memory_dropped_facts`), открытие/упоминание/закрытие нитей,
выжимка дня (`conversations.summary`), таймкоды цитаты в аудио по словам Deepgram, пары
«было → стало» (`PAIR_MIN_DAYS` между фактами, `PAIR_MIN_SIMILARITY` для пар по смыслу).
Повторный запуск ничего не добавляет.

### 5.5 ИИ пишет первым
`outreach.loop` раз в `REMINDER_TICK_MINUTES`: люди с `reminders_on`, каналом не `none`,
завершённым первым разговором, у которых наступил `reminder_hour` и сегодня ещё не писали.
Тема: открытая нить → цель после тишины → вчерашний разговор → общий вопрос. Не пишет, если
человек уже писал сегодня, после сообщения уровня безопасности 3, реже после
`OUTREACH_PAUSE_AFTER` неотвеченных, прощается после `OUTREACH_FAREWELL_DAYS` тишины.
Сообщение ложится в разговор дня (`source = outreach`), push/Telegram ведут на
`/today?o=<outreach_id>`.

### 5.6 Безопасность
`safety_check` на каждое сообщение человека (`SAFETY_MODEL`): 0 — обычно; 1 — мягче, при
частой усталости — редкий совет обратиться к специалисту; 2 — отдельный промпт без памяти и
прогресса; 3 — шаблон без модели с контактами `SAFETY_RESOURCES` по стране человека (пусто
— общая рекомендация без номеров). Ошибка проверки → уровень 0 и событие
`safety_check_failed`.

### 5.7 Прогресс и месячная сводка
`GET /api/progress`: цель и финиш, последние факты уровня, пары, открытые и закрытые нити,
новая сводка. `monthly_loop` 1-го числа после `CLOSE_DAY_HOUR` собирает сводку за прошедший
месяц: числа считает код; ниже `MONTHLY_MIN_CONVERSATIONS` разговоров и
`MONTHLY_MIN_PAIRS` пар — `thin` без модели; иначе модель пишет три поля с плейсхолдерами
цитат. Процентов нет нигде.

### 5.8 «Кажется, я стою на месте»
`POST /api/conversations/today/plateau` — SSE-ответ с доказательствами (якорь, до 3 пар с
наибольшим разрывом, закрытые нити); не засчитывает день и не проверяет лимит.

### 5.9 Лимит и Plus
Неделя — пн–вс в поясе человека; день засчитывается, когда человек написал
(`counts_for_limit`). `POST /api/paywall/click` ставит `plus_until`.

### 5.10 История, поиск, выгрузка
Лента дней, день целиком, удаление дня (вместе с сообщениями, аудио и фактами), поиск по
тексту, календарь для ленты недели, `GET /api/me/export` — JSON всех данных человека.

### 5.11 Аналитика и админка
`events.log_event` дополняет каждое событие `day_number`, `language`, `channel`. Клиентские
события — через `POST /api/events`. `/admin` (вход по паролю администратора, cookie
`ft_admin`): D1/D7 по когортам, доля ответов на сообщение ИИ первым, доля «помогло» с
цитатой и без, доля цитат «неточно», разговоры с уровнем безопасности ≥ 2, средняя
стоимость разговора, люди, события.

---

# 6. API

Ошибки v2-эндпоинтов — `{"detail": {"code", "message"}}` (`services/errors.py`);
аутентификация и push отдают строки, как раньше. Полный список с телами — `/docs`.

| Метод и путь | Что делает |
|---|---|
| `GET /health` | `{api, database}` без подробностей |
| `POST /api/auth/register` · `login` · `refresh` · `change-password` · `logout-everywhere` | аккаунт и токены |
| `POST /api/auth/verify` · `resend-verification` · `restore` | ссылки из писем (без сессии) |
| `GET` · `PATCH` · `DELETE /api/auth/me` | профиль; удаление с письмом о восстановлении |
| `GET /api/conversations/today` | разговор сегодня (`ConversationOut` с `limit`) |
| `POST /api/conversations/today/messages` | сообщение → SSE-ответ |
| `POST /api/conversations/today/plateau` | «стою на месте» → SSE-ответ |
| `GET /api/conversations?before=&limit=` | лента дней (`DayOut`) |
| `GET` · `DELETE /api/conversations/{YYYY-MM-DD}` | день целиком; удаление дня (409 во время ответа) |
| `GET /api/search?q=` | поиск по сообщениям |
| `GET /api/calendar?from=&to=` | дни с разговором (не больше `CALENDAR_MAX_DAYS`) |
| `GET /api/messages/{id}/audio` | запись сообщения (только владельцу) |
| `POST /api/messages/{id}/rating` | «Помогло» / «Не то» |
| `POST /api/facts/{id}/flag` | «Это неточно» — факт больше не используется |
| `PATCH /api/threads/{id}` | переименовать, закрыть, удалить нить |
| `GET /api/memory` | что ForwardTrace помнит: цель, нити, последние факты |
| `GET /api/progress` · `GET /api/progress/monthly?month=YYYY-MM` | прогресс; месячная сводка |
| `POST /api/pairs/{id}/hide` | скрыть карточку «было → стало» |
| `PATCH /api/goal` | цель, мотивация, финиш (`finish_line: null` — без финиша) |
| `POST /api/paywall/click` | бета-Plus → `{plus_until}` |
| `GET /api/me/export` | файл `forwardtrace-export-<дата>.json` |
| `POST /api/outreach/{id}/opened` | отметить, что сообщение ИИ открыто (204, идемпотентно) |
| `POST` · `DELETE /api/telegram/link` | ссылка привязки бота; отвязка |
| `POST /api/telegram/webhook` | вебхук (заголовок `X-Telegram-Bot-Api-Secret-Token`) |
| `GET /api/push/key` · `POST subscribe` · `POST unsubscribe` · `POST test` · `PATCH settings` | push |
| `POST /api/events` | клиентское событие в журнал |
| `GET /api/admin/overview` · `GET /api/admin/conversations/{id}` | JSON-админка (`ADMIN_EMAILS`) |
| `/admin`, `/admin/users`, `/admin/users/{id}`, `/admin/conversations/{id}`, `/admin/events` | HTML-админка |

Каждый эндпоинт отдаёт и меняет только данные текущего человека (тесты изоляции в
`tests/test_v2_*.py`).

---

# 7. Модель данных

Все PK — UUID (создаются в Python). FK на `users.id` — `ON DELETE CASCADE`. JSON-поля —
`JSONB` в Postgres (`JSON` в SQLite).

| Таблица | Что хранит |
|---|---|
| `users` | почта, пароль, пояс, язык, подтверждение, `token_version`, удаление; v2: `skill`, `country`, `outreach_channel`, `telegram_chat_id`, `telegram_link_token`, `outreach_unanswered`, `plus_until`, `first_conversation_done`; `reminder_hour`, `reminders_on`, `last_reminded_on` — час и дата сообщений ИИ первым |
| `goals` | одна активная цель-якорь: `title`, `why_text` (цитата мотивации), `finish_line`, `finish_set_on`, `why_message_id`, `baseline_message_id` |
| `conversations` | один на `(user_id, local_date)`: `kind` (`first`/`daily`), `started_by`, `state`, `summary`, `safety_level`, `counts_for_limit`, `memory_extracted_at` |
| `messages` | `role`, `source` (`text`/`voice`/`outreach`), `content_raw` (с плейсхолдерами), `content` (сегменты), `words` (таймкоды), аудио, `quick_replies`, `used_fact_ids`, `intent`, `safety_level`, `rating`, `cost_usd` |
| `facts` | `type`, `text`, `quote` (проверена), `local_date`, `message_id`, `audio_start_ms`/`audio_end_ms`, `thread_id`, `embedding`, `flagged_at` |
| `threads` | `title`, `status` (`open`/`closed`/`deleted`), `opened_fact_id`, `closed_fact_id`, даты |
| `pairs` | `then_fact_id`, `now_fact_id`, `theme`, `recalled`, `source`, `hidden_at`; уникальна пара фактов |
| `monthly_summaries` | `(user_id, month)` уникально: `status` (`done`/`thin`/`failed`), `stats`, `content`, `viewed_at` |
| `outreach` | сообщение ИИ первым: `topic`, `thread_id`, `channel`, `delivered`, `opened_at`, `replied_at` |
| `push_subscriptions` | браузер на устройстве: `endpoint` (уникален), ключи, счётчик сбоев |
| `events` | журнал: `type`, `payload` (с `day_number`, `language`, `channel`) |

Ссылки фактов на сообщение и нить, нитей на факты, целей и outreach на сообщения —
`SET NULL`; пары на факты и сообщения на разговор — `CASCADE`. Цикл `facts.thread_id` ↔
`threads.*_fact_id` разорван `use_alter`.

**Миграции.** Цепочка `0001_baseline … 0013_account_deletion` (v1) → `0014_v2_core`
(таблицы v2 и новые поля) → `0015_drop_v1` (удаляет `task_mentions`, `tasks`,
`activities`, `entries`, `reports`, `criteria` и `users.tasks_declined_on`; `downgrade`
восстанавливает их схему, но не данные). При старте `_check_schema` сверяет модели с базой
и отказывается подниматься, если чего-то не хватает («Run: alembic upgrade head»).
Импорт данных v1 (`scripts/import_v1.py`) удалён на этапе 10: у владельца не было
пользователей с данными v1, а `alembic upgrade head` в `docker-entrypoint.sh` проходит
0014 и 0015 подряд, так что окна для импорта на деплое нет; скрипт остаётся в истории git.

---

# 8. Фоновые циклы

Запускаются в `lifespan` (`app/main.py`), идемпотентны, ловят и логируют исключения,
пробрасывают `CancelledError`, состояние держат в БД.

| Цикл | Как часто | Что делает |
|---|---|---|
| `memory.memory_loop` | `MEMORY_TICK_MINUTES` (5) | извлекает память из разговоров, затихших на `MEMORY_IDLE_MINUTES` (30) |
| `memory.close_day_loop` | тот же тик | в `CLOSE_DAY_HOUR` (4) по местному времени закрывает день и добирает необработанное |
| `outreach.loop` | `REMINDER_TICK_MINUTES` (15) | ИИ пишет первым; выключается `REMINDERS_ENABLED=false` |
| `progress.monthly_loop` | `MONTHLY_TICK_MINUTES` (60) | месячные сводки 1-го числа |
| `accounts.loop` | `ACCOUNT_PURGE_TICK_MINUTES` (60) | стирает аккаунты, у которых истёк срок восстановления |

Ответ в разговоре — отдельная задача на каждое сообщение (не цикл); занятость разговора —
множество id в памяти процесса.

---

# 9. AI-функции

* **`llm.complete_json(system, user, schema)`** — JSON по строгой схеме (`OPENAI_MODEL`,
  `OPENAI_REASONING_EFFORT`); **`complete_json_with(..., model, reasoning_effort)`** — то же
  с другой моделью (`SAFETY_MODEL`); **`stream_chat(messages, model, reasoning_effort)`** —
  поток ответа (`CHAT_MODEL`, `CHAT_REASONING_EFFORT`); **`embed(texts)`** — эмбеддинги
  (`EMBEDDING_MODEL`). Повторы при 429/5xx/обрыве (`LLM_MAX_RETRIES`), семафор
  `LLM_CONCURRENCY`.
* **Промпты** — английские, в `services/prompts.py`; `_write_in(locale)` велит писать на
  языке человека, для русского — ещё и на «вы».
* **Цитаты**: `verify.normalize` (NFKC, без пунктуации и регистра) и
  `verify.quote_supported` (вхождение или `SequenceMatcher ≥ 0.90`, не короче 8 символов).
  Ни один факт не сохраняется без этой проверки; в ответ цитату подставляет код.
* **Речь**: `stt.transcribe` — Deepgram Nova-3, язык определяется по записи
  (`STT_LANGUAGE` пустой), `STT_MULTILINGUAL` для смешанной речи; слова с таймкодами
  (`words`) позволяют проигрывать фрагмент цитаты.
* **Стоимость**: `costs.track()` собирает STT и вызовы модели, `charge_message` пишет
  `messages.cost_usd`. Цены — настройки (`*_PRICE_*`); нулевые цены дают предупреждение
  при старте.
* **Оценка диалогов**: `scripts/eval_dialogs.py` по `tests/eval/dialogs.yaml` (нужен
  `OPENAI_API_KEY`, вызовы платные).

---

# 10. Безопасность и приватность

* Пароль: bcrypt (12 раундов), 8 символов – 72 байта при регистрации и смене.
* JWT HS256 с `JWT_SECRET`; вне `APP_ENV=test` приложение не стартует с секретом-заглушкой.
  Токены на клиенте — в `localStorage` (`progress.tokens`).
* Защита от перебора на вход, регистрацию, повторное письмо и вход в админку — по почте и
  по IP (`*_LIMIT_PER_EMAIL`, `*_LIMIT_PER_IP`, `CLIENT_IP_HEADER`), ответ 429 +
  `Retry-After`.
* Тратить деньги (сообщения, «стою на месте») может только подтверждённая почта.
* Аудио — `AUDIO_DIR/<user_id>/<message_id>.<ext>`, до `MAX_AUDIO_MB`, белый список MIME,
  отдаётся только владельцу; стирается вместе с днём или аккаунтом.
* Sentry без PII и тел запросов. Токен бота Telegram не попадает в логи.
* Секреты — только в `.env` (в git не коммитится); шаблон — `.env.example`.

---

# 11. Фронтенд

| Маршрут | Экран |
|---|---|
| `/` | лендинг (`public/landing/`, через `rewrites` в `next.config.mjs`) |
| `/register`, `/login`, `/verify`, `/restore` | вход и письма |
| `/today` | лента недели (`WeekStrip`) и разговор дня (`ChatThread`, `Composer`, `QuickReplies`); `?o=<id>` отмечает открытое сообщение ИИ |
| `/history`, `/history/[date]` | дни с разговорами, поиск; день целиком |
| `/progress`, `/progress/monthly/[month]` | цель и финиш (`FinishPath`), карточки (`PairCard`), нити (`ThreadChip`), сводка (`MonthlySummaryCard`) |
| `/profile` | профиль, язык, тема, канал и час сообщений, Telegram, выгрузка, удаление |

* `lib/api.ts`: `request` с Bearer и одним обновлением токена по 401; `streamPost` — SSE
  через `fetch` с той же логикой; `ApiError(status, message, retryAfter, code)`.
* `lib/i18n.ts` — словари ru/en (ru на «вы», без форм с родом), `errorText(code)`;
  `useT()` берёт язык из профиля.
* `app/tokens.css` — все цвета, отступы, радиусы и шрифты; тёмная (по умолчанию) и светлая
  темы через `data-theme`.
* `public/sw.js` — только push (без кеширования).

---

# 12. Настройки

Бэкенд читает `progress-backend/.env` (шаблон со всеми переменными и стартовыми
значениями — `.env.example`; поля — `app/config.py`). Главные группы:

| Группа | Переменные |
|---|---|
| Окружение | `APP_ENV` (`production`/`development`/`test`), `DATABASE_URL`, `CORS_ORIGINS`, `APP_URL`, `ADMIN_EMAILS`, `AUDIO_DIR`, `MAX_AUDIO_MB` |
| Аутентификация | `JWT_SECRET`, `ACCESS_TOKEN_TTL_MIN`, `REFRESH_TOKEN_TTL_DAYS`, лимиты перебора |
| Речь | `STT_PROVIDER`, `DEEPGRAM_API_KEY`, `DEEPGRAM_MODEL`, `STT_LANGUAGE`, `STT_DETECT_LANGUAGE`, `STT_MULTILINGUAL`, `STT_KEYTERMS`, `WHISPER_*` |
| Модели | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_REASONING_EFFORT`, `CHAT_MODEL`, `CHAT_REASONING_EFFORT`, `SAFETY_MODEL`, `EMBEDDING_MODEL`, `LLM_MAX_RETRIES` |
| Цены | `STT_PRICE_PER_MIN`, `LLM_PRICE_*`, `CHAT_PRICE_*`, `SAFETY_PRICE_*`, `EMBEDDING_PRICE_PER_1M` |
| Почта | `RESEND_API_KEY`, `EMAIL_FROM`, `REQUIRE_VERIFIED_EMAIL`, `EMAIL_VERIFICATION_TTL_HOURS` |
| Аккаунт | `ACCOUNT_RESTORE_DAYS`, `ACCOUNT_PURGE_TICK_MINUTES` |
| Push и outreach | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT_EMAIL`, `REMINDERS_ENABLED`, `REMINDER_TICK_MINUTES`, `OUTREACH_*` |
| Лимит | `FREE_TRIAL_DAYS`, `FREE_CONVERSATIONS_PER_WEEK`, `PLUS_BETA_DAYS` |
| Разговор | `REPLY_MAX_WORDS`, `REPLY_MAX_WORDS_LONG`, `REPLY_LONG_INPUT_WORDS`, `CONTEXT_FACTS`, `CONTEXT_THREADS`, `CONTEXT_DAYS`, `NO_SPEECH_MIN_CHARS`, `MAX_TEXT_CHARS`, `MAX_QUICK_REPLIES`, `FIRST_BASELINE_MAX_PAIRS`, `CALENDAR_MAX_DAYS` |
| Память | `MEMORY_IDLE_MINUTES`, `MEMORY_TICK_MINUTES`, `CLOSE_DAY_HOUR`, `MEMORY_RECENT_FACTS`, `PAIR_MIN_DAYS`, `PAIR_MIN_SIMILARITY` |
| Сводка | `MONTHLY_MIN_CONVERSATIONS`, `MONTHLY_MIN_PAIRS`, `MONTHLY_TICK_MINUTES` |
| Безопасность | `SAFETY_RESOURCES` (JSON по странам, заполняет владелец), `SAFETY_HELP_*` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` (без токена Telegram выключен) |
| Наблюдаемость | `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` |

Фронтенд: `NEXT_PUBLIC_API_URL` (по умолчанию `http://localhost:8000`),
`NEXT_PUBLIC_SITE_URL` (канонический адрес для метаданных).

Квоты записей v1 (`MAX_VOICE_ENTRIES_PER_DAY`, `MAX_TEXT_ENTRIES_PER_DAY`), периоды отчётов,
задачи, `KEEP_AUDIO`, `DEFAULT_REMINDER_HOUR` удалены — если они остались в вашем `.env`,
их можно стереть (лишние переменные игнорируются).

---

# 13. Установка, запуск, тесты

1. Установить Python 3.11+, Node.js 20+, Docker Desktop, Git.
2. Зависимости:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
   pip install -r progress-backend/requirements.txt
   cd progress-frontend; npm install; cd ..
   ```
3. Окружение:
   ```powershell
   copy progress-backend\.env.example progress-backend\.env
   copy progress-frontend\.env.local.example progress-frontend\.env.local
   ```
   Минимум: `JWT_SECRET` (`python -c "import secrets; print(secrets.token_hex(32))"`),
   `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ADMIN_EMAILS`; для локальной разработки
   `APP_ENV=development`. `RESEND_API_KEY` можно оставить пустым — регистрация пройдёт без
   письма.
4. База и бэкенд (из `progress-backend`):
   ```powershell
   docker compose up -d db
   alembic upgrade head
   python -m uvicorn app.main:app --reload
   ```
   Аккаунт без письма: `python scripts/make_account.py user@example.com password`.
   Ключи push: `python -m app.vapid`.
5. Фронтенд (из `progress-frontend`): `npm run dev` → `http://localhost:3000`.

**Тесты бэкенда** (из `progress-backend`): `python -m pytest -o addopts= -q`. SQLite,
провайдеры замоканы в `tests/conftest.py` (`fresh_db`), `.env` не читается. Тесты
миграций на Postgres (`-m postgres`) нужен `TEST_POSTGRES_URL`, например одноразовый
контейнер:
```powershell
docker run -d --rm --name ft_pg_test -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
$env:TEST_POSTGRES_URL = "postgresql://postgres:test@localhost:55432/postgres"
python -m pytest -o addopts= -q -m postgres
docker stop ft_pg_test
```
Они проверяют чистую базу 0001 → head → 0013 → head и `_check_schema`, а также что 0015
удаляет таблицы v1, не трогая v2, и что `downgrade` до 0014 восстанавливает их схему.

**Фронтенд**: `npx tsc --noEmit && npm run build`. Тестов и линтера на фронтенде нет.

**Проверка продукта руками**: зарегистрироваться → пройти первый разговор (навык,
мотивация, финиш, где вы сейчас, час) → написать и наговорить сообщение → увидеть
цитаты в ответе, «Прогресс», «Историю». Чек-лист экранов — в [docs/v2/stages.md](docs/v2/stages.md),
этап 5.

---

# 14. Деплой

* **Railway + Vercel** — [progress-backend/RAILWAY.md](progress-backend/RAILWAY.md): API из
  `progress-backend/Dockerfile`, managed Postgres (`DATABASE_URL`), volume на `/app/data`
  для аудио; фронтенд на Vercel с `NEXT_PUBLIC_API_URL`.
* **Свой сервер** — [progress-backend/DEPLOY.md](progress-backend/DEPLOY.md):
  `docker compose -f docker-compose.prod.yml up -d --build`, Caddy с HTTPS.
* `docker-entrypoint.sh`: `alembic upgrade head`, затем `uvicorn --workers 1 --proxy-headers`.
  **Первый деплой v2 на базу v1 применит 0014 и 0015 подряд — таблицы v1 и их данные будут
  удалены** (владелец подтвердил, что пользователей с данными v1 нет).
* Telegram: после деплоя владелец регистрирует вебхук (`setWebhook` на
  `<API>/api/telegram/webhook` с `secret_token` = `TELEGRAM_WEBHOOK_SECRET`).
* Для прода: свой `JWT_SECRET`, `APP_ENV=production`, ключи провайдеров, `CORS_ORIGINS` =
  точный адрес фронтенда, `APP_URL` для ссылок в письмах и Telegram.

---

# 15. Неполадки

| Симптом | Причина | Что делать |
|---|---|---|
| `Database schema is out of date - missing: …` | не применены миграции | `alembic upgrade head` из `progress-backend` |
| `JWT_SECRET is still the placeholder…` | секрет не задан | задать `JWT_SECRET` в `.env` (или `APP_ENV=test` только для тестов) |
| `Cannot read the database schema` / 10061 | база не запущена | `docker compose up -d db`, дождаться `healthy` |
| Запрос к `localhost:8000` висит (Windows) | `localhost` → `::1`, uvicorn слушает IPv4 | использовать `127.0.0.1` |
| `ModuleNotFoundError: No module named 'app'` | запуск не из `progress-backend` | перейти в `progress-backend` |
| SSE-событие `error` `llm_failed` / `stt_failed` | нет ключа или провайдер недоступен | заполнить `OPENAI_API_KEY` / `DEEPGRAM_API_KEY`, перезапустить (`--reload` не перечитывает `.env`) |
| Расшифровка — связная бессмыслица на чужом языке | задан неверный `STT_LANGUAGE` | оставить пустым; `python scripts/diagnose_stt.py` |
| 403 `email_not_verified` | Resend настроен, почта не подтверждена | подтвердить или `scripts/make_account.py` |
| 402 `limit_reached` | исчерпан недельный лимит | ждать понедельника, «Plus» в пейволле, или поднять `FREE_CONVERSATIONS_PER_WEEK` |
| ИИ не пишет первым | `REMINDERS_ENABLED=false`, канал `none`, онбординг не завершён, нет VAPID/подписки или бота | проверить профиль, `/admin`, логи `outreach` |
| Telegram 503 `telegram_disabled` | нет `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_USERNAME` | задать; вебхук без `TELEGRAM_WEBHOOK_SECRET` отвечает 403 |
| Сеть «падает» на всех запросах в проде | `CORS_ORIGINS` не совпадает с адресом фронтенда | указать точный адрес со схемой |
| Микрофон не включается | страница не по `localhost`/HTTPS | открыть по HTTPS |
| Аудио пропадает после деплоя | нет volume на `/app/data` | подключить volume |
| В логе `no price set for …` | цены моделей нулевые | заполнить `*_PRICE_*` |

---

# 16. Открытые места и ограничения

Заполняет владелец:
* `SAFETY_RESOURCES` — контакты линий помощи по странам, только из официальных источников;
* `EMBEDDING_MODEL` и цены `CHAT_MODEL`/`SAFETY_MODEL`/`EMBEDDING_MODEL` (сейчас 0);
* `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET`, вебхук;
* `tests/eval/dialogs.yaml` — содержание диалогов для оценки;
* текст лендинга — черновик v2 (`public/landing/shared/copy.js`), финал согласует владелец.

Ограничения by design:
* один воркер: ограничитель перебора, «ответ уже идёт» и циклы — в памяти процесса;
* аудио на диске рядом с приложением, без внешнего хранилища; бэкапы базы — вручную;
* токены в `localStorage` (httpOnly-cookie требуют общего домена фронтенда и API);
* восстановления пароля нет;
* на фронтенде нет автотестов.

Подробности по каждому этапу (что сделано, принятые умолчания) — [docs/v2/stages.md](docs/v2/stages.md).
