# Интерфейсы

Читается первым каждым исполнителем и ревьюером. Имена — английские, как в коде. Факты о текущем коде — `notes.md`.

## Правила проекта

1. Бриф (`2026-10-26-brief.md`) — часть спецификации; `spec.md` §1 перечисляет поправки к нему. Где спорят — верен `spec.md`.
2. **Русские тексты — только на «вы»**, без форм с родом. Шаблоны брифа на «ты» не копировать — брать переводы из `spec.md` §6.
3. Цитата попадает к человеку только из БД через плейсхолдер `{{quote:<fact_id>}}`, отрисованный кодом. Ни один факт не сохраняется без `verify.quote_supported(quote, verify.normalize(message_text))`.
4. Промпты — английские, в `services/prompts.py`, с `_write_in(locale)`; для русского — дополнительно требование обращаться на «вы».
5. Все строки для человека — i18n ru+en: сервер — `services/texts.py`, фронтенд — `lib/i18n.ts`.
6. Числа из таблицы «Конфигурация» брифа — поля `config.py` + строки `.env.example`, не литералы в коде.
7. Новые зависимости не добавлять (Python и npm). Telegram, SSE, эмбеддинги — на `httpx` / `StreamingResponse` / `fetch`.
8. Способ хранения токенов (localStorage `progress.tokens`) и схема JWT не меняются.
9. Не трогать «Оставить как есть» из брифа сверх того, что бриф там же разрешает (новые таблицы в стирании аккаунта, новые поля в `PATCH /api/auth/me`, события в `events`). Нужно больше — тикет возвращается с `BLOCKED`.
10. LLM/STT/эмбеддинги/push/Telegram в тестах замоканы; каждый новый эндпоинт — тест изоляции между двумя пользователями.
11. Тесты: `cd progress-backend && ../venv/Scripts/python.exe -m pytest -o addopts= -q`. Фронтенд: `cd progress-frontend && npx tsc --noEmit && npm run build`.
12. Фоновые циклы идемпотентны: ловят и логируют исключения, продолжают; `CancelledError` пробрасывают; состояние — в БД, не в памяти.
13. Каждый тикет дописывает строки в свой раздел `docs/v2/stages.md`: первый тикет этапа — план до правок кода; каждый — что сделано и тесты; последний — открытое и принятые умолчания.
14. `public/sw.js` не меняется. Ссылки из push и Telegram — `/today?o=<outreach_id>`.
15. Числа логики — настройки (`spec.md` §1.11 и таблица «Конфигурация» брифа).

## Границы, решённые в спецификации

### Данные — `app/models.py` (этап 1)

Новые модели: `Conversation`, `Message`, `Fact`, `Thread`, `Pair`, `MonthlySummary`, `Outreach` — таблицы и поля строго по брифу («Модель данных»), имена таблиц: `conversations`, `messages`, `facts`, `threads`, `pairs`, `monthly_summaries`, `outreach`. Новые поля `User` и `Goal` — по брифу. `pk()`, `fk()`, `JsonB`, `PgUUID` — существующие помощники. FK на `users.id` — `CASCADE`; `facts.message_id`, `facts.thread_id`, `threads.opened_fact_id/closed_fact_id`, `goals.why_message_id/baseline_message_id` — `SET NULL`; `pairs.then_fact_id/now_fact_id` — `CASCADE`; `messages.conversation_id` — `CASCADE`. Строковые перечисления — `String(16)`, значения как в брифе.

Pydantic (`app/schemas.py`): `MessageOut{id, role, source, content: list[Segment], quick_replies, intent, rating, has_audio, audio_seconds, detected_language, created_at}`, `Segment = {type:"text", text} | {type:"quote", fact_id, quote, local_date, recalled?: bool, audio_start_ms?, audio_end_ms?, message_id?}`, `ConversationOut{id, local_date, kind, started_by, state, messages, limit: {used, free, plus, trial}}`, `DayOut{local_date, summary, started_by, threads: list[{id,title,status}], message_count}`, `ThreadOut{id, title, status, opened_on, closed_on, last_mentioned_on}`, `FactOut{id, type, text, quote, local_date, message_id, audio_start_ms, audio_end_ms, flagged}`, `PairOut{id, theme, recalled, source, then: FactOut, now: FactOut}`, `GoalOut` (v2: id, title, why_text, finish_line, finish_set_on), `MemoryOut`, `ProgressOut{goal, level_facts, pairs, open_threads, closed_threads, monthly: MonthlySummaryOut|None}`, `MonthlySummaryOut{month:"YYYY-MM", status, stats, content: {intro, open_struggle, next_step} as segment lists, viewed_at}`. `UserOut` дополняется `skill, country, outreach_channel, telegram_linked: bool, plus_until, first_conversation_done`.

