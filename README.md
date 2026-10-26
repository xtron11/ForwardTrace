# ForwardTrace

Разговорный дневник прогресса для людей, которые долго развивают навык: программирование,
геймдев, языки, спорт, музыку. Человек говорит или пишет, ИИ сразу отвечает и доказывает
рост **его же словами с датами**.

Отличие от обычного ИИ-чата держится на трёх вещах:

1. **Память с проверенными цитатами.** Из каждого разговора в фоне извлекаются факты, и у
   каждого есть дословная цитата, найденная в тексте сообщения. ИИ ссылается на прошлое
   только через такие факты, а саму цитату в ответ подставляет код, а не модель.
2. **Нити.** Трудность, которую назвал человек, отслеживается, пока он не скажет, что
   справился. Тогда появляется карточка «было → стало».
3. **ИИ пишет первым.** Раз в день, в выбранный час, ИИ начинает разговор вопросом — по
   открытой нити, по цели или по вчерашнему разговору (push или Telegram).

---

## Как это работает

```
сообщение голосом или текстом (один разговор на календарный день)
  → проверки до потока: почта, лимит, формат и размер аудио, ответ уже идёт
  → речь в текст (Deepgram Nova-3, с таймкодами слов)
  → проверка безопасности (уровни 0–3)
  → ответ потоком (SSE) с плейсхолдерами {{quote:<fact_id>}} → код подставляет цитаты из БД
  → в фоне, когда разговор затих: факты с проверенными цитатами, нити, «было → стало»
  → раз в день ИИ пишет первым; раз в месяц — сводка
```

Первый разговор и есть онбординг: что человек развивает, зачем, финиш (момент, когда
цель достигнута), где он сейчас и с чего начинал — и сразу первое «тогда → сейчас».

---

## Из чего состоит

| Часть | Что это | Где |
|---|---|---|
| Бэкенд | FastAPI: REST + SSE, фоновые циклы в том же процессе, серверная HTML-админка | [`progress-backend/`](progress-backend/) |
| Фронтенд | Next.js 16 (App Router), PWA: Сегодня, История, Прогресс, Профиль | [`progress-frontend/`](progress-frontend/) |
| Лендинг | Статический HTML/CSS/JS, отдаётся фронтендом по адресу `/` | [`progress-frontend/public/landing/`](progress-frontend/public/landing/) |
| База | PostgreSQL 16, схемой управляет Alembic (в тестах — SQLite) | `progress-backend/alembic/` |

---

## Быстрый старт

Нужны Python 3.11+, Node 20+ и Docker Desktop. Три окна терминала:

```powershell
# 1. база
cd progress-backend
docker compose up -d db

# 2. бэкенд (из progress-backend, .env заполнен по .env.example)
alembic upgrade head
python -m uvicorn app.main:app --reload

# 3. фронтенд
cd ../progress-frontend
npm install
npm run dev
```

Приложение — `http://localhost:3000`, документация API — `http://127.0.0.1:8000/docs`.
Подробности и частые проблемы (в том числе на Windows) — в [DOCUMENTATION.md](DOCUMENTATION.md),
разделы 13 и 15. Ключи для `.env` — по `progress-backend/.env.example`.

---

## Документация

| Документ | О чём |
|---|---|
| [DOCUMENTATION.md](DOCUMENTATION.md) | технический справочник v2: модули, эндпоинты, модель данных, фоновые циклы, настройки, запуск, деплой |
| [progress-backend/README.md](progress-backend/README.md) | как устроен бэкенд и почему именно так |
| [progress-frontend/README.md](progress-frontend/README.md) | экраны, компоненты, решения фронтенда |
| [progress-backend/RAILWAY.md](progress-backend/RAILWAY.md) | деплой на Railway |
| [progress-backend/DEPLOY.md](progress-backend/DEPLOY.md) | деплой на свой сервер через Docker и Caddy |
| [docs/v2/stages.md](docs/v2/stages.md) | отчёты этапов сборки v2: что сделано, что открыто, принятые умолчания |

---

## Проверки

```powershell
cd progress-backend; python -m pytest -o addopts= -q   # ключи и сервер базы не нужны
cd progress-frontend; npx tsc --noEmit; npm run build  # типы и сборка
```

Тесты миграций на Postgres (маркер `postgres`) запускаются, только если задан
`TEST_POSTGRES_URL` — адрес одноразовой базы Postgres 16. То же самое (без Postgres)
запускает GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) на каждый
push в `main` и на каждый Pull Request.

---

## Стек

Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 16 ·
TypeScript, Next.js 16, React 19, Tailwind v4 ·
Deepgram Nova-3 для речи, OpenAI Chat Completions (ответ потоком, JSON-схемы, эмбеддинги) ·
Web Push (VAPID) и Telegram Bot API для сообщений ИИ первым · Resend для писем.

---

## Состояние

Бета на небольшое число людей; многое сделано под этот масштаб сознательно (один воркер,
фоновые циклы в процессе API, аудио на диске). Что заполняет владелец перед бетой —
контакты линий помощи (`SAFETY_RESOURCES`), модель эмбеддингов, цены моделей, бот Telegram,
окончательный текст лендинга (сейчас черновик) — перечислено в разделе 16
[DOCUMENTATION.md](DOCUMENTATION.md).
