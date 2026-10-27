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

## Этап 2. Разговор: бэкенд

### План (тикет 02, до правок кода)

- Создаются: `progress-backend/app/services/conversation.py` (разговор дня, проверки до потока, поток ответа SSE в отдельной задаче, сборка контекста, отрисовка плейсхолдеров, правила ответа и `BANNED`), `app/services/audio.py` (MIME, размер, сохранение `AUDIO_DIR/<user_id>/<message_id>.<ext>`, удаление файлов — вынесено из `routers/entries.py`), `app/services/limits.py` (подсчёт лимита недели; проверка — заготовка до этапа 7), `app/services/safety.py` (заготовка: уровень 0), `app/routers/conversations.py`, `tests/test_v2_conversation.py`.
- Меняются: `app/services/llm.py` (`stream_chat`, `complete_json_with`, общая функция запроса; `complete_json` — та же сигнатура), `app/services/stt.py` (`STTResult.words` с таймкодами Deepgram), `app/services/prompts.py` (системный промпт разговора), `app/main.py` (роутер разговоров; предупреждение `costs.missing_prices()` при старте), `app/routers/entries.py` и `app/routers/goals.py` (только импорт помощников аудио из `services/audio.py`), `tests/conftest.py` (подмены `stream_chat` и `transcribe` разговора).
- Ничего не удаляется.

## Этап 5. Фронтенд

### Сделано (тикет 05, часть 1: основа, токены, вход, навигация)

- Удалены экраны v1: `/setup`, `/record`, `/timeline`, `/report`, `/monthly`, `/goals`, `/settings`, `/today`, `/today/result`; компоненты `Tasks`, `WhyAnchor`, `Reminders`, `Shell`; `lib/serverErrors.ts`. Сохранены без изменений: `useRecorder`, `push`, `pwa`, `theme` (кроме цвета `theme-color`, он читается из токена), `Logo`, `NotFound`, `public/sw.js`, `public/landing/`, правило `/` в `next.config.mjs`.
- `app/tokens.css` — единственное место значений цветов, отступов, радиусов и размеров шрифта; тёмная (по умолчанию) и светлая темы через `data-theme`; `globals.css` импортирует его и маппит в `@theme inline`. Шрифты v1 сохранены. В компонентах литеральных цветов нет (единственное исключение — `themeColor` в метаданных `layout.tsx`, он задаётся до загрузки CSS).
- `lib/api.ts`: токены в `localStorage` `progress.tokens` и общий refresh — как в v1; `ApiError` получил `code` (из `detail.code`); методы всех эндпоинтов v2 из брифа; `streamPost(path, body, onEvent, signal)` на `fetch` + `ReadableStream`, разбор SSE (`parseSse`), по 401 до начала потока — один refresh и один повтор. Убраны методы v1 (цели, записи, отчёты, задачи).
- `lib/types.ts` — типы v2 по схемам бэкенда, список кодов ошибок `ERROR_CODES`. `lib/i18n.ts` — словари ru (на «вы», без форм с родом) и en заново; `errorText(code, t)` и `describeError(err, t)`; таблица кодов типизирована по `ERROR_CODES`, пропущенный код не компилируется (проверено: удалённый `bad_range` в ru даёт TS2741).
- Язык интерфейса: `lib/useT.ts` — внешнее хранилище; после входа язык берётся из `users.locale` (вход и `AppShell`), обновляется `<html lang>`; до входа — язык браузера.
- Оболочка `components/AppShell.tsx` (группа маршрутов `app/(app)/`): шапка с шестерёнкой справа (`/profile`), нижняя панель Сегодня / История / Прогресс с активной вкладкой, защита входа (без токена — `/login`), загрузка пользователя. Заготовки `/today`, `/history`, `/history/[date]`, `/progress`, `/profile` — их наполняет тикет 06.
- `/login`, `/register`, `/verify`, `/restore` — новая вёрстка (`AuthFrame`, `StatusScreen`), логика v1; после входа и регистрации — `/today`. На входе при 403 появилась кнопка «отправить ещё раз».
- `PlayAudio` принимает `startMs`/`endMs` и играет только фрагмент (останавливается на `endMs`).
- `robots.ts`: список закрытых маршрутов обновлён под v2.

Проверка: `npx tsc --noEmit` и `npm run build` проходят (маршруты: `/today`, `/history`, `/history/[date]`, `/progress`, `/profile`, `/login`, `/register`, `/verify`, `/restore`). Тестового раннера на фронтенде нет и не добавлялся.

### Сделано (тикет 06: экраны Сегодня, История, Профиль)

- Заготовки `ScreenPlaceholder` и `HistoryDayPlaceholder` удалены, ключи `placeholder` убраны из словарей. Новые компоненты в `components/`: `WeekStrip`, `ChatThread`, `MessageBubble`, `QuoteChip`, `QuickReplies`, `Composer`, `HourPicker`, `NotifyOffer`, `PaywallSheet`, `DayCard`, `ThreadChip`, `FinishPath` (пока цель, мотивация, финиш), а также экраны `TodayScreen`, `HistoryScreen`, `DayScreen`, `ProfileScreen`, `ProgressScreen`. Страницы в `app/(app)/` — тонкие обёртки. Добавлено `lib/dates.ts` (даты `YYYY-MM-DD`, неделя с понедельника, `todayIn(timezone)`, склонение). В `lib/i18n.ts` — разделы `today`, `notify`, `paywall`, `history`, `profile`, `progress` в ru (на «вы», без форм с родом) и en; в `lib/api.ts` — `telegramUnlink`.
- Сегодня: лента недели (сегодня обведён, будущие приглушены, зелёные = `active`; свайп и стрелки с анимацией; неделя подгружается через `/api/calendar`, предыдущая — заранее; после каждого разговора текущая неделя запрашивается заново). Тап: зелёный день → `/history/[date]`, сегодня → прокрутка к разговору, пустой прошлый → «В этот день разговора не было».
- Разговор: ответ рисуется по мере прихода событий `user_message` / `delta` / `quote` / `done` / `error` (код → текст через `errorText`); по завершении день запрашивается заново, чтобы у сообщений были серверные id (оценки, запись) и текущее состояние первого разговора. Быстрые ответы (до 5) под последним сообщением ИИ; «Выберу время» (третий ответ шага `schedule`) открывает выбор часа и шлёт «HH:00». Поле ввода и микрофон заблокированы, пока идёт ответ; при запрете микрофона — подпись и рабочее текстовое поле; беззвучная запись не отправляется. «Помогло / Не то» — под ответами ИИ после сообщения человека (не в первом разговоре). Цитаты: «ёлочки», дата, тап → день, фрагмент аудио, «Это неточно», подпись «по вашим воспоминаниям». Кнопка «Кажется, я стою на месте» → поток `/plateau`.
- 402 `limit_reached` открывает `PaywallSheet` (текст пока из §6 спецификации; финальный текст — тикет 08), кнопка вызывает `/api/paywall/click` и повторяет отказанное сообщение.
- После первого разговора — `NotifyOffer`: кнопка «Разрешить уведомления» (разрешение просится по нажатию), при отказе, ошибке или iPhone без установки — предложение Telegram, если `/api/telegram/link` вернул ссылку (при 503 блок скрыт). `?o=<id>` → `POST /api/outreach/{id}/opened`. При возврате во вкладку после смены даты разговор запрашивается заново.
- История: дни с выжимкой и нитями, подгрузка по 30, пустое состояние, поиск с паузой 350 мс и пустым результатом. День: сообщения целиком, проигрывание голосовых и цитат, удаление с подтверждением.
- Профиль: почта; цель, мотивация и финиш с правкой (`PATCH /api/goal`, «без финиша»); час и канал (push / telegram / не писать) через `PATCH /api/auth/me`; Telegram — ссылка только когда сервер её выдаёт; язык, тема, установка PWA; выгрузка файлом `forwardtrace-export-<дата>.json`; удаление аккаунта с подтверждением; выход. «Прогресс» — цель, мотивация, финиш (остальное — тикет 09).
- Тест бэкенда `tests/test_v2_path.py` (1): регистрация → первый разговор (навык и мотивация текстом, финиш быстрым ответом, точка старта голосом с замоканным STT) → сравнение «тогда → сейчас» с цитатами `recalled` и границами фрагмента → час «18:00» → `first_conversation_done` → сегодня `active` в календаре → день в ленте и целиком → аудио сообщения цитаты отдаётся целиком → у другого человека 404 на аудио и день, лента пуста.

Проверка: `npx tsc --noEmit` и `npm run build` проходят; бэкенд — все тесты. Браузера в сессии не было: ширина 375 px не проверялась глазами, только вёрсткой (колонка 40rem, `min-w-0`, `break-words`, переносы в рядах кнопок).

### Чек-лист «пройти руками» (критерий этапа 5, 375 px)

Бэкенд и фронтенд запущены локально; ширина окна 375 px (режим устройства в браузере); микрофон разрешён.

1. Зарегистрироваться: открывается `/today`, ИИ уже задал первый вопрос, лента недели без зелёных дней.
2. Нажать быстрый ответ «Программирование» (или написать своё), затем ответить на «Зачем вам это?» текстом.
3. На вопрос о финише нажать одну из кнопок. Должно появиться «Где вы сейчас относительно этого?».
4. Ответить на точку старта голосом (микрофон → стоп). Видно расшифровку, затем ответ с двумя цитатами в «ёлочках» и подписью «по вашим воспоминаниям», у цитаты из голоса есть кнопка «Слушать».
5. Нажать «Выберу время»: открывается выбор часа; выбрать час и убедиться, что ИИ подтвердил время.
6. Нажать «Разрешить уведомления»: браузер спрашивает разрешение. Проверить и отказ: должно появиться предложение Telegram (если бот настроен) или подсказка про профиль.
7. Сегодняшний день на ленте зелёный. Проверить: свайп влево/вправо листает недели с анимацией, стрелки то же, в будущую неделю уйти нельзя.
8. Тап по пустому прошедшему дню: подсказка «В этот день разговора не было». Тап по сегодняшнему: прокрутка к разговору.
9. Тап по зелёному дню (сегодня тоже, перейти через «История») открывает `/history/<дата>`: сообщения, голосовое проигрывается, цитата проигрывается (кнопка «Слушать» воспроизводит только фрагмент).
10. Горизонтального скролла нигде нет (Сегодня, История, День, Профиль), поле ввода не перекрывает нижнюю панель.
11. Прочее: «Помогло / Не то» под ответом ИИ после первого разговора; «Это неточно» в меню цитаты; кнопка «Кажется, я стою на месте»; поиск в истории (есть совпадение и «Ничего не нашлось»); удаление дня с подтверждением; профиль: правка цели и финиша, час, канал, язык, тема, выгрузка файла, выход.
12. `/today?o=<id>` из настоящего push: в базе у `outreach.opened_at` появляется время (после тикета 07).

### Принятые умолчания (тикет 06)

- Оценка «Помогло / Не то» не показывается в первом разговоре: его реплики написаны по шаблону, оценивать там нечего.
- `NotifyOffer` показывается один раз в сессии сразу после завершения первого разговора; потом включить уведомления можно только в профиле (там пока нет кнопки включения push — выбирается канал).
- Эндпоинта отвязки Telegram в бэкенде ещё нет: кнопка «Отвязать Telegram» вызывает `DELETE /api/telegram/link` и показывается только при `telegram_linked`; контракт нужно согласовать с тикетом 07.
- Поиск и список истории ограничены тем, что отдаёт бэкенд (до 50 совпадений, дни по 30).