### Ошибки — `app/services/errors.py`

`api_error(status: int, code: str, message: str) -> HTTPException` — `detail = {"code", "message"}`. Коды: `limit_reached`(402), `email_not_verified`(403), `audio_too_large`(413), `unsupported_audio`(415), `empty_audio`(400), `empty_text`/`text_too_long`(422), `reply_in_progress`(409), `not_found`(404), `telegram_disabled`(503), `bad_range`(400); события потока: `no_speech`, `stt_failed`, `llm_failed`.

### События — `app/services/events.py`

`async log_event(db: AsyncSession, user: User | None, type: str, payload: dict | None = None) -> None` — добавляет `Event` (без commit) с payload, дополненным `day_number`, `language`, `channel`. Существующие места (`accounts.py`) не переписываются.

### Тексты сервера — `app/services/texts.py`

`t(locale: str | None, key: str, **kw) -> str` и `quick(locale, key) -> list[str]`; словари `RU`, `EN`; ключи — по шагам первого разговора, темам outreach, шаблонам безопасности, сводке, push.

### Провайдеры

- `services/llm.py`: `complete_json(system, user, schema) -> LLMResult` — без изменений сигнатуры; новая `complete_json_with(system, user, schema, *, model: str, reasoning_effort: str | None = None) -> LLMResult` (обе — через общую внутреннюю функцию); `async def stream_chat(messages: list[dict], *, model: str | None = None, reasoning_effort: str | None = None) -> AsyncIterator[str]` — отдаёт текстовые куски, по завершении вызывает `costs.record_llm`; ошибки → `LLMError`. `async def embed(texts: list[str]) -> list[list[float]]` — `LLMError` при ошибке; вызывающий проверяет `settings.embedding_model` заранее.
- `services/stt.py`: `STTResult` получает `words: list[dict]` — `[{"w": str, "start": float, "end": float}]` (секунды, как у Deepgram; `punctuated_word` если есть, иначе `word`); пусто у локального провайдера.
- `services/costs.py`: места цен под `chat_model`, `safety_model`, `embedding_model` (настройки, по умолчанию 0); `charge_message(message, usage)` — пишет `cost_usd` (сумма STT+LLM) в `Message`.

### Аудио — `app/services/audio.py` (выносится из `routers/entries.py`)

`ALLOWED_AUDIO`, `async save_message_audio(file: UploadFile, user_id, message_id) -> tuple[str, str]` → `AUDIO_DIR/<user_id>/<message_id>.<ext>`; ошибки — `api_error` с кодами выше. `delete_files(paths: Iterable[str]) -> None`.

### Разговор — `app/services/conversation.py`

- `async get_or_create_today(db, user) -> Conversation` — создаёт `first` (с приветствием) если `not user.first_conversation_done` и разговоров нет; иначе `daily`.
- `async prepare_message(db, user, *, text: str | None, audio: UploadFile | None) -> PreparedMessage` — все проверки «до потока» (лимит, почта, занятость, аудио), сохраняет файл; бросает `HTTPException`.
- `def stream_reply(prepared: PreparedMessage, *, plateau: bool = False) -> AsyncIterator[str]` — SSE-строки; внутри — своя сессия и фоновая задача (ответ доживает до конца при разрыве).
- `class ReplyRenderer(known: dict[str, Fact])` — `feed(chunk: str) -> list[tuple[str, dict]]` (события `delta`/`quote`), `finish() -> RenderedReply(content_raw, segments, used_fact_ids, meta: dict)`. META после `<<<META>>>` не стримится.
- `def sse(event: str, data: dict) -> str`.
- `async build_context(db, user, conversation, text, *, mode: "normal"|"plateau", soft: bool) -> ChatContext(messages: list[dict], known: dict[str, Fact])`.
- `check_reply_rules(text: str, user_words: int) -> list[str]` — нарушения для `reply_rule_violation`. `BANNED` переносится из `reflection.py` в `services/conversation.py` (или `services/rules.py`) и импортируется оттуда.
- Первый разговор: `async first_conversation_step(db, user, conversation, message) -> FirstReply(text_segments, quick_replies, done: bool)` — шаги по брифу; живёт в `services/first_conversation.py`, вызывается из `stream_reply`.
- Занятость: in-process `set` id разговоров, у которых идёт ответ (один воркер).

