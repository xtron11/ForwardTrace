# Архитектура ForwardTrace v2

Свёрнуто из спецификации сборки. Где расходится с кодом, верен код. Подробности по этапам — `docs/v2/stages.md`, решения — `docs/adr/`, словарь — `CONTEXT.md`.

## Поток данных

1. Человек пишет или говорит в `/today`. Фронтенд шлёт `POST /api/conversations/today/messages` (текст или аудио) через `streamPost` (`progress-frontend/lib/api.ts`).
2. `conversation.prepare_message` делает все проверки до потока: лимит (`limits.ensure_can_message`, 402), почта (403), занятость разговора (409), размер и тип аудио; сохраняет файл `AUDIO_DIR/<user_id>/<message_id>.<ext>` (`audio.py`). Ошибки — `errors.api_error(status, code, message)`, у ответа `detail = {code, message}`.
3. `conversation.stream_reply` отдаёт SSE (`sse(event, data)`: `user_message`, `delta`, `quote`, ...). Ответ считается в отдельной фоновой задаче со своей сессией БД и доживает до конца при разрыве соединения; занятость — in-process `_busy`.
4. Порядок внутри ответа: STT (аудио, `stt.py`, слова с таймингами) -> `safety.safety_check` (до ветки первого разговора) -> ветка первого разговора (`first_conversation.py`) либо обычная: `build_context` (цель, финиш, нити, факты из `memory.relevant_facts`, прошлые дни) -> `llm.stream_chat` -> `ReplyRenderer`.
5. Модель пишет текст с плейсхолдерами `{{quote:<fact_id>}}`; `ReplyRenderer` заменяет их цитатами из БД и не стримит служебный хвост после `<<<META>>>` (quick_replies, intent). Цитата в ответе — только из БД (ADR 0001). `check_reply_rules` пишет `reply_rule_violation`.
6. Память: `memory_loop` берёт разговоры, затихшие на `MEMORY_IDLE_MINUTES`, и вызывает `memory.extract_memory` (идемпотентно): факты с дословной цитатой, нити (открыть, упомянуть, закрыть), `day_summary`. Факт не сохраняется без `verify.quote_supported(quote, verify.normalize(text))`; цитата привязывается к тайм-кодам аудио через `align_quote`. Эмбеддинги — JSON в таблице фактов (ADR 0003), поиск — `cosine`. `close_day_loop` закрывает день человека по `CLOSE_DAY_HOUR`. `make_pairs` собирает пары «было -> стало» (разница от `PAIR_MIN_DAYS`, сходство от `PAIR_MIN_SIMILARITY`).
7. Прогресс: `progress.progress_for` собирает цель, факты уровня, пары, нити и месячную сводку; `monthly_loop` строит сводку 1-го числа, идемпотентно.
8. Outreach (ИИ пишет первым): `outreach.loop` -> `run_once(now)` -> `pick_topic` -> модель -> сообщение попадает в разговор дня -> `deliver` (web push или Telegram). Ссылка из push и Telegram — `/today?o=<outreach_id>`; открытие — `POST /api/outreach/{id}/opened`.
9. Стирание аккаунта: `accounts.loop` удаляет данные после `ACCOUNT_RESTORE_DAYS`.

## Модули бэкенда (`progress-backend/app/`)

- `models.py`, `schemas.py`, `config.py` (все числа логики, `Settings`), `db.py`, `deps.py`, `security.py`, `time_utils.py`, `vapid.py`.
- `routers/`: `auth.py`, `conversations.py` (разговоры, день, поиск, календарь, аудио, оценка, флаг факта, нити, память), `progress.py` (`/api/progress`, месячная сводка, пары, цель), `me.py` (paywall, экспорт, outreach opened), `telegram.py`, `push.py`, `admin.py` (JSON; здесь же приём `POST /api/events` с клиента), `adminui.py` (HTML `/admin`, шаблоны в `app/templates/`).
- `services/` по ролям: разговор (`conversation`, `first_conversation`, `prompts`, `texts`, `limits`), память (`memory`, `verify`), безопасность (`safety`), исходящие (`outreach`, `push`, `telegram`), прогресс (`progress`), провайдеры (`llm`, `stt`, `retry`), учёт (`costs`, `events`, `adminstats`), аккаунты (`accounts`, `mail`, `ratelimit`), `audio`, `errors`.
- Границы: роутер тонкий, логика в `services/`; провайдеры (OpenAI, Deepgram, Bot API, push) вызываются только из `llm`, `stt`, `telegram`, `push`; админка не импортирует модели v1.

## Фронтенд (`progress-frontend/`)

- App Router. Маршруты в `app/(app)/`: `today`, `history` (+ `[date]`), `progress` (+ `monthly/[month]`), `profile`; вне группы: `login`, `register`, `verify`, `restore`; `/` — лендинг. Страницы-обёртки тонкие, экраны (`TodayScreen`, `HistoryScreen`, ...) и компоненты — в `components/`.
- `AppShell` (группа `(app)`) защищает вход и грузит `/api/auth/me`; `useUser()` работает только внутри него.
- Токены — `localStorage` ключ `progress.tokens`, схема JWT не меняется (ADR 0010). `streamPost` добавляет Bearer и делает один refresh по 401.
- Токены дизайна — `app/tokens.css`; `globals.css` маппит их в `@theme inline`. Локаль — `useT()`, строки — `lib/i18n.ts` (`errorText(code, t)` переводит коды ошибок API).

## Соглашения проекта

- Русские тексты только на «вы», без форм с родом (ADR 0007). Все строки для человека есть на ru и en: сервер — `services/texts.py` (`t(locale, key)`, `quick`), фронтенд — `lib/i18n.ts`.
- Промпты английские, в `services/prompts.py`, с `_write_in(locale)`; для русского требование обращаться на «вы».
- Числа логики — поля `config.py` и строки `.env.example`, не литералы.
- Новых зависимостей (Python, npm) не добавлять: Telegram, SSE, эмбеддинги — на `httpx`, `StreamingResponse`, `fetch`.
- События аналитики — только через `events.log_event(db, user, type, payload)` (без commit; день, язык, канал добавляются сервером).
- Фоновые циклы идемпотентны: ловят и логируют исключения, `CancelledError` пробрасывают, состояние в БД, функции принимают `now`. Циклы запускаются в `lifespan` (`app/main.py`) в процессе API, воркер один (ADR 0004).
- `provider.complete_json(system, user, schema)` для JSON; `complete_json_with(..., model=, reasoning_effort=)` для другой модели (ADR 0008).
- `public/sw.js` не меняется.
- Каждый новый эндпоинт — тест изоляции между двумя пользователями; LLM, STT, эмбеддинги, push, Telegram в тестах замоканы.

## Швы для тестов

- Подмена провайдеров по атрибуту модуля в `tests/conftest.py::fresh_db`: `conversation.stream_chat`, `conversation.transcribe`, `first_conversation.complete_json`, `memory.complete_json`, `memory.embed`, `outreach.complete_json`, `progress.complete_json`, `safety.complete_json_with`, `telegram.send_message`. Новый модуль, импортирующий провайдер по имени, добавляет подмену туда же.
- SSE в тестах разбирает `parse_sse(text)`; аккаунт — `register(client, email, locale, timezone)`.
- Тесты идут на SQLite (`test_suite.db`), `APP_ENV=test`; Postgres-миграции — маркер `postgres` и `TEST_POSTGRES_URL`.