### Сделано (тикет 02)

- `routers/conversations.py`: `GET /api/conversations/today` (создаёт разговор дня: `first` с приветствием из `texts` для человека без разговоров, незавершённый первый разговор продолжается на новый день с сохранённого шага, иначе `daily`; `limit` считается по `counts_for_limit` за неделю пн–вс), `POST /api/conversations/today/messages` (JSON `{text}` или multipart `audio`; SSE `user_message` → `delta`/`quote` → `done` | `error`), лента `GET /api/conversations?before=&limit=` (дни, где человек писал, с нитями дня), `GET`/`DELETE /api/conversations/{local_date}`, `GET /api/search?q=`, `GET /api/messages/{id}/audio`, `POST /api/messages/{id}/rating`, `POST /api/facts/{id}/flag`, `PATCH /api/threads/{id}`, `GET /api/calendar?from=&to=` (≤ `CALENDAR_MAX_DAYS`, иначе `bad_range`). Чужие строки — 404 `not_found`.
- `services/conversation.py`: проверки до потока (`email_not_verified`, `empty_text`, `text_too_long`, `unsupported_audio`, `empty_audio`, `audio_too_large`, `reply_in_progress`); ответ пишется отдельной `asyncio`-задачей со своей сессией и очередью — закрытая вкладка не мешает сохранить ответ; голос: синхронное распознавание, `messages.words`, < `NO_SPEECH_MIN_CHARS` → `no_speech`, ошибка STT → `stt_failed` (сообщение и файл не остаются, день не засчитан); шаг 3 (`counts_for_limit`, `outreach_unanswered = 0`, `outreach.replied_at`); контекст шага 6 (факты — последние по дате без `flagged_at`; цитаты, уже использованные сегодня, остаются отрисовываемыми); `ReplyRenderer` (неизвестный и незакрытый плейсхолдер выбрасываются, META не стримится, сломанный META → `[]`/`normal`); сохранение ответа с `content_raw`, `content`, `quick_replies`, `used_fact_ids`, `intent`, `model_name`, `llm_ms`, `cost_usd`; ошибка модели → `llm_failed`, сообщение человека сохранено, частичный ответ — нет; правила ответа → событие `reply_rule_violation` (`length`, `questions`, `banned`). `BANNED` перенесён сюда (с формами на «вы»).
- `services/audio.py` — MIME, размер, сохранение `AUDIO_DIR/<user_id>/<message_id>.<ext>`, `delete_files`; `routers/entries.py` и `routers/goals.py` импортируют помощник отсюда (ошибки теперь в форме `{"code", "message"}`).
- `services/llm.py`: `stream_chat()` (Chat Completions `stream: true` + `include_usage`, стоимость по итоговому `usage`, повтор только при открытии потока), `complete_json_with(..., model, reasoning_effort)`; `complete_json` — та же сигнатура, все три через общий код запроса. `services/stt.py`: `STTResult.words` (`punctuated_word` или `word`, `start`, `end`).
- `services/prompts.py`: `CHAT_SYSTEM` по черновику брифа и `chat_system(locale, ...)` — `_write_in` и для русского требование обращаться на «вы».
- Заготовки: `services/limits.py` (`limit_status` считает; `ensure_can_message` пропускает всех до этапа 7), `services/safety.py` (`safety_check` → уровень 0).
- `main.py`: роутер разговоров; при старте предупреждение `costs.missing_prices()` вместо старого про `LLM_PRICE_*`.

Тесты (`tests/test_v2_conversation.py`, 47): `TestStreamChat` (3), `TestCompleteJsonWith` (2), `TestDeepgramWords` (1), `TestReplyRenderer` (7), `TestReplyRules` (1), `test_sse_format`, `TestToday` (5), `TestSendText` (7), `TestContext` (1), `TestSendVoice` (3), `TestBeforeTheStream` (4), `TestDisconnect` (1), `TestFeedAndDay` (2), `TestDeleteDay` (2), `TestSearch` (1), `TestMessageFactThread` (4), `TestCalendar` (2). Подмены `conversation.stream_chat` и `conversation.transcribe` — в `conftest.fresh_db`.

### Принятые умолчания (тикет 02)

- Лента и календарь показывают дни, где человек писал (`counts_for_limit`); разговор только с сообщением ИИ первым в ленту не попадает.
- Правила ответа проверяются по тексту ответа без цитат (слова человека в цитате не считаются похвалой или диагнозом).
- В первом разговоре до тикета 04 отвечает обычный разговор; развилка — шаг 4 в `services/conversation.py`.
- Удаление дня во время ответа — 409 `reply_in_progress`.

## Этап 3. Память

### План (тикет 03, до правок кода)

- Создаются: `progress-backend/app/services/memory.py` (`extract_memory`, циклы памяти и закрытия дня, нити, выравнивание цитат по словам, эмбеддинги, `relevant_facts`, пары «было → стало»), `tests/test_v2_memory.py`.
- Меняются: `app/services/llm.py` (`embed` через `POST /embeddings`), `app/services/costs.py` (`missing_prices()` не считает неоценёнными незаданные `CHAT_MODEL`/`SAFETY_MODEL`), `app/services/prompts.py` (промпты извлечения памяти и темы пары; существующие не меняются), `app/services/conversation.py` (подбор фактов в контексте — через `memory.relevant_facts`), `app/routers/conversations.py` (`GET /api/memory`), `app/main.py` (циклы памяти и закрытия дня в `lifespan`), `tests/conftest.py` (подмены `memory.complete_json` и `memory.embed`).
- Ничего не удаляется.

### Сделано (тикет 03)

- `services/memory.py`: `extract_memory(conversation_id)` — своя сессия и один коммит; модели передаются сообщения человека за день (с id) и открытые нити (с id), ответ по `prompts.MEMORY_SCHEMA`. Факт сохраняется, только если цитата прошла `verify.quote_supported` по тексту своего сообщения, `message_id` — сообщение этого разговора, тип — `achievement`/`struggle`/`learned`/`level`; остальное отбрасывается и считается в событии `memory_dropped_facts` (`conversation_id`, `dropped`). Цитата, уже сохранённая для сообщений этого разговора (в т.ч. фактами первого разговора), не дублируется — по нормализованному совпадению. Голосовым — `audio_start_ms`/`audio_end_ms` по `messages.words` (`align_quote`, только точный пробег слов, иначе null). Нити: `open` — только с проверенным `struggle` без нити; `mention`/`close` — только для переданных открытых нитей этого человека; `close` — только фактом `achievement`/`learned`; `last_mentioned_on` обновляется. Эмбеддинги новых фактов — одним запросом при заданном `EMBEDDING_MODEL`, ошибка не мешает. `summary` ≤ 200 символов, `memory_extracted_at` = момент начала извлечения (сообщение, пришедшее во время извлечения, вызовет повтор).
- Пары «было → стало» (`make_pairs`) в конце извлечения: закрытая нить с разницей ≥ `PAIR_MIN_DAYS` → `thread_closed`, тема — название нити; новое `achievement` с эмбеддингом → ближайший `struggle` того же человека не моложе `PAIR_MIN_DAYS` дней с косинусом ≥ `PAIR_MIN_SIMILARITY`, ещё не бывший «тогда» в паре → `similarity`, тема — нить «тогда»-факта или `complete_json` (`prompts.PAIR_THEME_SCHEMA`; ошибка → текст факта). Не больше одной новой пары на факт, существующая пара не создаётся повторно.
- `relevant_facts(db, user_id, text, limit)` — по косинусу к эмбеддингу сообщения, добивается последними по дате; без `EMBEDDING_MODEL` или при ошибке — по дате; только без `flagged_at`. `conversation._context_facts` использует его.
- Циклы `memory_loop()` (`extract_due(now)`: последнее сообщение человека старше `MEMORY_IDLE_MINUTES`, `memory_extracted_at` пусто или раньше него) и `close_day_loop()` (`close_day(now)`: тот же отбор без условия тишины, если у человека наступил `CLOSE_DAY_HOUR` следующего дня) — в `lifespan`, раз в `MEMORY_TICK_MINUTES`, переживают исключения, `CancelledError` пробрасывают; одна ошибка разговора не останавливает остальные.
- `llm.embed(texts)` — `POST /embeddings`, векторы в порядке входа, стоимость `costs.record_embedding`, ошибки → `LLMError`. `costs.missing_prices()` больше не называет незаданные `CHAT_MODEL`/`SAFETY_MODEL` (они наследуют `OPENAI_MODEL`). Промпты `MEMORY_SYSTEM`/`memory_system`, `memory_user_prompt`, `PAIR_THEME_SYSTEM`/`pair_theme_system`, `pair_theme_user_prompt` — английские, с `_write_in` (и «вы» для русского у памяти).
- `GET /api/memory` — активная цель, открытые и закрытые нити (удалённые — нет), последние `MEMORY_RECENT_FACTS` фактов (отмеченные «неточно» — с `flagged: true`).

Тесты (`tests/test_v2_memory.py`, 26): `TestEmbedProvider` (2), `TestMissingPrices` (1), `TestAlignQuote` (2), `TestCosine` (1), `TestExtractFacts` (3), `TestThreads` (2), `TestEmbeddings` (3), `TestRelevantFacts` (3), `TestPairs` (4), `TestLoops` (4), `TestMemoryEndpoint` (1, с изоляцией). Подмены `memory.complete_json` и `memory.embed` — в `conftest.fresh_db`.

### Принятые умолчания (тикет 03)

- «Последнее сообщение» для цикла памяти — последнее сообщение человека: ответ ИИ и сообщение ИИ первым извлечения не вызывают; разговоры без сообщений человека не обрабатываются.
- Ошибка модели при извлечении оставляет `memory_extracted_at` пустым — разговор повторится на следующем такте.
- `EMBEDDING_MODEL` не задан (по умолчанию «Открытых решений»): поиск фактов по дате, пары `similarity` не создаются. Цену `EMBEDDING_PRICE_PER_1M` заполняет владелец.

## Этап 4. Первый разговор

### План (тикет 04, до правок кода)

- Создаются: `progress-backend/app/services/first_conversation.py` (шаги навык → мотивация → финиш → точка старта → час), `app/routers/progress.py` (пока только `PATCH /api/goal`), `tests/test_v2_first_conversation.py`.
- Меняются: `app/services/conversation.py` (развилка на первый разговор в `_reply`, шаг 4, и сохранение/отдача его ответа), `app/services/prompts.py` (промпты шагов; существующие не меняются), `app/main.py` (роутер), `tests/conftest.py` (подмена `first_conversation.complete_json`). Строки шагов уже лежат в `services/texts.py` с этапа 1 (на «вы», проверено тестом), поэтому `texts.py` не менялся.
- Ничего не удаляется.

### Сделано (тикет 04)

