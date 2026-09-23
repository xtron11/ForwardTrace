-- Неделя чек-инов на русском под цель «прокачать английский с A2 до B1».
--
-- Запуск из progress-backend:
--   Get-Content scripts/seed_english_week.sql | docker compose exec -T db psql -U progress -d progress
--
-- Что проверяет этот набор данных:
--   * метрики складываются за неделю (слова и страницы)
--   * есть траектория: сначала со словарём, потом без него
--   * один день пропущен намеренно - отчёт должен показать 6 из 7, а не округлить
--   * категории на русском, одна на всё чтение (без раздвоения Reading/English)
--   * первый критерий получает явные доказательства, второй - частичные
--
-- Даты считаются в часовом поясе ПОЛЬЗОВАТЕЛЯ, не сервера.

DO $$
DECLARE
    v_user  uuid;
    v_tz    text;
    v_goal  uuid;
    v_entry uuid;
    v_today date;
BEGIN
    SELECT id, coalesce(timezone, 'UTC') INTO v_user, v_tz
      FROM users ORDER BY created_at DESC LIMIT 1;
    IF v_user IS NULL THEN
        RAISE EXCEPTION 'Нет пользователей. Сначала зарегистрируйся в приложении.';
    END IF;

    v_today := (now() AT TIME ZONE v_tz)::date;

    SELECT id INTO v_goal FROM goals
     WHERE user_id = v_user AND is_active ORDER BY created_at DESC LIMIT 1;
    IF v_goal IS NULL THEN
        RAISE EXCEPTION 'Нет активной цели. Сначала создай цель в приложении.';
    END IF;

    DELETE FROM reports WHERE user_id = v_user;
    DELETE FROM entries WHERE user_id = v_user;   -- activities удалятся каскадом

    UPDATE goals SET started_on = v_today - 7 WHERE id = v_goal;

    ---------------------------------------------------------------- день -6
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today - 6, 'voice',
            'Сегодня читал минут сорок, прочитал 8 страниц на уровне A2. Почти каждое второе предложение лез в переводчик, это выматывает. Выучил 12 новых слов.',
            'Сегодня читал минут сорок, прочитал 8 страниц на уровне A2. Почти каждое второе предложение лез в переводчик, это выматывает. Выучил 12 новых слов.',
            'ru', false, 'tired',
            '[]'::jsonb,
            jsonb_build_array(jsonb_build_object(
                'text', 'Постоянно приходилось лезть в переводчик',
                'quote', 'Почти каждое второе предложение лез в переводчик',
                'goal_id', v_goal::text)),
            'done', 0, now() - INTERVAL '6 days');

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today - 6, 'Чтение', 'чтение',
            40, true, '["чтение на уровне A2", "много обращений к переводчику"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 8, 'unit', 'стр.',
                                   'quote', 'прочитал 8 страниц на уровне A2'),
                jsonb_build_object('name', 'новые слова', 'value', 12, 'unit', 'слов',
                                   'quote', 'Выучил 12 новых слов')),
            'Сегодня читал минут сорок, прочитал 8 страниц на уровне A2',
            now() - INTERVAL '6 days');

    ---------------------------------------------------------------- день -5
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today - 5, 'voice',
            'Полчаса чтения, 6 страниц. Выучил 9 слов. Заметил, что слова из вчерашних уже узнаю в тексте.',
            'Полчаса чтения, 6 страниц. Выучил 9 слов. Заметил, что слова из вчерашних уже узнаю в тексте.',
            'ru', false, 'neutral',
            jsonb_build_array(jsonb_build_object(
                'text', 'Начал узнавать вчерашние слова в тексте',
                'quote', 'слова из вчерашних уже узнаю в тексте',
                'goal_id', v_goal::text)),
            '[]'::jsonb,
            'done', 0, now() - INTERVAL '5 days');

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today - 5, 'Чтение', 'чтение',
            30, true, '["узнавание ранее выученных слов"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 6, 'unit', 'стр.',
                                   'quote', 'Полчаса чтения, 6 страниц'),
                jsonb_build_object('name', 'новые слова', 'value', 9, 'unit', 'слов',
                                   'quote', 'Выучил 9 слов')),
            'Полчаса чтения, 6 страниц', now() - INTERVAL '5 days');

    ---------------------------------------------------------------- день -4
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today - 4, 'voice',
            'Час читал, осилил 11 страниц, впервые взял текст уровня B1. Тяжело, но общий смысл понял без словаря. Выучил 14 слов.',
            'Час читал, осилил 11 страниц, впервые взял текст уровня B1. Тяжело, но общий смысл понял без словаря. Выучил 14 слов.',
            'ru', false, 'motivated',
            jsonb_build_array(jsonb_build_object(
                'text', 'Впервые прочитал текст уровня B1 и понял смысл без словаря',
                'quote', 'впервые взял текст уровня B1. Тяжело, но общий смысл понял без словаря',
                'goal_id', v_goal::text)),
            '[]'::jsonb,
            'done', 0, now() - INTERVAL '4 days');

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today - 4, 'Чтение', 'чтение',
            60, true, '["первый текст уровня B1", "смысл понят без словаря"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 11, 'unit', 'стр.',
                                   'quote', 'Час читал, осилил 11 страниц'),
                jsonb_build_object('name', 'новые слова', 'value', 14, 'unit', 'слов',
                                   'quote', 'Выучил 14 слов')),
            'Час читал, осилил 11 страниц, впервые взял текст уровня B1',
            now() - INTERVAL '4 days');

    ---------------------------------------------------------------- день -3 пропущен намеренно

    ---------------------------------------------------------------- день -2
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today - 2, 'voice',
            'Сорок пять минут, 9 страниц на B1. Первый раз прочитал главу вообще без переводчика, только два слова посмотрел. Выучил 11 слов. Под конец начал уставать и перечитывать одно и то же.',
            'Сорок пять минут, 9 страниц на B1. Первый раз прочитал главу вообще без переводчика, только два слова посмотрел. Выучил 11 слов. Под конец начал уставать и перечитывать одно и то же.',
            'ru', false, 'positive',
            jsonb_build_array(jsonb_build_object(
                'text', 'Прочитал целую главу без переводчика',
                'quote', 'Первый раз прочитал главу вообще без переводчика',
                'goal_id', v_goal::text)),
            jsonb_build_array(jsonb_build_object(
                'text', 'К концу занятия внимание рассеивается',
                'quote', 'Под конец начал уставать и перечитывать одно и то же',
                'goal_id', v_goal::text)),
            'done', 0, now() - INTERVAL '2 days');

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today - 2, 'Чтение', 'чтение',
            45, true, '["глава прочитана без переводчика", "уровень B1"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 9, 'unit', 'стр.',
                                   'quote', 'Сорок пять минут, 9 страниц на B1'),
                jsonb_build_object('name', 'новые слова', 'value', 11, 'unit', 'слов',
                                   'quote', 'Выучил 11 слов')),
            'Сорок пять минут, 9 страниц на B1', now() - INTERVAL '2 days');

    ---------------------------------------------------------------- день -1
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today - 1, 'voice',
            'Полчаса, 7 страниц. Выучил 8 слов. Ещё посмотрел ролик на английском и понял примерно половину без субтитров.',
            'Полчаса, 7 страниц. Выучил 8 слов. Ещё посмотрел ролик на английском и понял примерно половину без субтитров.',
            'ru', false, 'positive',
            jsonb_build_array(jsonb_build_object(
                'text', 'Понял половину видео без субтитров',
                'quote', 'понял примерно половину без субтитров',
                'goal_id', v_goal::text)),
            '[]'::jsonb,
            'done', 0, now() - INTERVAL '1 day');

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today - 1, 'Чтение', 'чтение',
            30, true, '["чтение", "видео без субтитров"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 7, 'unit', 'стр.',
                                   'quote', 'Полчаса, 7 страниц'),
                jsonb_build_object('name', 'новые слова', 'value', 8, 'unit', 'слов',
                                   'quote', 'Выучил 8 слов')),
            'Полчаса, 7 страниц', now() - INTERVAL '1 day');

    ---------------------------------------------------------------- сегодня
    v_entry := gen_random_uuid();
    INSERT INTO entries (id, user_id, goal_id, local_date, source, raw_transcript,
                         stt_transcript, detected_language, transcript_edited, mood,
                         wins, friction, status, dropped_facts, created_at)
    VALUES (v_entry, v_user, NULL, v_today, 'voice',
            'Час чтения, 13 страниц на B1, переводчик открывал два раза за всё занятие. Выучил 16 слов. Читать стало заметно легче, чем в начале недели.',
            'Час чтения, 13 страниц на B1, переводчик открывал два раза за всё занятие. Выучил 16 слов. Читать стало заметно легче, чем в начале недели.',
            'ru', false, 'positive',
            jsonb_build_array(jsonb_build_object(
                'text', 'Читает уровень B1 почти без словаря',
                'quote', 'переводчик открывал два раза за всё занятие',
                'goal_id', v_goal::text)),
            '[]'::jsonb,
            'done', 0, now());

    INSERT INTO activities (id, entry_id, user_id, goal_id, local_date, category,
                            category_key, minutes, minutes_explicit, details, metrics,
                            quote, created_at)
    VALUES (gen_random_uuid(), v_entry, v_user, v_goal, v_today, 'Чтение', 'чтение',
            60, true, '["уровень B1", "почти без переводчика"]'::jsonb,
            jsonb_build_array(
                jsonb_build_object('name', 'страницы', 'value', 13, 'unit', 'стр.',
                                   'quote', 'Час чтения, 13 страниц на B1'),
                jsonb_build_object('name', 'новые слова', 'value', 16, 'unit', 'слов',
                                   'quote', 'Выучил 16 слов')),
            'Час чтения, 13 страниц на B1', now());

    RAISE NOTICE 'Загружено 6 чек-инов за 7 дней (локальная дата %) для цели %', v_today, v_goal;
END $$;

SELECT local_date, count(*) AS записей FROM entries GROUP BY local_date ORDER BY local_date;

SELECT m->>'name' AS метрика,
       sum((m->>'value')::numeric) AS всего,
       count(*) AS дней
  FROM activities a, jsonb_array_elements(a.metrics) m
 GROUP BY m->>'name';

SELECT id AS goal_id, title FROM goals WHERE is_active;