### Лимит — `app/services/limits.py`

`async limit_status(db, user, today: date) -> LimitOut{used, free, plus, trial}`; `async ensure_can_message(db, user, conversation, today) -> None` — 402 `limit_reached`, если день ещё не засчитан и лимит исчерпан. Неделя — пн–вс в поясе человека.

### Память — `app/services/memory.py`

`async extract_memory(conversation_id: uuid.UUID) -> None` (своя сессия, идемпотентно); `async memory_loop()`, `async close_day_loop()`; `async relevant_facts(db, user_id, text: str, limit: int) -> list[Fact]` (эмбеддинг запроса или по дате; только `flagged_at IS NULL`); `align_quote(words: list[dict], quote: str) -> tuple[int, int] | None`; `cosine(a, b) -> float`; `async make_pairs(db, user_id, new_facts, closed_threads) -> list[Pair]`.

### Безопасность — `app/services/safety.py`

`async safety_check(text: str, locale: str | None) -> int` (0 при ошибке + событие `safety_check_failed` пишет вызывающий через флаг результата: возвращает `SafetyResult(level, failed: bool)`); `resources_for(country: str | None) -> list[dict]`; `level3_text(user) -> str`; `async level2_reply_stream(...)` использует `prompts.SAFETY_SYSTEM`; `async should_suggest_help(db, user, today) -> bool`.

### Outreach — `app/services/outreach.py`

`async run_once(now: datetime | None = None) -> int`, `async loop()`; `async pick_topic(db, user, today) -> Topic(kind, thread, ...)`; `async deliver(db, user, outreach, text_plain) -> bool` (push или Telegram). Заменяет `reminders.run_once`; `reminders.py` удаляется на этапе 10 (тексты `MESSAGES` → `texts.py`).

### Telegram — `app/services/telegram.py`, `app/routers/telegram.py`

`enabled() -> bool`; `async send_message(chat_id: int, text: str, button_url: str | None) -> bool`; `async create_link(db, user) -> str`; `async handle_update(update: dict) -> None` (`/start <token>`; ответы в бот — Should, через `prepare_message`/`stream_reply`, собирая поток в одно сообщение).

### Прогресс — `app/services/progress.py`

`async progress_for(db, user) -> ProgressOut`; `async build_monthly(user_id, month: date) -> MonthlySummary | None`; `async monthly_loop()`. Подсчёт дней — по `conversations.counts_for_limit`.

### Роутеры

- `routers/conversations.py`: `/api/conversations/*`, `/api/search`, `/api/messages/{id}/audio`, `/api/messages/{id}/rating`, `/api/facts/{id}/flag`, `/api/threads/{id}`, `/api/memory`, `/api/calendar`.
- `routers/progress.py`: `/api/progress`, `/api/progress/monthly`, `/api/pairs/{id}/hide`, `/api/goal`.
- `routers/me.py`: `/api/paywall/click`, `/api/me/export`, `POST /api/outreach/{id}/opened` (204, идемпотентно; ставит `opened_at`, событие `outreach_opened`).
- `routers/telegram.py`: `/api/telegram/link`, `/api/telegram/webhook`.
- `routers/auth.py`: `UserUpdate` + `skill`, `country`, `outreach_channel`; смена пароля — проверка 72 байт.

### Импорт — `scripts/import_v1.py`

`async run(db_url: str | None = None) -> ImportSummary(conversations, messages, facts, dropped_quotes)`; читает таблицы v1 через SQLAlchemy Core (`text()`-запросы), не через ORM-модели v1 — чтобы не зависеть от их удаления. Идемпотентность — по `(user_id, local_date)` разговора, по совпадению текста сообщения внутри разговора и по нормализованной цитате факта.