- `first_conversation.first_conversation_step(db, user, conversation, message) -> FirstReply(text_segments, quick_replies, done, used_fact_ids)`; состояние шага — в `conversations.state` (`step`, `retries`, `no_finish`, `just_started`, плюс служебные `finish_options` и `session_end`).
- skill: `users.skill` и `goals.title` (цель создаётся здесь, если её нет), название — из `complete_json`, не длиннее 120 символов. motivation: цитата проверяется `verify.quote_supported` по тексту сообщения, только прошедшая попадает в `goals.why_text`/`why_message_id` и в ответ; 4 варианта финиша (до 60 символов) плюс «Без финиша — хочу просто расти» идут быстрыми ответами и в обоих случаях (с цитатой и без). finish: вариант кнопкой или свой текст → `finish_line`, `finish_set_on`; «Без финиша» (на любом языке) или два пустых ответа → `finish_line = null`, `no_finish = true`.
- baseline: сообщение → `goals.baseline_message_id`; из ответа модели остаются только пары, обе цитаты которых прошли проверку (не больше `FIRST_BASELINE_MAX_PAIRS`), факты `struggle`/`achievement` и `pairs` (`recalled = true`, `source = first_conversation`), `level_quote` → факт `level`; для голосовых — границы фрагмента по `messages.words`. В ответ идёт первая пара, цитаты — событиями `quote` с `recalled: true` и сегментами с тем же флагом. Без пар, при `just_started` или после двух неудачных ответов — ветка «Вы в самом начале».
- schedule: «Вечером» → 21; «После занятия» → вопрос с быстрыми ответами 18:00–21:00 и разбор часа; «Выберу время» → фронтенд присылает «HH:00»; любой текст разбирается (`20:00`, `8 pm`, «в 8 вечера»); не разобрано — один повтор, затем 20. В конце `reminder_hour`, `first_conversation_done = true`, `step = done`, событие `first_conversation_done`.
- Пустой («...») или не по теме (`on_topic = false`) ответ — один мягкий повтор на шаг, затем следующий шаг с тем, что есть (навык — «мой навык»/«my skill»). Сбой модели не считается неудачей человека: ответ принимается как есть.
- Безопасность: проверка идёт до шага; уровень 2–3 не двигает шаг и отдаёт сообщение в обычный путь ответа (сейчас `safety_check` — заглушка с уровнем 0, тикет 08 делает её настоящей).
- Незавершённый первый разговор на следующий день продолжается с сохранённого шага (логика `get_or_create_today` из тикета 02, закреплена тестом).
- Ответ первого разговора отдаётся тем же потоком: `delta` с полным текстом (при цитате внутри — по куску текста между цитатами), `quote`, `done` с быстрыми ответами.
- `PATCH /api/goal` `{title?, why_text?, finish_line?}` → `GoalOut`; меняются только присланные ключи, `finish_line: null` — без финиша; чужая цель недоступна, без цели — 404 `not_found`.

Тесты (`tests/test_v2_first_conversation.py`, 33): `TestSkill` (3), `TestMotivation` (2), `TestFinish` (3), `TestBaseline` (4), `TestSchedule` (6), `TestRetry` (4), `TestNextDay` (1), `TestSafety` (2), `TestRussian` (4), `TestGoalPatch` (4, с изоляцией двух людей). Подмена `first_conversation.complete_json` — в `conftest.fresh_db`.

### Принятые умолчания (тикет 04)

- Цитата мотивации — не факт (у факта нет такого типа), поэтому в ответе она стоит внутри текстового сегмента в «ёлочках» (из `goals.why_text`, уже проверенной), а не отдельным сегментом `quote`.
- Текст факта пары/уровня — сама цитата (модель в схеме брифа возвращает только цитаты); эмбеддинги этим фактам считать не нужно — повторное извлечение отбросит их по совпадению цитаты.
- На шаге финиша модель не вызывается: любой непустой текст — финиш.

## Этап 6. Сообщения ИИ первым

### План (тикет 07, до правок кода)

- Создаются: `progress-backend/app/services/outreach.py` (отбор людей, «не отправлять», паузы, тема, текст, запись, доставка; цикл вместо `reminders.loop`), `app/services/telegram.py` (Bot API через `httpx`: отправка, ссылка привязки, разбор обновлений, ответ в бот), `app/routers/telegram.py` (`POST`/`DELETE /api/telegram/link`, `POST /api/telegram/webhook`), `app/routers/me.py` (`POST /api/outreach/{id}/opened`), `tests/test_v2_outreach.py`.
- Меняются: `app/services/prompts.py` (промпт сообщения ИИ первым; существующие не меняются), `app/services/texts.py` (строки Telegram), `app/schemas.py` (`UserOut.telegram_available` — признак без побочных эффектов), `app/main.py` (цикл outreach в `lifespan` вместо цикла напоминаний, роутеры), `tests/conftest.py` (подмены `outreach.complete_json`, `telegram.send_message`), фронтенд `components/ProfileScreen.tsx`, `components/NotifyOffer.tsx`, `lib/types.ts` (Telegram: ссылка создаётся по нажатию, а не при каждом открытии профиля).
- Ничего не удаляется: `services/reminders.py` уходит на этапе 10 (из него ещё читает `routers/push.py`).

### Сделано (тикет 07)

- `services/outreach.py`: `run_once(now)` — люди с `reminders_on`, каналом не `none`, завершённым первым разговором, у которых по их поясу сейчас `reminder_hour` и `last_reminded_on` не сегодня; каждый — в своей сессии (ошибка одного не мешает остальным). `loop()` — в `lifespan` вместо `reminders.loop`, раз в `REMINDER_TICK_MINUTES`, стартует и без VAPID (сообщение всё равно ложится в разговор дня, канал может быть Telegram).
- «Не отправлять»: человек уже писал сегодня; последнее сообщение человека — уровень безопасности 3 (до следующего его сообщения); `OUTREACH_FAREWELL_DAYS` (14) дней тишины — одно сообщение `farewell` (шаблон, без модели), затем тишина до следующего сообщения человека; при `outreach_unanswered ≥ OUTREACH_PAUSE_AFTER` (3) — не чаще раза в `OUTREACH_PAUSE_EVERY_DAYS` (3) дня.
- `pick_topic(db, user, today) -> Topic(kind, thread, goal, yesterday, facts)`: открытая нить с `last_mentioned_on` за `OUTREACH_THREAD_RECENT_DAYS` → цель после `OUTREACH_ANCHOR_SILENCE_DAYS` дней тишины → вчерашний разговор с сообщением человека → `general`.
- Текст: `complete_json` с `prompts.OUTREACH_SCHEMA` `{text, quick_replies}`; модели передаются до 3 фактов темы (нить, последние, вчерашние), цитата — только плейсхолдером, отрисовывает `conversation.ReplyRenderer` (неизвестный id выбрасывается). Код проверяет: непустой текст, ≤ `OUTREACH_MAX_WORDS` слов без учёта цитаты, ровно один «?», не больше одной цитаты, нет `BANNED`; нарушение (событие `outreach_rule_violation`) или сбой модели → шаблон темы из `texts.py`.
- Запись: разговор дня (`started_by = ai`; уже открытый пустой день тоже помечается `ai`), сообщение `role = assistant`, `source = outreach`, строка `outreach` (`topic`, `thread_id`, `channel`), `last_reminded_on`, `outreach_unanswered += 1` — коммит до доставки. День не красится: `counts_for_limit` ставит только сообщение человека; оно же (тикет 02) сбрасывает `outreach_unanswered` и ставит `replied_at`.
- `deliver(db, user, outreach, text_plain) -> bool`: push `{title, body, url: /today?o=<id>, tag}` (тело без плейсхолдеров, цитаты в «ёлочках», в английском — “…”) или Telegram с кнопкой «Ответить» на `APP_URL/today?o=<id>`; без подписки, без привязки или без бота — `delivered = false`; ошибки доставки ловятся. Событие `outreach_sent` {outreach_id, topic, delivered, template}.
- `services/telegram.py`: `enabled()` (токен и имя бота), `secret_ok(header)`, `send_message(chat_id, text, button_url=None, *, button_text=None)` (Bot API `sendMessage` через `httpx`; отказ с кнопкой — повтор без кнопки), `create_link(db, user)` (новый одноразовый токен заменяет прежний), `handle_update(update)`: `/start <token>` привязывает чат (чат, привязанный к другому аккаунту, переходит к новому), ставит канал `telegram`, стирает токен и отвечает «Готово…»; неизвестный/использованный токен → «Ссылка устарела — получите новую в профиле.»; текст или голосовое из привязанного чата → `prepare_message` + `stream_reply` сегодняшнего разговора, ответ собирается из потока и уходит одним сообщением; лимит, занятость и прочие ошибки — короткий текст с кнопкой «Открыть приложение»; чужой чат — «привяжите Telegram в профиле». URL с токеном бота не логируются.
- `routers/telegram.py`: `POST /api/telegram/link` → `{url}` (503 `telegram_disabled` без бота), `DELETE /api/telegram/link` → 204 (обнуляет чат и токен; канал `telegram` → `push`; работает и без бота), `POST /api/telegram/webhook` (503 без бота; без верного `X-Telegram-Bot-Api-Secret-Token` или без `TELEGRAM_WEBHOOK_SECRET` → 403; обработка — после ответа). `routers/me.py`: `POST /api/outreach/{id}/opened` → 204, идемпотентно, `opened_at` и событие `outreach_opened` только в первый раз, чужой/несуществующий → 404 `not_found`.
- `UserOut.telegram_available` — признак без побочных эффектов; профиль и `NotifyOffer` больше не создают ссылку при открытии: кнопка «Подключить Telegram» видна при `telegram_available`, ссылка создаётся по нажатию (`openTelegramLink()` в `lib/api.ts`), профиль обновляет статус при возврате во вкладку. Отвязка вызывает новый `DELETE`.

Тесты (`tests/test_v2_outreach.py`, 47): `TestSelection` (8), `TestDontSend` (7), `TestTopic` (5), `TestText` (8), `TestDelivery` (5), `TestReply` (1), `TestOpened` (2, с изоляцией), `TestTelegram` (10, с изоляцией двух людей), `TestTelegramSend` (1, `httpx.MockTransport`). Подмены `outreach.complete_json` и `telegram.send_message` — в `conftest.fresh_db`.

### Открыто и принятые умолчания (этап 6)

- Вебхук у Telegram регистрирует владелец (внешнее действие): `setWebhook` на `<API>/api/telegram/webhook` с `secret_token` = `TELEGRAM_WEBHOOK_SECRET`. Без `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` Telegram выключен (умолчание «Открытых решений»: PWA — основной интерфейс, Telegram — канал).
- Людям, не завершившим первый разговор, ИИ первым не пишет: сообщение создало бы день `daily` и оборвало онбординг.
- Тема общего вопроса хранится как `outreach.topic = general` (в брифе у неё нет имени).
- Повторная доставка того же обновления Telegram (если вебхук не ответил вовремя) не отсекается по `update_id`: ответ отдаётся сразу, работа идёт после него.
- Быстрые ответы в Telegram не показываются (только текст); голосовое из бота проходит тот же путь распознавания, что и в приложении.
- `public/sw.js` не менялся: тег уведомления в payload передаётся, но `sw.js` по-прежнему ставит свой; `services/reminders.py` остаётся до этапа 10 (из него читает `routers/push.py`).
- Отвязка Telegram переключает канал на push, только если он был telegram (выбранное «не писать» не включается обратно).

## Этап 7. Безопасность, «стою на месте», лимит, выгрузка

### План (тикет 08, до правок кода)

