<!-- autopilot:start -->
# ForwardTrace

Разговорный дневник прогресса: человек говорит или пишет, ИИ отвечает и доказывает рост его же словами с датами. Бэкенд FastAPI + SQLAlchemy, фронтенд Next.js 16.

## Команды

Из корня репозитория. Локальный venv лежит в `venv/` (в чистом клоне: `py -3.11 -m venv .venv`, вместо `../venv` — `../.venv`).

| Команда | Что делает |
|---------|------------|
| `cd progress-backend && ../venv/Scripts/python.exe -m pip install -r requirements.txt` | Зависимости бэкенда |
| `cd progress-backend && ../venv/Scripts/python.exe -m pytest -o addopts= -q` | Все тесты (LLM, STT, push, Telegram замоканы; SQLite). Без `-o addopts=` итоговой строки нет |
| `cd progress-backend && ../venv/Scripts/python.exe -m pytest -o addopts= -q tests/test_v2_conversation.py` | Один файл |
| `cd progress-backend && TEST_POSTGRES_URL=postgresql+asyncpg://USER:PASS@HOST/DB ../venv/Scripts/python.exe -m pytest -o addopts= -q -m postgres` | Тесты миграций на одноразовом `postgres:16` |
| `cd progress-backend && DATABASE_URL=... APP_ENV=development ../venv/Scripts/python.exe -m alembic upgrade head` | Миграции (голова `0016_pair_source_length`) |
| `cd progress-backend && ../venv/Scripts/python.exe -m uvicorn app.main:app --port 8000` | API локально; нужен `.env` (см. «Окружение») |
| `cd progress-frontend && npm ci` | Зависимости фронтенда |
| `cd progress-frontend && npm run dev` | Фронтенд локально, порт 3000 |
| `cd progress-frontend && npx tsc --noEmit && npm run build` | Типы и сборка (то же гоняет CI, `.github/workflows/ci.yml`) |

SQLite без Postgres: `DATABASE_URL=sqlite+aiosqlite:///C:/abs/path.db AUTO_CREATE_TABLES=true`. Путь только Windows-абсолютный; POSIX-путь на Windows не открывается.

## Где что

- `progress-backend/app/services/` — вся логика; `routers/` тонкие. Поток данных, границы, соглашения — `docs/architecture.md`.
- `progress-backend/app/config.py` — `Settings` и все числа логики; значения по умолчанию и пояснения — `progress-backend/.env.example`.
- `progress-backend/app/services/conversation.py` — ответ и SSE; `prompts.py` — все промпты; `texts.py` — строки сервера ru/en.
- `progress-backend/tests/conftest.py` — `fresh_db`, `client`, `register`, `parse_sse`, фейки провайдеров; тесты v2 — `tests/test_v2_*.py`.
- `progress-backend/alembic/versions/` — миграции; `scripts/` — `make_account.py`, `eval_dialogs.py`, `diagnose_stt.py`; запуск — по докстрингу файла.
- `progress-frontend/lib/api.ts` (клиент и `streamPost`), `lib/i18n.ts` (строки ru/en), `components/*Screen.tsx` (экраны), `app/(app)/` (маршруты), `app/tokens.css` (токены дизайна).
- `docs/adr/` — почему так (10 решений); `CONTEXT.md` — словарь (разговор, факт, нить, пара); `DOCUMENTATION.md` и `docs/v2/stages.md` — справочник и отчёты по этапам; `progress-backend/DEPLOY.md`, `RAILWAY.md` — выкладка.

## Подводные камни

- Провайдеры в тестах подменяются по атрибуту модуля в `tests/conftest.py::fresh_db`. Модуль, импортирующий `complete_json`, `stream_chat`, `embed`, `transcribe` по имени, надо добавить туда, иначе тест уйдёт в настоящий API.
- `tests/test_app.py` держит собственные `fresh_db` и `client`; остальные тесты берут из `conftest.py`.
- Поток SSE открывает свою сессию БД (`SessionLocal` в `conversation.py`) и живёт в фоновой задаче; сессия запроса к этому моменту закрыта.
- Занятость разговора (`_busy`), rate-limit и фоновые циклы (outreach, память, закрытие дня, месячная сводка, стирание аккаунтов) живут в памяти процесса `uvicorn`, воркер строго один.
- `_check_schema` в `app/main.py` при старте валит приложение, если в БД нет таблицы или колонки из моделей: сначала `alembic upgrade head` (или `AUTO_CREATE_TABLES=true` для SQLite).
- `JWT_SECRET` по умолчанию, заглушка или короче 32 символов вне `APP_ENV=test` валит создание `Settings`; вместе с приложением падают alembic и скрипты.
- Цитата попадает к человеку только из БД через `{{quote:<fact_id>}}`; факт без `verify.quote_supported` не сохраняется (ADR 0001).
- Русские тексты только на «вы», без форм с родом; любая строка для человека — сразу ru и en.
- Числа логики — только `config.py` и `.env.example`, не литералы в коде.
- `progress-frontend/AGENTS.md`: Next.js 16 отличается от привычного, перед кодом читать `progress-frontend/node_modules/next/dist/docs/`.
- `progress-frontend/public/sw.js` не меняется; ссылки из push и Telegram — `/today?o=<outreach_id>`.
- Новых зависимостей (pip, npm) не добавлять; хранение токенов (`localStorage` `progress.tokens`) и схема JWT не меняются (ADR 0010).
- Таблицы v1 удалены миграцией `0015_drop_v1` без переноса данных (ADR 0009).

