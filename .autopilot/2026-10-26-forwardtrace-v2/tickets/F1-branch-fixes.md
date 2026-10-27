# F1 — Исправления по ревью ветки

**Требования:** R185, R200, R204, R101, R157, R154, R134, R135
**Зависит от:** —
**Зона:** `progress-backend/app/config.py` · `progress-backend/.env.example` · `app/services/adminstats.py` · `app/services/progress.py` · `app/services/conversation.py` · `app/services/first_conversation.py` · `app/services/outreach.py` · `app/services/memory.py` · `app/services/prompts.py` · `progress-backend/tests/` · `progress-frontend/app/` · `progress-frontend/lib/i18n.ts` · `progress-frontend/components/MonthlySummaryCard.tsx` · `docs/v2/stages.md`
**Волна:** 11
**Ревью:** да — ремонт ветки
**Модель:** сильная

## Что должно заработать

Замечания «исправить сейчас» из ревью всей ветки.

## Из брифа, дословно

> «приложение отказывается стартовать, если `JWT_SECRET` равен значению по умолчанию (кроме тестового окружения).»
> «Все числа из этого документа — стартовые значения, их не хардкодить.»
> «все цвета, отступы, радиусы и шрифты — CSS-переменные в одном файле (`app/tokens.css`)» · «все строки интерфейса — через i18n, русский и английский.»
> «2 — безнадёжность | Отдельный промпт `SAFETY_SYSTEM` без памяти и прогресса»

## Критерии приёмки

- [ ] Вне `APP_ENV=test` Settings отвергает любой заглушечный `JWT_SECRET`, который есть в коде или в `.env.example` (в т.ч. `replace-me`), а также пустой и короче 32 символов; тест покрывает значение из `.env.example` (`app/config.py:12,334`, `.env.example:11`)
- [ ] `adminstats.outreach_reply_share` исключает строки `topic="monthly"` из отправленных/отвеченных/открытых; тест с одной доставленной monthly-строкой не меняет долю (`adminstats.py:84-93`)
- [ ] Числа логики — поля `config.py` + строки `.env.example`, код читает их из `settings`: `progress.py` `LEVEL_FACTS_SHOWN`, `MONTHLY_MAX_PAIRS`; `conversation.py` `PLATEAU_MAX_PAIRS`; `first_conversation.py` `DEFAULT_HOUR`, `EVENING_HOUR`, `TITLE_MAX`, `OPTION_MAX`, число вариантов финиша (`[:4]`); лимит слов в `SAFETY_SYSTEM` (`prompts.py`, «At most 80 words») подставляется из настройки
- [ ] Одновременное создание разговора дня (`conversation.py:147-155`) возвращает существующий день с 200, без 500: вставка в savepoint (`db.begin_nested()`) или повторная загрузка `user` после отката; то же в `outreach.py:359-366`; тест на гонку/повтор
- [ ] Незавершённый первый разговор, перенесённый на новый день (`conversation.py:139-141`), получает сообщение ассистента с вопросом текущего шага и его быстрыми ответами (в т.ч. вариантами финиша); тест
- [ ] (сверх списка ревью, по решению оркестратора) Извлечение памяти пропускает сообщения человека с `safety_level ≥ 2` (`memory.py:277-285`); тест
- [ ] Заголовки вкладок берутся из словаря ru+en, а не литералами: `app/(app)/{today,history,history/[date],profile,progress}/page.tsx`, `app/login/layout.tsx`, `app/register/layout.tsx`, `app/restore/layout.tsx`, `app/verify/layout.tsx`
- [ ] 409 при регистрации показывает строку i18n ru+en, а не английский текст сервера (`app/register/page.tsx:59-62`, `lib/i18n.ts describeError`)
- [ ] Цвета, шрифты, отступы, размеры — только из переменных `tokens.css`: `app/layout.tsx:84` themeColor (с учётом светлой темы — по `prefers-color-scheme` в metadata/viewport), `app/globals.css:42-44` стеки шрифтов, `globals.css:114` `.field padding`, `MonthlySummaryCard.tsx:66` `text-[2rem]`
- [ ] Все тесты проходят; `npx tsc --noEmit && npm run build` проходят; строки в `docs/v2/stages.md` («Исправления после ревью»)