- Меняются: `progress-backend/app/services/safety.py` (заготовка → проверка и уровни), `app/services/limits.py` (`ensure_can_message`), `app/services/conversation.py` (ветки безопасности 1–3, сценарий plateau, `prepare_plateau`), `app/services/prompts.py` (проверка безопасности, `SAFETY_SYSTEM`, блок plateau), `app/services/texts.py` (строка контакта помощи), `app/routers/me.py` (`/api/paywall/click`, `/api/me/export`), `app/routers/conversations.py` (`/api/conversations/today/plateau`), `tests/conftest.py` (подмена `safety.complete_json_with`), фронтенд `components/PaywallSheet.tsx`, `lib/i18n.ts`.
- Создаются: `tests/test_v2_safety_limits.py`, `tests/eval/dialogs.yaml`, `scripts/eval_dialogs.py`.
- Ничего не удаляется.

### Сделано (тикет 08)

- `safety.safety_check(text, locale) -> SafetyResult(level, failed)` — `complete_json_with(model=SAFETY_MODEL)` со схемой `{level 0–3, reason}`; любая ошибка → уровень 0, `failed=True`, вызывающий пишет `safety_check_failed`. Проверяется каждое сообщение человека, включая первый разговор; уровень пишется в `messages.safety_level` и максимум дня — в `conversations.safety_level`.
- Уровень 1: в контекст — пометка «мягче» (`prompts.CHAT_SOFT`). Если уровень 1 был в `SAFETY_HELP_MIN_DAYS` (5) из последних `SAFETY_HELP_WINDOW_DAYS` (14) дней (сегодня включительно) и за `SAFETY_HELP_COOLDOWN_DAYS` (14) совета не было — к ответу добавляется одна фраза `safety.suggest_help`, событие `safety_suggest_help`.
- Уровень 2: `prompts.SAFETY_SYSTEM` + только сообщения сегодняшнего разговора (у ответов ИИ — без цитат); ни цели, ни фактов, ни нитей, ни выжимок дней; плейсхолдеры цитат не отрисовываются; без быстрых ответов, `intent = normal`. Событие `safety_flag {level}`.
- Уровень 3: шаблон `safety.level3_text(user)` без вызова модели: контакты `SAFETY_RESOURCES` по `users.country`, иначе список `default`, иначе общая рекомендация (местная экстренная служба и близкий человек, без номера). Записи без имени или контакта не показываются. Шаблон не обещает конфиденциальность и не говорит, кого известят. Событие `safety_flag {level: 3}`; outreach молчит до следующего сообщения человека (тикет 07 читает `messages.safety_level`).
- Первый разговор: уровень ≥ 2 — ответ по протоколу безопасности, шаг не двигается, модель шага не вызывается.
- «Кажется, я стою на месте»: `POST /api/conversations/today/plateau` (SSE, только ответ ассистента; без лимита, день не засчитывается; нужна подтверждённая почта; 409 при идущем ответе) и `intent = plateau` прошлого ответа. Модели передаются только якорь, до 3 пар с наибольшим разрывом дат (скрытые и с флажком «неточно» — нет), закрытые нити и число разговоров — вместо обычных фактов, открытых нитей и выжимок дней. Меньше двух доказательств (пары + закрытые нити) — добавляются самые ранние факты `level` (точка старта) и число дней до сравнения (`PAIR_MIN_DAYS` минус дни с первого разговора, не меньше 1). Если сегодня уже был уровень 2–3, кнопка отвечает по протоколу безопасности.
- Лимит: `ensure_can_message` — засчитанный сегодня день не блокируется; пробный период (`FREE_TRIAL_DAYS` от локальной даты регистрации) и `plus_until ≥ сегодня` снимают лимит; иначе при `used ≥ FREE_CONVERSATIONS_PER_WEEK` за неделю пн–вс в поясе человека — 402 `limit_reached` до потока.
- `POST /api/paywall/click` → `{plus_until}` = локальное сегодня + `PLUS_BETA_DAYS`, событие `paywall_clicked`. Пейволл на фронтенде открывается по `limit_reached`, пишет `paywall_viewed`, обещает только безлимит, после нажатия — «Мы в бете — вам месяц бесплатно» и дата; закрытие отправляет отклонённое сообщение снова.
- `GET /api/me/export` — JSON-файл `forwardtrace-export-<дата>.json`: аккаунт (почта, пояс, язык, навык), цель, разговоры с сообщениями, факты, нити — только владельца; аудио не входит (`has_audio`).
- `tests/eval/dialogs.yaml` — 50 заготовок (40 обычных, 10 дистресса), 8 заполнены примерами, остальные `turns: []` (TODO). `scripts/eval_dialogs.py` прогоняет диалоги тем же путём, что и приложение (проверка безопасности → шаблон / `SAFETY_SYSTEM` / промпт разговора), проверяет длину, один вопрос, `BANNED`, известные `fact_id`, ожидаемый уровень; печатает отчёт (`--out` — JSON); без `OPENAI_API_KEY` — понятное сообщение и код 2.

Тесты (`tests/test_v2_safety_limits.py`, 36): `TestSafetyCheck` (3), `TestLevelOne` (4), `TestLevelTwo` (2), `TestLevelThree` (5), `TestPlateau` (7, с изоляцией), `TestLimitStatus` (2), `TestLimit` (6: граница недели, пояса, Plus, пробный период), `TestPaywall` (2), `TestExport` (2, с изоляцией), `TestEvalDialogs` (3). Подмена `safety.complete_json_with` — в `conftest.fresh_db` (`SAFETY_RESULT`, `SAFETY_CALLS`).

### Открыто и принятые умолчания (этап 7)

- `SAFETY_RESOURCES` пуст (`{}`): контакты линий помощи по странам заполняет владелец по официальным источникам; до этого уровень 3 даёт общую рекомендацию без номеров.
- `tests/eval/dialogs.yaml`: содержание 42 диалогов дописывает владелец; `eval_dialogs.py` с настоящей моделью в сборке не запускался (нужен ключ, это платные вызовы).
- «До 3 пар» в plateau — константа `conversation.PLATEAU_MAX_PAIRS`, а не настройка: `config.py` вне зоны тикета.
- Уровень 2 видит сегодняшний разговор (без цитат из прошлого) — иначе ответ теряет нить; память и прогресс не передаются.
- Совет специалисту дописывается в конец ответа отдельным абзацем; окно «раз в 14 дней» считается по времени события `safety_suggest_help`.
- Пейволл не показывает дату обновления лимита точнее «в понедельник».

## Этап 8. Прогресс и месячная сводка

### План (тикет 09, до правок кода)

- Создаются: `progress-backend/app/services/progress.py`, `tests/test_v2_progress.py`, `progress-frontend/app/(app)/progress/monthly/[month]/page.tsx`, `components/PairCard.tsx`, `components/MonthlySummaryCard.tsx`.
- Меняются: `app/routers/progress.py` (`GET /api/progress`, `GET /api/progress/monthly`, `POST /api/pairs/{id}/hide`), `app/services/prompts.py` (только сводка), `app/main.py` (цикл), `tests/conftest.py` (подмена `progress.complete_json`), `components/ProgressScreen.tsx`, `FinishPath.tsx`, `lib/i18n.ts`, `lib/types.ts`.
- `texts.py` не меняется: `monthly.ready` и `monthly.thin` уже есть с этапа 1. Ничего не удаляется.

### Сделано (тикет 09)

- `progress.progress_for(db, user) -> ProgressOut` без вызова модели: активная цель (мотивация — `why_text`, финиш — `finish_line`, `null` = «Без финиша — расту» на фронтенде); последние 3 факта `level` без «неточно» (новые сверху, с датами); карточки `pairs` новые сверху (по дате факта «стало»), без скрытых и без карточек, где любой факт помечен «неточно»; открытые и закрытые нити; непросмотренная готовая (`done`/`thin`) сводка последнего месяца.
- `POST /api/pairs/{id}/hide` → 204, повтор безвреден, чужая или несуществующая карточка → 404 `not_found`. `GET /api/progress/monthly?month=YYYY-MM` → `MonthlySummaryOut`; первый показ ставит `viewed_at`; нет сводки, `failed` или чужая → 404; неверный формат месяца → 422.
- Сводка за месяц, `build_monthly(user_id, month)`: считает код — `days` (разговоры с `counts_for_limit`), `conversations` (то же число), `closed_threads`, `new_pairs`, `level_facts`; карточки — до 3 пар месяца с наибольшим разрывом дат между «было» и «стало»; одна открытая нить. Нет ни одного разговора — сводки нет. Меньше `MONTHLY_MIN_CONVERSATIONS` разговоров и меньше `MONTHLY_MIN_PAIRS` новых пар — `thin`, модель не вызывается. Иначе `complete_json` пишет `intro`, `open_struggle`, `next_step`; хранится текст с `{{quote:<id>}}`, лишние плейсхолдеры (не из переданных фактов) удалены; цитаты рисует `ReplyRenderer` при каждом чтении, поэтому факт, помеченный «неточно» позже, исчезает и из старой сводки. Ошибка модели, пустое поле или `%` в тексте — `failed`; `done`/`thin` не пересобирается (unique `(user_id, month)`).
- `stats` в ответе API — посчитанные числа плюс `pairs` (карточки), `closed` (нити, закрытые за месяц) и `why_text` (мотивация), собранные при чтении; хранимые `pair_ids`/`closed_thread_ids` наружу не идут. Схемы `schemas.py` не менялись.
- `monthly_once(now)` / `monthly_loop()` (раз в `MONTHLY_TICK_MINUTES`, в `main.py`): для людей, у которых по их поясу сейчас 1-е число и час ≥ `CLOSE_DAY_HOUR`, собирает сводку за прошлый месяц; `failed` повторяется при следующих проходах в тот же день; готовая пропускается без запроса к модели.
- Уведомление «Сводка за {месяц} готова» (`outreach.deliver`, строка `outreach` с `topic = monthly`, без сообщения и без разговора): только людям с включёнными напоминаниями, каналом не `none` и завершённым первым разговором. `outreach_unanswered` не меняется; `replied_at` не ставится.
- Фронтенд: `/progress` (сводка сверху, цель/мотивация/финиш, путь к финишу из 3 фактов `level`, `PairCard` с «Скрыть» и «по вашим воспоминаниям», нити с «Отметить как преодолённую» и «Удалить»), `/progress/monthly/[month]` (`MonthlySummaryView`). Пустые состояния истории 8: нет карточек и нет фактов `level` — тексты из спецификации. Тексты — `lib/i18n.ts` ru+en, на «вы».

Тесты (`tests/test_v2_progress.py`, 26): экран (пустой, с данными за месяц, без финиша, скрытые/«неточно», изоляция), скрытие карточки (изоляция), чтение сводки (`viewed_at`, 404, `failed` не показывается), сборка (нет разговоров, `thin` без модели, пороги, чужие плейсхолдеры, флаг после сборки, три самые длинные карточки, `%` → `failed` → повтор, однократность), уведомление, цикл (час и пояс, 2-е число, повтор после сбоя, удалённые аккаунты, живучесть цикла).

### Открыто и принятые умолчания (этап 8)

- «3 факта `level`» и «до 3 карточек» в сводке — константы `progress.LEVEL_FACTS_SHOWN`, `progress.MONTHLY_MAX_PAIRS`, а не настройки: `config.py` вне зоны тикета.
- Сводка собирается только 1-го числа (час ≥ `CLOSE_DAY_HOUR`); если сервер был выключен весь этот день, сводка за месяц не появится.
- Ссылка уведомления о сводке — общая `/today?o=<outreach_id>` (правило 14): ведёт на «Сегодня», а не на сводку; сводка ждёт сверху на «Прогрессе». Прямая ссылка потребует правки `outreach.deliver` и экрана «Сегодня».
- Для `thin`-сводки уведомление тоже «Сводка за {месяц} готова».

