window.STATE =
{
  "version": 2,
  "slug": "forwardtrace-v2",
  "dir": "2026-10-26-forwardtrace-v2--wip",
  "title": "ForwardTrace v2: разговорный дневник прогресса",
  "mode": "semi",
  "depth": "normal",
  "tier": "T3",
  "briefFile": "2026-10-26-brief.md",
  "memoryFile": "AGENTS.md",
  "memoryOwner": "autopilot",
  "skillDir": "C:/Users/xtron/.claude/skills/autopilot",
  "baseCommit": null,
  "startedAt": "2026-10-26T22:21:49+05:00",
  "updatedAt": "2026-10-26T22:47:48+05:00",
  "finishedAt": null,
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-10-26T22:21:49+05:00",
      "finishedAt": "2026-10-26T22:22:13+05:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-10-26T22:22:13+05:00",
      "finishedAt": "2026-10-26T22:24:39+05:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-10-26T22:24:39+05:00",
      "finishedAt": "2026-10-26T22:29:18+05:00"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-10-26T22:29:18+05:00",
      "finishedAt": "2026-10-26T22:44:03+05:00"
    },
    {
      "id": "plan",
      "status": "active",
      "startedAt": "2026-10-26T22:44:03+05:00"
    },
    {
      "id": "build",
      "status": "pending"
    },
    {
      "id": "review",
      "status": "pending"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 212,
    "done": 0,
    "inTicket": 211,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 1,
    "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Подготовка, модель данных v2 и импорт v1",
      "requirements": [
        "R015",
        "R017",
        "R018",
        "R020",
        "R021",
        "R024",
        "R041",
        "R042",
        "R043",
        "R044",
        "R045",
        "R046",
        "R047",
        "R048",
        "R049",
        "R050",
        "R053",
        "R054",
        "R055",
        "R056",
        "R057",
        "R058",
        "R059",
        "R184",
        "R185",
        "R186",
        "R187",
        "R188",
        "R189",
        "R204",
        "R205",
        "R206",
        "R208",
        "R209",
        "R211"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "progress-backend/app/config.py",
        "app/models.py",
        "app/schemas.py",
        "app/services/accounts.py",
        "app/services/errors.py",
        "app/services/events.py",
        "app/services/texts.py",
        "app/services/costs.py",
        "app/routers/auth.py",
        "alembic/versions/0014_v2_core.py",
        "scripts/import_v1.py",
        "tests/conftest.py",
        "tests/test_v2_foundation.py",
        "tests/test_app.py",
        "progress-backend/.env.example",
        "docs/v2/stages.md"
      ],
      "review": "да — фундамент",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "02",
      "title": "Разговор дня: бэкенд, поток ответа, цитаты",
      "requirements": [
        "R001",
        "R002",
        "R004",
        "R008",
        "R019",
        "R022",
        "R023",
        "R027",
        "R028",
        "R030",
        "R033",
        "R060",
        "R061",
        "R062",
        "R063",
        "R065",
        "R066",
        "R067",
        "R068",
        "R069",
        "R070",
        "R071",
        "R072",
        "R079",
        "R084",
        "R085",
        "R086",
        "R087",
        "R088",
        "R091",
        "R094",
        "R095",
        "R096",
        "R097",
        "R099",
        "R100",
        "R190",
        "R191",
        "R210"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "progress-backend/app/services/conversation.py",
        "app/services/audio.py",
        "app/services/limits.py",
        "app/services/safety.py",
        "app/services/llm.py",
        "app/services/stt.py",
        "app/services/prompts.py",
        "app/routers/conversations.py",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_v2_conversation.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "03",
      "title": "Память: факты, нити, пары «было → стало»",
      "requirements": [
        "R003",
        "R005",
        "R029",
        "R051",
        "R052",
        "R073",
        "R089",
        "R112",
        "R113",
        "R114",
        "R115",
        "R116",
        "R117",
        "R118",
        "R119",
        "R120",
        "R121",
        "R122",
        "R123",
        "R124",
        "R192",
        "R207"
      ],
      "blockedBy": [
        "02"
      ],
      "wave": 3,
      "zone": [
        "progress-backend/app/services/memory.py",
        "app/services/llm.py",
        "embed",
        "app/services/prompts.py",
        "app/services/conversation.py",
        "app/routers/conversations.py",
        "GET /api/memory",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_v2_memory.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "04",
      "title": "Первый разговор вместо онбординга",
      "requirements": [
        "R007",
        "R031",
        "R083",
        "R092",
        "R101",
        "R102",
        "R103",
        "R104",
        "R105",
        "R106",
        "R107",
        "R108",
        "R109",
        "R110",
        "R193",
        "G01"
      ],
      "blockedBy": [
        "03"
      ],
      "wave": 4,
      "zone": [
        "progress-backend/app/services/first_conversation.py",
        "app/services/conversation.py",
        "app/services/prompts.py",
        "app/services/texts.py",
        "app/routers/progress.py",
        "PATCH /api/goal",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_v2_first_conversation.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "05",
      "title": "Фронтенд: основа, токены, вход, навигация",
      "requirements": [
        "R009",
        "R013",
        "R016",
        "R040",
        "R154",
        "R155",
        "R156",
        "R157",
        "R158",
        "R159",
        "R160",
        "R161",
        "R163",
        "R164",
        "R172",
        "R208",
        "G01"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "progress-frontend/",
        "public/landing/",
        "public/sw.js"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "06",
      "title": "Фронтенд: Сегодня, История, Профиль",
      "requirements": [
        "R010",
        "R011",
        "R162",
        "R165",
        "R166",
        "R167",
        "R170",
        "R173",
        "R174",
        "R175",
        "R176",
        "R177",
        "R178",
        "R183",
        "R194"
      ],
      "blockedBy": [
        "04",
        "05"
      ],
      "wave": 5,
      "zone": [
        "progress-frontend/app/today",
        "app/history",
        "app/profile",
        "app/progress",
        "progress-frontend/components/",
        "progress-frontend/lib/",
        "progress-backend/tests/test_v2_path.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "07",
      "title": "ИИ пишет первым: push и Telegram",
      "requirements": [
        "R006",
        "R025",
        "R032",
        "R075",
        "R076",
        "R078",
        "R125",
        "R126",
        "R127",
        "R128",
        "R129",
        "R130",
        "R131",
        "R151",
        "R152",
        "R153",
        "R195"
      ],
      "blockedBy": [
        "06"
      ],
      "wave": 6,
      "zone": [
        "progress-backend/app/services/outreach.py",
        "app/services/telegram.py",
        "app/routers/telegram.py",
        "app/routers/me.py",
        "/api/outreach/{id}/opened",
        "app/services/prompts.py",
        "app/services/texts.py",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_v2_outreach.py",
        "progress-frontend/app/profile",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "08",
      "title": "Безопасность, «стою на месте», лимит и фейковая дверь, выгрузка",
      "requirements": [
        "R064",
        "R074",
        "R077",
        "R090",
        "R093",
        "R098",
        "R132",
        "R133",
        "R134",
        "R135",
        "R136",
        "R137",
        "R145",
        "R146",
        "R147",
        "R148",
        "R149",
        "R150",
        "R182",
        "R196",
        "R197"
      ],
      "blockedBy": [
        "07"
      ],
      "wave": 7,
      "zone": [
        "progress-backend/app/services/safety.py",
        "app/services/limits.py",
        "app/services/conversation.py",
        "app/services/prompts.py",
        "app/services/texts.py",
        "app/routers/me.py",
        "app/routers/conversations.py",
        "tests/conftest.py",
        "tests/test_v2_safety_limits.py",
        "tests/eval/dialogs.yaml",
        "scripts/eval_dialogs.py",
        "progress-frontend/components/PaywallSheet.tsx",
        "progress-frontend/app/today",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "09",
      "title": "Прогресс и месячная сводка",
      "requirements": [
        "R012",
        "R080",
        "R081",
        "R082",
        "R138",
        "R139",
        "R140",
        "R141",
        "R142",
        "R143",
        "R144",
        "R168",
        "R169",
        "R179",
        "R180",
        "R181",
        "R198"
      ],
      "blockedBy": [
        "08"
      ],
      "wave": 8,
      "zone": [
        "progress-backend/app/services/progress.py",
        "app/routers/progress.py",
        "app/services/prompts.py",
        "app/services/texts.py",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_v2_progress.py",
        "progress-frontend/app/progress",
        "progress-frontend/components/",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "10",
      "title": "Аналитика и админка v2",
      "requirements": [
        "R026",
        "R199",
        "R200"
      ],
      "blockedBy": [
        "09"
      ],
      "wave": 9,
      "zone": [
        "progress-backend/app/services/adminstats.py",
        "app/routers/admin.py",
        "app/routers/adminui.py",
        "app/templates/",
        "app/services/*",
        "app/routers/*",
        "progress-frontend/",
        "tests/test_v2_analytics.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "11",
      "title": "Очистка v1, лендинг, документация",
      "requirements": [
        "R014",
        "R034",
        "R035",
        "R036",
        "R037",
        "R038",
        "R039",
        "R171",
        "R201",
        "R202",
        "R203"
      ],
      "blockedBy": [
        "10"
      ],
      "wave": 10,
      "zone": [
        "progress-backend/",
        "alembic/versions/0015_drop_v1.py",
        "tests/test_app.py",
        "progress-frontend/public/landing/",
        "README.md",
        "DOCUMENTATION.md",
        "progress-backend/README.md",
        "progress-frontend/README.md",
        "docs/v2/stages.md"
      ],
      "review": "да — удаление данных",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    }
  ],
  "tests": null,
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "found": 13,
    "fixed": 13,
    "deferred": 0,
    "items": []
  },
  "concerns": [],
  "blind": null,
  "beats": [
    "2026-10-26T22:21:49+05:00",
    "2026-10-26T22:22:13+05:00",
    "2026-10-26T22:22:21+05:00",
    "2026-10-26T22:24:39+05:00",
    "2026-10-26T22:25:14+05:00",
    "2026-10-26T22:29:04+05:00",
    "2026-10-26T22:29:18+05:00",
    "2026-10-26T22:43:49+05:00",
    "2026-10-26T22:44:03+05:00",
    "2026-10-26T22:44:38+05:00",
    "2026-10-26T22:47:48+05:00"
  ],
  "rev": 13,
  "waiting": null,
  "waits": [
    {
      "kind": "briefing",
      "from": "2026-10-26T22:25:14+05:00",
      "to": "2026-10-26T22:29:04+05:00"
    }
  ],
  "log": [
    {
      "t": "2026-10-26T22:21:49+05:00",
      "k": "init"
    },
    {
      "t": "2026-10-26T22:22:13+05:00",
      "k": "stage",
      "id": "manifest",
      "act": "start"
    },
    {
      "t": "2026-10-26T22:24:39+05:00",
      "k": "stage",
      "id": "briefing",
      "act": "start"
    },
    {
      "t": "2026-10-26T22:25:14+05:00",
      "k": "ask",
      "kind": "briefing",
      "note": "три вопроса — ты/вы, удаление таблиц v1, недельная выжимка в Plus"
    },
    {
      "t": "2026-10-26T22:29:04+05:00",
      "k": "answered",
      "kind": "briefing"
    },
    {
      "t": "2026-10-26T22:29:18+05:00",
      "k": "gate",
      "g": "G1",
      "ok": false,
      "open": 212,
      "total": 212
    },
    {
      "t": "2026-10-26T22:29:18+05:00",
      "k": "stage",
      "id": "spec",
      "act": "start"
    },
    {
      "t": "2026-10-26T22:43:49+05:00",
      "k": "gate",
      "g": "G2",
      "ok": true,
      "found": 13,
      "fixed": 13,
      "deferred": 0
    },
    {
      "t": "2026-10-26T22:44:03+05:00",
      "k": "stage",
      "id": "plan",
      "act": "start"
    },
    {
      "t": "2026-10-26T22:44:38+05:00",
      "k": "tier",
      "v": "T3"
    },
    {
      "t": "2026-10-26T22:47:48+05:00",
      "k": "tickets",
      "n": 11
    },
    {
      "t": "2026-10-26T22:47:48+05:00",
      "k": "gate",
      "g": "G3",
      "ok": true,
      "problems": 0
    }
  ],
  "reqList": [
    {
      "id": "R001",
      "text": "«Каждый календарный день человека — отдельный разговор.»",
      "status": "in-ticket"
    },
    {
      "id": "R002",
      "text": "«Человек говорит или пишет, ИИ сразу отвечает и доказывает рост его же словами с датами.»",
      "status": "in-ticket"
    },
    {
      "id": "R003",
      "text": "«Из каждого разговора в фоне извлекаются факты, и у каждого есть дословная цитата, найденная в тексте.»",
      "status": "in-ticket"
    },
    {
      "id": "R004",
      "text": "«ИИ ссылается на прошлое только через такие факты. Цитаты в ответ подставляет код, а не модель.»",
      "status": "in-ticket"
    },
    {
      "id": "R005",
      "text": "«Трудность, которую назвал человек, отслеживается, пока он не скажет, что справился. Тогда ИИ показывает «было → стало».»",
      "status": "in-ticket"
    },
    {
      "id": "R006",
      "text": "«Раз в день в выбранное время ИИ начинает разговор вопросом по открытой нити, по цели или по вчерашнему разговору.»",
      "status": "in-ticket"
    },
    {
      "id": "R007",
      "text": "«Онбординг тоже происходит в разговоре»",
      "status": "in-ticket"
    },
    {
      "id": "R008",
      "text": "«Разговор может касаться любой темы жизни (усталость, учёба, сон), но память и доказательства собираются вокруг цели.»",
      "status": "in-ticket"
    },
    {
      "id": "R009",
      "text": "«Навигация — три вкладки и шестерёнка»",
      "status": "in-ticket"
    },
    {
      "id": "R010",
      "text": "«Сегодня — лента дней сверху (дни с разговорами подсвечены зелёным, свайп листает недели) и разговор дня под ней.»",
      "status": "in-ticket"
    },
    {
      "id": "R011",
      "text": "«История — все дни с разговорами и поиск; тап по зелёному дню на ленте открывает этот день здесь.»",
      "status": "in-ticket"
    },
    {
      "id": "R012",
      "text": "«Прогресс — цель и финиш, карточки «было → стало» по мере появления, нити, месячная сводка.»",
      "status": "in-ticket"
    },
    {
      "id": "R013",
      "text": "«Шестерёнка справа сверху — профиль и настройки.»",
      "status": "in-ticket"
    },
    {
      "id": "R014",
      "text": "«Чего в v2 нет: недельных отчётов, критериев прогресса (их заменяет один финиш), задач-намерений, шага проверки расшифровки, нескольких целей одновременно, процентов «пройдено к финишу».»",
      "status": "in-ticket"
    },
    {
      "id": "R015",
      "text": "«Бэкенд эволюционирует в том же репозитории: новый модуль разговоров рядом со старым кодом, затем удаление ненужного.»",
      "status": "in-ticket"
    },
    {
      "id": "R016",
      "text": "«Фронтенд пишется заново внутри progress-frontend/: старые экраны удаляются, несколько библиотек из lib/ переносятся.»",
      "status": "in-ticket"
    },
    {
      "id": "R017",
      "text": "«Работа идёт в новой ветке v2 от main.»",
      "status": "in-ticket"
    },
    {
      "id": "R018",
      "text": "«Стек остаётся прежним»",
      "status": "in-ticket"
    },
    {
      "id": "R019",
      "text": "«Фоновые задачи остаются в процессе API через BackgroundTasks и asyncio-циклы в lifespan, один воркер.»",
      "status": "in-ticket"
    },
    {
      "id": "R020",
      "text": "«Аутентификация … Регистрация, вход, подтверждение почты, JWT с token_version, защита от перебора» (оставить как есть)",
      "status": "in-ticket"
    },
    {
      "id": "R021",
      "text": "«Удаление и восстановление аккаунта … Добавить в список стирания новые таблицы»",
      "status": "in-ticket"
    },
    {
      "id": "R022",
      "text": "«Проверка цитат … Ядро v2: NFKC, без пунктуации и регистра, точное вхождение или SequenceMatcher ≥ 0.90, минимум 8 символов»",
      "status": "in-ticket"
    },
    {
      "id": "R023",
      "text": "«Вызов модели … JSON-ответы для памяти, безопасности, тем сообщений; учёт стоимости»",
      "status": "in-ticket"
    },
    {
      "id": "R024",
      "text": "«Время … Локальный день человека = разговор»",
      "status": "in-ticket"
    },
    {
      "id": "R025",
      "text": "«Push … Доставка сообщений ИИ первым»",
      "status": "in-ticket"
    },
    {
      "id": "R026",
      "text": "«Телеметрия и админка … Аналитика v2 пишется в events»",
      "status": "in-ticket"
    },
    {
      "id": "R027",
      "text": "«Сохранять слова с таймкодами из ответа Deepgram (words[]: word, start, end). Для смешанной речи использовать STT_MULTILINGUAL»",
      "status": "in-ticket"
    },
    {
      "id": "R028",
      "text": "«Аудио принадлежит сообщению: AUDIO_DIR/<user_id>/<message_id>.<ext>. Те же проверки MIME и размера»",
      "status": "in-ticket"
    },
    {
      "id": "R029",
      "text": "«Новая схема (achievement / struggle / learned, нити, выжимка дня), та же обязательная проверка цитат и счётчик отброшенных»",
      "status": "in-ticket"
    },
    {
      "id": "R030",
      "text": "«Рефлексия … Не вызывается. Фильтр похвалы и диагнозов (BANNED) переносится в пост-обработку ответа разговора»",
      "status": "in-ticket"
    },
    {
      "id": "R031",
      "text": "«Становится целью-якорем с финишем: одна активная цель, критерии не используются»",
      "status": "in-ticket"
    },
    {
      "id": "R032",
      "text": "«Становятся сообщениями ИИ первым (раздел «Логика»). Сохраняются правила локального часа и «не чаще раза в день»»",
      "status": "in-ticket"
    },
    {
      "id": "R033",
      "text": "«Добавить потоковую функцию stream_chat() для ответа в разговоре»",
      "status": "in-ticket"
    },
    {
      "id": "R034",
      "text": "«Недельные отчёты и старый дайджест … services/reports.py, aggregate.py, summary.py, monthly.py, routers/reports.py, таблица reports.» (удалить на этапе 10)",
      "status": "in-ticket"
    },
    {
      "id": "R035",
      "text": "«Критерии: таблица criteria, POST /api/goals/suggest-criteria, CRITERIA_ в prompts.py.» (удалить)",
      "status": "in-ticket"
    },
    {
      "id": "R036",
      "text": "«Задачи: services/tasks.py, routers/tasks.py, таблицы tasks, task_mentions, поле users.tasks_declined_on.» (удалить)",
      "status": "in-ticket"
    },
    {
      "id": "R037",
      "text": "«Шаг проверки расшифровки: статус awaiting_review, POST /api/entries/{id}/confirm.» (удалить)",
      "status": "in-ticket"
    },
    {
      "id": "R038",
      "text": "«Старые чек-ины: routers/entries.py и таблицы entries, activities — только после импорта их данных (раздел «Модель данных») и с подтверждением владельца.»",
      "status": "in-ticket"
    },
    {
      "id": "R039",
      "text": "«Квоты на записи: MAX_VOICE_ENTRIES_PER_DAY, MAX_TEXT_ENTRIES_PER_DAY. Их заменяет лимит разговоров.»",
      "status": "in-ticket"
    },
    {
      "id": "R040",
      "text": "«Все старые экраны фронтенда.» (удалить)",
      "status": "in-ticket"
    },
    {
      "id": "R041",
      "text": "«Новые таблицы и поля добавляются миграцией 0014_v2_core … Все PK — UUID, все FK на users.id — ON DELETE CASCADE … JSON-поля — тип JsonB из models.py»",
      "status": "in-ticket"
    },
    {
      "id": "R042",
      "text": "«users (существующая; новые и переименованные поля) skill … country … outreach_channel … telegram_chat_id … telegram_link_token … outreach_unanswered … plus_until … first_conversation_done»",
      "status": "in-ticket"
    },
    {
      "id": "R043",
      "text": "«goals … why_message_id … finish_line … finish_set_on … baseline_message_id»",
      "status": "in-ticket"
    },
    {
      "id": "R044",
      "text": "«conversations … local_date … unique (user_id, local_date) … kind … started_by … state … summary … safety_level … counts_for_limit … memory_extracted_at»",
      "status": "in-ticket"
    },
    {
      "id": "R045",
      "text": "«messages … role … source … content_raw … content … words … audio_path … quick_replies … used_fact_ids … intent … safety_level … rating … model_name, llm_ms, stt_ms, cost_usd»",
      "status": "in-ticket"
    },
    {
      "id": "R046",
      "text": "«facts … message_id … origin … local_date … type … text … quote … audio_start_ms, audio_end_ms … thread_id … embedding … flagged_at»",
      "status": "in-ticket"
    },
    {
      "id": "R047",
      "text": "«threads … title … status … opened_fact_id, closed_fact_id … opened_on, closed_on, last_mentioned_on»",
      "status": "in-ticket"
    },
    {
      "id": "R048",
      "text": "«pairs — карточки «было → стало» … then_fact_id, now_fact_id … theme … recalled … source … hidden_at … unique (then_fact_id, now_fact_id)»",
      "status": "in-ticket"
    },
    {
      "id": "R049",
      "text": "«monthly_summaries … month … unique (user_id, month) … status … stats … content … viewed_at»",
      "status": "in-ticket"
    },
    {
      "id": "R050",
      "text": "«outreach … topic … thread_id … channel … sent_at, delivered (bool), opened_at, replied_at»",
      "status": "in-ticket"
    },
    {
      "id": "R051",
      "text": "«Эмбеддинги фактов хранятся в facts.embedding как JSON, а косинусное сходство считается в Python по фактам одного пользователя.»",
      "status": "in-ticket"
    },
    {
      "id": "R052",
      "text": "«Если эмбеддинг не удалось получить, факт сохраняется без него, а поиск откатывается на последние по дате факты.»",
      "status": "in-ticket"
    },
    {
      "id": "R053",
      "text": "«Импорт данных v1 — скрипт scripts/import_v1.py, идемпотентный»",
      "status": "in-ticket"
    },
    {
      "id": "R054",
      "text": "«Для каждой записи entries со статусом done создать или найти разговор за local_date (kind=daily, started_by=user) и сообщение role=user с raw_transcript, аудио и source.»",
      "status": "in-ticket"
    },
    {
      "id": "R055",
      "text": "«wins → факты achievement, friction → struggle, цитаты activities.quote → achievement без дублей по цитате. intentions не переносить.»",
      "status": "in-ticket"
    },
    {
      "id": "R056",
      "text": "«Каждую цитату повторно прогнать через verify.py по тексту сообщения; не прошедшие — пропустить и посчитать.»",
      "status": "in-ticket"
    },
    {
      "id": "R057",
      "text": "«Цель с why_text оставить целью-якорем.»",
      "status": "in-ticket"
    },
    {
      "id": "R058",
      "text": "«В конце вывести сводку: сколько разговоров, сообщений, фактов создано и сколько цитат отброшено.»",
      "status": "in-ticket"
    },
    {
      "id": "R059",
      "text": "«Старые таблицы скрипт не меняет.»",
      "status": "in-ticket"
    },
    {
      "id": "R060",
      "text": "«Все новые эндпоинты требуют Bearer-токен, как в v1, и фильтруют данные по current_user.id.»",
      "status": "in-ticket"
    },
    {
      "id": "R061",
      "text": "«Ошибки новых эндпоинтов возвращаются с машинным кодом: {\"detail\": {\"code\": \"limit_reached\", \"message\": \"...\"}}. Фронтенд переводит ошибки по code, а не по тексту.»",
      "status": "in-ticket"
    },
    {
      "id": "R062",
      "text": "«GET /api/conversations/today … Если у человека ещё нет разговоров, создаёт первый разговор с первым вопросом ИИ … limit {used, free, plus}»",
      "status": "in-ticket"
    },
    {
      "id": "R063",
      "text": "«POST /api/conversations/today/messages … JSON {text} или multipart audio … До начала потока: 402 limit_reached, 403 email_not_verified, 413, 415, 400 empty_audio»",
      "status": "in-ticket"
    },
    {
      "id": "R064",
      "text": "«POST /api/conversations/today/plateau … «Кажется, я стою на месте» по кнопке … только ответ ассистента»",
      "status": "in-ticket"
    },
    {
      "id": "R065",
      "text": "«GET /api/conversations?before=&limit=30 … Лента: дата, выжимка, кто начал, нити дня»",
      "status": "in-ticket"
    },
    {
      "id": "R066",
      "text": "«GET /api/conversations/{local_date} … Разговор дня целиком»",
      "status": "in-ticket"
    },
    {
      "id": "R067",
      "text": "«DELETE /api/conversations/{local_date} … Удалить разговор: сообщения, аудиофайлы и факты из него; ссылки нитей на удалённые факты обнуляются»",
      "status": "in-ticket"
    },
    {
      "id": "R068",
      "text": "«GET /api/search?q= … Поиск по сообщениям человека»",
      "status": "in-ticket"
    },
    {
      "id": "R069",
      "text": "«GET /api/messages/{id}/audio … Аудио сообщения, только владельцу»",
      "status": "in-ticket"
    },
    {
      "id": "R070",
      "text": "«POST /api/messages/{id}/rating … helped … not_it … 204»",
      "status": "in-ticket"
    },
    {
      "id": "R071",
      "text": "«POST /api/facts/{id}/flag … «Это неточно»: факт больше не используется в ответах»",
      "status": "in-ticket"
    },
    {
      "id": "R072",
      "text": "«PATCH /api/threads/{id} … {status?: \"closed\" | \"deleted\", title?}»",
      "status": "in-ticket"
    },
    {
      "id": "R073",
      "text": "«GET /api/memory … Цель, открытые и закрытые нити, последние 50 фактов (Should)»",
      "status": "in-ticket"
    },
    {
      "id": "R074",
      "text": "«POST /api/paywall/click … Нажатие на фейковой двери: plus_until = сегодня + 30 дней»",
      "status": "in-ticket"
    },
    {
      "id": "R075",
      "text": "«POST /api/telegram/link … Ссылка привязки бота»",
      "status": "in-ticket"
    },
    {
      "id": "R076",
      "text": "«POST /api/telegram/webhook … Входящие от Telegram; проверка секретного заголовка»",
      "status": "in-ticket"
    },
    {
      "id": "R077",
      "text": "«GET /api/me/export … Выгрузка: разговоры, сообщения, факты, нити, цель»",
      "status": "in-ticket"
    },
    {
      "id": "R078",
      "text": "«PATCH /api/auth/me … Существующий эндпоинт + поля skill, country, outreach_channel»",
      "status": "in-ticket"
    },
    {
      "id": "R079",
      "text": "«GET /api/calendar?from=&to= … какие дни зелёные (counts_for_limit = true) … диапазон до 62 дней»",
      "status": "in-ticket"
    },
    {
      "id": "R080",
      "text": "«GET /api/progress … цель, мотивация, финиш, последние 3 факта level с датами, карточки «было → стало», открытые и закрытые нити, последняя месячная сводка»",
      "status": "in-ticket"
    },
    {
      "id": "R081",
      "text": "«GET /api/progress/monthly?month=YYYY-MM … Месячная сводка; при первом открытии ставит viewed_at»",
      "status": "in-ticket"
    },
    {
      "id": "R082",
      "text": "«POST /api/pairs/{id}/hide … Скрыть карточку «было → стало»»",
      "status": "in-ticket"
    },
    {
      "id": "R083",
      "text": "«PATCH /api/goal … Изменить цель, мотивацию или финиш из профиля: {title?, why_text?, finish_line?} (finish_line: null — «без финиша»)»",
      "status": "in-ticket"
    },
    {
      "id": "R084",
      "text": "«Ответ — Server-Sent Events. Клиент собирает сегменты сообщения ассистента в порядке прихода событий.» (user_message, delta, quote, done, error)",
      "status": "in-ticket"
    },
    {
      "id": "R085",
      "text": "«Для голосового сообщения сервер сначала синхронно распознаёт речь и отправляет user_message с расшифровкой, затем начинает ответ. Если распознавание вернуло меньше 10 символов, поток завершается событием error с кодом no_speech.»",
      "status": "in-ticket"
    },
    {
      "id": "R086",
      "text": "«Новый код домена разговоров кладётся в services/conversation.py … services/memory.py … services/outreach.py … services/safety.py и routers/conversations.py. Промпты — в services/prompts.py … на английском, с блоком _write_in для русского»",
      "status": "in-ticket"
    },
    {
      "id": "R087",
      "text": "«В лимит засчитывается день, где человек отправил хотя бы одно сообщение. Сообщение ИИ первым без ответа не засчитывается.»",
      "status": "in-ticket"
    },
    {
      "id": "R088",
      "text": "«В ответы попадают только проверенные факты без flagged_at.»",
      "status": "in-ticket"
    },
    {
      "id": "R089",
      "text": "«Пара «тогда → сейчас» — факт struggle и более поздний факт achievement той же нити или близкие по смыслу (косинус ≥ 0,8), разница не меньше 7 дней.»",
      "status": "in-ticket"
    },
    {
      "id": "R090",
      "text": "«Проверить лимит … При превышении — 402 до начала потока.»",
      "status": "in-ticket"
    },
    {
      "id": "R091",
      "text": "«Отметить counts_for_limit = true, сбросить users.outreach_unanswered = 0, проставить outreach.replied_at, если сегодня было сообщение ИИ первым.»",
      "status": "in-ticket"
    },
    {
      "id": "R092",
      "text": "«Если разговор kind=first и не завершён — передать в сценарий первого разговора (ниже) и выйти.»",
      "status": "in-ticket"
    },
    {
      "id": "R093",
      "text": "«safety_check(text) → уровень 0–3. При уровне 2 и выше — ответ по протоколу безопасности, шаги 6–8 пропускаются.»",
      "status": "in-ticket"
    },
    {
      "id": "R094",
      "text": "«Собрать контекст: системный промпт; навык и язык; цитата цели; до 5 открытых нитей с id; до 5 проверенных фактов, ближайших по смыслу к сообщению, с id и датами; выжимки 3 последних разговоров; сообщения текущего разговора.»",
      "status": "in-ticket"
    },
    {
      "id": "R095",
      "text": "«Модель пишет обычный текст с плейсхолдерами {{quote:<fact_id>}}, затем строку-разделитель <<<META>>> и JSON»",
      "status": "in-ticket"
    },
    {
      "id": "R096",
      "text": "«если fact_id был в контексте, отправить событие quote с цитатой и датой из базы, иначе молча выбросить … Ошибка парсинга META не ломает ответ: quick_replies = [], intent = normal.»",
      "status": "in-ticket"
    },
    {
      "id": "R097",
      "text": "«Сохранить сообщение ассистента: content_raw, content, quick_replies, used_fact_ids, intent, стоимость и время. Отправить done.»",
      "status": "in-ticket"
    },
    {
      "id": "R098",
      "text": "«Если intent = plateau, следующий ответ строится по сценарию «Кажется, я стою на месте».»",
      "status": "in-ticket"
    },
    {
      "id": "R099",
      "text": "«После ответа проверить правила (до 120 слов или до 250 … не больше одного ?; нет слов из BANNED) … нарушение пишется событием reply_rule_violation»",
      "status": "in-ticket"
    },
    {
      "id": "R100",
      "text": "«Черновик системного промпта … В prompts.py хранится на английском; ниже — смысл, который нужно сохранить.»",
      "status": "in-ticket"
    },
    {
      "id": "R101",
      "text": "«Первый разговор заменяет экраны онбординга: после регистрации человек сразу попадает на «Сегодня», где ИИ начинает разговор.»",
      "status": "in-ticket"
    },
    {
      "id": "R102",
      "text": "«Состояние хранится в conversations.state … Вопросы — строки из i18n, ответы ИИ отдаются тем же потоком: одно событие delta с полным текстом и done с быстрыми ответами.»",
      "status": "in-ticket"
    },
    {
      "id": "R103",
      "text": "«Создание … «Привет! Я помогу тебе замечать, как ты растёшь, — твоими же словами. Что ты сейчас развиваешь?» Быстрые ответы: «Программирование», «Геймдев», «Иностранный язык», «Спорт», «Музыка».»",
      "status": "in-ticket"
    },
    {
      "id": "R104",
      "text": "«skill. Ответ сохраняется в users.skill и goals.title (до 120 символов; длинный ответ complete_json сокращает до короткого названия).»",
      "status": "in-ticket"
    },
    {
      "id": "R105",
      "text": "«motivation. complete_json возвращает дословную цитату мотивации и 4 варианта финиша … Цитата проверяется verify.py … Если цитата не прошла проверку — «Запомнил. Когда ты скажешь, что цель достигнута?»»",
      "status": "in-ticket"
    },
    {
      "id": "R106",
      "text": "«finish. Текст варианта или свой ответ сохраняется в goals.finish_line и finish_set_on. «Без финиша» → finish_line = null, no_finish = true.»",
      "status": "in-ticket"
    },
    {
      "id": "R107",
      "text": "«baseline … до 3 пар. Все цитаты проверяются; по каждой паре создаются факты struggle и achievement и запись pairs с recalled = true … level_quote → факт level … Без пар или при just_started: «Ты в самом начале …»»",
      "status": "in-ticket"
    },
    {
      "id": "R108",
      "text": "«schedule. Ответ задаёт reminder_hour … Фронтенд запрашивает разрешение на уведомления, а при отказе или на iPhone без установленного PWA предлагает Telegram.»",
      "status": "in-ticket"
    },
    {
      "id": "R109",
      "text": "«Если ответ пустой или не по теме, ИИ переспрашивает один раз мягче (retries), затем переходит к следующему шагу.»",
      "status": "in-ticket"
    },
    {
      "id": "R110",
      "text": "«Цель, мотивацию и финиш потом можно изменить в профиле.»",
      "status": "in-ticket"
    },
    {
      "id": "R111",
      "text": "«После MVP: углублённый разговор о прошлом … Сейчас не делать.»",
      "status": "deferred",
      "why": "бриф: «Сейчас не делать»"
    },
    {
      "id": "R112",
      "text": "«Цикл в lifespan раз в 5 минут находит разговоры, где последнее сообщение старше 30 минут, а memory_extracted_at пусто или раньше последнего сообщения, и запускает extract_memory.»",
      "status": "in-ticket"
    },
    {
      "id": "R113",
      "text": "«Второй цикл закрывает день в 04:00 по времени человека и запускает извлечение для ещё не обработанных разговоров.»",
      "status": "in-ticket"
    },
    {
      "id": "R114",
      "text": "«На вход модели — сообщения человека за день с id, открытые нити с id. Ответ по JSON-схеме» (facts, threads open/mention/close, day_summary)",
      "status": "in-ticket"
    },
    {
      "id": "R115",
      "text": "«Каждую цитату проверить verify.py по тексту своего сообщения. Не прошла — факт отброшен, счётчик пишется в событие memory_dropped_facts. message_id не из этого разговора — факт отброшен.»",
      "status": "in-ticket"
    },
    {
      "id": "R116",
      "text": "«Для голосовых сообщений найти цитату в messages.words и записать audio_start_ms, audio_end_ms. Не нашлось точное выравнивание — оставить null.»",
      "status": "in-ticket"
    },
    {
      "id": "R117",
      "text": "«open: создать нить, только если ссылка на факт struggle прошла проверку. mention и close принимаются только для thread_id из переданных открытых нитей. close требует факт achievement или learned. Обновить last_mentioned_on.»",
      "status": "in-ticket"
    },
    {
      "id": "R118",
      "text": "«Получить эмбеддинги новых фактов одним запросом. Ошибка не ломает извлечение.»",
      "status": "in-ticket"
    },
    {
      "id": "R119",
      "text": "«Записать summary (до 200 символов) и memory_extracted_at.»",
      "status": "in-ticket"
    },
    {
      "id": "R120",
      "text": "«Тип level — факт, в котором человек говорит о своём уровне относительно финиша»",
      "status": "in-ticket"
    },
    {
      "id": "R121",
      "text": "«Закрытая нить → пара из факта открытия и факта закрытия, если между ними не меньше PAIR_MIN_DAYS (7) дней (source = thread_closed).»",
      "status": "in-ticket"
    },
    {
      "id": "R122",
      "text": "«Для каждого нового факта achievement с эмбеддингом — поиск самого близкого факта struggle … старше 7 дней с косинусом не ниже PAIR_MIN_SIMILARITY (0,8) … Не больше одной новой пары на факт.»",
      "status": "in-ticket"
    },
    {
      "id": "R123",
      "text": "«theme — короткая тема из названия нити или из complete_json по двум цитатам.»",
      "status": "in-ticket"
    },
    {
      "id": "R124",
      "text": "«Пары с фактами, у которых есть flagged_at, не показываются.»",
      "status": "in-ticket"
    },
    {
      "id": "R125",
      "text": "«Цикл раз в 15 минут выбирает пользователей с reminders_on, каналом не none, у которых сейчас локальный час reminder_hour и last_reminded_on не сегодня.»",
      "status": "in-ticket"
    },
    {
      "id": "R126",
      "text": "«Не отправлять, если человек уже писал сегодня, если сегодня был уровень безопасности 3 или если сработали правила паузы.»",
      "status": "in-ticket"
    },
    {
      "id": "R127",
      "text": "«Тема по приоритету: открытая нить с last_mentioned_on за последние 3 дня → цель-якорь, если человек молчит 2 дня и больше → вчерашний разговор → общий вопрос из i18n»",
      "status": "in-ticket"
    },
    {
      "id": "R128",
      "text": "«Текст: complete_json со схемой {\"text\", \"quick_replies\"}, до 25 слов, один вопрос, цитата плейсхолдером. Проверка длины в коде; при нарушении — шаблон из i18n по теме.»",
      "status": "in-ticket"
    },
    {
      "id": "R129",
      "text": "«Запись: создать разговор дня (started_by = ai), если его нет, и сообщение ассистента source = outreach; строку outreach; last_reminded_on = сегодня; outreach_unanswered += 1.»",
      "status": "in-ticket"
    },
    {
      "id": "R130",
      "text": "«Доставка: push с телом без плейсхолдеров (цитаты в «ёлочках») и url = /today, либо Telegram … Ошибки доставки обрабатываются как в v1.»",
      "status": "in-ticket"
    },
    {
      "id": "R131",
      "text": "«Пауза: при outreach_unanswered ≥ 3 — отправлять раз в 3 дня. При 14 днях без сообщений человека — одно сообщение с темой farewell … затем не отправлять до следующего сообщения человека.»",
      "status": "in-ticket"
    },
    {
      "id": "R132",
      "text": "«Проверяется каждое сообщение человека, включая первый разговор. При ошибке модели считать уровень 0 и писать событие safety_check_failed.»",
      "status": "in-ticket"
    },
    {
      "id": "R133",
      "text": "«1 — усталость, апатия … пометка «мягче, без давления» … Если уровень 1 был в 5 из последних 14 дней — один раз мягко советовать врача или психолога, не чаще раза в 14 дней (событие safety_suggest_help)»",
      "status": "in-ticket"
    },
    {
      "id": "R134",
      "text": "«2 — безнадёжность … Отдельный промпт SAFETY_SYSTEM без памяти и прогресса … conversations.safety_level, событие safety_flag»",
      "status": "in-ticket"
    },
    {
      "id": "R135",
      "text": "«3 — риск для жизни … Шаблон из i18n без вызова модели + контакты из SAFETY_RESOURCES для users.country … сообщения ИИ первым не отправляются до следующего сообщения человека»",
      "status": "in-ticket"
    },
    {
      "id": "R136",
      "text": "«Не придумывай номера телефонов и названия служб: оставь значения пустыми … Шаблон уровня 3 не обещает конфиденциальность и не говорит, кого и когда известят.»",
      "status": "in-ticket"
    },
    {
      "id": "R137",
      "text": "«Система отбирает цель-якорь, до 3 пар «тогда → сейчас» с наибольшей разницей во времени, закрытые нити и число разговоров … Если доказательств меньше двух, ИИ опирается на точку старта и говорит, через сколько дней появится что сравнить.»",
      "status": "in-ticket"
    },
    {
      "id": "R138",
      "text": "«Экран «Прогресс» (GET /api/progress) собирается из готовых данных, без вызова модели» (цель, мотивация, финиш или «Без финиша — расту», 3 факта level, карточки новые сверху с «по твоим воспоминаниям», нити, непросмотренная сводка сверху)",
      "status": "in-ticket"
    },
    {
      "id": "R139",
      "text": "«Месячная сводка — цикл раз в час: для каждого человека, у которого сейчас 1-е число и наступил CLOSE_DAY_HOUR по его времени … Идемпотентно: unique (user_id, month).»",
      "status": "in-ticket"
    },
    {
      "id": "R140",
      "text": "«Не собирать, если в прошлом месяце не было ни одного разговора с сообщением человека.»",
      "status": "in-ticket"
    },
    {
      "id": "R141",
      "text": "«Код считает stats: дни с разговорами, закрытые нити, новые пары за месяц, факты level за месяц.»",
      "status": "in-ticket"
    },
    {
      "id": "R142",
      "text": "«Если разговоров меньше MONTHLY_MIN_CONVERSATIONS (8) и новых пар меньше MONTHLY_MIN_PAIRS (2) — status = thin, без вызова модели.»",
      "status": "in-ticket"
    },
    {
      "id": "R143",
      "text": "«complete_json пишет только три поля: intro … open_struggle … next_step … Ошибка модели → status = failed, повтор при следующем запуске цикла.»",
      "status": "in-ticket"
    },
    {
      "id": "R144",
      "text": "«После сборки — push или Telegram: «Сводка за {месяц} готова» (outreach.topic = monthly), не считается сообщением ИИ первым за день.»",
      "status": "in-ticket"
    },
    {
      "id": "R145",
      "text": "«Первые 7 дней с регистрации — без ограничений.»",
      "status": "in-ticket"
    },
    {
      "id": "R146",
      "text": "«Дальше бесплатно FREE_CONVERSATIONS_PER_WEEK (3) разговоров за календарную неделю в часовом поясе человека.»",
      "status": "in-ticket"
    },
    {
      "id": "R147",
      "text": "«Первое сообщение в новом дне сверх лимита → 402 limit_reached. Сообщения в уже засчитанном сегодняшнем разговоре разрешены.»",
      "status": "in-ticket"
    },
    {
      "id": "R148",
      "text": "«Без лимита, если plus_until ≥ сегодня.»",
      "status": "in-ticket"
    },
    {
      "id": "R149",
      "text": "«Фронтенд на 402 показывает пейволл. Нажатие «Продолжить с Plus» … экран «Мы в бете — тебе месяц бесплатно». События paywall_viewed, paywall_clicked.»",
      "status": "in-ticket"
    },
    {
      "id": "R150",
      "text": "«Память, цитаты и «Кажется, я стою на месте» доступны всем; в Plus — только безлимит и недельная выжимка.»",
      "status": "in-ticket"
    },
    {
      "id": "R151",
      "text": "«Бот работает через вебхук с секретным заголовком. POST /api/telegram/link выдаёт одноразовую ссылку; /start <token> привязывает telegram_chat_id и ставит outreach_channel = telegram.»",
      "status": "in-ticket"
    },
    {
      "id": "R152",
      "text": "«Сообщения ИИ первым приходят в бот текстом с кнопкой «Ответить», которая открывает приложение.»",
      "status": "in-ticket"
    },
    {
      "id": "R153",
      "text": "«Желательно: текстовый или голосовой ответ боту обрабатывается как сообщение в сегодняшний разговор, ответ ИИ уходит одним сообщением без потока.»",
      "status": "in-ticket"
    },
    {
      "id": "R154",
      "text": "«все цвета, отступы, радиусы и шрифты — CSS-переменные в одном файле (app/tokens.css), тёмная и светлая темы»",
      "status": "in-ticket"
    },
    {
      "id": "R155",
      "text": "«сначала мобильная вёрстка (375 px), затем десктоп»",
      "status": "in-ticket"
    },
    {
      "id": "R156",
      "text": "«только Tailwind, без библиотек компонентов, если владелец не одобрит другое»",
      "status": "in-ticket"
    },
    {
      "id": "R157",
      "text": "«все строки интерфейса — через i18n, русский и английский.»",
      "status": "in-ticket"
    },
    {
      "id": "R158",
      "text": "«api.ts … Оставить клиент с Bearer и обновлением токена. Добавить streamPost() на fetch + ReadableStream для SSE»",
      "status": "in-ticket"
    },
    {
      "id": "R159",
      "text": "«useRecorder.ts … Перенести без изменений: выбор формата для iOS, определение тишины, выбор микрофона»",
      "status": "in-ticket"
    },
    {
      "id": "R160",
      "text": "«push.ts, pwa.ts … Перенести без изменений»",
      "status": "in-ticket"
    },
    {
      "id": "R161",
      "text": "«i18n.ts, theme.ts … Перенести механизм; строки написать заново»",
      "status": "in-ticket"
    },
    {
      "id": "R162",
      "text": "«PlayAudio … Перенести загрузку аудио blob'ом; добавить проигрывание фрагмента от start_ms до end_ms»",
      "status": "in-ticket"
    },
    {
      "id": "R163",
      "text": "«serverErrors.ts … Удалить: ошибки переводятся по detail.code»",
      "status": "in-ticket"
    },
    {
      "id": "R164",
      "text": "«/login, /register, /verify, /restore … Логика из v1, новая вёрстка; после входа — /today»",
      "status": "in-ticket"
    },
    {
      "id": "R165",
      "text": "«/today … Сверху WeekStrip и шестерёнка справа. Ниже — разговор дня … быстрые ответы, микрофон и поле ввода, цитаты с датами, «помогло / не то» под ответами ИИ, кнопка «Кажется, я стою на месте». После первого разговора — запрос уведомлени…",
      "status": "in-ticket"
    },
    {
      "id": "R166",
      "text": "«/history … Дни с разговорами: дата, выжимка, нити дня; поиск»",
      "status": "in-ticket"
    },
    {
      "id": "R167",
      "text": "«/history/[date] … Разговор дня целиком, проигрывание голосовых, удаление разговора с подтверждением»",
      "status": "in-ticket"
    },
    {
      "id": "R168",
      "text": "«/progress … Новая месячная сводка сверху; цель, мотивация и финиш; путь к финишу (факты level с датами); карточки «было → стало»; нити — открытые и закрытые, закрыть или удалить»",
      "status": "in-ticket"
    },
    {
      "id": "R169",
      "text": "«/progress/monthly/[month] … Сводка целиком»",
      "status": "in-ticket"
    },
    {
      "id": "R170",
      "text": "«/profile … Почта; цель, мотивация и финиш с редактированием; час и канал сообщений ИИ, привязка Telegram; язык, тема, установка PWA; выгрузка, удаление аккаунта, выход»",
      "status": "in-ticket"
    },
    {
      "id": "R171",
      "text": "«/ … Лендинг … Остаётся статическим; текст обновляется на этапе 10»",
      "status": "in-ticket"
    },
    {
      "id": "R172",
      "text": "«Навигация: после входа всегда /today … Нижняя панель: Сегодня, История, Прогресс. Шестерёнка в шапке открывает /profile.»",
      "status": "in-ticket"
    },
    {
      "id": "R173",
      "text": "«WeekStrip — неделя с днями и числами … сегодня выделен, будущие дни приглушены, дни с active = true подсвечены зелёным. Свайп листает недели с анимацией … Тап по зелёному дню → /history/[date]; по сегодняшнему → прокрутка к разговору; по…",
      "status": "in-ticket"
    },
    {
      "id": "R174",
      "text": "«ChatThread — список сообщений с автопрокруткой; загрузка через GET /api/conversations/today.»",
      "status": "in-ticket"
    },
    {
      "id": "R175",
      "text": "«MessageBubble — отрисовка сегментов content: текст и QuoteChip.»",
      "status": "in-ticket"
    },
    {
      "id": "R176",
      "text": "«QuoteChip — цитата в «ёлочках» и дата; тап открывает /history/[date]; если есть аудиофрагмент — кнопка проигрывания; меню — «Это неточно». Цитаты с recalled: true подписаны «по твоим воспоминаниям».»",
      "status": "in-ticket"
    },
    {
      "id": "R177",
      "text": "«QuickReplies — до 5 кнопок; нажатие отправляет текст как сообщение.»",
      "status": "in-ticket"
    },
    {
      "id": "R178",
      "text": "«Composer — кнопка записи и поле текста; во время ответа ИИ ввод заблокирован.»",
      "status": "in-ticket"
    },
    {
      "id": "R179",
      "text": "«PairCard — карточка «было → стало»: тема, две цитаты с датами, проигрывание, скрыть.»",
      "status": "in-ticket"
    },
    {
      "id": "R180",
      "text": "«FinishPath — финиш и последние факты level в виде короткой ленты с датами, без процентов и шкал.»",
      "status": "in-ticket"
    },
    {
      "id": "R181",
      "text": "«MonthlySummaryCard — превью сводки на «Прогрессе»; тап → /progress/monthly/[month].»",
      "status": "in-ticket"
    },
    {
      "id": "R182",
      "text": "«PaywallSheet — открывается по ошибке limit_reached.»",
      "status": "in-ticket"
    },
    {
      "id": "R183",
      "text": "«DayCard, ThreadChip — для истории и прогресса.»",
      "status": "in-ticket"
    },
    {
      "id": "R184",
      "text": "«существующие и новые тесты проходят (python -m pytest из progress-backend); у фронтенда проходят npm run build и проверка типов; LLM и STT в тестах замоканы … каждый новый эндпоинт имеет тест изоляции данных между пользователями.»",
      "status": "in-ticket"
    },
    {
      "id": "R185",
      "text": "«config.py: убрать дубли полей; приложение отказывается стартовать, если JWT_SECRET равен значению по умолчанию (кроме тестового окружения).»",
      "status": "in-ticket"
    },
    {
      "id": "R186",
      "text": "«Смена пароля проверяет ограничение 72 байта, как регистрация.»",
      "status": "in-ticket"
    },
    {
      "id": "R187",
      "text": "«.gitignore: правило .md заменить так, чтобы документация в корне и в docs/ попадала в git.»",
      "status": "in-ticket"
    },
    {
      "id": "R188",
      "text": "«.env.example: убрать дубли разделов и несуществующий generate_vapid_keys.py.»",
      "status": "in-ticket"
    },
    {
      "id": "R189",
      "text": "«миграция применяется на чистой базе и на базе с данными v1; импорт на тестовых данных создаёт разговоры и факты, повторный запуск ничего не дублирует; стирание аккаунта не оставляет строк и файлов.»",
      "status": "in-ticket"
    },
    {
      "id": "R190",
      "text": "«тесты проверяют: порядок событий SSE; неизвестный fact_id не попадает в ответ; сломанный META не ломает ответ; голос с пустой речью даёт no_speech; удаление разговора удаляет файлы; чужой разговор недоступен.»",
      "status": "in-ticket"
    },
    {
      "id": "R191",
      "text": "«До этапа 3 факты для контекста берутся по дате, без эмбеддингов.»",
      "status": "in-ticket"
    },
    {
      "id": "R192",
      "text": "«тесты проверяют: непроверенная цитата отброшена и посчитана; нить нельзя закрыть чужим или выдуманным thread_id; ошибка эмбеддингов не ломает извлечение; выравнивание даёт верные audio_start_ms и audio_end_ms на фикстуре; закрытая нить ст…",
      "status": "in-ticket"
    },
    {
      "id": "R193",
      "text": "«тесты покрывают все шаги; варианты финиша приходят быстрыми ответами; свой вариант финиша и «Без финиша» сохраняются верно; ветку «только начал»; повторный вопрос при пустом ответе; непрошедшую проверку цитаты мотивации; сравнение без пар…",
      "status": "in-ticket"
    },
    {
      "id": "R194",
      "text": "«в браузере шириной 375 px проходит путь: регистрация → первый разговор голосом и текстом с выбором финиша кнопкой → сравнение «тогда → сейчас» → выбор часа → разрешение уведомлений → сегодняшний день зелёный на ленте → свайп недель → тап…",
      "status": "in-ticket"
    },
    {
      "id": "R195",
      "text": "«тесты проверяют выбор темы, «не отправлять, если человек уже писал», паузы после 3 неотвеченных и после 14 дней тишины, подавление после уровня безопасности 3, сброс счётчика при ответе.»",
      "status": "in-ticket"
    },
    {
      "id": "R196",
      "text": "«тесты проверяют: на уровнях 2 и 3 не используются память и прогресс; на уровне 3 ответ — шаблон без вызова модели; лимит корректно считается на границе недели и в разных часовых поясах; plus_until снимает лимит; выгрузка содержит только д…",
      "status": "in-ticket"
    },
    {
      "id": "R197",
      "text": "«Набор эталонных диалогов: tests/eval/dialogs.yaml (заготовка на 50 диалогов, из них 10 сценариев дистресса; владелец дописывает содержание) и scripts/eval_dialogs.py … проверяет длину, один вопрос, отсутствие BANNED, только известные fact…",
      "status": "in-ticket"
    },
    {
      "id": "R198",
      "text": "«тесты проверяют: сводка собирается один раз за месяц в 1-е число по времени человека; при малом числе данных — thin без вызова модели; в тексте сводки нет цитат вне переданных фактов; скрытые карточки и факты с «это неточно» не показывают…",
      "status": "in-ticket"
    },
    {
      "id": "R199",
      "text": "«События: onboarding_completed, first_conversation_step, … monthly_summary_viewed. Каждое несёт номер дня с регистрации, язык и канал.»",
      "status": "in-ticket"
    },
    {
      "id": "R200",
      "text": "«Админка: D1 и D7 по когортам, доля ответивших на сообщения ИИ первым, доля «помогло» у ответов с цитатой и без, доля цитат с «это неточно», список разговоров с флагом безопасности со ссылкой на разговор, средняя стоимость разговора.»",
      "status": "in-ticket"
    },
    {
      "id": "R201",
      "text": "«Удалить модули из списка «Удалить» и миграцией удалить их таблицы. Таблицы entries и activities — только после подтверждения владельца, что импорт проверен.»",
      "status": "in-ticket"
    },
    {
      "id": "R202",
      "text": "«Обновить текст лендинга на русском и английском под разговорный формат: черновик подготовить, финальный текст согласовать с владельцем.»",
      "status": "in-ticket"
    },
    {
      "id": "R203",
      "text": "«Обновить README.md и DOCUMENTATION.md.»",
      "status": "in-ticket"
    },
    {
      "id": "R204",
      "text": "«Новые переменные добавляются в config.py и .env.example. Все числа из этого документа — стартовые значения, их не хардкодить.» (таблица «Конфигурация»)",
      "status": "in-ticket"
    },
    {
      "id": "R205",
      "text": "«Если в services/costs.py нет цен для CHAT_MODEL, SAFETY_MODEL или EMBEDDING_MODEL, добавь место под них и пометь в отчёте этапа, что цены нужно заполнить.»",
      "status": "in-ticket"
    },
    {
      "id": "R206",
      "text": "«Работай строго по этапам … В начале каждого этапа коротко напиши план изменений … В конце этапа — что сделано, какие тесты добавлены, что осталось открытым.»",
      "status": "in-ticket"
    },
    {
      "id": "R207",
      "text": "«Фоновые циклы идемпотентны и переживают рестарт»",
      "status": "in-ticket"
    },
    {
      "id": "R208",
      "text": "«Не меняй способ хранения токенов и схему аутентификации без согласия владельца.»",
      "status": "in-ticket"
    },
    {
      "id": "R209",
      "text": "«Не добавляй платные внешние сервисы. Новые зависимости — только если без них нельзя; Telegram и SSE реализуются на httpx и StreamingResponse без отдельных библиотек.»",
      "status": "in-ticket"
    },
    {
      "id": "R210",
      "text": "«Остановись и спроси владельца: перед удалением таблиц entries, activities или любых данных пользователей; если для выполнения этапа нужно изменить что-то из раздела «Оставить как есть»; если код v1 серьёзно расходится с DOCUMENTATION.md»",
      "status": "in-ticket"
    },
    {
      "id": "R211",
      "text": "«Пока владелец не решил иначе, используй значения по умолчанию и упоминай их в отчётах этапов.» (PWA основной; localStorage; OPENAI_MODEL; эмбеддинги не заданы; функциональный дизайн; почта как в v1; контакты пустые)",
      "status": "in-ticket"
    },
    {
      "id": "G01",
      "text": "«Всегда обращаться на вы»",
      "status": "in-ticket"
    }
  ],
  "gates": {
    "G1": {
      "ok": false,
      "at": "2026-10-26T22:29:18+05:00",
      "open": 212,
      "total": 212
    },
    "G2": {
      "ok": true,
      "at": "2026-10-26T22:43:49+05:00",
      "found": 13,
      "fixed": 13,
      "deferred": 0
    },
    "G3": {
      "ok": true,
      "at": "2026-10-26T22:47:48+05:00",
      "problems": 0
    }
  },
  "result": null
}