### Фронтенд — `progress-frontend/`

- `app/tokens.css` — все токены; `globals.css` импортирует его и маппит в `@theme inline`.
- `lib/api.ts`: `ApiError(status, message, retryAfter, code: string | null)`; `api.*` для всех эндпоинтов v2; `streamPost(path: string, body: object | FormData, onEvent: (event: string, data: any) => void, signal?: AbortSignal): Promise<void>` — Bearer + один refresh по 401, ошибки до потока → `ApiError` с `code`.
- `lib/types.ts` — типы v2 по схемам выше.
- `lib/i18n.ts` — `dict(locale)`, `errorText(code, t)`; `lib/useT.ts` — locale из `users.locale` после входа.
- Компоненты (`components/`): `WeekStrip`, `ChatThread`, `MessageBubble`, `QuoteChip`, `QuickReplies`, `Composer`, `PairCard`, `FinishPath`, `MonthlySummaryCard`, `PaywallSheet`, `DayCard`, `ThreadChip`, `PlayAudio` (+ `startMs?`, `endMs?`), `AppShell` (шапка с шестерёнкой + нижняя панель Сегодня/История/Прогресс, защита входа).
- Маршруты: `/login`, `/register`, `/verify`, `/restore`, `/today`, `/history`, `/history/[date]`, `/progress`, `/progress/monthly/[month]`, `/profile`. Лендинг `/` — без изменений до этапа 10.

## Швы для тестов

- Подмена провайдеров по атрибуту модуля в `conftest.fresh_db`: `conversation.stream_chat`, `first_conversation.complete_json`, `memory.complete_json`, `memory.embed`, `safety.complete_json`, `outreach.complete_json`, `progress.complete_json`, `conversation.transcribe` (или единая точка, если модуль импортирует модулем). Каждый новый модуль, импортирующий провайдер по имени, добавляет свою подмену сюда.
- Время: функции циклов принимают `now`.
- `push.send_to_user` и `telegram.send_message` подменяются в тестах outreach.
- SSE разбирается в тестах помощником `parse_sse(text) -> list[tuple[event, data]]` в `conftest.py`.

## Что построили готовые тикеты

(дописывается по мере сдачи)

### T01 — фундамент (коммит T01)
- Модели: `Conversation`, `Message` (свойство `has_audio`), `Fact`, `Thread`, `Pair`, `MonthlySummary`, `Outreach`; новые поля `User`/`Goal` по брифу; `fk(..., use_alter=False)`.
- Схемы: `TextSegment`, `QuoteSegment`, `Segment`, `MessageOut`, `LimitOut{used,free,plus,trial}`, `ConversationOut`, `ThreadBrief`, `DayOut`, `ThreadOut`, `ThreadUpdate`, `FactOut(flagged)`, `PairOut`, `GoalPatch`, `MemoryOut`, `MonthlyContentOut`, `MonthlySummaryOut`, `ProgressOut`, `RatingIn`, `SearchHitOut`, `CalendarDayOut`, `PaywallClickOut`, `TelegramLinkOut`; `GoalOut` + `finish_line`, `finish_set_on`; `UserOut` + `telegram_linked` и новые поля.
- `errors.api_error(status, code, message)` + константы кодов; `events.log_event(db, user, type, payload=None)`, `events.day_number(user, at=None)`; `texts.t(locale, key, **kw)`, `texts.quick(locale, key)`, `texts.month_name(locale, n)`, словари `RU`/`EN`.
- `costs.llm_price(..., model=None)`, `costs.record_embedding(model, usage)`, `costs.missing_prices() -> list[str]` (предупреждение при старте — ещё не вызвано: добавить в `main.py` lifespan), `costs.charge_message(message, usage)`; `accounts.country_for_timezone(tz)`; `import_v1.run(db_url=None) -> ImportSummary`.
- Настройки: `app_env`, модели/цены chat/safety/embedding, все числа «Конфигурации» и `spec.md` §1.11, `monthly_tick_minutes`, `safety_resources: dict`, `telegram_*` (пустая строка → None). `JWT_SECRET` по умолчанию вне `app_env=test` → ошибка создания Settings.
- `conftest`: автофикстура `fresh_db`, `client`, `register(client, email, locale, timezone)`, `parse_sse(text)`; маркер `postgres` (`TEST_POSTGRES_URL`).