## Этап 9. Аналитика и админка

### План (тикет 10, до правок кода)

- Составить список 27 событий брифа и сверить с кодом: что уже пишет `events.log_event`, чего нет. Недостающие серверные — в местах действия, без перестройки логики; клиентские идут через `POST /api/events`, сервер дополняет `day_number`, `language`, `channel`.
- Админку переписать на данных v2 (разговоры, сообщения, факты, outreach, события); страницы по `entries`/`reports`/`tasks` убрать — таблицы v1 удалит тикет 11.

### Сделано (тикет 10)

- Уже писались до тикета: `first_conversation_done`, `outreach_sent`, `outreach_opened`, `safety_flag`, `paywall_clicked`, `reply_rule_violation` (плюс служебные `safety_check_failed`, `safety_suggest_help`, `memory_dropped_facts`).
- Добавлены серверные: `message_sent`, `ai_reply` (`kind` = model | first | safety | safety_template, `with_quote`, `intent`, `llm_ms`, `cost_usd`), `reply_rated`, `quote_flagged`, `outreach_replied`, `plateau_triggered`, `search_used`, `thread_opened`, `thread_closed` (`by` = memory | user), `first_conversation_step` (только при переходе на следующий шаг), `onboarding_completed` (вместе с `first_conversation_done`), `anchor_saved`, `start_comparison_shown`, `finish_set` (первый разговор и профиль; снятие финиша — не событие), `pair_hidden`, `monthly_summary_viewed` (только первое открытие).
- Клиентские через `api.logEvent`: `quote_opened`, `week_strip_day_opened`, `paywall_viewed` (были), `feed_opened`, `progress_opened`, `pair_shown` (добавлены). `POST /api/events` теперь идёт через `log_event`: `day_number`, `language`, `channel` ставит сервер и перекрывает присланные.
- Админка (`adminstats.py`, `/admin`, `/api/admin/overview`): D1 и D7 по неделям регистрации (Dn — разговор, засчитанный в день через N дней, считаются только те, у кого этот день уже наступил); доля ответивших на сообщение ИИ первым (доставленные `outreach` с `replied_at`); доля «помогло» среди оценённых ответов с цитатой и без; доля цитат «это неточно» (факты, показанные в ответах, из них с `flagged_at`); список разговоров с `safety_level` ≥ 2 со ссылкой `/admin/conversations/{id}` (страница с сообщениями); средняя стоимость разговора (сумма `messages.cost_usd` по разговорам, где она записана). Страницы: обзор, люди, человек, разговор, события. Удалены `/admin/entries`, `/admin/feedback`, `PUT /api/admin/reports/{id}/content`, `GET /api/admin/entries|feedback`.
- Тесты `tests/test_v2_analytics.py` (15). В `tests/test_app.py` удалён `test_admin_user_page_shows_what_that_person_cost` (проверял стоимость записей v1 на странице человека); `test_admins_still_see_which_providers_are_configured` и тесты входа в админку остались.

### Открыто и принятые умолчания (этап 9)

- Когорта — неделя регистрации (понедельник по поясу человека); D1/D7 — «говорил в день N после регистрации», а не «в любой из дней до N».
- Стоимость разговора не включает фоновые вызовы (память, пары, сводка, outreach): они не привязаны к сообщению.
- `outreach_opened` несёт `channel` из строки outreach, но `log_event` перекрывает его каналом человека.

## Этап 10. Очистка

### План (тикет 11, до правок кода)

- Удаляются (бэкенд): `app/routers/entries.py`, `reports.py`, `tasks.py`, `goals.py` (v2 правит цель через `PATCH /api/goal`; создание цели и «почему» — в первом разговоре); `app/services/reports.py`, `aggregate.py`, `summary.py`, `monthly.py`, `tasks.py`, `extraction.py`, `reflection.py`, `reminders.py`; модели `Criterion`, `Entry`, `Activity`, `Report`, `Task`, `TaskMention`, перечисление `Status`, поле `User.tasks_declined_on`; v1-схемы (критерии, записи, отчёты, задачи, дайджест, сводка дня); v1-промпты (`CRITERIA_*`, `EXTRACTION_*`, `REPORT_*`, `TASK_MATCH_*`, `REFLECTION_*`); v1-настройки (квоты записей, период отчёта, задачи, `MAX_ACTIVE_GOALS`, `DEFAULT_REMINDER_HOUR`, `KEEP_AUDIO` и т. п.) из `config.py` и `.env.example`; недельная арифметика из `time_utils.py`; `scripts/smoke_test.py`, `scripts/seed_english_week.sql` (живой прогон и данные v1); пустая папка `app/{services,routers}`.
- Переносятся: тексты push `MESSAGES` (`reminders.py`) → `services/texts.py` (ключи `push_test_*`), `routers/push.py` берёт их оттуда.
- Меняются: `app/main.py` (роутеры, без сброса зависших записей), `services/accounts.py` (стирание без таблиц v1), `routers/conversations.py`, `routers/progress.py`, `services/progress.py` (без подгрузки критериев), `schemas.GoalOut` (без `criteria`), `services/verify.py` (только `normalize`/`quote_supported` и их константы), `tests/test_app.py` (остаются тесты аутентификации, перебора, писем, удаления аккаунта, push, провайдеров, здоровья; v1-тесты удаляются), тест миграций на Postgres (0015 и откат).
- Создаётся: `alembic/versions/0015_drop_v1.py` — удаляет `task_mentions`, `tasks`, `activities`, `entries`, `reports`, `criteria`, `users.tasks_declined_on`; `downgrade` восстанавливает их схему (как после 0013).
- `scripts/import_v1.py` и его тесты — решение в «Сделано».
- Лендинг `public/landing/` (тексты ru/en), `README.md`, `DOCUMENTATION.md`, `progress-backend/README.md`, `progress-frontend/README.md` — переписываются под v2.

### Сделано (тикет 11)

- Удалены модули v1: `routers/entries.py`, `reports.py`, `tasks.py`, `goals.py` (вместе с `POST /api/goals/suggest-criteria`, шагом проверки расшифровки `POST /api/entries/{id}/confirm` и статусом `awaiting_review`), `services/reports.py`, `aggregate.py`, `summary.py`, `monthly.py`, `tasks.py`, `extraction.py`, `reflection.py`, `reminders.py`; модели `Criterion`, `Entry`, `Activity`, `Report`, `Task`, `TaskMention`, `Status`, поле `User.tasks_declined_on`; v1-схемы; v1-промпты (`CRITERIA_*`, `EXTRACTION_*`, `REPORT_*`, `TASK_MATCH_*`, `REFLECTION_*`); `verify.normalize_category/clean_facts/clean_metrics`, `costs.charge`; недельная арифметика `time_utils` (остались `valid_timezone`, `tz_of`, `local_today`); `scripts/smoke_test.py` и `scripts/seed_english_week.sql`. Пустой папки `app/{services,routers}` уже не было.
- Настройки v1 убраны из `config.py` и `.env.example`: `MAX_VOICE_ENTRIES_PER_DAY`, `MAX_TEXT_ENTRIES_PER_DAY`, `MAX_ONBOARDING_TRANSCRIBES_PER_DAY`, `REPORT_PERIOD_DAYS`, `FIRST_REPORT_AFTER_DAYS`, `MIN_ENTRIES_FOR_REPORT`, `MIN_ENTRIES_FIRST_REPORT`, `MAX_ACTIVE_GOALS`, `MAX_ACTIVE_TASKS`, `TASK_SUGGESTION_COOLDOWN_DAYS`, `DEFAULT_REMINDER_HOUR`, `KEEP_AUDIO`. В `.env.example` добавлена строка `MAX_AUDIO_MB` (настройка была, строки не было).
- Тексты тестового push (`reminders.MESSAGES`, в русском было «Над чем работал» — на «ты» и с родом) → `texts.py`, ключи `push.test_title` / `push.test_body`; `routers/push.py` берёт их оттуда; дубль `UnsubscribeIn` убран.
- `main.py`: без роутеров v1 и без сброса «зависших» записей `entries` при старте; заголовок API — «ForwardTrace API» 2.0.0. `accounts.erase` больше не трогает таблицы v1. `GoalOut` без `criteria`; `/api/memory`, `PATCH /api/goal` и `progress` не подгружают критерии.
- Письма (`mail.py`): «начать записывать чек-ины» → «начать первый разговор», «записи, аудио, цели и отчёты» → «разговоры, аудио, цель и то, что мы запомнили» (ru и en, ru — на «вы»). Комментарии с отсылками к удалённым модулям обновлены; `DEPLOY.md`, `RAILWAY.md` — про разговоры и метрики v2.
- Миграция `0015_drop_v1` (`down_revision = "0014_v2_core"`): удаляет `task_mentions`, `tasks`, `activities`, `entries`, `reports`, `criteria` и `users.tasks_declined_on`. `downgrade` воссоздаёт их схему как после 0013 (колонки, умолчания, индексы, уникальные ограничения, FK), без данных.
- `scripts/import_v1.py` и его тесты **удалены**. Причина: после 0015 таблиц v1 нет ни на одной схеме, на которой запускается приложение; `docker-entrypoint.sh` делает `alembic upgrade head` и проходит 0014 и 0015 подряд, так что на деплое окна для импорта нет; у владельца нет пользователей с данными v1 («У меня сейчас нету пользователей так что можно удалять без проблем»). Скрипт и его проверенный прогон остаются в истории git (этап 1); чтобы им воспользоваться, нужно `alembic downgrade 0014_v2_core` на базе, где данные v1 ещё есть, — после 0015 их уже нет.
- Тест миграций на Postgres выполнен локально (Docker Desktop, временный контейнер `postgres:16`, удалён после прогона): чистая база 0001 → head → 0013 → head, таблиц v1 нет, `_check_schema` проходит; база на 0014 с данными во всех таблицах v1 и строкой `conversations` → head: таблицы v1 и колонка удалены, `users`/`goals`/`conversations` целы; `downgrade 0014_v2_core` возвращает ровно ту же схему (колонки с типами и умолчаниями, индексы, уникальные ограничения, FK), таблицы пусты; снова head. `alembic check` на head расхождений по таблицам не показал (только известные с этапа 1 `created_at`/`sent_at` NULL при `server_default`).
- Лендинг (`public/landing/shared/copy.js`, статический текст в `index.html` синхронизирован с ru): **черновик** под разговорный формат — один разговор в день голосом или текстом, ответ сразу, память и цитаты с датами, нити и «было → стало», ИИ пишет первым в выбранный час, первый разговор как онбординг, условия бесплатного доступа (7 дней без ограничений, затем 3 разговора в неделю — из настроек). Русский на «вы», без форм с родом, в том числе в примерах цитат (прежние «опять не успел», «показал прототип» переписаны). Неиспользуемые ключи вариантов `v2.*`/`v3.*` и `hero.before…`, `cmp.ai.*` удалены. Цен, числа пользователей, отзывов нет.
- `README.md`, `DOCUMENTATION.md`, `progress-backend/README.md`, `progress-frontend/README.md` переписаны под v2: модули, эндпоинты, модель данных и миграции, фоновые циклы, настройки, запуск, тесты (в том числе Postgres), деплой, неполадки, открытые места.

