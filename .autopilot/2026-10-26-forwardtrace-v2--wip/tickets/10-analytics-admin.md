# 10 — Аналитика и админка v2

**Требования:** R026, R199, R200
**Зависит от:** 09
**Зона:** `progress-backend/app/services/adminstats.py` · `app/routers/admin.py` · `app/routers/adminui.py` · `app/templates/` · места записи событий в `app/services/*` и `app/routers/*` · `progress-frontend/` (клиентские события) · `tests/test_v2_analytics.py` · `docs/v2/stages.md`
**Волна:** 9
**Ревью:** нет
**Модель:** обычная

## Что должно заработать

Этап 9 брифа. Все события из списка пишутся в `events` с номером дня с регистрации, языком и каналом — серверные через `log_event`, клиентские через `POST /api/events` (сервер дополняет поля). Админка показывает на данных v2: D1 и D7 по когортам, долю ответивших на сообщения ИИ первым, долю «помогло» у ответов с цитатой и без, долю цитат с «это неточно», список разговоров с флагом безопасности со ссылкой на разговор, среднюю стоимость разговора.

## Из брифа, дословно

> «События: `onboarding_completed`, `first_conversation_step`, `anchor_saved`, `start_comparison_shown`, `message_sent`, `ai_reply`, `reply_rated`, `quote_opened`, `quote_flagged`, `outreach_sent`, `outreach_opened`, `outreach_replied`, `thread_opened`, `thread_closed`, `plateau_triggered`, `safety_flag`, `paywall_viewed`, `paywall_clicked`, `feed_opened`, `search_used`, `reply_rule_violation`, finish_set, week_strip_day_opened, progress_opened, pair_shown, pair_hidden, monthly_summary_viewed. Каждое несёт номер дня с регистрации, язык и канал.»
> «Админка: D1 и D7 по когортам, доля ответивших на сообщения ИИ первым, доля «помогло» у ответов с цитатой и без, доля цитат с «это неточно», список разговоров с флагом безопасности со ссылкой на разговор, средняя стоимость разговора.»
> «Готово, когда события пишутся в `events` (тесты) и страницы админки показывают метрики на тестовых данных.»

## Разделы спецификации

`spec.md` §2 (аналитика, админка); `interfaces.md` — «События».

## Критерии приёмки

- [ ] Каждое событие списка пишется в нужном месте с `day_number`, `language`, `channel` (тест на каждое серверное; клиентские — через `/api/events` с дополнением полей)
- [ ] Фронтенд отправляет `quote_opened`, `feed_opened`, `week_strip_day_opened`, `progress_opened`, `pair_shown`, `paywall_viewed`
- [ ] `adminstats` и страницы админки на v2-данных: шесть метрик брифа; страница разговора с флагом безопасности открывается по ссылке (тест на тестовых данных)
- [ ] Админка больше не читает `entries`/`reports`/`tasks` (готовность к тикету 11)
- [ ] Раздел «Этап 9» в `docs/v2/stages.md`