### T05 — основа фронтенда (коммит T05)
- `lib/api.ts`: `streamPost(path, body: object|FormData, onEvent(event, data), signal?): Promise<void>`; `parseSse(buffer) -> {messages, rest}`; `ApiError(status, message, retryAfter, code|null)`; `api.*`: streamMessage, streamPlateau, todayConversation, listDays, getConversation, deleteConversation, search, calendar, messageAudioUrl, rateMessage, flagFact, updateThread, memory, progress, monthly, hidePair, patchGoal, paywallClick, telegramLink, exportData (Blob), outreachOpened, changePassword, updateMe(UserPatch). v1-обёртки goals/entries/reports/tasks удалены.
- `lib/i18n.ts`: `errorText(code, t)`, `describeError(err, t)`, `toLocale()`, `ERROR_CODES`/`ErrorCode`; `lib/useT.ts`: `useT() -> {t, locale, setLocale}` (localStorage `forwardtrace.locale`, обновляет `<html lang>`).
- `useUser() -> {user, setUser, signOut}` — внутри `AppShell`; `AppShell` — в группе маршрутов `app/(app)/layout.tsx` (дети рендерятся после загрузки `/api/auth/me`).
- `PlayAudio({fetchUrl, seconds?, startMs?, endMs?, playLabel?, stopLabel?})`. Заготовки: `components/ScreenPlaceholder`, `HistoryDayPlaceholder`; `AuthFrame` для экранов входа.
- Маршрута `/progress/monthly/[month]` ещё нет (тикет 09).

### T02 — разговор, бэкенд (коммит T02)
- `conversation`: `get_or_create_today(db,user)->Conversation`; `conversation_out(db,user,conv)->ConversationOut`; `prepare_message(db,user,*,text,audio)->PreparedMessage(user_id,conversation_id,message_id,source,text,audio_path,audio_mime,started)`; `stream_reply(prepared,*,plateau=False)->AsyncIterator[str]`; `release_if_unstarted(prepared)`; `is_busy(conv_id)`; `ReplyRenderer(known, recalled=None).feed/flush()/finish()->RenderedReply(content_raw,segments,used_fact_ids,meta)`; `quote_segment(fact,*,recalled)`; `sse(event,data)`; `build_context(db,user,conv,text,*,mode,soft)->ChatContext(messages,known,recalled)`; `check_reply_rules(text,user_words)->["length"|"questions"|"banned"]`; `BANNED`; `FIRST_STATE`; **`_context_facts(db,user_id,text,limit)` — точка замены для тикета 03**; ветка первого разговора — помеченный комментарий в `_reply` (шаг 4) для тикета 04. DELETE дня во время ответа → 409 `reply_in_progress`.
- `llm.complete_json_with(system,user,schema,*,model,reasoning_effort=None)`; `llm.stream_chat(messages,*,model=None,reasoning_effort=None)`; `STTResult.words`.
- `audio`: `ALLOWED_AUDIO`, `extension_for`, `save_upload`, `save_message_audio`, `delete_files`.
- `limits.limit_status`, `limits.week_bounds`, `limits.ensure_can_message` (заготовка — тикет 08); `safety.SafetyResult(level, failed)`, `safety.safety_check(text, locale)` (заготовка, 0 — тикет 08).
- `prompts.META_SEPARATOR`, `CHAT_SYSTEM`, `chat_system(locale,*,skill,anchor_quote,finish_line,threads,facts,days,max_words,soft,plateau)`.
- `conftest`: `CHAT_REPLY`, `TRANSCRIPT`, `TRANSCRIPT_WORDS`, `fake_stream_chat`, `fake_transcribe`.
- Известно: `costs.missing_prices()` ошибочно называет CHAT_MODEL/SAFETY_MODEL неоценёнными, когда они не заданы (должны наследовать OPENAI_MODEL) — правит тикет 03.