Тесты: `tests/test_v2_cleanup.py` (6): модулей v1 нет и никто их не импортирует; моделей, таблиц и колонки v1 нет; настроек v1 нет в `Settings` и `.env.example`; маршруты `/api/entries|reports|tasks|goals` отвечают 404/405; у `GoalOut` нет `criteria`; тестовый push на языке человека, русский — без «ты» и рода. `tests/test_app.py` очищен от v1 (извлечение, квоты, статистика, отчёты, цели и критерии, напоминания v1, задачи, сводка дня, рефлексия, дайджест, периоды); оставшиеся тесты (почта, вход, перебор, локализация промптов v2, настройки, push-подписки, пояса, стоимость, повторы провайдеров, здоровье, письма, удаление аккаунта) идут на общих фикстурах `conftest.py`; тест стирания переписан на данных v2 (цель, разговор, голосовое сообщение с файлом, push-подписка), «удалённому аккаунту не пишут» — на `outreach.run_once`. Postgres-тесты `TestMigrationsOnPostgres` (2) покрывают 0015 и её `downgrade`. Итог: 334 passed, 2 skipped (было 390 passed, 2 skipped: ушли ~60 тестов v1 и 2 теста импорта).

### Открыто и принятые умолчания (этап 10)

- **Согласовать текст лендинга** с владельцем (ru и en, `public/landing/shared/copy.js`): сейчас черновик. Иллюстрации лендинга (героя и финала) не менялись.
- `progress-frontend/lib/types.ts` всё ещё объявляет `Criterion` и `Goal.criteria` (поле больше не приходит с сервера; в коде экранов не читается) — вне зоны тикета, убрать при следующей правке фронтенда.
- Первый деплой v2 на прод-базу v1 выполнит 0014 и 0015 подряд и удалит таблицы v1 с данными — по подтверждению владельца. Деплой и миграции на Railway делает владелец.
- `facts.origin = import_v1` остаётся допустимым значением (строки, импортированные раньше, не переписываются).
- Открытые места прошлых этапов в силе: `SAFETY_RESOURCES`, `EMBEDDING_MODEL`, цены моделей, `TELEGRAM_*` и вебхук, содержание `tests/eval/dialogs.yaml` (сводка — `DOCUMENTATION.md`, раздел 16).

## Исправления после ревью ветки (тикет F1)

- `JWT_SECRET`: вне `APP_ENV=test` `Settings` отвергает пустой секрет, секрет короче 32 символов и любую заглушку из кода или `.env.example` (`CHANGE-ME-openssl-rand-hex-32`, `replace-me`; без учёта регистра). Сообщение называет переменную, не значение.
- Админка: доля ответов на сообщения ИИ (`adminstats.outreach_reply_share`) не считает строки `topic="monthly"` — уведомление о сводке ни о чём не спрашивает.
- Числа логики стали настройками (`config.py` + `.env.example`): `LEVEL_FACTS_SHOWN`, `MONTHLY_MAX_PAIRS`, `PLATEAU_MAX_PAIRS`, `FIRST_DEFAULT_REMINDER_HOUR`, `FIRST_EVENING_HOUR`, `GOAL_TITLE_MAX_CHARS`, `FINISH_OPTION_MAX_CHARS`, `FINISH_OPTIONS_MAX`, `SAFETY_REPLY_MAX_WORDS` (подставляется в `SAFETY_SYSTEM`). Константы `progress.LEVEL_FACTS_SHOWN`, `progress.MONTHLY_MAX_PAIRS`, `conversation.PLATEAU_MAX_PAIRS` и числа в `first_conversation.py` удалены.
- Гонка создания дня: вставка разговора дня в `conversation.get_or_create_today` и в outreach (`_day_conversation`) идёт в savepoint (`db.begin_nested()`); проигравший запрос получает уже созданный день (200), остальное в сессии и `user` не сбрасываются.
- Первый разговор, перенесённый на новый день, открывается сообщением ассистента с вопросом сохранённого шага и его быстрыми ответами (`first_conversation.resume_question(locale, state)`; на шаге финиша — сохранённые варианты и «Без финиша»); счётчик повторов шага на новый день обнуляется. Для вопроса шага финиша взят текст `first.retry.finish` (у `first.ask_finish` есть «Запомнил» — о вчерашнем ответе), для расписания — `first.retry.schedule`.
- Извлечение памяти пропускает сообщения человека с `safety_level ≥ 2`: из них не делаются факты, цитаты и пары.
- Фронтенд: заголовки вкладок — из словаря `pageTitles` (ru+en): metadata — английская запись, клиентский `app/PageTitle.tsx` ставит заголовок на языке человека. 409 при регистрации — строка `auth.emailTaken`, `describeError` больше не показывает английский текст сервера. `themeColor` — по `prefers-color-scheme`, цвета `--ink` обеих тем читаются из `tokens.css` при сборке (`app/themeColor.ts`); стеки шрифтов, отступ `.field` и размер цифр сводки — переменные `tokens.css`.

Тесты: `tests/test_v2_review_fixes.py` (6): настройки и строки `.env.example` для чисел логики; лимит слов `SAFETY_SYSTEM` из настройки; число фактов уровня на «Прогрессе» из настройки; гонка создания дня в `GET /api/conversations/today` и в `outreach.run_once`; память пропускает уровни 2–3. `test_v2_foundation.py`: заглушка из `.env.example`, пустой, короткий и `replace-me` секреты. `test_v2_analytics.py`: строка monthly не меняет долю. `test_v2_first_conversation.py`: вопрос каждого шага на новый день (5 случаев) и вопрос финиша с вариантами. Итог: 352 passed, 2 skipped (было 334 passed, 2 skipped).

Открыто: ручное переключение темы (`lib/theme.ts`, вне зоны) переписывает только первый из двух `meta[name="theme-color"]`; при теме, отличной от системной, цвет панели браузера остаётся по системной теме.

# v2.1

## Таск 12. Баги первой сборки: тройная отправка, цитата в строке, «ты» в диалоге, «B1» не час

### План (до правок кода)

- Идемпотентная отправка: `models.Message.client_msg_id` + уникальный `uq_messages_user_client_msg`, миграция `alembic/versions/0017_client_msg_id.py`; `routers/conversations.py` (`_read_message` читает и проверяет `client_msg_id`); `services/conversation.py` (`DuplicateMessage`, `_inflight`, повтор до занятости/лимита/аудио, `replay_duplicate`, `IntegrityError` при вставке → повтор); `services/errors.py` (`bad_client_msg_id`).
- Фронтенд: `lib/ids.ts` (`newClientMsgId`), `lib/api.ts` (`streamMessage` с `client_msg_id`), `lib/types.ts`, `components/TodayScreen.tsx` (id в `pending`, синхронная блокировка), `Composer.tsx`, `QuickReplies.tsx`; `lib/i18n.ts` — новый код ошибки.
- Цитата в строке: `components/QuoteChip.tsx` (inline, дата мелко, меню по нажатию), `MessageBubble.tsx`.
- «Ты» в диалоге: `services/texts.py` (`first.*`, `outreach.*` кроме `push_title`/`reply_button`, `safety.*`; `first.greeting`, `first.comparison`, `outreach.farewell` по §2.4), `services/prompts.py` (`_address_formally` → требование «ты» без рода для промптов разговора, уровня 2 и тем outreach), `services/first_conversation.py` (тексты).
- Час: `first_conversation.parse_hour` — число после буквы не час.
- Тесты: `tests/test_v2_idempotency.py` (новый), правки тестов «вы» в `test_v2_foundation.py`, `test_v2_first_conversation.py`, `test_v2_conversation.py`.

### Сделано (таск 12)

- `POST /api/conversations/today/messages` принимает `client_msg_id` (JSON или поле multipart; `^[A-Za-z0-9-]{1,64}$`, иначе 422 `bad_client_msg_id`). `messages.client_msg_id String(64) NULL` + `uq_messages_user_client_msg (user_id, client_msg_id)`, миграция `0017_client_msg_id` (downgrade снимает индекс и колонку).
- `conversation.prepare_message(..., client_msg_id=None) -> PreparedMessage | DuplicateMessage`: повтор ищется в `_inflight` и в БД до занятости, лимита и записи аудио; событие `message_duplicate {client_msg_id, state: replayed|in_flight}`. `stream_reply(DuplicateMessage)` → `replay_duplicate`: `user_message`, сохранённый ответ (`delta`/`quote`/`done` с его `message_id`, `duplicate: true`) или `done {message_id: null, duplicate: true, …}`. `IntegrityError` при вставке сообщения — ответ как на повтор. Без ключа (Telegram) — как раньше.
- Фронтенд: `lib/ids.ts newClientMsgId()` (запасной UUID v4 без `crypto.randomUUID`); `api.streamMessage` шлёт `client_msg_id`; `TodayScreen` даёт id каждому новому сообщению (текст, голос, быстрый ответ, час из `HourPicker`), «Повторить» и повтор после Plus шлют тот же; замок `busyRef` берётся синхронно до первого `await`; `Composer` не отправляет запись дважды при двойном «стоп и отправить». Новый код `bad_client_msg_id` в `lib/types.ts` и `lib/i18n.ts` (ru на «вы»).
- `QuoteChip` — inline: «цитата» и короткая дата мелко в той же строке; по нажатию меню — полная дата, пометка «по воспоминаниям», «Открыть этот день» (событие `quote_opened`), фрагмент аудио, «Это неточно».
- «Ты» в диалоге: `first.*`, `outreach.*` (кроме `push_title`, `reply_button`), `safety.*` переписаны на «ты» без рода; `first.greeting`, `first.comparison` — дословно по §2.4; вопрос «Во сколько тебе написать завтра?» после сравнения — новый ключ `first.ask_schedule`, дописывается в тот же абзац; `outreach.farewell` — «Я тут, когда захочешь поговорить. Всё, о чём мы говорили, никуда не делось.» `prompts._address_informally` («ты», без рода, род — только если человек сам его обозначил) заменил `_address_formally` в `chat_system`, `outreach_system`, `safety_system`; служебные промпты (память, первый разговор, сводка) — без изменений. `telegram.*`, `push.*`, `monthly.*`, `lib/i18n.ts`, письма, лендинг не тронуты.
- `first_conversation.parse_hour`: число сразу после буквы — не час (`(?<![\w:.])`); «уровень B1» → переспрос.

Тесты: новые `tests/test_v2_idempotency.py` (16: три отправки → одно сообщение/один ответ/один вызов модели; повтор не проверяет лимит; тот же id у другого человека; повтор во время ответа → `done {duplicate}` без 409; гонка вставки; голосовой повтор без второго файла; без ключа — два сообщения; 422 на кривой ключ в JSON и multipart; модель и миграция), `tests/test_v2_dialogue_tone.py` (20: «ты» без «вы» в диалоговых ключах, «вы» вне диалога, нет форм с родом во всех ru-строках, дословные приветствие и сравнение, прощание, «ты» в промптах разговора/безопасности/outreach для ru, `parse_hour`). Переписаны проверки «вы»: `test_v2_foundation.py`, `test_v2_first_conversation.py::TestRussian`, `test_v2_conversation.py` (приветствие, промпт), `test_v2_outreach.py` (прощание), `test_v2_safety_limits.py` (уровень 3). Итог: 388 passed, 2 skipped (было 352 passed, 2 skipped); `npx tsc --noEmit && npm run build` — зелёные.

## Таск 13. Эталонные диалоги и сравнение версий