## Окружение

Только имена. `progress-backend/.env` не открывать, образец — `progress-backend/.env.example`; фронтенд — `progress-frontend/.env.local.example`.

- `DATABASE_URL` — БД (Postgres `postgresql+asyncpg://`, SQLite `sqlite+aiosqlite:///`).
- `APP_ENV` — `production` | `development` | `test`; от него зависит проверка `JWT_SECRET`.
- `JWT_SECRET` — подпись токенов, от 32 символов; `AUTO_CREATE_TABLES` — создать таблицы из моделей вместо миграций.
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `CHAT_MODEL`, `SAFETY_MODEL`, `EMBEDDING_MODEL` — ответы, память, безопасность, эмбеддинги; `*_PRICE_*` и `STT_PRICE_PER_MIN` — учёт стоимости.
- `STT_PROVIDER` (`deepgram` | `local`), `DEEPGRAM_API_KEY` — распознавание речи; `AUDIO_DIR` — каталог записей.
- `CORS_ORIGINS`, `APP_URL` — адрес фронтенда (CORS и ссылки в письмах); `CLIENT_IP_HEADER` — заголовок реального IP за прокси.
- `RESEND_API_KEY`, `EMAIL_FROM`, `REQUIRE_VERIFIED_EMAIL` — почта; без ключа письма не уходят и проверка пропускается.
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT_EMAIL` — web push (`python -m app.vapid` генерирует; смена ломает подписки).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `TELEGRAM_WEBHOOK_SECRET` — бот; пусто — Telegram выключен (503).
- `REMINDERS_ENABLED`, `ADMIN_EMAILS` — цикл outreach и список админов; `SENTRY_DSN` — ошибки.
- `TEST_POSTGRES_URL` — только для маркера `postgres`; `NEXT_PUBLIC_API_URL` — адрес API для фронтенда.

Архитектура (поток данных, границы модулей, соглашения): `docs/architecture.md`.

## Как здесь работает Autopilot

Сборка ведётся навыком `/autopilot`. Требования, спецификация и таски — в `.autopilot/`.
Прогресс — `.autopilot/dashboard.html`. Требование из `manifest.md` может снять
только пользователь. Прерванную сборку продолжает «продолжи автопилот».

### Правка без автопилота

Мелкий баг или доводка после сборки — обычная сессия, без прогона.

Сначала прочитай:
1. `.autopilot/PROGRESS.md` — что не доделано, известные баги, о чём договорились с пользователем.
2. Что правили после последней сборки — первая строка таблицы в «История git».
3. Только если правка их касается: почему сделано так — `docs/adr/`; что значат слова — `CONTEXT.md`;
   что именно просили — `manifest.md` в папке сборки (указана в начале `PROGRESS.md`).

После правки:
- коммит — по правилам из «История git»;
- строка в «Правки без автопилота» в `PROGRESS.md`: дата — что — почему;
- починенный пункт из «Не доделано» или «Известные баги» — удали;
- договорились с пользователем о том, что следующая сборка не должна пересматривать, —
  строка в «Договорились», его словами.

### История git

Целиком не читай — бери срез под вопрос:

| Вопрос | Команда |
|---|---|
| что правили после последней сборки | `git log --oneline "$(git log -1 --format=%h --grep='^Autopilot: сборка сдана')"..HEAD -- . ':(exclude).autopilot'` |
| всё, что делали ради требования | `git log --oneline --grep="R02"` |
| история файла | `git log --oneline -10 -- <файл>` |
| когда появился или исчез код | `git log --oneline -S "<фрагмент>"` |
| почему строка такая | `git blame -L <с>,<по> <файл>`, затем `git show <sha>` |
| что внутри коммита | `git show --stat <sha>` |

Срез длиннее ~30 коммитов — отдай его субагенту и возьми выжимку в десять строк.

Коммит: заголовок — что (`fix: даты в одном формате`), тело — почему, трейлер
`--trailer "Requirements: R02"`, если правка касается требования из `manifest.md`.
Заголовок `Autopilot: сборка сдана` пишет только автопилот — по нему находят последнюю сборку.
<!-- autopilot:end -->