### T03 — память (коммит T03)
- `memory`: `extract_memory(conversation_id)`; `relevant_facts(db, user_id, text, limit) -> list[Fact]` (используется в `conversation._context_facts`); `align_quote(words, quote)`; `cosine(a, b)`; `make_pairs(db, user_id, new_facts, closed_threads) -> list[Pair]`; `extract_due(now=None) -> int`; `close_day(now=None) -> int`; `memory_loop()`, `close_day_loop()`; `FACT_TYPES`. Извлечение срабатывает по последнему сообщению человека.
- `llm.embed(texts) -> list[list[float]]`; `costs.missing_prices()` исправлен.
- `prompts`: `MEMORY_SCHEMA`, `MEMORY_SYSTEM`, `memory_system(locale,*,skill,finish_line,threads)`, `memory_user_prompt([(message_id, text)])`, `PAIR_THEME_SCHEMA`, `PAIR_THEME_SYSTEM`, `pair_theme_system(locale)`, `pair_theme_user_prompt(then, now)`.
- Событие `memory_dropped_facts` {conversation_id, dropped}; `GET /api/memory` → `MemoryOut`.
- `conftest`: `MEMORY_RESULT`, `PAIR_THEME`, `fake_memory_json`, `fake_embed`; подменены `memory.complete_json`, `memory.embed`.

### T04 — первый разговор (коммит T04)
- `first_conversation.first_conversation_step(db, user, conversation, message) -> FirstReply(text_segments, quick_replies, done, used_fact_ids)`; `in_first_conversation(user, conversation) -> bool`; `parse_hour(text) -> int | None`; шов теста — модульный `complete_json`.
- `conversation._first_reply(...)` вызывается из `_reply` шаг 4: сначала `safety_check`, уровень ≥ 2 — шаг не продвигается, обычный путь безопасности (тикет 08 наполняет).
- `PATCH /api/goal` {title?, why_text?, finish_line?} → `GoalOut` (меняются только присланные ключи; null — без финиша; 404 `not_found` без цели) — `routers/progress.py`.
- Ключи `state`: + `finish_options`, `session_end`. Событие `first_conversation_done`. Цитата мотивации показывается текстом в «», а не сегментом-цитатой (это не факт).
- `conftest`: `FIRST_RESULTS`, `FIRST_CALLS`, `fake_first_json`.

### T06 — экраны (коммит T06)
- Компоненты: `WeekStrip({today, refreshKey, onToday})`, `ChatThread`, `MessageBubble({message, onRate?, streaming?, currentDay?})`, `QuoteChip({segment, current?})`, `QuickReplies({options, onPick(text, index), disabled?})`, `Composer({busy, onSendText, onSendAudio(FormData), onProblem})`, `PaywallSheet({open, onClose, onGranted})` (текст-заготовка, тикет 08), `DayCard({day})`, `ThreadChip({thread})`, `FinishPath({goal})`, `HourPicker`, `NotifyOffer({hour, onClose})`; экраны `TodayScreen`, `HistoryScreen`, `DayScreen`, `ProfileScreen`, `ProgressScreen` (заготовка — тикет 09); страницы `app/(app)/*` — тонкие обёртки.
- `lib/dates.ts`: `toYmd`, `addDays`, `weekStart`, `todayIn(tz)`, `formatDay`, `weekdayShort`, `plural`.
- `api.telegramUnlink()` = `DELETE /api/telegram/link` — **эндпоинта ещё нет, добавляет тикет 07**. Профиль сейчас узнаёт, включён ли Telegram, вызовом `/api/telegram/link` (создаёт лишний токен) — тикет 07 заменяет на признак без побочных эффектов.
- «Помогло / Не то» скрыты в первом разговоре.