### План (до правок кода)

- `app/services/prompts.py`: `ContextData` и строки (`ThreadLine`, `FactLine`, `RecentLine`), `compose_messages`, реестр `CHAT_PROMPTS` (пока только `"v2.0"` — прежний промпт), `load_prompt_file` для `.txt` с плейсхолдерами v2.1.
- `app/services/conversation.py`: `build_context` делится на `load_context_data` (БД) и `compose_messages(version="v2.0")`; поведение не меняется.
- `scripts/eval_dialogs.py`: сборка контекста той же `compose_messages`, `--prompt-a/--prompt-b`, `--model-a/--model-b`, отчёт Markdown + `.json` в `tests/eval/reports/`.
- `tests/eval/dialogs.yaml`: новый формат (память со смещениями дат), 3 заполненных обычных сценария, 17 заготовок, `ten_in_a_row`, 10 сценариев дистресса (4 перенесены без правки реплик, 6 заготовок).
- Тесты: `tests/test_v2_eval.py` (новый), правка теста скрипта в `test_v2_safety_limits.py`.

### Сделано (таск 13)

- `prompts.compose_messages(data, *, version="v2.0", soft, plateau_block, examples_limit)` -> `[system, *recent, user(current)]`; версия — имя из `CHAT_PROMPTS`, путь к `.txt` или готовая функция. `"v2.1"` до таска 14 не зарегистрирована: вызов даёт `ValueError` со списком известных версий. Плейсхолдеры `.txt`: `{skill} {anchor} {finish} {threads} {facts} {days} {recent} {examples} {extra}`; прочие фигурные скобки остаются как есть.
- `conversation.load_context_data(db, user, conversation, text, *, mode) -> ContextData`; `build_context` = она + `compose_messages(version="v2.0")`. Сообщения разговора пока идут в `recent`, `current` пуст; уровни памяти — таск 14.
- Скрипт: каждый ход — проверка безопасности, затем шаблон уровня 3, протокол уровня 2 или `compose_messages` и `stream_chat(model=…)`; история растёт ответами той же версии; проверка безопасности одна на реплику для A и B. Жёсткие проверки: разобранная META, известные `fact_id`, уровень безопасности = `expected_safety`. Отчёт: сводка с диагностикой версий (доля «?», средняя длина в словах, цель без повода), память и таблица «человек | A | B» по сценарию, пустая таблица оценок по пяти критериям, пункт «Главный ручной тест». Код выхода 0/1/2.
- `dialogs.yaml`: 31 сценарий. Заполнены `normal-01` (достижение/MVP), `normal-02` (тяжёлый день, `expected_safety: 1` — предположение, поправить после первого прогона), `normal-03` (смена темы); 17 заготовок `todo: true` покрывают все восемь типов; `ten_in_a_row` — заготовка.

Команды (из `progress-backend`, нужен `OPENAI_API_KEY` в `.env`; тратят деньги):

- Один прогон: `../venv/Scripts/python.exe scripts/eval_dialogs.py --prompt-a v2.0`
- Сравнение промптов: `../venv/Scripts/python.exe scripts/eval_dialogs.py --prompt-a v2.0 --prompt-b v2.1` (или `--prompt-b путь/к/черновику.txt`)
- Сравнение моделей: `../venv/Scripts/python.exe scripts/eval_dialogs.py --prompt-a v2.0 --model-a МОДЕЛЬ1 --model-b МОДЕЛЬ2`
- Один сценарий: добавить `--only normal-01`. Отчёт по умолчанию — `tests/eval/reports/<дата>-<a>-vs-<b>.md` и `.json`.

Тесты: `tests/test_v2_eval.py` (13: числа и состав `dialogs.yaml`, реплики дистресса не изменены, `"v2.1"` не зарегистрирована, `"v2.0"` == `chat_system`, `.txt`, A|B рядом с историей каждой версии, модели в `chat`, жёсткие проблемы и пропуск `todo`, диагностика, смещения дат).

## Таск 14. Новый промпт, примеры, контекст по трём уровням, модель, без жёстких правил

### План (до правок кода)

- `app/services/prompts.py`: `CHAT_SYSTEM_RU` / `CHAT_SYSTEM_EN` (текст брифа с правками §2.4), блоки «мягче» и plateau парами ru/en, рендер плейсхолдеров v2.1 (`{goal} {anchor_quote} {finish_line} {threads} {facts} {day_summaries} {recent_messages} {examples}`), версия `"v2.1"` в `CHAT_PROMPTS` -> `[system, user(текущее)]`; `"v2.0"` — прежний текст и прежний вид истории ролями (120 слов литералом), только для эталонов; `.txt` — на плейсхолдерах v2.1.
- `app/services/prompt_examples.py` (новый): `Example`, `EXAMPLES` (5 заполненных + 4 `TODO(owner)`), `render_examples(lang, limit)`.
- `app/services/conversation.py`: `select_recent` (уровень 1 по бюджету токенов), `load_context_data` по трём уровням, `build_context` на `"v2.1"`, `mentions_goal`; удалить `BANNED`, `check_reply_rules`, `reply_rule_violation`; мягкая диагностика в `ai_reply`.
- `app/services/outreach.py`: `_breaks_rules` — только `empty`, `length`, `quotes`.
- `app/config.py`, `.env.example`: `CHAT_REASONING_EFFORT=medium`, `CONTEXT_RECENT_TOKENS`, `CONTEXT_RECENT_MIN_DAYS`, `CONTEXT_RECENT_HARD_TOKENS`, `CONTEXT_CHARS_PER_TOKEN`, `PROMPT_EXAMPLES_MAX`; удалить `REPLY_MAX_WORDS*`, `REPLY_LONG_INPUT_WORDS`.
- `scripts/eval_dialogs.py`: `conversation.mentions_goal`, `--prompt-b v2.1`.
- Тесты: новый `tests/test_v2_prompt_context.py`; переписать тесты старых правил (`test_v2_conversation.py`, `test_v2_outreach.py`, `test_v2_eval.py`, `test_v2_safety_limits.py`, `conftest.CHAT_REPLY` без вариантов).

### Сделано (таск 14)

- Промпт разговора: `prompts.CHAT_SYSTEM_RU` (текст брифа с правками §2.4: «помнишь, недавно было…», «не ссылайся на то, чего нет…», строка «О человеке — без форм с родом…») и `CHAT_SYSTEM_EN`; другим языкам — английский текст. Плейсхолдеры `{goal} {anchor_quote} {finish_line} {threads} {facts} {day_summaries} {recent_messages} {examples}`, пустой блок — «нет»/«none», финиша нет — «без финиша». Блоки «мягче» (`chat_soft(locale)`) и plateau (`plateau_note(..., locale)`) — пары ru/en, дописываются после основного текста. `_address_*` к промпту v2.1 не добавляется.
- Реестр: `CHAT_PROMPTS = {"v2.1", "v2.0"}`, `DEFAULT_VERSION = "v2.1"` — в приложении. Версия — функция `(data, *, soft, plateau_block, examples_limit) -> messages`: `"v2.1"` и `.txt` — `[system, user(текущее)]`, история внутри `{recent_messages}`; `"v2.0"` — прежний `CHAT_SYSTEM` дословно, история ролями, 120 слов литералом (только эталоны). `.txt` — на плейсхолдерах v2.1.
- `services/prompt_examples.py`: `Example(kind, user, bad, good, todo)`, `EXAMPLES` — 5 примеров брифа (ru+en, `good` без форм с родом по §2.4) и 4 места `TODO(owner)`; `render_examples(lang, limit)` — заполненные по порядку, не больше `PROMPT_EXAMPLES_MAX`; заголовок блока говорит, что `f_12`, `f_87` — условные id. `{{quote:f_12}}` от модели выбрасывается рендерером.
- Контекст по трём уровням (`conversation.load_context_data`): (1) `select_recent(lines_newest_first, today, *, budget, min_days, hard, chars_per_token)` — сообщения всех разговоров, оценка `ceil(len/CONTEXT_CHARS_PER_TOKEN)`, последние `CONTEXT_RECENT_MIN_DAYS` дней всегда, старше — пока влезают в `CONTEXT_RECENT_TOKENS`, выше `CONTEXT_RECENT_HARD_TOKENS` отрезаются самые старые; строки `[дата] Человек:/Person:/ForwardTrace:` (D01), цитаты «…»; текущее сообщение — последним `user`, не в истории. (2) открытые нити до `CONTEXT_THREADS`, недавно упомянутые первыми, `[id] (вид) название — с дата` (`kind` до миграции 0018 — `struggle`). (3) только активная цель; факты `relevant_facts` по дате `[id] дата тип: «цитата»` с пометкой «утверждение на свою дату, новое важнее»; выжимки дней, которых нет в уровне 1, до `CONTEXT_DAYS`.
- Модель: `CHAT_REASONING_EFFORT=medium` по умолчанию; служебные вызовы — `OPENAI_REASONING_EFFORT=low`, как были.
- Быстрые ответы: фейк `CHAT_REPLY` без вариантов; код META не менялся; первый разговор — с вариантами.
- Удалены `BANNED`, `check_reply_rules`, событие `reply_rule_violation`, `REPLY_MAX_WORDS`, `REPLY_MAX_WORDS_LONG`, `REPLY_LONG_INPUT_WORDS`. `outreach._breaks_rules` — только `empty`, `length`, `quotes`. Ответ сохраняется целиком. `ai_reply` получил `words`, `questions`, `mentions_goal`, `with_quick_replies` (плюс прежний `with_quote`). `conversation.mentions_goal(text, goal_title, skill)` (название целиком или слово прозы с основой — первые 5 букв — слова цели от 4 букв; D01) — его же вызывает эталонный скрипт.
- Новые настройки (`config.py`, `.env.example`): `CONTEXT_RECENT_TOKENS=6000`, `CONTEXT_RECENT_MIN_DAYS=2`, `CONTEXT_RECENT_HARD_TOKENS=24000`, `CONTEXT_CHARS_PER_TOKEN=3`, `PROMPT_EXAMPLES_MAX=8`.
- Эталоны: `--prompt-a v2.0 --prompt-b v2.1` работает; A по умолчанию — `v2.0`.

Тесты: новый `tests/test_v2_prompt_context.py` (33: нет старых правил ru/en, текст и META брифа, правки §2.4, пустые блоки, «мягче» и plateau ru/en, 5 примеров + 4 TODO, предел примеров, `f_12` выбрасывается, реестр и вид сообщений, строки нитей и фактов, `.txt` на новых плейсхолдерах, `select_recent` (порядок, бюджет, минимум дней, жёсткий предел), вчерашние сообщения дословно и без повторной выжимки, бюджет в приложении, нити/факты/неактивная цель, `medium`/`low`, пустые `quick_replies`, 200 слов с двумя «?» целиком + поля `ai_reply`, неизвестный `fact_id`, `mentions_goal`, удалённые правила и настройки, outreach-проверки, ru «мягче» и plateau в приложении). Переписаны: `test_v2_conversation.py` (удалён `TestReplyRules`, правило → «не проверяется», быстрые ответы пусты), `test_v2_outreach.py` (вопросы и похвала не ведут к шаблону), `test_v2_eval.py` (`v2.0` = прежний текст, `v2.0` против `v2.1`, `.txt` на новых плейсхолдерах), `test_v2_safety_limits.py` (`chat_soft`), `test_v2_idempotency.py` (повтор с вариантами), `conftest.CHAT_REPLY`.

