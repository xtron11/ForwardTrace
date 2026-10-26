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
