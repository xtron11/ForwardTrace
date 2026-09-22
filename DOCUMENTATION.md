# ForwardTrace — техническая документация

> Документ описывает состояние кода ветки `backend` на 2026-09-18 (коммит `b60ee8b`, совпадает по содержимому с `main` `8d6e1fa`).
> Всё, что сказано ниже, проверено по исходному коду. Места, где код и существующие README расходятся, собраны в разделе [17.2](#172-противоречия-между-частями-проекта).

---

# 1. Общее описание проекта

* **Название проекта: ForwardTrace**
* **Назначение проекта: ForwardTrace — приложение, которое собирает свидетельство прогресса из ежедневных голосовых рассказов и возвращает человеку доказательства того, что он изменился. Не трекер привычек, а реестр: каждое утверждение о прогрессе подкреплено дословной цитатой из его собственной речи.**
* **Какую проблему решает: человек занимается делом неделями — учит язык, программирует, ходит в зал, — дисциплина уже есть, но понять, продвинулся ли он, невозможно. Изменения слишком медленные, чтобы почувствовать их изнутри. Трекеры с сериями отвечают на вопрос «пришёл ли я сегодня», а не «работает ли то, что я делаю»**
* **Основные пользователи:люди, которые уже несколько недель что-то делают регулярно и близки к тому, чтобы бросить из-за невидимости результата. Они, как правило, уже пробовали трекеры со сериями и ушли от них. Человеку, у которого ничего не начато, продукт бесполезен: записывать нечего**
* **Основной пользовательский сценарий: вечером человек тридцать секунд наговаривает, как прошёл день. Проверяет расшифровку — можно поправить неверно расслышанные слова. Получает разбор: что сделано, сколько времени, названные числа — и рядом свои же слова, из которых это взято. Ниже появляется наблюдение о дне: противоречие между намерением и тем, что вышло, или изменение относительно конкретного прошлого дня с цитатой и датой. На третий день приходит первый отчёт, дальше по одному в неделю, раз в месяц — итоговый дайджест**
* **Ключевые возможности: Голосовой ввод с проверкой расшифровки перед анализом. Извлечение фактов, где каждый обязан нести дословную цитату — непроверяемое отбрасывается до попадания в базу. Отклик сразу после записи, опирающийся на историю человека с датами и цитатами. Несколько целей одновременно с автоматической маршрутизацией сказанного. Критерии прогресса, которые человек формулирует сам, и отчёт сверяется именно с ними. Задачи-намерения без флага «выполнено» — система показывает, как рассказ соотносится с задуманным, а вывод делает человек. Мотивация «ради чего начал» на главном экране, текстом или голосом. Напоминания, которые не приходят тому, кто уже отметился. Два языка, установка как приложение, админка с воронкой удержания**

---

# 2. Архитектура проекта

## 2.1 Общая архитектура

Монорепозиторий из двух независимых приложений и статического лендинга:

| Часть | Что это | Где |
|---|---|---|
| Backend | REST API на FastAPI (Python, async), фоновые задачи в том же процессе, серверная HTML-админка | `progress-backend/` |
| Frontend | SPA-подобное приложение на Next.js 16 (App Router), все экраны — клиентские компоненты | `progress-frontend/` |
| Лендинг | Статический HTML/CSS/JS, отдаётся фронтендом по адресу `/` | `progress-frontend/public/landing/` |
| БД | PostgreSQL 16 (в тестах — SQLite) | `docker-compose.yml`, Alembic-миграции |

Отдельного воркера или очереди задач нет: тяжёлая работа (распознавание речи, вызовы LLM, генерация отчёта) выполняется через `fastapi.BackgroundTasks` внутри процесса API, а планировщик напоминаний — это `asyncio`-задача, запускаемая в `lifespan` ([progress-backend/app/main.py](progress-backend/app/main.py)). Поэтому API запускается строго с одним воркером (`--workers 1` в [docker-entrypoint.sh](progress-backend/docker-entrypoint.sh)).

```mermaid
flowchart LR
    U[Браузер / PWA] -->|HTTPS, JWT Bearer| FE[Next.js frontend<br/>Vercel]
    U -->|fetch напрямую на API| API[FastAPI<br/>progress-backend]
    FE -.->|отдаёт статику и JS| U
    API --> DB[(PostgreSQL)]
    API --> FS[(Файлы аудио<br/>AUDIO_DIR)]
    API -->|STT| DG[Deepgram API<br/>или локальный faster-whisper]
    API -->|LLM, JSON-схема| OAI[OpenAI Chat Completions]
    API -->|письмо подтверждения| RS[Resend API]
    API -->|Web Push, VAPID| PS[Push-сервисы браузеров]
    PS --> SW[Service Worker sw.js]
    ADM[Администратор] -->|cookie ft_admin| API
```

Важно: фронтенд не проксирует API. Браузер ходит на бэкенд напрямую по `NEXT_PUBLIC_API_URL`, поэтому на бэкенде обязателен корректный `CORS_ORIGINS`.

## 2.2 Frontend

* Next.js 16, React 19, TypeScript, Tailwind CSS v4.
* Все страницы — `"use client"`; данные загружаются в `useEffect` через единый клиент [progress-frontend/lib/api.ts](progress-frontend/lib/api.ts).
* Токены хранятся в `localStorage` (`progress.tokens`), автоматический refresh при 401.
* Локализация en/ru без роутинга, по `navigator.languages` ([lib/i18n.ts](progress-frontend/lib/i18n.ts)).
* PWA: `manifest.json` + `sw.js` (только push-уведомления, без офлайн-кеша).
* Корень `/` переписывается на статический лендинг ([next.config.mjs](progress-frontend/next.config.mjs)).

## 2.3 Backend

* FastAPI 0.115, SQLAlchemy 2 (async, asyncpg), Pydantic v2, Alembic.
* Слои: `routers/` (HTTP) → `services/` (бизнес-логика, внешние API) → `models.py` (ORM).
* При старте ([main.py](progress-backend/app/main.py) `lifespan`):
  1. создаёт `AUDIO_DIR`;
  2. сверяет схему БД с моделями (`_check_schema`) и **отказывается стартовать**, если не хватает таблиц/колонок (или создаёт таблицы, если `AUTO_CREATE_TABLES=true`);
  3. переводит записи в статусах `pending`/`processing` в `failed` («Interrupted by a server restart»);
  4. запускает цикл напоминаний, если есть `VAPID_PRIVATE_KEY` и `REMINDERS_ENABLED`.
* Глобальный обработчик исключений возвращает `500 {"detail": "Internal server error"}`.

## 2.4 База данных

PostgreSQL 16 (JSONB, native UUID). Схема управляется Alembic (11 миграций, `0001_baseline` … `0011_verification_sent_at`). Подробно — раздел 8.

## 2.5 Внешние сервисы и API

| Сервис | Для чего | Где в коде | Обязателен |
|---|---|---|---|
| Deepgram (`/v1/listen`, модель `nova-3`) | Речь → текст | [services/stt.py](progress-backend/app/services/stt.py) `_transcribe_deepgram` | Да, при `STT_PROVIDER=deepgram` |
| faster-whisper (локально) | Альтернатива Deepgram | `services/stt.py` `_transcribe_local` | Нет; зависимость закомментирована в `requirements.txt` |
| OpenAI Chat Completions (structured outputs) | Извлечение фактов, отчёты, рефлексия, сопоставление задач, подсказки критериев | [services/llm.py](progress-backend/app/services/llm.py) `_call_openai` | Да |
| Resend (`https://api.resend.com/emails`) | Письмо подтверждения e-mail | [services/mail.py](progress-backend/app/services/mail.py) | Нет — без ключа подтверждение отключается |
| Web Push (pywebpush, VAPID) | Ежедневные напоминания | [services/push.py](progress-backend/app/services/push.py) | Нет — без ключей напоминания не отправляются |
| Google Fonts | Шрифты фронтенда и лендинга | `app/layout.tsx` (`next/font/google`), `public/landing/index.html` | Нужен доступ при сборке |

## 2.6 Поток данных: от действия пользователя до результата

Главный сценарий — голосовой чек-ин:

1. `/record`: хук [useRecorder](progress-frontend/lib/useRecorder.ts) пишет аудио (webm/opus или mp4/aac на iOS), следит за пиковым уровнем; тишина (`peak < 0.035`) не отправляется.
2. `POST /api/entries/voice` (multipart, `review=true`) → бэкенд проверяет подтверждение почты, наличие активной цели, дневную квоту; сохраняет файл в `AUDIO_DIR/<user_id>/<entry_id>.<ext>`; создаёт `entries` со статусом `pending`; отвечает `202` сразу.
3. Фон: `transcribe_entry` → Deepgram → `raw_transcript`, `stt_transcript`, `detected_language` → статус `awaiting_review`.
4. Фронтенд опрашивает `GET /api/entries/{id}` (`pollUntilSettled`, каждые 900 мс, таймаут 90 с) и показывает транскрипт для правки.
5. `POST /api/entries/{id}/confirm` с исправленным текстом → фон: `process_entry`:
   LLM-извлечение под JSON-схемой → проверка цитат ([verify.py](progress-backend/app/services/verify.py)) → строки `activities` → рефлексия (отдельный вызов LLM) → сопоставление с задачами (ещё один вызов LLM, если есть активные задачи) → статус `done`.
6. Фронтенд переходит на `/today/result?entry=…` и показывает извлечённое, рефлексию и совпадения с задачами.

Подробная sequence-диаграмма — в [разделе 19](#19-приложения).

---

# 3. Структура проекта

```
ForwardTrace/
├── RUNNING.md                    инструкция локального запуска (рус.)
├── progress-backend/
│   ├── app/
│   │   ├── main.py               точка входа: lifespan, CORS, роутеры, /health
│   │   ├── config.py             Settings (pydantic-settings), читает .env
│   │   ├── db.py                 async engine, SessionLocal, get_db
│   │   ├── deps.py               current_user, admin_user, admin_from_cookie
│   │   ├── security.py           bcrypt, JWT (access/refresh/verify)
│   │   ├── models.py             ORM-модели (10 таблиц)
│   │   ├── schemas.py            Pydantic-схемы запросов/ответов
│   │   ├── time_utils.py         таймзоны, «локальный день», периоды отчётов
│   │   ├── vapid.py              генератор VAPID-ключей (python -m app.vapid)
│   │   ├── routers/              auth, goals, entries, reports, tasks, push, admin, adminui
│   │   ├── services/             stt, llm, prompts, verify, extraction, reflection,
│   │   │                         aggregate, summary, monthly, reports, tasks,
│   │   │                         push, reminders, mail, adminstats
│   │   └── templates/            Jinja2-шаблоны админки (/admin)
│   ├── alembic/ + alembic.ini    миграции 0001–0011
│   ├── tests/test_app.py         83 теста (SQLite, STT/LLM замоканы)
│   ├── smoke_test.py             сквозной прогон одного сценария
│   ├── make_account.py           создать подтверждённый аккаунт вручную
│   ├── diagnose_stt.py           диагностика распознавания Deepgram
│   ├── seed_english_week.sql     тестовые данные: неделя чек-инов
│   ├── Dockerfile, docker-entrypoint.sh
│   ├── docker-compose.yml        локально: db (+ api)
│   ├── docker-compose.prod.yml   VPS: db + api + caddy
│   ├── Caddyfile                 TLS и reverse proxy для VPS
│   ├── .env.example
│   └── README.md, DEPLOY.md, RAILWAY.md
└── progress-frontend/
    ├── app/                      страницы App Router (по папке на маршрут)
    ├── components/               Shell/TabBar, Tasks, Reminders, PlayAudio, WhyAnchor, ui
    ├── lib/                      api-клиент, типы, i18n, запись звука, push, PWA, тема
    ├── public/                   sw.js, manifest.json, иконки, og.png, landing/
    ├── next.config.mjs           rewrite "/" → /landing/index.html
    └── package.json
```

| Директория | Зачем | Кто от неё зависит |
|---|---|---|
| `progress-backend/app/routers/` | HTTP-слой: валидация, авторизация, проверки владельца, постановка фоновых задач | Frontend (все экраны), админка |
| `progress-backend/app/services/` | Вся бизнес-логика и интеграции (STT, LLM, почта, push), расчёт статистики | Роутеры, фоновые задачи, планировщик |
| `progress-backend/app/templates/` | HTML админ-панели (`base`, `login`, `overview`, `users`, `user`, `entries`, `feedback`) | `routers/adminui.py` |
| `progress-backend/alembic/versions/` | История схемы БД | Старт приложения (проверка схемы), деплой (`alembic upgrade head` в entrypoint) |
| `progress-frontend/app/` | Экраны приложения | Пользователь |
| `progress-frontend/lib/` | Общий код клиента: `api.ts` (все запросы), `types.ts` (типы ответов API), `i18n.ts` (все строки en/ru) | Все страницы и компоненты |
| `progress-frontend/public/landing/` | Маркетинговая страница на `/` | `next.config.mjs` rewrite |

---

# 4. Технологический стек

| Технология | Назначение | Где используется |
|---|---|---|
| Python 3.12 (Docker), 3.11+ локально | Язык backend | `progress-backend/` |
| TypeScript 5.7 | Язык frontend | `progress-frontend/` |
| FastAPI 0.115 + Uvicorn 0.34 | Backend framework / ASGI-сервер | `app/main.py`, `docker-entrypoint.sh` |
| Next.js ^16.3 (App Router), React 19 | Frontend framework | `progress-frontend/app/` |
| Tailwind CSS v4 (`@tailwindcss/postcss`) | Стили | `app/globals.css`, классы в компонентах |
| PostgreSQL 16 | Основная БД | `docker-compose*.yml`, Railway Postgres |
| SQLite + aiosqlite | БД для тестов и smoke-теста | `tests/`, `smoke_test.py` |
| SQLAlchemy 2.0 (asyncio) + asyncpg | ORM и драйвер | `app/db.py`, `app/models.py` |
| Alembic 1.14 | Миграции | `alembic/` |
| Pydantic 2 / pydantic-settings | Валидация, конфигурация | `app/schemas.py`, `app/config.py` |
| PyJWT (HS256) + bcrypt | Аутентификация: JWT access/refresh, хеш паролей | `app/security.py`, `app/deps.py` |
| REST (JSON + multipart) | API | `app/routers/` |
| OpenAI Chat Completions, модель по умолчанию `gpt-5.6-luna`, structured outputs | AI/LLM | `app/services/llm.py` |
| Deepgram Nova-3 | Speech-to-text | `app/services/stt.py` |
| faster-whisper (опционально) | Локальный STT | `app/services/stt.py` |
| httpx | HTTP-клиент к внешним API | `llm.py`, `stt.py`, `mail.py` |
| Resend | Отправка e-mail | `app/services/mail.py` |
| pywebpush + cryptography (VAPID) | Web Push | `app/services/push.py`, `app/vapid.py` |
| Jinja2 | Серверная админ-панель | `app/routers/adminui.py`, `app/templates/` |
| tzdata | IANA-таймзоны на Windows | `requirements.txt` |
| pytest + pytest-asyncio | Тесты | `tests/test_app.py` |
| Docker, Docker Compose | Локальная БД, прод-образ API | `Dockerfile`, `docker-compose*.yml` |
| Caddy 2 | TLS + reverse proxy (вариант VPS) | `Caddyfile`, `docker-compose.prod.yml` |
| Railway | Хостинг API + Postgres (описан в `RAILWAY.md`) | документация |
| Vercel | Хостинг frontend (описан в `DEPLOY.md`/`RAILWAY.md`) | документация |
| MediaRecorder / Web Audio API | Запись голоса в браузере | `lib/useRecorder.ts` |
| Service Worker, Push API, Web App Manifest | PWA и уведомления | `public/sw.js`, `lib/push.ts`, `lib/pwa.ts` |

---

# 5. Функциональность

### 5.1 Регистрация, вход, подтверждение e-mail
* **Что делает:** создаёт аккаунт с таймзоной и языком браузера; при настроенной почте требует подтверждения адреса.
* **Кто:** любой посетитель (регистрация открыта).
* **Запуск:** `/register`, `/login`, ссылка из письма `/verify?token=…`.
* **Внутри:** [routers/auth.py](progress-backend/app/routers/auth.py). Если `RESEND_API_KEY` не задан, аккаунт сразу помечается подтверждённым и возвращаются токены. Если задан — отправляется письмо с подписанным JWT (`type=verify`, TTL 48 ч), токены не выдаются; при неудачной отправке аккаунт удаляется и возвращается 503.
* **Сохраняется:** `users` (email в нижнем регистре, bcrypt-хеш, timezone, locale, `email_verified`, `verification_sent_at`).
* **Результат:** пара токенов либо `{verification_required, email}`.

### 5.2 Цели, мотивация и критерии прогресса
* **Что делает:** пользователь задаёт цель (до 5 активных), отвечает «почему это важно» (текстом или голосом) и выбирает критерии прогресса — из 4 предложенных моделью или свои.
* **Запуск:** `/setup` (первичный онбординг), `/goals` (редактирование, архивирование, добавление).
* **Внутри:** [routers/goals.py](progress-backend/app/routers/goals.py). Подсказки — `POST /api/goals/suggest-criteria` (LLM). Голосовой ответ сначала транскрибируется синхронно (`POST /api/entries/transcribe`), после создания цели аудио загружается `POST /api/goals/{id}/why-audio` (повторно транскрибируется и хранится).
* **Сохраняется:** `goals` (+ `started_on` = локальная дата создания), `criteria`. При замене критериев старые не удаляются, а получают `is_active=false` (на них ссылаются старые отчёты).
* **Результат:** `GoalOut` с активными критериями.

### 5.3 Чек-ин (голос или текст)
* **Что делает:** ежедневный рассказ о дне превращается в проверенные факты.
* **Запуск:** `/record` (голос), `/record?mode=text` (текст).
* **Ограничения:** нужна подтверждённая почта (`REQUIRE_VERIFIED_EMAIL`), хотя бы одна активная цель (иначе 409), квоты на локальный день: 3 голосовых / 10 текстовых (иначе 429). Аудио до 10 МБ, допустимые MIME: webm, ogg, mp4, mpeg, wav, aac, flac.
* **Внутри:** [services/extraction.py](progress-backend/app/services/extraction.py) `transcribe_entry` / `process_entry` (см. 2.6 и раздел 10).
* **Сохраняется:** `entries` (транскрипт, исходный STT-транскрипт, флаг правки, mood, wins, friction, intentions, reflection, латентности, `dropped_facts`), `activities` (по одной на извлечённую активность), `task_mentions`.
* **Результат:** `202 {id, status, local_date, poll_url}`; итог — через опрос `GET /api/entries/{id}`.

### 5.4 Экран результата и рефлексия
* После обработки `/today/result` показывает активности, метрики, цитаты, рефлексию (0–3 абзаца от модели, каждый со ссылкой на дату и дословную цитату прошлой записи, проверенную кодом), совпадения с задачами и предложение задач. Рефлексия — [services/reflection.py](progress-backend/app/services/reflection.py).

### 5.5 Экран «Сегодня»
* `GET /api/entries/summary` ([services/summary.py](progress-backend/app/services/summary.py) `daily_summary`): число дней с записями, отметка «сегодня уже записано», «горизонт» из 14 столбиков (высота — объём сказанного относительно самого насыщенного дня), накопленная метрика за всё время, личный рекорд (только если побит сегодня и был предыдущий), дней до отчёта. Все числа считаются в SQL/Python, не моделью.
* Также показывает мотивацию цели (`WhyAnchor`, с воспроизведением записи) и активные задачи (`TodaysTasks`).

### 5.6 Хроника (Timeline)
* `/timeline`: список записей (`GET /api/entries`, до 60), транскрипт, воспроизведение аудио (`GET /api/entries/{id}/audio`, загружается blob'ом с Bearer-токеном), кнопка повтора для `failed` (`POST /api/entries/{id}/retry`). Параметр `?date=` подсвечивает день.

### 5.7 Еженедельный отчёт
* **Запуск:** `/report`, кнопка генерации → `POST /api/reports`.
* **Периоды** ([time_utils.py](progress-backend/app/time_utils.py) `completed_period`): первый отчёт доступен на 3-й день после создания цели и покрывает первые 2 дня; дальше — полные 7-дневные периоды. Отчёт покрывает только завершённые дни.
* **Минимум записей:** 2 для первого отчёта, 3 для последующих — иначе отчёт сохраняется со статусом `failed` и пояснением.
* **Внутри:** [services/reports.py](progress-backend/app/services/reports.py): статистика ([aggregate.py](progress-backend/app/services/aggregate.py) `compute_stats`) → LLM пишет только текст → валидация (выдуманные id критериев отбрасываются, «доказательство», отрицающее само себя, понижается до `no_evidence`, `what_changed` ≤ 3, уверенность паттерна `low` при < 4 днях).
* **Сохраняется:** `reports` (stats, content, snapshot названия цели и критериев, модель, время генерации). Отчёт генерируется **один раз**: повторный запрос возвращает сохранённый (кроме `force=true` или статуса `failed`).
* **Обратная связь:** оценка 1–4 и текст — `POST /api/reports/{id}/feedback`.
* Из рекомендации отчёта можно создать задачу (`TaskFromRecommendation`, `source="ai"`).

### 5.8 Месячный дайджест
* `/monthly` → `GET /api/reports/monthly?year=&month=` ([services/monthly.py](progress-backend/app/services/monthly.py)). По умолчанию — прошлый месяц. Полностью вычисляемый, без вызова LLM: дни с записями, топ-3 метрики, самый насыщенный день (по минутам), до 3 изменений из уже провалидированных недельных отчётов, первая и последняя запись месяца. Флаг `thin` при < 5 днях.

### 5.9 Задачи (намерения)
* **Что делает:** «намерения» пользователя на срок 1–30 дней, без флага «выполнено». После каждого чек-ина LLM сопоставляет транскрипт с активными задачами; совпадение сохраняется только с проверенной цитатой.
* **Запуск:** предложения на экране результата (`GET /api/tasks/suggestions` — берутся только intentions, произнесённые самим пользователем в последних 3 записях), создание `POST /api/tasks`, продление/закрытие `PATCH /api/tasks/{id}`, «не сейчас» `POST /api/tasks/decline` (тишина 3 дня).
* **Ограничения:** до 5 активных задач (409). Предложения показываются только когда активных задач нет.
* **Сохраняется:** `tasks`, `task_mentions`, `users.tasks_declined_on`.

### 5.10 Push-напоминания
* **Что делает:** раз в день в выбранный локальный час (по умолчанию 20) присылает напоминание, если сегодня ещё не было записи.
* **Запуск:** `/settings` (или `ReminderSettings` на `/goals`): включение push → Service Worker → `POST /api/push/subscribe`; час — `PATCH /api/push/settings`; тест — `POST /api/push/test`.
* **Внутри:** [services/reminders.py](progress-backend/app/services/reminders.py) `loop` просыпается каждые `reminder_tick_minutes` (15 мин), `run_once` выбирает пользователей с подпиской, у которых сейчас их локальный час напоминания, нет записи сегодня и не было напоминания сегодня. `last_reminded_on` ставится даже при неудачной доставке. Подписки удаляются после 404/410 или 3 ошибок подряд.

### 5.11 Админ-инструменты
* **JSON API** (`/api/admin/*`, по Bearer-токену и `ADMIN_EMAILS`): сводка, все транскрипты с извлечённым, ручная замена содержимого отчёта (`generated_by="human"`, «режим консьержа»), лента отзывов.
* **HTML-панель** (`/admin`, cookie `ft_admin`): удержание (кто дошёл до 3-го дня), здоровье конвейера, эффект напоминаний, список пользователей, карточка пользователя, последние записи, отзывы. Логика — [services/adminstats.py](progress-backend/app/services/adminstats.py).

### 5.12 Исследовательская телеметрия
* `POST /api/events` пишет произвольные события клиента в `events` (например, `silent_recording`). Также `onboarding_transcribe` используется бэкендом как счётчик квоты.

### 5.13 Лендинг, PWA, тема, локализация
* `/` — статический лендинг с видео и en/ru копирайтом (`public/landing/shared/copy.js`, `i18n.js`), CTA ведёт на `/register`.
* PWA-установка (`lib/pwa.ts`), светлая/тёмная тема (`lib/theme.ts`, `localStorage: forwardtrace.theme`), язык — по браузеру; тот же `locale` отправляется при регистрации и определяет язык ответов модели.

---

# 6. Пользовательские сценарии

### 6.1 Регистрация (почта настроена)
1. Пользователь открывает `/register` (или жмёт CTA на лендинге).
2. Frontend отправляет `POST /api/auth/register` с email, паролем, именем, `Intl…timeZone` и локалью браузера.
3. Backend валидирует (пароль ≥ 8 символов и ≤ 72 байта, валидная IANA-таймзона, locale → `en`/`ru`), создаёт `users`, отправляет письмо через Resend.
4. Ответ `201 {verification_required: true, email}` — токенов нет. Экран «проверьте почту», кнопка повторной отправки (`POST /api/auth/resend-verification`, не чаще раза в 60 с).
5. Пользователь открывает ссылку `/verify?token=…` → `POST /api/auth/verify` → `email_verified=true`.
6. Пользователь входит на `/login`.

*Почта не настроена:* шаг 3 сразу ставит `email_verified=true`, шаг 4 возвращает токены, и фронтенд переходит на `/setup`.

### 6.2 Вход
1. `/login` → `POST /api/auth/login`.
2. Backend: неверные данные → 401 (одно сообщение для обоих случаев); почта не подтверждена (при настроенной почте) → 403; аккаунт выключен → 403. Обновляется `last_seen_at`.
3. Токены сохраняются в `localStorage`; frontend запрашивает `GET /api/goals` и ведёт на `/today` или `/setup`, если целей нет.

### 6.3 Онбординг цели
1. `/setup` (без токена — редирект на `/login`): название цели.
2. «Почему это важно» — текстом или голосом (`POST /api/entries/transcribe`, синхронно, до 5 раз в сутки; файл после распознавания удаляется).
3. `POST /api/goals/suggest-criteria` → 4 подсказки (при ошибке LLM показывается сообщение, можно ввести свои).
4. Пользователь выбирает/добавляет критерии → `POST /api/goals` (критерии из подсказок получают `source="ai"`).
5. Если ответ был голосом — `POST /api/goals/{id}/why-audio` (best effort, ошибка игнорируется).
6. Переход на `/today`.

### 6.4 Голосовой чек-ин
1. На `/today` пользователь нажимает запись → `/record`, запись начинается сразу.
2. Остановка: если тишина — ошибка на клиенте и событие `silent_recording`.
3. `POST /api/entries/voice` → `202`. Опрос `GET /api/entries/{id}`.
4. Статус `awaiting_review` → показ транскрипта для правки.
5. `POST /api/entries/{id}/confirm` → опрос до `done`/`failed`.
6. Переход на `/today/result?entry=…`: активности, метрики, цитаты, рефлексия, задачи.

### 6.5 Текстовый чек-ин
1. `/record?mode=text` → ввод текста.
2. `POST /api/entries/text` → сразу `process_entry` (без шага проверки транскрипта).
3. Опрос → `/today/result`.

### 6.6 Повтор неудачной записи
1. На `/timeline` запись со статусом `failed` имеет кнопку повтора.
2. `POST /api/entries/{id}/retry` (проверяется дневная квота по типу записи) → `process_entry`. Если транскрипт уже есть, STT пропускается.

### 6.7 Получение недельного отчёта
1. `/report` загружает цели и список отчётов (`GET /api/reports`), показывает последний отчёт выбранной цели.
2. Кнопка генерации → `POST /api/reports {goal_id}`.
3. Backend вычисляет последний завершённый период; если его нет → `425` («период ещё не закончился»). Если отчёт за период уже есть — возвращает его.
4. Фон: `generate_report_task` → статистика → проверка минимума записей → LLM → валидация → `done`.
5. Frontend опрашивает `GET /api/reports/{id}` и рендерит блоки: что сделано, что изменилось, паттерн, трения, рекомендация, прогресс по критериям, итог.
6. Пользователь оценивает отчёт (1–4 + текст) → `POST /api/reports/{id}/feedback`.

### 6.8 Задачи
1. После чек-ина `TaskSuggestion` запрашивает `GET /api/tasks/suggestions`; если активных задач нет и нет недавнего отказа — показываются намерения, произнесённые пользователем.
2. Пользователь выбирает текст и срок → `POST /api/tasks`, либо «не сейчас» → `POST /api/tasks/decline`.
3. Следующие чек-ины сопоставляются с задачей; на `/today` видно «дней затронуто / дней в сроке» и цитаты.
4. Продление или закрытие — `PATCH /api/tasks/{id}`.

### 6.9 Включение напоминаний
1. `/settings` → переключатель push → регистрация `/sw.js`, запрос разрешения, `GET /api/push/key`, `pushManager.subscribe`.
2. `POST /api/push/subscribe` (также ставит `reminders_on=true`).
3. Выбор часа → `PATCH /api/push/settings`; «проверить» → `POST /api/push/test` (503, если ни одно устройство не приняло).
4. Планировщик отправляет уведомление; клик по нему открывает `/today`.

### 6.10 Работа администратора
1. `/admin/login` (форма email+пароль) → проверка пароля и вхождения в `ADMIN_EMAILS` → httpOnly-cookie `ft_admin` на путь `/admin` на время жизни access-токена (30 мин).
2. Страницы `/admin`, `/admin/users`, `/admin/users/{id}`, `/admin/entries`, `/admin/feedback`.
3. Ручная правка отчёта — только через JSON API `PUT /api/admin/reports/{id}/content` (например, из `/docs`).

---

# 7. Backend и API

Базовый URL — `NEXT_PUBLIC_API_URL` (локально `http://127.0.0.1:8000`). Swagger: `/docs`.
Авторизация «Bearer» — заголовок `Authorization: Bearer <access_token>`; проверка в [deps.py](progress-backend/app/deps.py) `current_user` (тип токена `access`, пользователь активен, `tv == token_version`). Ошибка — `401 Not authenticated`.
Ошибки валидации Pydantic — стандартные `422`. Непойманные исключения — `500`.

### 7.1 Служебные

| Метод | URL | Назначение | Auth | Ответ |
|---|---|---|---|---|
| GET | `/health` | Проверка API и БД | нет | `{api, database, stt_provider, llm_model}` |

### 7.2 Auth — [routers/auth.py](progress-backend/app/routers/auth.py)

| Метод | URL | Назначение | Auth | Тело | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| POST | `/api/auth/register` | Регистрация | нет | `RegisterIn {email, password, display_name?, timezone="UTC", locale="en"}` | `201 TokenPair` или `RegisteredOut` | 409 email занят, 503 письмо не отправлено, 422 |
| POST | `/api/auth/login` | Вход | нет | `{email, password}` | `TokenPair` | 401, 403 почта не подтверждена / аккаунт отключён |
| POST | `/api/auth/refresh` | Новая пара токенов | refresh-токен в теле | `{refresh_token}` | `TokenPair` | 401 |
| POST | `/api/auth/change-password` | Смена пароля, инвалидирует все токены | Bearer | `{current_password, new_password}` | `TokenPair` | 400 неверный текущий пароль |
| POST | `/api/auth/logout-everywhere` | Инкремент `token_version` | Bearer | — | 204 | — |
| POST | `/api/auth/verify` | Подтверждение e-mail | нет | `{token}` | `{verified, email}` | 400 невалидная ссылка |
| POST | `/api/auth/resend-verification` | Повтор письма | нет | `{email}` | `202 {sent: true}` всегда | — |
| GET | `/api/auth/me` | Профиль | Bearer | — | `UserOut` | 401 |
| PATCH | `/api/auth/me` | Изменить профиль | Bearer | `UserUpdate {display_name, timezone, locale, reminder_hour, reminders_on, cohort, intake}` | `UserOut` | 422 |

`TokenPair = {access_token, refresh_token, token_type:"bearer", expires_in}`. Access живёт 30 мин, refresh — 60 дней. Refresh-токены не ротируются и не хранятся на сервере; отзываются только через `token_version`.

### 7.3 Goals — [routers/goals.py](progress-backend/app/routers/goals.py)

| Метод | URL | Назначение | Auth | Вход | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| POST | `/api/goals/suggest-criteria` | 4 подсказки критериев от LLM | Bearer | `{title, why_text?}` | `{criteria: string[]}` (≤4) | 503 ошибка LLM |
| POST | `/api/goals` | Создать цель | Bearer | `GoalCreate {title, why_text?, why_source, criteria[≤10]}` | `201 GoalOut` | 409 уже 5 активных целей |
| GET | `/api/goals` | Все цели пользователя (вкл. архивные) | Bearer | — | `GoalOut[]` | — |
| GET | `/api/goals/{id}` | Одна цель | Bearer | — | `GoalOut` | 404 |
| PATCH | `/api/goals/{id}` | Изменить title/why/is_active/criteria | Bearer | `GoalUpdate` | `GoalOut` | 404 |
| POST | `/api/goals/{id}/why-audio` | Загрузить и распознать запись мотивации | Bearer | multipart `audio` | `GoalOut` | 404, 413, 415, 400 пустой файл, 503 STT |
| GET | `/api/goals/{id}/why-audio` | Скачать запись мотивации | Bearer | — | аудиофайл | 404 |

Удаления целей нет — только архивирование через `is_active=false`.

### 7.4 Entries — [routers/entries.py](progress-backend/app/routers/entries.py)

| Метод | URL | Назначение | Auth | Вход | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| POST | `/api/entries/voice` | Голосовой чек-ин | Bearer + подтверждённая почта | multipart `audio`, `goal_id?`, `review=true` | `202 EntryAccepted` | 403, 409 нет цели, 429 квота, 404 цель, 413, 415, 400 |
| POST | `/api/entries/{id}/confirm` | Подтвердить/исправить транскрипт | Bearer | `{text}` (1–8000) | `202 EntryAccepted` | 404, 409 не в `awaiting_review` |
| POST | `/api/entries/text` | Текстовый чек-ин | Bearer + подтверждённая почта | `{text, goal_id?}` | `202 EntryAccepted` | 403, 409, 429, 404 |
| POST | `/api/entries/transcribe` | Синхронная транскрипция (онбординг), файл не хранится | Bearer + подтверждённая почта | multipart `audio` | `{text, seconds, stt_ms}` | 403, 429 (5/сутки), 503 |
| PATCH | `/api/entries/activities/{id}` | Перепривязать активность к другой цели / ни к какой | Bearer | `{goal_id: uuid\|null}` | `ActivityOut` | 404 |
| GET | `/api/entries/summary` | Числа для экрана «Сегодня» | Bearer | query `goal_id?` | `DailySummaryOut` | — |
| GET | `/api/entries/{id}/audio` | Аудио записи | Bearer | — | файл | 404 |
| GET | `/api/entries/{id}` | Запись с активностями (для опроса) | Bearer | — | `EntryOut` | 404 |
| GET | `/api/entries` | Хроника | Bearer | `limit≤200` (60), `offset` | `EntryOut[]` | — |
| POST | `/api/entries/{id}/retry` | Повтор обработки | Bearer | — | `202 EntryAccepted` | 404, 409 уже `done`, 429 |

`EntryAccepted = {id, status, local_date, poll_url}`. Статусы записи: `pending` → `processing` → (`awaiting_review` → `pending` → `processing`) → `done` | `failed`.

### 7.5 Reports — [routers/reports.py](progress-backend/app/routers/reports.py)

| Метод | URL | Назначение | Auth | Вход | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| GET | `/api/reports/monthly` | Месячный дайджест | Bearer | `year?`, `month?` | `MonthlyDigestOut` | 422 месяц вне 1–12 |
| POST | `/api/reports` | Создать/вернуть отчёт | Bearer | `{goal_id?, period_end?, force=false}` | `202 ReportOut` | 404 нет цели, 425 период не завершён |
| GET | `/api/reports` | Список отчётов | Bearer | `limit≤100` (20) | `ReportOut[]` | — |
| GET | `/api/reports/latest` | Последний отчёт | Bearer | — | `ReportOut` | 404 |
| GET | `/api/reports/{id}` | Отчёт | Bearer | — | `ReportOut` | 404 |
| POST | `/api/reports/{id}/feedback` | Оценка | Bearer | `{rating: 1..4, text?}` | `ReportOut` | 404 |

`period_end` задаёт 7-дневное окно, заканчивающееся этой датой (используется для отладки, см. `RUNNING.md`).

### 7.6 Tasks — [routers/tasks.py](progress-backend/app/routers/tasks.py)

| Метод | URL | Назначение | Auth | Вход | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| GET | `/api/tasks` | Активные задачи (или все) | Bearer | `include_closed=false` | `TaskOut[]` | — |
| POST | `/api/tasks` | Создать задачу | Bearer | `{text, goal_id?, source="user", days 1..30}` | `201 TaskOut` | 409 лимит 5, 404 цель |
| PATCH | `/api/tasks/{id}` | Текст / продлить / закрыть | Bearer | `{text?, extend_days?, close?}` | `TaskOut` | 404 |
| POST | `/api/tasks/decline` | «Не сейчас» | Bearer | — | 204 | — |
| GET | `/api/tasks/suggestions` | Собственные намерения пользователя | Bearer | — | `{should_ask, suggestions[≤3]}` | — |

### 7.7 Push — [routers/push.py](progress-backend/app/routers/push.py)

| Метод | URL | Назначение | Auth | Вход | Ответ | Ошибки |
|---|---|---|---|---|---|---|
| GET | `/api/push/key` | Публичный VAPID-ключ | нет | — | `{key, enabled}` | — |
| POST | `/api/push/subscribe` | Зарегистрировать устройство | Bearer | `{endpoint, keys:{p256dh, auth}}` | `201 {ok}` | — |
| POST | `/api/push/unsubscribe` | Удалить устройство | Bearer | `{endpoint}` | 204 | — |
| POST | `/api/push/test` | Тестовое уведомление | Bearer | — | `{delivered}` | 503 |
| PATCH | `/api/push/settings` | Вкл/выкл, час | Bearer | `{reminders_on?, reminder_hour 0..23?}` | `{reminders_on, reminder_hour}` | 422 |

### 7.8 Admin JSON и события — [routers/admin.py](progress-backend/app/routers/admin.py)

| Метод | URL | Назначение | Auth | Ответ |
|---|---|---|---|---|
| POST | `/api/events` | Записать событие телеметрии `{type≤64, payload?}` | Bearer (любой пользователь) | `201 {ok}` |
| GET | `/api/admin/overview` | Сводка: пользователи, записи, ошибки, отброшенные факты, латентности, распределение оценок | Bearer + `ADMIN_EMAILS` (иначе 403) | JSON |
| GET | `/api/admin/entries` | Транскрипты + извлечённое (`limit≤500`) | admin | JSON |
| PUT | `/api/admin/reports/{id}/content` | Заменить содержимое отчёта вручную | admin | `ReportOut` (404) |
| GET | `/api/admin/feedback` | Отзывы на отчёты | admin | JSON |

### 7.9 Admin HTML — [routers/adminui.py](progress-backend/app/routers/adminui.py) (не в OpenAPI)

| Метод | URL | Назначение |
|---|---|---|
| GET / POST | `/admin/login` | Форма входа; при успехе cookie `ft_admin` и редирект на `/admin` |
| GET | `/admin/logout` | Удаление cookie |
| GET | `/admin` | Удержание, здоровье, эффект напоминаний |
| GET | `/admin/users`, `/admin/users/{id}` | Список и карточка пользователя |
| GET | `/admin/entries` | Последние записи |
| GET | `/admin/feedback` | Отзывы |

Без валидной cookie все страницы редиректят на `/admin/login`.

**Итого:** 48 JSON-эндпоинтов (включая `/health`) и 8 HTML-маршрутов админки.

---

# 8. База данных

Модели — [progress-backend/app/models.py](progress-backend/app/models.py). Все PK — UUID (`uuid4`). `JsonB` = JSONB в Postgres / JSON в SQLite. Все FK на `users.id` — `ON DELETE CASCADE`; FK на `goals.id` из `entries`/`activities`/`reports`/`tasks` — `SET NULL`; FK `criteria.goal_id`, `activities.entry_id`, `task_mentions.*` — `CASCADE`.

### `users`
| Поле | Тип | Примечание |
|---|---|---|
| id | UUID PK | |
| email | varchar(255) | unique index, хранится в нижнем регистре |
| password_hash | varchar(255) | bcrypt, 12 раундов |
| display_name | varchar(120) | |
| timezone | varchar(64) | IANA, default `UTC`; определяет «день» и «неделю» |
| locale | varchar(8) | `en`/`ru`; язык ответов LLM и письма |
| email_verified | bool | |
| verification_sent_at | timestamptz | анти-спам повторной отправки |
| token_version | int | инвалидирует все JWT |
| is_active | bool | отключённый аккаунт не входит |
| intake | JSONB | «ответы на 5 вопросов» — в UI не используется |
| cohort | varchar(64) | для исследований |
| tasks_declined_on | date | кулдаун предложений задач |
| reminder_hour | int (20) | локальный час напоминания |
| reminders_on | bool | |
| last_reminded_on | date | не более одного напоминания в день |
| created_at, last_seen_at | timestamptz | |

### `goals`
`id`, `user_id → users`, `title` (200), `why_text` (text), `why_source` (`text|voice`), `why_audio_path`, `why_audio_mime`, `why_audio_seconds`, `is_active`, `started_on` (date — от неё считаются периоды отчётов), `created_at`.

### `criteria`
`id`, `goal_id → goals`, `text` (300), `source` (`ai|user`), `position`, `is_active` (старые деактивируются, не удаляются), `created_at`.

### `entries` — один чек-ин
`id`, `user_id → users`, `goal_id → goals` (nullable; обычно null — маршрутизация идёт на уровне активностей), `local_date` (date), `source` (`voice|text`), `audio_path`, `audio_mime`, `audio_seconds`, `raw_transcript` (итоговый текст), `stt_transcript` (что услышал STT), `transcript_edited`, `detected_language`, `mood`, `wins`/`friction` (JSONB `[{text, quote, goal_id}]`), `intentions` (JSONB `[{text, quote, goal_id}]`), `reflection` (JSONB `[{text, reference:{date, quote}|null}]`), `status` (index), `error`, `stt_ms`, `llm_ms`, `dropped_facts`, `created_at`.
Индекс: `(user_id, local_date)`.

### `activities` — проверенные факты
`id`, `entry_id → entries`, `user_id → users`, `goal_id → goals` (nullable), `local_date`, `category`, `category_key` (нормализованный), `minutes` (NULL, если длительность не произнесена), `minutes_explicit`, `details` (JSONB, ≤4 строк), `metrics` (JSONB `[{name, value, unit, quote}]`), `quote`, `created_at`.
Индексы: `(user_id, local_date)`, `(user_id, category_key)`.

### `reports`
`id`, `user_id → users`, `goal_id → goals`, `period_start`, `period_end` (включительно), `status`, `stats` (JSONB, посчитано в Python, включая snapshot цели и критериев), `content` (JSONB, текст модели после валидации), `generated_by` (`ai|human`), `model_name`, `generation_ms`, `error`, `feedback_rating` (1–4), `feedback_text`, `feedback_at`, `created_at`.
Unique: `(user_id, goal_id, period_start)` — `uq_report_period`.

### `tasks`
`id`, `user_id`, `goal_id` (nullable), `text`, `source` (`ai|user`), `starts_on`, `ends_on` (включительно), `status` (`active|closed`), `closed_at`, `created_at`. Индекс `(user_id, status)`.

### `task_mentions`
`id`, `task_id → tasks`, `entry_id → entries`, `local_date`, `evidence` (цитата), `created_at`. Unique `(task_id, entry_id)`.

### `push_subscriptions`
`id`, `user_id → users`, `endpoint` (unique), `p256dh`, `auth`, `user_agent`, `failure_count`, `last_success_at`, `created_at`.

### `events`
`id`, `user_id → users` (nullable), `type` (index), `payload` (JSONB), `created_at`. Append-only.

### Кто использует сущности

| Таблица | Роутеры / сервисы |
|---|---|
| users | auth, deps, reminders, adminui, все роутеры (через `current_user`) |
| goals, criteria | goals, extraction (маршрутизация), reports, summary, monthly, reflection |
| entries | entries, extraction, reflection, summary, aggregate, monthly, reminders, admin |
| activities | extraction (запись), aggregate, summary, monthly, entries (перепривязка), admin |
| reports | reports (router/service), summary (`days_until_report`), monthly (`_changes`), admin |
| tasks, task_mentions | tasks (router/service), extraction (`match_entry`) |
| push_subscriptions | push (router/service), reminders |
| events | admin (`/api/events`), entries (квота `onboarding_transcribe`), adminstats |

### ER-диаграмма

```mermaid
erDiagram
    users ||--o{ goals : has
    users ||--o{ entries : records
    users ||--o{ activities : owns
    users ||--o{ reports : receives
    users ||--o{ tasks : sets
    users ||--o{ push_subscriptions : devices
    users ||--o{ events : logs
    goals ||--o{ criteria : "defines progress"
    goals |o--o{ entries : "optional pin"
    goals |o--o{ activities : "routed to"
    goals |o--o{ reports : "about"
    goals |o--o{ tasks : "optional"
    entries ||--o{ activities : "extracted into"
    entries ||--o{ task_mentions : "evidence"
    tasks ||--o{ task_mentions : "touched on"
```

---

# 9. Авторизация и безопасность

### Регистрация и вход
* Пароль: минимум 8 символов, максимум 72 байта (ограничение bcrypt) — только при регистрации ([schemas.py](progress-backend/app/schemas.py) `RegisterIn.check_password`). При смене пароля проверяется только минимальная длина.
* Хеширование — bcrypt, 12 раундов ([security.py](progress-backend/app/security.py)).
* Логин не раскрывает, существует ли email (одно сообщение 401). `resend-verification` всегда отвечает одинаково.

### Сессии и токены
* JWT HS256, секрет `JWT_SECRET`. Поля: `sub`, `tv` (token_version), `typ` (`access`/`refresh`), `iat`, `exp`, `jti`.
* Access 30 мин, refresh 60 дней. Refresh не ротируется при использовании; новый refresh выдаётся, старый продолжает действовать до истечения или смены `token_version`.
* Отзыв всех токенов: смена пароля, `POST /api/auth/logout-everywhere`.
* На клиенте оба токена лежат в `localStorage` ([lib/api.ts](progress-frontend/lib/api.ts)), то есть доступны любому JS на странице. Выход в `/settings` только удаляет токены локально (серверный `logout-everywhere` фронтендом не вызывается).
* Токен подтверждения e-mail — отдельный JWT (`type=verify`, 48 ч) с email внутри: смена email инвалидирует ссылку.

### Middleware и защита API
* Единственный middleware — `CORSMiddleware` с `allow_origins=CORS_ORIGINS`, `allow_credentials=True`.
* Авторизация — через зависимости FastAPI: `CurrentUser`, `AdminUser` (роль «админ» = email в `ADMIN_EMAILS`), `admin_from_cookie` для HTML-админки.
* Изоляция данных: все выборки фильтруются по `user_id == current_user.id` (покрыто тестами `test_one_user_cannot_read_another_users_entry`, `test_admin_routes_are_closed_to_ordinary_users`). Аудиофайлы отдаются только владельцу.
* Cookie админки: `httponly`, `samesite=lax`, `secure` при https, `path=/admin`. CSRF-токенов нет (изменяющих HTML-форм, кроме логина, нет).

### Защита от злоупотреблений (фактическая)
* Дневные квоты на чек-ины (3 голосовых / 10 текстовых) и онбординг-транскрипции (5/сутки).
* Чек-ины и транскрипции требуют подтверждённой почты (если почта настроена).
* Лимит размера аудио 10 МБ (+ `max_size 12MB` в Caddy), белый список MIME.
* Лимиты: 5 активных целей, 5 активных задач, 10 критериев.
* **Общего rate limiting нет** — в том числе на `/api/auth/login`, `/admin/login`, `/api/goals/suggest-criteria` (вызов LLM без квоты), `POST /api/reports` с `force=true` (перегенерация отчёта через LLM без квоты).

### Хранение секретов
* Все ключи — в `progress-backend/.env` (в `.gitignore`), шаблон — `.env.example` без реальных значений.
* **Проверка утечек:** поиск по отслеживаемым файлам и по всей истории git (`git log --all -p`) шаблонов ключей OpenAI (`sk-…`), Resend (`re_…`), AWS, приватных ключей, непустых `*_API_KEY=`/`JWT_SECRET=`/`VAPID_PRIVATE_KEY=` ничего не нашёл. Файлы `.env` в git никогда не коммитились (коммитились только `.env.example` и `.env.local.example`). Локальный `progress-backend/.env` существует и игнорируется git.
* В [config.py](progress-backend/app/config.py) `jwt_secret` имеет значение по умолчанию `"CHANGE-ME-openssl-rand-hex-32"`, и приложение **не проверяет**, что секрет заменён. Если `JWT_SECRET` не задан в окружении, токены подписываются общеизвестной строкой.

### Валидация данных
* Pydantic-схемы с ограничениями длины на все текстовые поля; проверка таймзон через `zoneinfo`; нормализация locale.
* `POST /api/events`: `payload` — произвольный dict без ограничения размера.
* Вывод LLM не доверяется: JSON-схема + проверка цитат + валидация отчётов (см. раздел 10).
* Шаблоны админки — Jinja2 через `Jinja2Templates` (автоэкранирование HTML включено по умолчанию).

### Прочие важные места
* Фоновые задачи в процессе API: при рестарте незавершённые записи помечаются `failed`, отчёты в статусе `processing` — не сбрасываются (для них повтор возможен только через `force`).
* Аудиозаписи (голос пользователей) хранятся на диске без шифрования; `KEEP_AUDIO=true` по умолчанию.
* `--forwarded-allow-ips '*'` в entrypoint: uvicorn доверяет `X-Forwarded-*` от любого источника (в prod-compose API недоступен снаружи, кроме как через Caddy; на Railway — через их прокси).

---

# 10. AI-функции

Все вызовы LLM проходят через одну функцию `complete_json(system, user, schema)` ([services/llm.py](progress-backend/app/services/llm.py)):
* единственный провайдер — OpenAI: `POST {OPENAI_BASE_URL}/chat/completions`, `response_format: json_schema (strict)`, `reasoning_effort` (по умолчанию `low`) либо `temperature=0`; модель `OPENAI_MODEL` (по умолчанию `gpt-5.6-luna`);
* семафор параллелизма (`LLM_CONCURRENCY=4`), таймаут 180 с, 2 повтора с паузой 1.5 с × попытка;
* ответ чистится от ``` и парсится как JSON; при неудаче — `LLMError`.

Все промпты — в [services/prompts.py](progress-backend/app/services/prompts.py). Инструкции на английском; для `locale=ru` добавляется блок `_write_in` («пиши весь текст для человека по-русски, цитаты — на языке оригинала»).

| # | Функция | Где вызывается | Промпт / схема | Что уходит в модель | Обработка ответа | Где сохраняется | Fallback |
|---|---|---|---|---|---|---|---|
| 1 | Подсказка критериев | `POST /api/goals/suggest-criteria` | `CRITERIA_SYSTEM` / `CRITERIA_SCHEMA` (ровно 4 строки) | название цели, «почему» | обрезка до 4 непустых | не сохраняется (пользователь выбирает) | 503, UI позволяет ввести свои |
| 2 | Извлечение фактов | `extraction.extract_from_transcript` | `EXTRACTION_SYSTEM` / `EXTRACTION_SCHEMA` | транскрипт, активные цели с id и критериями, ранее использованные категории | см. ниже | `entries.*`, `activities` | запись → `failed`, кнопка Retry |
| 3 | Рефлексия | `reflection.reflect` | `REFLECTION_SYSTEM` / `REFLECTION_SCHEMA` | сегодняшний транскрипт, цель, «почему», 3 самые ранние записи, до 10 записей за 21 день, повторяющиеся трения, числа из `daily_summary` | цитаты проверяются по записи с указанной датой; фильтр похвалы/диагнозов (`BANNED`, `!`); ≤ 3 абзацев | `entries.reflection` | пустой список, чек-ин не падает |
| 4 | Сопоставление задач | `tasks.match_entry` | `TASK_MATCH_SYSTEM` / `TASK_MATCH_SCHEMA` | активные задачи (id, текст), транскрипт | только известные id и проверенные цитаты | `task_mentions` | 0 совпадений, чек-ин не падает |
| 5 | Недельный отчёт | `reports.build_report` | `REPORT_SYSTEM` / `REPORT_SCHEMA` | цель, «почему», критерии с id, вычисленная статистика, победы/трения, настроения, разбивка по дням; **сырых транскриптов нет** | `_validate` (см. ниже) | `reports.content` | отчёт `failed` с текстом ошибки; повтор через `POST /api/reports` |

**Проверки после извлечения** ([verify.py](progress-backend/app/services/verify.py), [extraction.py](progress-backend/app/services/extraction.py)):
* каждая активность, win, friction, intention и метрика должна иметь `quote`, найденный в транскрипте (нормализация NFKC, без пунктуации и регистра; точное вхождение или скользящее сравнение `SequenceMatcher ≥ 0.90`; минимум 8 символов) — иначе отбрасывается, счётчик идёт в `entries.dropped_facts`;
* `goal_id` вне списка активных целей → `null` (не привязано);
* `minutes` сохраняется, только если `minutes_explicit=true` и 0 < минут ≤ 960, иначе `NULL`;
* метрики: значение > 0 и ≤ 1 000 000, не более 4 на активность; не более 6 активностей; `mood` из фиксированного набора, иначе `neutral`;
* категории склеиваются с ранее использованными (`SequenceMatcher ≥ 0.88`).

**Валидация отчёта** (`reports._validate`): выдуманные `criterion_id` отбрасываются; каждый критерий обязательно присутствует (по умолчанию `no_evidence`); статус с пустым или «отрицающим» доказательством (`DENIAL_MARKERS`, en/ru) понижается до `no_evidence`; `what_changed` ≤ 3; `pattern.confidence` принудительно `low` при < 4 днях; длины обрезаются.

**Числа никогда не считает модель:** суммы, серии, покрытие времени — в `aggregate.py`/`summary.py`/`monthly.py`.

**Речь в текст** ([stt.py](progress-backend/app/services/stt.py)): Deepgram с `smart_format`, `punctuate`, без слов-паразитов; язык по умолчанию определяется автоматически (`detect_language=true`), `STT_LANGUAGE` жёстко фиксирует язык, `STT_MULTILINGUAL` → `language=multi`. `keyterm` отправляются только при зафиксированном языке и модели `nova-3`. Записи короче 10 символов транскрипта помечаются `done` с ошибкой «No speech detected».

---

# 11. Frontend

### Страницы

| Маршрут | Файл | Назначение | Защита |
|---|---|---|---|
| `/` | `public/landing/index.html` (rewrite) | Лендинг | — |
| `/register` | `app/register/page.tsx` | Регистрация, экран «проверьте почту» | — |
| `/login` | `app/login/page.tsx` | Вход | — |
| `/verify` | `app/verify/page.tsx` | Подтверждение e-mail по `?token=` | — |
| `/setup` | `app/setup/page.tsx` | Онбординг: цель → «почему» → критерии | редирект на `/login` без токена |
| `/today` | `app/today/page.tsx` | Главный экран: горизонт, счётчики, задачи, кнопки записи | `Shell` |
| `/record` | `app/record/page.tsx` | Запись голоса / ввод текста, проверка транскрипта | `BareShell` |
| `/today/result` | `app/today/result/page.tsx` | Результат чек-ина | `Shell` |
| `/timeline` | `app/timeline/page.tsx` | Хроника записей | `Shell` |
| `/report` | `app/report/page.tsx` | Недельный отчёт, переключатель целей, отзыв | `Shell` |
| `/monthly` | `app/monthly/page.tsx` | Месячный дайджест | `BareShell` |
| `/goals` | `app/goals/page.tsx` | Цели, архив, критерии, настройки напоминаний | `Shell` |
| `/settings` | `app/settings/page.tsx` | Push, час напоминания, установка PWA, тема, выход | `BareShell` |

`app/*/layout.tsx` задают только `metadata.title`. `robots.ts` закрывает от индексации все экраны приложения; `sitemap.ts` публикует лендинг и страницы авторизации.

### Компоненты
* [Shell.tsx](progress-frontend/components/Shell.tsx) — `Shell` (шапка с темой и шестерёнкой настроек + нижний `TabBar`: Today / Timeline / Report / Goals), `BareShell` (без таб-бара). Оба редиректят на `/login`, если токенов нет.
* [Tasks.tsx](progress-frontend/components/Tasks.tsx) — `TodaysTasks`, `TaskReflection`, `TaskSuggestion`, `TaskFromRecommendation`.
* [Reminders.tsx](progress-frontend/components/Reminders.tsx) — `ReminderSettings` (используется на `/goals`); `ReminderPrompt` и `InstallApp` определены, но нигде не используются.
* `PlayAudio` — проигрывание аудио, загружаемого blob'ом; `WhyAnchor` — мотивация цели; `ui.tsx` — `Button`, `Field`, `Quote`, `Notice`, `Spinner`, `Eyebrow`; `Logo`.

### State management
Глобального стора нет. Локальный `useState`/`useEffect` на каждой странице; постоянное состояние — только `localStorage` (токены, тема, флаг скрытия подсказки напоминаний). Язык — `useT()` (стартует с `en` и переключается после монтирования, чтобы не было расхождения гидрации).

### Формы
Нативные `<form>`/контролируемые инпуты без библиотек: регистрация, вход, онбординг, редактирование цели и критериев, текстовый чек-ин, правка транскрипта, отзыв на отчёт, создание задачи.

### Взаимодействие с API
Только через `api.*` в [lib/api.ts](progress-frontend/lib/api.ts): добавляет Bearer, JSON-заголовки, при 401 делает один общий refresh и повтор, при неудаче чистит токены. Ошибки — `ApiError(status, message)` с текстом `detail` сервера. Английские сообщения сервера частично переводятся [lib/serverErrors.ts](progress-frontend/lib/serverErrors.ts) по регулярным выражениям. Долгие операции — `pollUntilSettled` (900 мс, до 90 с, затем `ApiError(408)`).

### Loading / error states
Страницы используют `Spinner`, флаги `busy`/`loading`/`generating` и блоки `Notice`/сообщения об ошибке. Некоторые вторичные запросы молча игнорируют ошибки (`.catch(() => {})`: загрузка why-audio, retry в хронике, настройки часа, `logEvent`).

### Запись звука
[useRecorder.ts](progress-frontend/lib/useRecorder.ts) выбирает поддерживаемый контейнер, измеряет уровень, определяет тишину, позволяет выбрать устройство ввода. Микрофон работает только на `localhost` или HTTPS.

---

# 12. Конфигурация и environment variables

### Backend (`progress-backend/.env`, читается [config.py](progress-backend/app/config.py))

| Переменная | Назначение | Обязательна | Пример / значение по умолчанию |
|---|---|---|---|
| `DATABASE_URL` | Строка подключения; `postgres://`/`postgresql://` переписываются на `asyncpg` | Да | `postgresql+asyncpg://progress:progress@localhost:5432/progress` |
| `JWT_SECRET` | Подпись JWT | **Да** (есть небезопасный default) | `openssl rand -hex 32` |
| `ACCESS_TOKEN_TTL_MIN` | Время жизни access | Нет | `30` |
| `REFRESH_TOKEN_TTL_DAYS` | Время жизни refresh | Нет | `60` |
| `STT_PROVIDER` | `deepgram` / `local` | Нет | `deepgram` |
| `DEEPGRAM_API_KEY` | Ключ Deepgram | Да при deepgram | — |
| `DEEPGRAM_MODEL` | Модель Deepgram | Нет | `nova-3` |
| `STT_LANGUAGE` | Жёстко задать язык (рекомендуется пусто) | Нет | пусто |
| `STT_DETECT_LANGUAGE` | Автоопределение языка | Нет | `true` |
| `STT_MULTILINGUAL` | `language=multi` | Нет | `false` |
| `STT_KEYTERMS` | Словарь терминов (через запятую) | Нет | `recursion,LeetCode,API,…` |
| `STT_TIMEOUT_SEC`, `STT_CONCURRENCY` | Таймаут и параллелизм STT | Нет | `120`, `1` |
| `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | faster-whisper | Нет | `base.en`, `cpu`, `int8` |
| `OPENAI_API_KEY` | Ключ OpenAI | Да | — |
| `OPENAI_MODEL` | Модель | Нет | `gpt-5.6-luna` |
| `OPENAI_REASONING_EFFORT` | Уровень рассуждений | Нет | `low` |
| `OPENAI_BASE_URL` | Базовый URL | Нет | `https://api.openai.com/v1` |
| `LLM_CONCURRENCY`, `LLM_TIMEOUT_SEC`, `LLM_MAX_RETRIES` | Параметры LLM | Нет | `4`, `180`, `2` |
| `RESEND_API_KEY` | Ключ Resend; без него подтверждение почты отключено | Нет | — |
| `EMAIL_FROM` | Отправитель | Нет | `ForwardTrace <onboarding@resend.dev>` |
| `APP_URL` | URL **фронтенда** для ссылки в письме | Да при Resend | `https://your-app.vercel.app` |
| `REQUIRE_VERIFIED_EMAIL` | Требовать подтверждение для чек-инов | Нет | `true` |
| `EMAIL_VERIFICATION_TTL_HOURS` | Срок ссылки | Нет | `48` |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | Ключи Web Push (`python -m app.vapid`) | Нет (без них push выключен) | — |
| `VAPID_SUBJECT_EMAIL` | Контакт для push-сервисов | Нет | `admin@example.com` |
| `PUSH_TTL_SECONDS` | TTL уведомления | Нет | `43200` (итоговое значение, см. 17.2) |
| `REMINDERS_ENABLED` | Включить планировщик | Нет | `true` |
| `REMINDER_TICK_MINUTES` | Период планировщика | Нет | `15` |
| `CORS_ORIGINS` | Точный origin фронтенда (через запятую) | Да в проде | `http://localhost:3000` |
| `ADMIN_EMAILS` | Админы (через запятую) | Нет | `you@example.com` |
| `AUTO_CREATE_TABLES` | `create_all` вместо проверки схемы | Нет | `false` |
| `AUDIO_DIR` | Папка аудио | Нет | `./data/audio` |
| `KEEP_AUDIO` | Хранить аудио после обработки | Нет | `true` |
| `MAX_AUDIO_MB` | Лимит загрузки | Нет | `10` |
| `REPORT_PERIOD_DAYS`, `FIRST_REPORT_AFTER_DAYS` | Длина периода, день первого отчёта | Нет | `7`, `3` |
| `MIN_ENTRIES_FOR_REPORT`, `MIN_ENTRIES_FIRST_REPORT` | Минимум записей | Нет | `3`, `2` |
| `MAX_ACTIVE_GOALS`, `MAX_ACTIVE_TASKS` | Лимиты | Нет | `5`, `5` |
| `TASK_SUGGESTION_COOLDOWN_DAYS` | Пауза после «не сейчас» | Нет | `3` |
| `MAX_VOICE_ENTRIES_PER_DAY`, `MAX_TEXT_ENTRIES_PER_DAY`, `MAX_ONBOARDING_TRANSCRIBES_PER_DAY` | Квоты | Нет | `3`, `10`, `5` |
| `POSTGRES_PASSWORD`, `API_DOMAIN` | Только `docker-compose.prod.yml` | Да для VPS | — |
| `PORT` | Порт uvicorn (задаёт Railway) | Нет | `8000` |

Переменные из `.env.example`, **которые код не использует**: `REMINDER_INTERVAL_SECONDS` (поле `reminder_interval_seconds` есть, но не читается планировщиком), `DEFAULT_REMINDER_HOUR` (поле есть, но в модели час по умолчанию захардкожен как 20).

### Frontend (`progress-frontend/.env.local`)

| Переменная | Назначение | Обязательна | Пример |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Адрес API | Да (иначе `http://localhost:8000`) | `https://YOUR-APP.up.railway.app` |
| `NEXT_PUBLIC_SITE_URL` | Канонический URL для metadata/robots/sitemap | Нет (иначе `https://forward-trace.com`) | `https://forward-trace.com` |

### Проверка утечки ключей
Реальных ключей в репозитории и его истории не обнаружено (подробно — раздел 9, «Хранение секретов»). Рекомендация, вытекающая из кода: задавать `JWT_SECRET` обязательно, так как дефолт не блокирует старт.

---

# 13. Установка и запуск проекта

1. **Установить:** Python 3.11+, Node.js 20+, Docker Desktop, Git.
2. **Клонировать:**
   ```bash
   git clone <URL репозитория> ForwardTrace
   cd ForwardTrace
   ```
3. **Зависимости:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1          # Linux/macOS: source venv/bin/activate
   pip install -r progress-backend/requirements.txt
   cd progress-frontend; npm install; cd ..
   ```
4. **Переменные окружения:**
   ```powershell
   copy progress-backend\.env.example progress-backend\.env
   copy progress-frontend\.env.local.example progress-frontend\.env.local
   ```
   Заполнить минимум `JWT_SECRET` (`python -c "import secrets; print(secrets.token_hex(32))"`), `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `ADMIN_EMAILS`. `RESEND_API_KEY` локально можно оставить пустым — регистрация пройдёт без письма. Проверьте, что порт в `DATABASE_URL` совпадает с портом в `docker-compose.yml` (5432; если он занят локальным Postgres — меняйте в обоих местах).
5. **База данных:**
   ```powershell
   cd progress-backend
   docker compose up -d db
   docker compose ps                    # ждать healthy
   alembic upgrade head
   ```
   Опционально: тестовые данные `Get-Content seed_english_week.sql | docker compose exec -T db psql -U progress -d progress`; аккаунт без письма — `python make_account.py user@example.com password`.
6. **Development:**
   ```powershell
   # окно 1, из progress-backend
   python -m uvicorn app.main:app --reload
   # проверка
   Invoke-RestMethod http://127.0.0.1:8000/health
   # окно 2, из progress-frontend
   npm run dev                          # http://localhost:3000
   ```
   Тесты: `python -m pytest` (из `progress-backend`), сквозной прогон: `python smoke_test.py`. VAPID-ключи: `python -m app.vapid`.
7. **Production build:**
   ```bash
   # frontend
   cd progress-frontend && npm run build && npm run start
   # backend (образ сам применяет миграции при старте)
   cd progress-backend && docker build -t forwardtrace-api . && docker run --env-file .env -p 8000:8000 forwardtrace-api
   ```

---

# 14. Deployment

В репозитории описаны два варианта; какой используется в реальности, по коду определить нельзя.

**Вариант A — Railway + Vercel** ([RAILWAY.md](progress-backend/RAILWAY.md)):
* API: Railway собирает `progress-backend/Dockerfile` (Root Directory `progress-backend`), managed PostgreSQL инжектит `DATABASE_URL`, домен `*.up.railway.app`. Volume на `/app/data` для аудио (без него записи теряются при каждом деплое).
* Frontend: Vercel, Root Directory `progress-frontend`, переменная `NEXT_PUBLIC_API_URL`.

**Вариант B — VPS + Docker Compose + Caddy** ([DEPLOY.md](progress-backend/DEPLOY.md)): `docker compose -f docker-compose.prod.yml up -d --build`; наружу открыт только Caddy (80/443, Let's Encrypt, домен из `API_DOMAIN`, например DuckDNS); бэкапы через `pg_dump` в cron.

**Сборка:** `Dockerfile` (python:3.12-slim + ffmpeg) → `docker-entrypoint.sh`: `alembic upgrade head`, затем `uvicorn --workers 1 --proxy-headers`. Frontend — стандартный `next build` на Vercel.

**Переменные:** см. раздел 12; для прода обязательно новый `JWT_SECRET`, ключи провайдеров, `CORS_ORIGINS` = точный URL фронтенда, `APP_URL` при Resend.

**После push/merge:** в репозитории нет CI/CD-конфигурации (нет `.github/workflows`, нет `railway.json`/`vercel.json`). Автодеплой возможен только через Git-интеграции Railway/Vercel, настраиваемые в их панелях — в коде это не видно. В `DEPLOY.md` сказано, что frontend «redeploys itself when you push».

**Ветка деплоя:** по коду не указана; судя по истории, итоговые изменения сливаются в `main`.

---

# 15. Git workflow

По истории коммитов (45 коммитов, один автор, с 2026-08-26):

| Ветка | Фактическое использование |
|---|---|
| `backend` | Рабочая ветка: сюда идут все коммиты, включая изменения фронтенда и лендинга (несмотря на название) |
| `main` | Интеграционная ветка; почти все её коммиты — `Merge branch 'backend'` |
| `develop` | Последний merge из `backend` 2026-09-09, отстаёт от `main` на 25 коммитов |
| `frontend` (только origin) | Последнее обновление 2026-08-31 (PR #1 из `backend`), отстаёт на 39 коммитов |

Процесс: коммит в `backend` → push → локальный merge `backend` → `main` → push. Ветки `develop` и `frontend` в текущем процессе фактически не участвуют. Pull request использовался один раз (PR #1). Тесты перед merge не запускаются автоматически (CI нет).

Обратите внимание: `.gitignore` содержит правило `*.md`, поэтому новые Markdown-файлы (включая этот `DOCUMENTATION.md`) не попадут в git без `git add -f`. `README.md`, `RUNNING.md`, `DEPLOY.md`, `RAILWAY.md` отслеживаются, так как были добавлены раньше/принудительно.

---

# 16. Troubleshooting

| Симптом | Причина | Диагностика / решение |
|---|---|---|
| API не стартует: `Database schema is out of date - missing: …` | Не применены миграции | `alembic upgrade head` из `progress-backend` |
| `Cannot read the database schema` / ошибки 10061 | БД не запущена | `docker compose up -d db`, `docker compose ps` → `healthy` |
| Ошибка 10054 / неверные учётные данные | На порту 5432 другой Postgres | Сменить порт в `docker-compose.yml` и `DATABASE_URL` |
| Запрос к `localhost:8000` висит | Windows резолвит `localhost` в `::1`, uvicorn слушает IPv4 | Использовать `127.0.0.1` |
| `ModuleNotFoundError: No module named 'app'` | Запуск не из `progress-backend` | Перейти в `progress-backend` |
| Чек-ин `failed`: `DEEPGRAM_API_KEY is not set` / `OPENAI_API_KEY is not set` | Нет ключей | Заполнить `.env`, перезапустить uvicorn (`--reload` не перечитывает `.env`) |
| Транскрипт — связная бессмыслица на чужом языке | Зафиксирован неверный `STT_LANGUAGE` | Оставить `STT_LANGUAGE` пустым; `python diagnose_stt.py` |
| Frontend: «network error» на всех запросах в проде | `CORS_ORIGINS` не совпадает с origin фронтенда | Скопировать точный URL со схемой |
| Микрофон не включается | Страница открыта не по `localhost`/HTTPS | Открывать через `localhost` или HTTPS |
| Push не работает | Нет VAPID-ключей (в логах: `reminders on but VAPID keys missing`) или нет HTTPS | `python -m app.vapid`, тестировать на HTTPS |
| 403 «Confirm your email…» | Resend настроен, почта не подтверждена | Подтвердить или `python make_account.py` |
| 409 «Set a goal first» | Нет активной цели | Создать цель на `/setup` |
| 429 «Daily limit reached» | Квота на день (в т.ч. при Retry) | Увеличить `MAX_*_PER_DAY` или ждать следующего локального дня |
| 425 при генерации отчёта | Первый период ещё не завершён | Подождать или `POST /api/reports {"period_end": "...", "force": true}` через `/docs` |
| Отчёт `failed`: «Only N check-in(s)…» | Мало записей в периоде | Нужно ≥ 2 (первый) / ≥ 3 записей |
| Записи «зависли» в обработке после рестарта | Фоновые задачи живут в процессе | При старте они становятся `failed` → Retry в хронике |
| Аудио пропадает после деплоя | Нет volume на `/app/data` | Подключить volume |
| Консоль PowerShell «зависла» | Выделение текста мышью замораживает процесс | Esc; отключить «Быстрая вставка» |
| Где смотреть ошибки | — | Лог uvicorn; `GET /api/admin/entries` (транскрипт, `dropped_facts`, `error`); `/admin` |

---

# 17. Известные ограничения

## 17.1 Незавершённое, временные решения, технический долг

* **TODO/FIXME в коде нет.** Явно помеченные временные решения:
  * [lib/serverErrors.ts](progress-frontend/lib/serverErrors.ts) — «Stopgap»: перевод сообщений сервера по регуляркам вместо кодов ошибок в API.
  * Фоновые задачи в процессе, один воркер, нет очереди (признано в `README.md`/`DEPLOY.md`).
* **Нет восстановления пароля** (признано в `README.md`).
* **Нет общего rate limiting** (в т.ч. на вход и на вызовы LLM вне чек-инов) — признано в `README.md`.
* **Регистрация открыта**, инвайт-кодов нет (признано в `DEPLOY.md`).
* **Нет CI/CD и мониторинга.**
* **Нет удаления** аккаунта, целей, записей, задач через API.
* **Нереализованные в UI возможности бэкенда:** перепривязка активности к цели (`PATCH /api/entries/activities/{id}`, в `lib/api.ts` есть `reassignActivity`, но он нигде не вызывается), `GET /api/reports/latest` (не используется), `users.intake` (пишется только через `PATCH /api/auth/me`, в UI не заполняется), серверный `logout-everywhere` (в UI нет).
* **Мёртвый код фронтенда:** компоненты `ReminderPrompt` и `InstallApp` в [Reminders.tsx](progress-frontend/components/Reminders.tsx) не используются.
* **Брошенный шаг проверки транскрипта:** запись в статусе `awaiting_review`, если пользователь ушёл со страницы, остаётся навсегда; хроника показывает её как «обрабатывается» без кнопки действия, при рестарте она не сбрасывается, но учитывается в дневной квоте.
* **Retry и квота:** `retry` проверяет квоту по количеству записей того же типа за *сегодня*, включая саму повторяемую запись, поэтому при исчерпанной квоте повторить сегодняшнюю неудачную запись нельзя.
* **Отчёт, прерванный рестартом:** статус `processing` не сбрасывается при старте (в отличие от записей); повтор `POST /api/reports` без `force` вернёт «висящий» отчёт.
* **`force=true` и `suggest-criteria`** доступны любому пользователю без квоты и вызывают платный LLM.
* **Смена пароля** не проверяет ограничение 72 байта (в отличие от регистрации).
* **`JWT_SECRET`** имеет небезопасное значение по умолчанию без проверки при старте.

## 17.2 Противоречия между частями проекта

1. **Дублирующиеся поля в [config.py](progress-backend/app/config.py):** `vapid_public_key`, `vapid_private_key`, `vapid_subject_email`, `push_ttl_seconds`, `reminders_enabled` объявлены дважды; действует второе объявление (например, `push_ttl_seconds` = 12 ч, а не 6 ч).
2. **Неиспользуемые настройки:** `reminder_interval_seconds` (и `REMINDER_INTERVAL_SECONDS=600` в `.env.example`) — планировщик использует `reminder_tick_minutes=15`; `default_reminder_hour` (`DEFAULT_REMINDER_HOUR`) не используется.
3. **`.env.example`**: разделы «email» и «push reminders» продублированы; первый ссылается на несуществующий `generate_vapid_keys.py` (так же в комментарии `config.py`), правильная команда — `python -m app.vapid`.
4. **Порт БД:** `RUNNING.md` приводит `DATABASE_URL` с портом `5433`, а `docker-compose.yml` и `.env.example` — `5432`.
5. **Сообщение «период не завершён»:** бэкенд пишет `The first 3-day period is not over yet.`, а фронтенд ищет регуляркой `7-day period is not over` — перевод на русский не срабатывает при настройках по умолчанию.
6. **Тип ответа регистрации:** `api.register` объявлен как `Promise<Tokens>`, хотя сервер может вернуть `RegisteredOut`; страница обходит это type guard'ом.
7. **Устаревший `progress-backend/README.md`:** раздел «Чего здесь нет» утверждает, что подтверждения почты нет, — оно реализовано (миграции 0010–0011, `/api/auth/verify`).
8. **Устаревший `progress-frontend/README.md`:** называет проект «Evidence», говорит о «шести экранах», описывает `/` как экран-тезис и светлую палитру «ledger paper»; фактически `/` — статический лендинг, экранов 13, основная тема тёмная (`#0E1116`) с переключателем.
9. **`RUNNING.md`:** «около шестидесяти тестов» — фактически 83.
10. **Названия:** продукт — ForwardTrace, пакеты — `progress-backend`/`progress-frontend`, FastAPI title — «Progress API», frontend README — «Evidence».
11. **Дубли кода:** двойные импорты `asyncio` и `suppress` в `main.py`; класс `UnsubscribeIn` объявлен дважды в `routers/push.py`.
12. **`monthly._strongest_day`:** докстринг обещает не выбирать день при ничьей, код берёт первую строку сортировки без проверки ничьей.
13. **`services/mail.py`:** докстринг «a failed letter must not cost someone the account», а `register` при неудачной отправке удаляет только что созданный аккаунт (сделано намеренно, чтобы освободить адрес; комментарии расходятся по смыслу).
14. **Названия ветки:** ветка `backend` содержит и frontend-изменения; ветки `develop`/`frontend` устарели.

---

# 19. Приложения

> Раздел 18 в исходной структуре отсутствует — нумерация сохранена.

### 19.1 Архитектура

```mermaid
flowchart TB
    subgraph Client[Браузер]
        LND[Лендинг /]
        APP[Next.js экраны]
        SW[sw.js]
        LS[(localStorage<br/>токены, тема)]
    end
    subgraph API[FastAPI, 1 процесс]
        R[routers]
        S[services]
        BG[BackgroundTasks]
        RL[reminder loop]
        ADM[Jinja2 /admin]
    end
    APP --> R
    R --> S
    R --> BG --> S
    RL --> S
    ADM --> S
    S --> PG[(PostgreSQL)]
    S --> DISK[(AUDIO_DIR)]
    S --> DG[Deepgram]
    S --> LLM[OpenAI]
    S --> RS[Resend]
    S --> WP[Web Push] --> SW
    APP --- LS
```

### 19.2 User flow

```mermaid
flowchart LR
    A[Лендинг] --> B[/register/]
    B -->|почта настроена| C[Письмо] --> D[/verify/] --> E[/login/]
    B -->|без почты| F[/setup/]
    E -->|нет целей| F
    E -->|есть цели| G[/today/]
    F --> G
    G --> H[/record/] --> I[Проверка транскрипта] --> J[/today/result/]
    J --> K[Задача из намерения]
    G --> L[/timeline/]
    G --> M[/report/] --> N[Оценка отчёта]
    M --> O[/monthly/]
    G --> P[/goals/]
    G --> Q[/settings/ push]
```

### 19.3 ER-диаграмма
См. [раздел 8](#8-база-данных).

### 19.4 Sequence: голосовой чек-ин

```mermaid
sequenceDiagram
    actor U as Пользователь
    participant FE as /record (Next.js)
    participant API as FastAPI
    participant DB as PostgreSQL
    participant BG as BackgroundTask
    participant DG as Deepgram
    participant LLM as OpenAI

    U->>FE: запись и стоп
    FE->>API: POST /api/entries/voice (audio, review=true)
    API->>DB: проверки (почта, цель, квота), INSERT entries (pending)
    API-->>FE: 202 {id, poll_url}
    API->>BG: transcribe_entry(id)
    BG->>DG: /v1/listen
    DG-->>BG: transcript, language
    BG->>DB: raw/stt_transcript, status=awaiting_review
    loop каждые 900 мс
        FE->>API: GET /api/entries/{id}
    end
    FE->>U: показать транскрипт
    U->>FE: исправить и подтвердить
    FE->>API: POST /api/entries/{id}/confirm {text}
    API->>BG: process_entry(id)
    BG->>LLM: извлечение (EXTRACTION_SCHEMA)
    BG->>BG: verify: цитаты, минуты, метрики, goal_id
    BG->>DB: entries.*, INSERT activities
    BG->>LLM: рефлексия (REFLECTION_SCHEMA)
    BG->>BG: проверка дат и цитат, фильтр похвалы
    BG->>LLM: сопоставление задач (если есть активные)
    BG->>DB: task_mentions, status=done
    FE->>API: GET /api/entries/{id} (опрос до done)
    FE->>U: /today/result
```

### 19.5 Sequence: недельный отчёт

```mermaid
sequenceDiagram
    participant FE as /report
    participant API as FastAPI
    participant BG as generate_report_task
    participant DB as PostgreSQL
    participant LLM as OpenAI

    FE->>API: POST /api/reports {goal_id}
    API->>API: completed_period(started_on, today)
    alt период не завершён
        API-->>FE: 425
    else отчёт уже есть
        API-->>FE: 202 существующий Report
    else новый
        API->>DB: INSERT reports (pending)
        API-->>FE: 202 Report
        API->>BG: запуск
        BG->>DB: compute_stats (SQL)
        alt записей меньше минимума
            BG->>DB: status=failed, error
        else
            BG->>LLM: REPORT_SCHEMA (только факты и числа)
            BG->>BG: _validate
            BG->>DB: content, status=done
        end
    end
    loop пока pending/processing
        FE->>API: GET /api/reports/{id}
    end
```