### T07 — outreach и Telegram (коммит T07)
- `outreach.run_once(now=None)->int`, `outreach.loop()`, `outreach.pick_topic(db,user,today)->Topic(kind,thread,goal,yesterday,facts)`, `outreach.deliver(db,user,outreach,text_plain)->bool`, `outreach.plain_text(locale,segments)->str`. Тема `general` для общего вопроса. Пауза уровня 3 — по `safety_level` последнего сообщения человека (наполнит тикет 08). Не пишет тем, кто не завершил первый разговор.
- `telegram.enabled()`, `secret_ok(header)`, `app_link(path)`, `send_message(chat_id,text,button_url=None,*,button_text=None)->bool`, `create_link(db,user)`, `handle_update(update)`; `_transport` для моков httpx.
- `POST /api/telegram/link` → {url} | 503; `DELETE /api/telegram/link` → 204; `POST /api/telegram/webhook` → {ok} | 403 | 503; `POST /api/outreach/{id}/opened` → 204 | 404 — `routers/me.py`, `routers/telegram.py`.
- `UserOut.telegram_available: bool`; `prompts.OUTREACH_SCHEMA`, `outreach_system(...)`, `outreach_user_prompt(today)`; события `outreach_sent`, `outreach_rule_violation`, `outreach_opened`; push payload {title, body, url:/today?o=<id>, tag}.
- `conftest`: `OUTREACH_RESULT`, `fake_outreach_json`, `TELEGRAM_SENT`, `fake_send_message`. `reminders.py` пока жив (push.py импортирует MESSAGES) — тикет 11.

### T08 — безопасность, plateau, лимит (коммит T08)
- `safety.safety_check(text, locale)->SafetyResult(level, failed)` (через `complete_json_with(model=SAFETY_MODEL)`); `resources_for(country)`; `level3_text(user)`; `level2_messages(locale, history)->list[dict]` (поток — тот же `stream_chat`); `should_suggest_help(db,user,today)`. Безопасность проверяется до ветки первого разговора.
- `limits.ensure_can_message` → 402 `limit_reached`; `conversation.prepare_plateau(db,user)->PreparedMessage(plateau_only=True)`; `PlateauEvidence`, `PLATEAU_MAX_PAIRS`.
- `prompts`: `SAFETY_CHECK_SCHEMA`, `SAFETY_CHECK_SYSTEM`, `SAFETY_SYSTEM`, `safety_system(locale)`, `plateau_note(...)`, `chat_system(..., plateau_block=None)`.
- `POST /api/conversations/today/plateau` → SSE без `user_message`; `POST /api/paywall/click` → {plus_until}; `GET /api/me/export` → файл `forwardtrace-export-<date>.json`; события `safety_flag{level}`, `safety_suggest_help`, `paywall_clicked`; `paywall_viewed` — с клиента.
- `conftest`: `SAFETY_RESULT`, `SAFETY_CALLS`, `fake_safety_json`; `scripts/eval_dialogs.py`: `main(argv)->0|1|2`.

### T09 — прогресс и сводка (коммит T09)
- `progress.progress_for(db, user)->ProgressOut`; `monthly_out(db, user, row)->MonthlySummaryOut`; `build_monthly(user_id, month)`; `monthly_once(now=None)->int`; `monthly_loop()`; `SHOWN_STATUSES`, `LEVEL_FACTS_SHOWN=3`, `MONTHLY_MAX_PAIRS=3`. `MonthlySummaryOut.stats` несёт `pairs`, `closed`, `why_text` (разрешаются при чтении).
- `GET /api/progress`; `GET /api/progress/monthly?month=YYYY-MM` (200|404|422); `POST /api/pairs/{id}/hide` (204|404).
- `prompts.MONTHLY_SCHEMA`, `monthly_system(...)`, `monthly_user_prompt(month)`; `conftest`: `MONTHLY_RESULT`, `MONTHLY_CALLS`, `fake_monthly_json`.
- Фронтенд: `PairCard({pair, onHidden?})`, `MonthlySummaryCard({summary})`, `MonthlySummaryView({month})`, `monthLabel(month, locale)`, `FinishPath({goal, levelFacts?})`; маршрут `/progress/monthly/[month]`.

### T10 — аналитика и админка (коммит T10)
- `POST /api/events` идёт через `events.log_event` (поля дня/языка/канала — серверные). `GET /api/admin/overview`, `GET /api/admin/conversations/{id}`; HTML `/admin`, `/admin/users`, `/admin/users/{id}`, `/admin/conversations/{id}`, `/admin/events`. v1-админка (entries, feedback, reports) удалена; админка не импортирует Entry/Activity/Report/Task (тест по исходникам).
- `adminstats`: `retention(db, now)`, `outreach_reply_share`, `helped_share`, `flagged_quote_share`, `safety_conversations`, `average_conversation_cost`, `event_counts`, `overview`, `user_rows`, `user_detail`, `conversation_detail`. Все 27 событий брифа пишутся.
