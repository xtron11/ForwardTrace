# ForwardTrace — фронтенд

Next.js 16 (App Router), React 19, TypeScript, Tailwind v4. PWA разговорного дневника:
Сегодня, История, Прогресс и Профиль. Экраны — клиентские компоненты, данные — из API
бэкенда (`progress-backend`).

```bash
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL должен указывать на бэкенд
npm install
npm run dev
```

Открывается на `http://localhost:3000`. Бэкенд запускается отдельно — см.
`DOCUMENTATION.md` в корне, раздел 13.

---

## Переменные окружения

| Переменная | Зачем |
|---|---|
| `NEXT_PUBLIC_API_URL` | адрес бэкенда, по умолчанию `http://localhost:8000` |
| `NEXT_PUBLIC_SITE_URL` | канонический адрес для метаданных, `robots.txt` и `sitemap.xml` |

Обе видны в браузере — секретов здесь быть не должно.

---

## Проверки

```bash
npx tsc --noEmit   # типы
npm run build      # сборка
```

То же запускает CI (`.github/workflows/ci.yml`). Линтера и тестов на фронтенде нет;
путь по экранам проверяется руками по чек-листу в `docs/v2/stages.md` (этап 5).

---

## Экраны

| Маршрут | Задача |
|---|---|
| `/` | лендинг: статический HTML из `public/landing/` (через `rewrites` в `next.config.mjs`) |
| `/register`, `/login` | аккаунт; пояс и язык браузера уходят в профиль |
| `/verify`, `/restore` | ссылки из писем: подтверждение почты, восстановление аккаунта |
| `/today` | лента недели (зелёные дни — с разговором, свайп листает недели) и разговор дня; первый разговор — онбординг. `?o=<id>` — пришли из сообщения ИИ |
| `/history`, `/history/[date]` | все дни с разговорами и поиск; день целиком |
| `/progress`, `/progress/monthly/[month]` | цель и финиш, карточки «было → стало», нити, месячная сводка |
| `/profile` | язык, тема, канал и час сообщений ИИ (push / Telegram / не писать), что ИИ помнит, выгрузка, удаление аккаунта |

Внизу три вкладки (Сегодня, История, Прогресс), профиль — за шестерёнкой в шапке
(`AppShell`). `AppShell` в `app/(app)/layout.tsx` проверяет вход и загружает профиль.

---

## Как устроено

**Поток ответа.** `lib/api.ts::streamPost` читает SSE через `fetch` (Bearer, одно обновление
токена по 401, как и обычный `request`). События: `user_message`, `delta`, `quote`, `done`,
`error`. Ошибки до потока приходят JSON с `{"detail": {"code"}}` и превращаются в
`ApiError` с `code`; текст для человека — `errorText(code)` из `lib/i18n.ts`.

**Цитаты.** Сегмент `quote` показывается `QuoteChip`: дата, дословный текст, «это неточно»;
у голосового сообщения — проигрывание фрагмента (`PlayAudio` с `startMs`/`endMs`).
Сказанное человеком (`.said`) и вывод модели оформлены по-разному и никогда не
смешиваются.

**Языки.** `lib/i18n.ts` — словари ru и en; русский только на «вы» и без форм с родом.
`useT()` берёт язык из профиля (`users.locale`), до входа — из браузера, и обновляет
`<html lang>`. У лендинга свой словарь — `public/landing/shared/copy.js` (сейчас черновик
текста v2, финал согласует владелец).

**Дизайн.** Все цвета, отступы, радиусы и шрифты — токены в `app/tokens.css`; `globals.css`
отображает их в Tailwind (`@theme inline`). Тёмная тема по умолчанию, светлая — через
`data-theme`, выбор применяется до первой отрисовки. Мобильная вёрстка от 375 px, на
десктопе — колонка до ~640 px. Красного нет нигде, кроме настоящего технического сбоя.

**Запись голоса.** `lib/useRecorder.ts` выбирает контейнер (webm/opus, на iOS — mp4/aac);
бэкенд принимает оба.

**Токены.** `localStorage` (`progress.tokens`), access 30 минут, refresh 60 дней;
параллельные 401 переиспользуют один запрос обновления.

**Уведомления.** `public/sw.js` — только push, кеширования нет; клик ведёт на
`/today?o=<id>`. `lib/push.ts` — подписка, `lib/pwa.ts` — установка на домашний экран
(на iOS push работает только после «На экран „Домой“»).

---

## Структура

```
app/             маршруты; (app)/ — экраны после входа
components/      TodayScreen, ChatThread, MessageBubble, QuoteChip, QuickReplies, Composer,
                 WeekStrip, HistoryScreen, DayScreen, DayCard, ProgressScreen, PairCard,
                 FinishPath, ThreadChip, MonthlySummaryCard, PaywallSheet, ProfileScreen,
                 NotifyOffer, HourPicker, PlayAudio, AppShell, AuthFrame, ui
lib/
├── api.ts         клиент API, токены, SSE
├── types.ts       типы ответов бэкенда
├── i18n.ts, useT.ts  словари и язык
├── dates.ts       даты в поясе человека
├── useRecorder.ts запись звука
├── push.ts, pwa.ts  уведомления и установка
└── theme.ts       тёмная и светлая тема
public/landing/  статический лендинг, отдаётся по адресу /
```

`AGENTS.md` и `CLAUDE.md` в этой папке создаёт `next dev`: они просят ИИ-ассистентов
читать документацию Next 16 из `node_modules`. Править их руками не нужно.