## Таск 15. Память о жизни: события, решения, темы, follow_up, «Что я помню»

### План (до правок кода)

- Миграция `0018_memory_kinds`: `threads.kind String(16) NOT NULL server_default 'struggle'`; `outreach.topic` `thread→follow_up`, `yesterday→day`, `general→day`; downgrade обратный (`follow_up→thread`, `day→yesterday`, колонка удаляется). `facts.type` — строка, схема не меняется. Модель `Thread.kind`.
- `memory.py`: `FACT_TYPES` += `event`, `decision`; `THREAD_KINDS`; открытие нити по виду (`struggle` — только на факте `struggle`, `topic` — на любом проверенном), отброшенное считается; закрытие `topic` любым фактом; пары — только из `struggle`, «тогда» по сходству — не из `topic`; `follow_up` в `conversation.state`; `delete_fact(db, user, fact_id)`.
- `prompts.py`: `MEMORY_SCHEMA` (`event`/`decision`, `threads.open[].kind`, `follow_up | null`), `MEMORY_SYSTEM` (определения, «без интерпретаций»), нити передаются с видом.
- API: `ThreadOut.kind`; `DELETE /api/facts/{id}` → 204/404; `PATCH /api/threads/{id}` для `topic` — тестом.
- Фронтенд: `Thread.kind`, `api.deleteFact`, `components/MemorySection.tsx` в профиле, строки `memory.*` ru+en на «вы».
- Тесты: `tests/test_v2_memory.py` (извлечение, пары, follow_up, промпт, эндпоинты), `tests/test_v2_foundation.py` (миграция на Postgres).

### Сделано (таск 15)

- Миграция `0018_memory_kinds` (голова): старые нити получают `kind='struggle'`, темы outreach переименованы; downgrade возвращает `thread`/`yesterday` (бывшие `general` возвращаются как `yesterday` — на подъёме они слились).
- `memory.extract_memory`: факты `event`/`decision` сохраняются только с цитатой, прошедшей `verify.quote_supported`. Открытие: `kind` из ответа модели (нет поля — `struggle`); `struggle` на не-`struggle` факте, неизвестный вид, пустое название или отброшенный факт — не открываются и считаются. `mention` — для обоих видов. `close`: `struggle` — как раньше (`achievement`/`learned`), `topic` — любым проверенным фактом. Модель видит нити как `[id] (вид) название (opened дата)`.
- Пары (`make_pairs`): по закрытию — только из нитей `struggle`; по сходству — «тогда» не берётся из фактов, привязанных к нити `topic`.
- `follow_up`: сообщение из этого разговора (те же, что ушли модели) и проверенная цитата → `conversation.state["follow_up"] = {message_id, quote, local_date, used_at: null}`, словарь переприсваивается целиком, прочие ключи `state` сохраняются; та же цитата при повторном извлечении не сбрасывает `used_at`; `null` не стирает сохранённый.
- Событие `memory_dropped_facts` теперь `{conversation_id, dropped, threads_dropped, follow_up_dropped}`, пишется, если что-то из трёх больше нуля.
- `memory.delete_fact(db, user, fact_id) -> bool`: явно удаляет пары с фактом («тогда» или «сейчас»), обнуляет `threads.opened_fact_id/closed_fact_id`, удаляет факт, событие `fact_deleted {fact_id, type}`. `DELETE /api/facts/{fact_id}` → 204, чужой или несуществующий → 404 `not_found`.
- `ThreadOut.kind`; `GET /api/memory` уже отдавал цель, открытые и закрытые нити без `deleted` и до `MEMORY_RECENT_FACTS` фактов — теперь с `kind`.
- Фронтенд: `lib/types.ts` `ThreadKind`, `Thread.kind`; `api.deleteFact(id)`; `components/MemorySection.tsx` — раздел «Что я помню» / «What I remember» в профиле перед «Вашими данными»: цель, мотивация, финиш и «Изменить» (прокрутка к разделу цели и открытие редактирования); темы обоих видов с «Закрыть»/«Удалить», закрытые — в свёрнутом `<details>` с «Удалить»; факты с датой, типом словом, цитатой и «Удалить» с подтверждением; строка исчезает сразу и возвращается на место с текстом ошибки при сбое; пустое состояние «Пока ничего — запоминаю по ходу разговоров». Строки `memory.*` ru+en.
- Вне зоны не тронуто: `outreach.py` по-прежнему пишет `thread`/`yesterday`/`general` для новых сообщений — темы переписывает таск 16.

Тесты: `tests/test_v2_memory.py` +15 (`event`/`decision` только с проверенной цитатой; `topic` открывается на `event`, `struggle` на `decision` отброшен и посчитан; модели передаётся вид нити; `topic` закрывается `event`, `struggle` — нет; пара не создаётся по закрытию `topic` и по сходству с фактом `topic`; `follow_up` в `state` с прочими ключами; непроверенный и из чужого разговора отброшены и посчитаны; `null` не стирает; схема и промпт; `/api/memory` с `kind` без `deleted`; `DELETE /api/facts` удаляет пары и обнуляет ссылки, событие; чужой и несуществующий → 404, изоляция двух пользователей; `PATCH` закрывает и удаляет `topic`). `tests/test_v2_foundation.py::TestMigrationsOnPostgres::test_0018_...` — нити и outreach старых тем на 0017 → upgrade → downgrade. Итог: 447 passed, 3 skipped; `-m postgres` на одноразовом `postgres:16` — 3 passed; `npx tsc --noEmit && npm run build` — зелёные.

## Таск 16. ИИ пишет первым как приглашение, финиш из слов человека, документация

### План (до правок кода)

- `outreach.py`: `Topic(kind, goal, follow_up, conversation, yesterday, facts)`; `pick_topic` пишет только `follow_up` | `day` | `anchor` (`farewell` и `monthly` — как раньше); `follow_up` из `conversations.state["follow_up"]` последнего засчитанного разговора, не старше `OUTREACH_FOLLOW_UP_DAYS`, без `used_at`; при отправке `used_at` проставляется; `quick_replies == []`.
- `prompts.py` (только `OUTREACH_*`, `FIRST_SKILL_*`, `FIRST_MOTIVATION_*`): `OUTREACH_SCHEMA = {"text"}`, промпт тем под интерес вместо проверки со списком «никогда»; `named_finish` в схемах skill и motivation, `first_motivation_system(..., named_finish=)`.
- `texts.py`: `outreach.follow_up` / `day` / `anchor`, ключи `thread` / `yesterday` / `general` удалены.
- `config.py`, `.env.example`: `OUTREACH_FOLLOW_UP_DAYS=3` вместо `OUTREACH_THREAD_RECENT_DAYS`, `OUTREACH_ANCHOR_SILENCE_DAYS=3`.
- `first_conversation.py`: `state["named_finish"]`, `_finish_options(data, named_finish)`.
- Документация: `DOCUMENTATION.md`, `docs/architecture.md`, `CONTEXT.md`, ADR 0011 (заменяет 0007), этот файл. Таблица оценок эталонного отчёта — пять критериев брифа дословно (`scripts/eval_dialogs.py`).
- Тесты: `tests/test_v2_outreach.py`, `tests/test_v2_first_conversation.py`.

### Сделано (таск 16)

- `pick_topic`: свежий неиспользованный `follow_up` → иначе `anchor` (есть активная цель и молчание от 3 дней) → иначе `day` (с выжимкой и фактами вчерашнего дня, если они есть). Открытая нить-трудность темой не бывает и в промпт не попадает. Порядок «follow_up → anchor → day» — прочтение, принятое в спецификации §2.1 #6.
- `used_at` проставляется при отправке (в той же транзакции, словарь `state` переприсваивается): на следующий день тот же `follow_up` не выбирается.
- Текст модели: `OUTREACH_SCHEMA = {"text"}`, быстрых ответов нет. Проверки `_breaks_rules`: пустой / длиннее `OUTREACH_MAX_WORDS` / больше одной цитаты → шаблон темы и событие `outreach_rule_violation`. Промпт: «ты» без рода (`_address_informally`), интерес вместо проверки, список «никогда» из брифа («Удалось выполнить?», «Ты планировал…», «Ты пропустил N дней», открытая трудность как невыполненная задача).
- Шаблоны по §2.4: `outreach.follow_up` «Недавно было: «{quote}». Как в итоге?», `outreach.day`, `outreach.anchor`; `outreach.farewell` оставлен как был (уже на «ты», без упрёка).
- Первый разговор: `named_finish` на шаге `skill` кладётся в `state`, на шаге `motivation` может быть заменён; `_finish_options` ставит его первым, без повторов (`verify.normalize`) и не больше `FINISH_OPTIONS_MAX`; промпт `motivation` получает названный финиш.
- Эталонный отчёт: таблица оценок — ровно пять критериев брифа («Попадание в контекст», «Естественность», «Работа с памятью», «Отсутствие шаблонности», «Полезность»).
- Документация: `DOCUMENTATION.md` описывает промпт v2.1 и примеры, три уровня контекста, `client_msg_id`, `DELETE /api/facts/{id}`, `kind` нитей, `event`/`decision`, `follow_up`, темы outreach, настройки v2.1, эталонный прогон и выбор модели (`CHAT_MODEL=gpt-6-sol` по сравнению 2026-10-27, память и служебные вызовы — `OPENAI_MODEL`), голову миграций `0018_memory_kinds`. Из `DOCUMENTATION.md`, `docs/architecture.md` убраны правила длины, `BANNED`, `check_reply_rules`, `reply_rule_violation`. ADR 0011 записан, в 0007 — «Заменено ADR 0011». `CONTEXT.md`: «событие», «решение», «тема (нить `topic`)», `follow_up`, уточнены «нить» и «сообщение ИИ первым».

Тесты: `tests/test_v2_outreach.py` — `follow_up` выбирается первым и используется один раз, использованный и старше 3 дней не выбираются, молчание 1–2 дня → `day`, 3 → `anchor`, без цели → `day`, открытая трудность не попадает в промпт, выжимка вчера в `day`, текст модели длиннее лимита / пустой / с двумя цитатами → шаблон, `OUTREACH_SCHEMA`, шаблоны (нет «вы», рода, «Удалось», «планировал», «пропустил»), русский промпт («ты», интерес, «никогда»). `tests/test_v2_first_conversation.py::TestNamedFinish` — первый без дубля, замена на `motivation`, промпт получает финиш, чистая `_finish_options`. `tests/test_v2_eval.py` — пять критериев. Мелкие правки чужих тестов: `test_v2_foundation.py` (`outreach.general` → `outreach.day`; «прошёл день» — глагол согласован с «день»), `test_v2_dialogue_tone.py` (то же).

### Итог v2.1

Сделано в порядке брифа: идемпотентная отправка и цитата в строке (12), эталонные диалоги (13), новый промпт, примеры и контекст по трём уровням без жёстких правил (14), память о жизни и «Что я помню» (15), сообщения ИИ первым как приглашение, финиш из слов человека и документация (16). Между 14 и 15 — сравнение на настоящей модели (отчёты в `progress-backend/tests/eval/reports/`), владелец выбрал `gpt-6-sol` для разговора. Голова миграций — `0018_memory_kinds`. Открыто для владельца: четыре примера `TODO(owner)` в `prompt_examples.py`, заготовки `todo: true` в `dialogs.yaml`, главный ручной тест «10 сообщений подряд», оценки в таблицах отчётов.
