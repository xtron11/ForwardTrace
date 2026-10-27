window.STATE =
{
  "version": 2,
  "slug": "forwardtrace-v2",
  "dir": "2026-10-26-forwardtrace-v2",
  "title": "ForwardTrace v2: разговорный дневник прогресса",
  "mode": "semi",
  "depth": "normal",
  "tier": "T2",
  "briefFile": "2026-10-27-brief.md",
  "memoryFile": "AGENTS.md",
  "memoryOwner": "autopilot",
  "skillDir": "C:/Users/xtron/.claude/skills/autopilot",
  "baseCommit": "e21f607",
  "startedAt": "2026-10-26T22:21:49+05:00",
  "updatedAt": "2026-10-27T22:39:55+05:00",
  "finishedAt": "2026-10-27T22:39:55+05:00",
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
      "startedAt": "2026-10-27T17:57:32+05:00",
      "finishedAt": "2026-10-27T17:59:54+05:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-10-27T17:59:54+05:00",
      "finishedAt": "2026-10-27T18:07:05+05:00"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-10-27T18:07:05+05:00",
      "finishedAt": "2026-10-27T18:19:45+05:00"
    },
    {
      "id": "plan",
      "status": "done",
      "startedAt": "2026-10-27T18:19:45+05:00",
      "finishedAt": "2026-10-27T18:22:38+05:00"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-10-27T18:22:38+05:00",
      "finishedAt": "2026-10-27T22:26:38+05:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-10-27T22:26:38+05:00",
      "finishedAt": "2026-10-27T22:30:59+05:00"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-10-27T22:30:59+05:00",
      "finishedAt": "2026-10-27T22:39:55+05:00"
    }
  ],
  "requirements": {
    "total": 288,
    "done": 283,
    "inTicket": 0,
    "inSpec": 0,
    "placeholder": 3,
    "deferred": 1,
    "dropped": 1
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
      "status": "done",
      "startedAt": "2026-10-26T22:48:22+05:00",
      "finishedAt": "2026-10-26T23:11:31+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 160,
        "failed": 0
      },
      "commit": "32959c9"
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
      "status": "done",
      "startedAt": "2026-10-26T23:08:28+05:00",
      "finishedAt": "2026-10-26T23:29:00+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 207,
        "failed": 0
      },
      "commit": "47133f4"
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
      "status": "done",
      "startedAt": "2026-10-26T23:29:01+05:00",
      "finishedAt": "2026-10-26T23:41:22+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 233,
        "failed": 0
      },
      "commit": "2d22c21"
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
      "status": "done",
      "startedAt": "2026-10-26T23:41:23+05:00",
      "finishedAt": "2026-10-26T23:50:51+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 266,
        "failed": 0
      },
      "commit": "005bbcb"
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
      "status": "done",
      "startedAt": "2026-10-26T23:08:28+05:00",
      "finishedAt": "2026-10-26T23:16:53+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 0,
        "failed": 0
      },
      "commit": "56a2474"
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
      "status": "done",
      "startedAt": "2026-10-26T23:50:52+05:00",
      "finishedAt": "2026-10-27T00:07:34+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 267,
        "failed": 0
      },
      "commit": "122cebe"
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
      "status": "done",
      "startedAt": "2026-10-27T02:54:05+05:00",
      "finishedAt": "2026-10-27T03:12:44+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 314,
        "failed": 0
      },
      "commit": "c2d70f1"
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
      "status": "done",
      "startedAt": "2026-10-27T03:12:45+05:00",
      "finishedAt": "2026-10-27T03:33:01+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 350,
        "failed": 0
      },
      "commit": "37d2e31"
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
      "status": "done",
      "startedAt": "2026-10-27T03:33:02+05:00",
      "finishedAt": "2026-10-27T03:47:55+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 376,
        "failed": 0
      },
      "commit": "fbfebec"
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
      "status": "done",
      "startedAt": "2026-10-27T03:47:56+05:00",
      "finishedAt": "2026-10-27T03:59:47+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 390,
        "failed": 0
      },
      "commit": "d2f7a69"
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
      "status": "done",
      "startedAt": "2026-10-27T03:59:48+05:00",
      "finishedAt": "2026-10-27T04:29:20+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 334,
        "failed": 0
      },
      "commit": "93600e5"
    },
    {
      "id": "12",
      "title": "Баги первой сборки: тройная отправка, цитата в строке, «ты» в диалоге, «B1» не час",
      "requirements": [
        "R261",
        "R262",
        "R263",
        "R264",
        "R283i",
        "G02",
        "G03",
        "G04",
        "G05",
        "R212",
        "R213",
        "R282"
      ],
      "blockedBy": [],
      "wave": 12,
      "zone": [
        "progress-backend/app/services/conversation.py",
        "app/routers/conversations.py",
        "app/models.py",
        "app/schemas.py",
        "app/services/errors.py",
        "app/services/texts.py",
        "app/services/prompts.py",
        "_address_formally",
        "app/services/first_conversation.py",
        "parse_hour",
        "alembic/versions/0017_client_msg_id.py",
        "progress-backend/tests/",
        "progress-frontend/lib/api.ts",
        "lib/ids.ts",
        "lib/types.ts",
        "components/TodayScreen.tsx",
        "components/Composer.tsx",
        "components/QuickReplies.tsx",
        "components/QuoteChip.tsx",
        "components/MessageBubble.tsx",
        "lib/i18n.ts",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "сильная",
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "startedAt": "2026-10-27T18:22:38+05:00",
      "finishedAt": "2026-10-27T18:41:07+05:00",
      "tests": {
        "passed": 388,
        "failed": 0
      },
      "commit": "7b94113"
    },
    {
      "id": "13",
      "title": "Эталонные диалоги и сравнение версий",
      "requirements": [
        "R265",
        "R266",
        "R267",
        "R268",
        "R269",
        "R270",
        "R271",
        "R272",
        "R273",
        "R274",
        "R275",
        "A01",
        "R280"
      ],
      "blockedBy": [
        "12"
      ],
      "wave": 13,
      "zone": [
        "progress-backend/scripts/eval_dialogs.py",
        "progress-backend/tests/eval/",
        "app/services/conversation.py",
        "load_context_data",
        "build_context",
        "app/services/prompts.py",
        "ContextData",
        "compose_messages",
        "CHAT_PROMPTS",
        "\"v2.0\"",
        "progress-backend/tests/test_v2_safety_limits.py",
        "progress-backend/tests/test_v2_eval.py",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "startedAt": "2026-10-27T18:41:08+05:00",
      "finishedAt": "2026-10-27T18:53:43+05:00",
      "tests": {
        "passed": 399,
        "failed": 0
      },
      "commit": "b40dcc8"
    },
    {
      "id": "14",
      "title": "Новый промпт, примеры, контекст по трём уровням, модель, без жёстких правил",
      "requirements": [
        "R214",
        "R215",
        "R216",
        "R217",
        "R218",
        "R219",
        "R220",
        "R221",
        "R222",
        "R223",
        "R224",
        "R225",
        "R226",
        "R227",
        "R228",
        "R229",
        "R230",
        "R231",
        "R232",
        "R233",
        "R234",
        "R241",
        "R278",
        "R279",
        "R213"
      ],
      "blockedBy": [
        "13"
      ],
      "wave": 14,
      "zone": [
        "progress-backend/app/services/prompts.py",
        "app/services/prompt_examples.py",
        "app/services/conversation.py",
        "app/services/outreach.py",
        "BANNED",
        "_breaks_rules",
        "app/config.py",
        "progress-backend/.env.example",
        "scripts/eval_dialogs.py",
        "mentions_goal",
        "progress-backend/tests/",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "сильная",
      "status": "done",
      "retries": 0,
      "repairs": 1,
      "startedAt": "2026-10-27T18:54:21+05:00",
      "repairFindings": [
        "метка «Ты:» → «Человек:»/«Person:»; mentions_goal по основам"
      ],
      "finishedAt": "2026-10-27T19:38:28+05:00",
      "tests": {
        "passed": 432,
        "failed": 0
      },
      "commit": "dbae026"
    },
    {
      "id": "15",
      "title": "Память о жизни: события, решения, темы, follow_up, «Что я помню»",
      "requirements": [
        "R235",
        "R236",
        "R237",
        "R238",
        "R239",
        "R240",
        "R242",
        "R243",
        "R244",
        "R245",
        "R246",
        "R247",
        "R248",
        "R249",
        "R279",
        "R281"
      ],
      "blockedBy": [
        "14"
      ],
      "wave": 15,
      "zone": [
        "progress-backend/app/services/memory.py",
        "app/services/prompts.py",
        "MEMORY_SCHEMA",
        "MEMORY_SYSTEM",
        "app/models.py",
        "app/schemas.py",
        "app/routers/conversations.py",
        "/memory",
        "DELETE /facts/{id}",
        "PATCH /threads",
        "alembic/versions/0018_memory_kinds.py",
        "progress-backend/tests/test_v2_memory.py",
        "tests/test_v2_foundation.py",
        "progress-frontend/components/ProfileScreen.tsx",
        "components/MemorySection.tsx",
        "lib/api.ts",
        "lib/types.ts",
        "lib/i18n.ts",
        "docs/v2/stages.md"
      ],
      "review": "да — удаление и миграция данных пользователей",
      "model": "сильная",
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "startedAt": "2026-10-27T21:49:19+05:00",
      "finishedAt": "2026-10-27T22:09:36+05:00",
      "tests": {
        "passed": 447,
        "failed": 0
      },
      "commit": "c39c2fd"
    },
    {
      "id": "16",
      "title": "ИИ пишет первым как приглашение, финиш из слов человека, документация",
      "requirements": [
        "R250",
        "R251",
        "R252",
        "R253",
        "R254",
        "R255",
        "R256",
        "R257",
        "R258",
        "R259",
        "R260",
        "R276",
        "R212",
        "G02"
      ],
      "blockedBy": [
        "15"
      ],
      "wave": 16,
      "zone": [
        "progress-backend/app/services/outreach.py",
        "app/services/first_conversation.py",
        "app/services/prompts.py",
        "OUTREACH_*",
        "FIRST_SKILL_*",
        "FIRST_MOTIVATION_*",
        "app/services/texts.py",
        "outreach.*",
        "app/config.py",
        "progress-backend/.env.example",
        "progress-backend/tests/test_v2_outreach.py",
        "tests/test_v2_first_conversation.py",
        "DOCUMENTATION.md",
        "docs/adr/0011-*.md",
        "docs/adr/0007-obrashenie-na-vy.md",
        "CONTEXT.md",
        "docs/v2/stages.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "startedAt": "2026-10-27T22:07:37+05:00",
      "finishedAt": "2026-10-27T22:26:36+05:00",
      "tests": {
        "passed": 464,
        "failed": 0
      },
      "commit": "34c7286"
    },
    {
      "id": "F1",
      "title": "Исправления по ревью ветки",
      "requirements": [
        "R185",
        "R200",
        "R204",
        "R101",
        "R157",
        "R154",
        "R134",
        "R135"
      ],
      "blockedBy": [],
      "wave": 11,
      "zone": [
        "progress-backend/app/config.py",
        "progress-backend/.env.example",
        "app/services/adminstats.py",
        "app/services/progress.py",
        "app/services/conversation.py",
        "app/services/first_conversation.py",
        "app/services/outreach.py",
        "app/services/memory.py",
        "app/services/prompts.py",
        "progress-backend/tests/",
        "progress-frontend/app/",
        "progress-frontend/lib/i18n.ts",
        "progress-frontend/components/MonthlySummaryCard.tsx",
        "docs/v2/stages.md"
      ],
      "review": "да — ремонт ветки",
      "model": "сильная",
      "status": "done",
      "startedAt": "2026-10-27T04:36:30+05:00",
      "finishedAt": "2026-10-27T04:54:05+05:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 352,
        "failed": 0
      },
      "commit": "d47bf08"
    }
  ],
  "tests": {
    "passed": 464,
    "failed": 0
  },
  "debt": {
    "placeholders": [
      "Цены CHAT_MODEL/SAFETY_MODEL/EMBEDDING_MODEL = 0 — заполнит владелец",
      "SAFETY_RESOURCES = {} — контакты линий помощи заполнит владелец",
      "tests/eval/dialogs.yaml — 50 диалогов, 8 написаны примерами, 42 дописывает владелец"
    ],
    "assumptions": [],
    "emptyEnv": [
      "EMBEDDING_MODEL",
      "TELEGRAM_BOT_TOKEN",
      "TELEGRAM_BOT_USERNAME",
      "TELEGRAM_WEBHOOK_SECRET",
      "SAFETY_RESOURCES"
    ]
  },
  "additions": [],
  "coverage": {
    "found": 5,
    "fixed": 5,
    "deferred": 0,
    "items": []
  },
  "concerns": [
    "config.py — JWT_SECRET по умолчанию валит создание Settings, значит и alembic/скрипты; локальному docker-compose нужен JWT_SECRET в .env",
    "import_v1 — импортированным ставит first_conversation_done=true, skill=название цели",
    "accounts.country_for_timezone — ручная страна, совпавшая со страной старой зоны, перезаписывается при смене зоны",
    "scripts/import_v1.py _import — факты импорта ссылаются на импортированное сообщение, а бриф говорит message_id null у импортированных; тест test_v2_foundation.py:584 это закрепляет",
    "app/models.py Thread.opened_fact_id/closed_fact_id — use_alter FK без имени; drop_all на Postgres не сможет их удалить; назвать как в миграции",
    "app/models.py Goal.why_message_id/baseline_message_id — имена FK в модели и миграции расходятся",
    "scripts/import_v1.py ACTIVITY_QUOTES — Fact.text = название категории, а не формулировка",
    "progress-frontend — 375 px без горизонтального скролла не проверены в браузере (только по построению)",
    "app/(app)/* — заготовки страниц с английскими metadata-заголовками",
    "routers/entries.py, goals.py — ошибки загрузки аудио v1 теперь {code,message} вместо строки",
    "services/conversation.py — BANNED скопирован; reflection.py держит свою копию до тикета 11",
    "services/memory.py — ошибка модели при извлечении: разговор повторяется каждые MEMORY_TICK_MINUTES без ограничения попыток",
    "services/memory.py — порядок вставки facts→threads проверен только на SQLite",
    "services/first_conversation.py — шаг finish без вызова модели: любой непустой ответ — финиш, «не по теме» не ловится (история 16)",
    "services/first_conversation.py — при ошибке модели ответ шага принимается как есть",
    "tests/test_v2_path.py — зелёный с первого запуска, мутационной проверки нет",
    "components/ProfileScreen.tsx — /api/telegram/link вызывается при каждом открытии профиля, создавая лишний токен (правит тикет 07)",
    "services/telegram.py — голосовой ответ боту не покрыт тестом; повторные апдейты Telegram не дедуплицируются по update_id",
    "services/outreach.py — не пишет тем, кто не завершил первый разговор",
    "services/conversation.py PLATEAU_MAX_PAIRS=3 — константа, а не настройка (правило «числа не хардкодить»)",
    "services/safety.py — кулдаун совета специалисту считается по UTC-времени события",
    "scripts/eval_dialogs.py — не прогонялся на настоящей модели (платные вызовы)",
    "services/progress.py LEVEL_FACTS_SHOWN/MONTHLY_MAX_PAIRS — константы, не настройки",
    "services/progress.py — сводка собирается только 1-го числа; если сервер лежал весь день, месяц пропускается",
    "services/progress.py — thin-сводка тоже шлёт «Сводка готова»; уведомление ведёт на /today, а не на сводку",
    "services/progress.py — «%» в тексте модели делает сводку failed",
    "tests/test_v2_analytics.py — тесты написаны после кода, без красной фазы",
    "services/adminstats.py — стоимость разговора не включает фоновые вызовы (память, пары, сводка, outreach)",
    "progress-frontend/lib/types.ts — остались Criterion и Goal.criteria",
    "services/mail.py — тексты писем переписаны под v2 на «вы» (вне списка брифа)",
    "public/landing/shared/copy.js:16 final.a11y — «его собственные даты»: форма с родом в тексте для скринридера",
    "conversation.py — гонка IntegrityError при повторе не пишет событие message_duplicate (user истёк после rollback)",
    "eval_dialogs.py — таблица оценок в отчёте названа не критериями брифа (попадание в контекст, естественность, работа с памятью, отсутствие шаблонности, полезность) — поправить в таске 16",
    "T15: outreach.py пишет старые темы thread/yesterday/general до T16",
    "T15: раздел «Что я помню» не проверен глазами в браузере",
    "T15: план в stages.md записан после кода",
    "T15 ревью: i18n.ts:612 (en :302) — подтверждение удаления факта обещает «больше не будет использоваться», но цитата остаётся в уже показанных ответах",
    "T15 ревью: i18n.ts:603 «Без финиша — расту» от первого лица в интерфейсе на «вы»",
    "T15 ревью: MemorySection.tsx FactItem busy={false} — нет признака занятости при удалении факта",
    "T16: outreach.farewell не переписан — test_v2_dialogue_tone требует «захочешь»; критерий таска «переписан»",
    "T16: DOCUMENTATION.md строка-примечание об удалённых REPLY_MAX_WORDS*",
    "T16: правки тестов вне зоны — test_v2_foundation/test_v2_dialogue_tone (регэксп рода игнорирует «прошёл день»)"
  ],
  "blind": {
    "checked": 23,
    "matched": 20,
    "mismatches": [
      "Сравнение «тогда → сейчас» одной фразой на живом прогоне не показано: на ответ «сейчас A2… год назад не мог связать двух слов» пара не создалась (pairs=0)",
      "Текст struggle-факта из живой памяти содержит интерпретацию, которой человек не говорил («хотя раньше уже не боялись начать говорить»); цитата верная",
      "Живой ответ «Похоже, ты решил…» — форма с родом при запрете в промпте (усиление правила владелец оставил себе)"
    ]
  },
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
    "2026-10-26T22:47:48+05:00",
    "2026-10-26T22:47:55+05:00",
    "2026-10-26T22:48:06+05:00",
    "2026-10-26T22:48:22+05:00",
    "2026-10-26T23:08:09+05:00",
    "2026-10-26T23:08:10+05:00",
    "2026-10-26T23:08:11+05:00",
    "2026-10-26T23:08:27+05:00",
    "2026-10-26T23:08:28+05:00",
    "2026-10-26T23:11:31+05:00",
    "2026-10-26T23:11:32+05:00",
    "2026-10-26T23:16:53+05:00",
    "2026-10-26T23:29:00+05:00",
    "2026-10-26T23:29:01+05:00",
    "2026-10-26T23:41:22+05:00",
    "2026-10-26T23:41:23+05:00",
    "2026-10-26T23:50:51+05:00",
    "2026-10-26T23:50:52+05:00",
    "2026-10-27T00:07:34+05:00",
    "2026-10-27T00:07:35+05:00",
    "2026-10-27T00:07:36+05:00",
    "2026-10-27T02:52:28+05:00",
    "2026-10-27T02:54:05+05:00",
    "2026-10-27T03:12:44+05:00",
    "2026-10-27T03:12:45+05:00",
    "2026-10-27T03:33:01+05:00",
    "2026-10-27T03:33:02+05:00",
    "2026-10-27T03:47:55+05:00",
    "2026-10-27T03:47:56+05:00",
    "2026-10-27T03:59:47+05:00",
    "2026-10-27T03:59:48+05:00",
    "2026-10-27T04:27:36+05:00",
    "2026-10-27T04:27:37+05:00",
    "2026-10-27T04:27:38+05:00",
    "2026-10-27T04:29:20+05:00",
    "2026-10-27T04:29:21+05:00",
    "2026-10-27T04:36:28+05:00",
    "2026-10-27T04:36:29+05:00",
    "2026-10-27T04:36:30+05:00",
    "2026-10-27T04:52:18+05:00",
    "2026-10-27T04:52:19+05:00",
    "2026-10-27T04:54:05+05:00",
    "2026-10-27T04:54:06+05:00",
    "2026-10-27T14:53:03+05:00",
    "2026-10-27T14:53:06+05:00",
    "2026-10-27T14:55:06+05:00",
    "2026-10-27T17:57:32+05:00",
    "2026-10-27T17:57:50+05:00",
    "2026-10-27T17:59:54+05:00",
    "2026-10-27T18:04:37+05:00",
    "2026-10-27T18:06:45+05:00",
    "2026-10-27T18:07:05+05:00",
    "2026-10-27T18:19:39+05:00",
    "2026-10-27T18:19:45+05:00",
    "2026-10-27T18:21:58+05:00",
    "2026-10-27T18:21:59+05:00",
    "2026-10-27T18:22:06+05:00",
    "2026-10-27T18:22:14+05:00",
    "2026-10-27T18:22:38+05:00",
    "2026-10-27T18:41:07+05:00",
    "2026-10-27T18:41:08+05:00",
    "2026-10-27T18:53:43+05:00",
    "2026-10-27T18:54:21+05:00",
    "2026-10-27T19:11:48+05:00",
    "2026-10-27T19:38:28+05:00",
    "2026-10-27T19:38:37+05:00",
    "2026-10-27T19:47:32+05:00",
    "2026-10-27T19:49:48+05:00",
    "2026-10-27T21:49:18+05:00",
    "2026-10-27T21:49:19+05:00",
    "2026-10-27T22:07:35+05:00",
    "2026-10-27T22:07:36+05:00",
    "2026-10-27T22:07:37+05:00",
    "2026-10-27T22:09:36+05:00",
    "2026-10-27T22:26:36+05:00",
    "2026-10-27T22:26:37+05:00",
    "2026-10-27T22:26:38+05:00",
    "2026-10-27T22:30:53+05:00",
    "2026-10-27T22:30:59+05:00",
    "2026-10-27T22:39:10+05:00",
    "2026-10-27T22:39:55+05:00"
  ],
  "rev": 125,
  "waiting": null,
  "waits": [
    {
      "kind": "briefing",
      "from": "2026-10-26T22:25:14+05:00",
      "to": "2026-10-26T22:29:04+05:00"
    },
    {
      "kind": "briefing",
      "from": "2026-10-27T17:59:54+05:00",
      "to": "2026-10-27T18:06:45+05:00"
    },
    {
      "kind": "action",
      "from": "2026-10-27T19:38:37+05:00",
      "to": "2026-10-27T19:47:32+05:00"
    },
    {
      "kind": "action",
      "from": "2026-10-27T19:49:48+05:00",
      "to": "2026-10-27T21:49:18+05:00"
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
    },
    {
      "t": "2026-10-26T22:48:06+05:00",
      "k": "stage",
      "id": "build",
      "act": "start"
    },
    {
      "t": "2026-10-26T22:48:22+05:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-26T23:08:09+05:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "done",
      "tests": {
        "passed": 160,
        "failed": 0
      }
    },
    {
      "t": "2026-10-26T23:08:10+05:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 2
    },
    {
      "t": "2026-10-26T23:08:11+05:00",
      "k": "add",
      "key": "debt.emptyEnv",
      "n": 5
    },
    {
      "t": "2026-10-26T23:08:11+05:00",
      "k": "add",
      "key": "concerns",
      "n": 3
    },
    {
      "t": "2026-10-26T23:08:27+05:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "review"
    },
    {
      "t": "2026-10-26T23:08:28+05:00",
      "k": "ticket",
      "ids": [
        "02",
        "05"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-26T23:11:31+05:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "done"
    },
    {
      "t": "2026-10-26T23:11:32+05:00",
      "k": "add",
      "key": "concerns",
      "n": 4
    },
    {
      "t": "2026-10-26T23:16:53+05:00",
      "k": "ticket",
      "ids": [
        "05"
      ],
      "act": "done",
      "tests": {
        "passed": 0,
        "failed": 0
      }
    },
    {
      "t": "2026-10-26T23:16:53+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-26T23:29:00+05:00",
      "k": "ticket",
      "ids": [
        "02"
      ],
      "act": "done",
      "tests": {
        "passed": 207,
        "failed": 0
      }
    },
    {
      "t": "2026-10-26T23:29:01+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-26T23:29:01+05:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-26T23:41:22+05:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "done",
      "tests": {
        "passed": 233,
        "failed": 0
      }
    },
    {
      "t": "2026-10-26T23:41:22+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-26T23:41:23+05:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-26T23:50:51+05:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "done",
      "tests": {
        "passed": 266,
        "failed": 0
      }
    },
    {
      "t": "2026-10-26T23:50:52+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-26T23:50:52+05:00",
      "k": "ticket",
      "ids": [
        "06"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T00:07:34+05:00",
      "k": "ticket",
      "ids": [
        "06"
      ],
      "act": "done",
      "tests": {
        "passed": 267,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T00:07:35+05:00",
      "k": "add",
      "key": "report",
      "n": 1
    },
    {
      "t": "2026-10-27T00:07:35+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-27T00:07:36+05:00",
      "k": "ticket",
      "ids": [
        "07"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T02:52:28+05:00",
      "k": "ticket",
      "ids": [
        "07"
      ],
      "act": "reset"
    },
    {
      "t": "2026-10-27T02:54:05+05:00",
      "k": "ticket",
      "ids": [
        "07"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T03:12:44+05:00",
      "k": "ticket",
      "ids": [
        "07"
      ],
      "act": "done",
      "tests": {
        "passed": 314,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T03:12:44+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-27T03:12:45+05:00",
      "k": "add",
      "key": "report",
      "n": 1
    },
    {
      "t": "2026-10-27T03:12:45+05:00",
      "k": "ticket",
      "ids": [
        "08"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T03:33:01+05:00",
      "k": "ticket",
      "ids": [
        "08"
      ],
      "act": "done",
      "tests": {
        "passed": 350,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T03:33:01+05:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-27T03:33:02+05:00",
      "k": "add",
      "key": "concerns",
      "n": 3
    },
    {
      "t": "2026-10-27T03:33:02+05:00",
      "k": "ticket",
      "ids": [
        "09"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T03:47:55+05:00",
      "k": "ticket",
      "ids": [
        "09"
      ],
      "act": "done",
      "tests": {
        "passed": 376,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T03:47:55+05:00",
      "k": "add",
      "key": "concerns",
      "n": 4
    },
    {
      "t": "2026-10-27T03:47:56+05:00",
      "k": "ticket",
      "ids": [
        "10"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T03:59:47+05:00",
      "k": "ticket",
      "ids": [
        "10"
      ],
      "act": "done",
      "tests": {
        "passed": 390,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T03:59:47+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-27T03:59:48+05:00",
      "k": "ticket",
      "ids": [
        "11"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T04:27:36+05:00",
      "k": "ticket",
      "ids": [
        "11"
      ],
      "act": "done",
      "tests": {
        "passed": 334,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T04:27:37+05:00",
      "k": "add",
      "key": "report",
      "n": 3
    },
    {
      "t": "2026-10-27T04:27:37+05:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-27T04:27:38+05:00",
      "k": "ticket",
      "ids": [
        "11"
      ],
      "act": "review"
    },
    {
      "t": "2026-10-27T04:29:20+05:00",
      "k": "ticket",
      "ids": [
        "11"
      ],
      "act": "done"
    },
    {
      "t": "2026-10-27T04:29:21+05:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-27T04:29:21+05:00",
      "k": "stage",
      "id": "review",
      "act": "start"
    },
    {
      "t": "2026-10-27T04:36:28+05:00",
      "k": "tickets",
      "n": 12
    },
    {
      "t": "2026-10-27T04:36:29+05:00",
      "k": "gate",
      "g": "G3",
      "ok": true,
      "problems": 0
    },
    {
      "t": "2026-10-27T04:36:30+05:00",
      "k": "add",
      "key": "report",
      "n": 22
    },
    {
      "t": "2026-10-27T04:36:30+05:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T04:52:18+05:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "done",
      "tests": {
        "passed": 352,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T04:52:18+05:00",
      "k": "add",
      "key": "report",
      "n": 1
    },
    {
      "t": "2026-10-27T04:52:19+05:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "review"
    },
    {
      "t": "2026-10-27T04:54:05+05:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "done"
    },
    {
      "t": "2026-10-27T04:54:06+05:00",
      "k": "stage",
      "id": "final",
      "act": "start"
    },
    {
      "t": "2026-10-27T14:53:03+05:00",
      "k": "gate",
      "g": "G4",
      "ok": false,
      "checked": 85,
      "matched": 81
    },
    {
      "t": "2026-10-27T14:53:06+05:00",
      "k": "tests",
      "passed": 352,
      "failed": 0
    },
    {
      "t": "2026-10-27T14:55:06+05:00",
      "k": "finish",
      "result": "ForwardTrace v2 — разговорный дневник прогресса в ветке v2: поток ответа с цитатами, память и нити, первый разговор, ИИ пишет первым, безопасность, лимит, Прогресс и сводка; v1 удалён"
    },
    {
      "t": "2026-10-27T17:57:32+05:00",
      "k": "reopen"
    },
    {
      "t": "2026-10-27T17:59:54+05:00",
      "k": "stage",
      "id": "briefing",
      "act": "start"
    },
    {
      "t": "2026-10-27T17:59:54+05:00",
      "k": "ask",
      "kind": "briefing",
      "note": "три вопроса — «ты» вместо «вы», прогон эталонных диалогов на настоящей модели, хвосты прошлой сборки"
    },
    {
      "t": "2026-10-27T18:04:37+05:00",
      "k": "ask",
      "kind": "briefing",
      "note": "граница «ты»/«вы»: кнопки и экраны приложения"
    },
    {
      "t": "2026-10-27T18:06:45+05:00",
      "k": "answered",
      "kind": "briefing"
    },
    {
      "t": "2026-10-27T18:07:05+05:00",
      "k": "gate",
      "g": "G1",
      "ok": false,
      "open": 76,
      "total": 288
    },
    {
      "t": "2026-10-27T18:07:05+05:00",
      "k": "stage",
      "id": "spec",
      "act": "start"
    },
    {
      "t": "2026-10-27T18:19:39+05:00",
      "k": "gate",
      "g": "G2",
      "ok": true,
      "found": 5,
      "fixed": 5,
      "deferred": 0
    },
    {
      "t": "2026-10-27T18:19:45+05:00",
      "k": "stage",
      "id": "plan",
      "act": "start"
    },
    {
      "t": "2026-10-27T18:21:58+05:00",
      "k": "tier",
      "v": "T2"
    },
    {
      "t": "2026-10-27T18:21:58+05:00",
      "k": "tickets",
      "n": 17
    },
    {
      "t": "2026-10-27T18:21:59+05:00",
      "k": "gate",
      "g": "G3",
      "ok": false,
      "problems": 2
    },
    {
      "t": "2026-10-27T18:22:06+05:00",
      "k": "tickets",
      "n": 17
    },
    {
      "t": "2026-10-27T18:22:06+05:00",
      "k": "gate",
      "g": "G3",
      "ok": true,
      "problems": 0
    },
    {
      "t": "2026-10-27T18:22:38+05:00",
      "k": "stage",
      "id": "build",
      "act": "start"
    },
    {
      "t": "2026-10-27T18:22:38+05:00",
      "k": "ticket",
      "ids": [
        "12"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T18:41:07+05:00",
      "k": "ticket",
      "ids": [
        "12"
      ],
      "act": "done",
      "tests": {
        "passed": 388,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T18:41:07+05:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-27T18:41:08+05:00",
      "k": "ticket",
      "ids": [
        "13"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T18:53:43+05:00",
      "k": "ticket",
      "ids": [
        "13"
      ],
      "act": "done",
      "tests": {
        "passed": 399,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T18:54:21+05:00",
      "k": "add",
      "key": "report",
      "n": 1
    },
    {
      "t": "2026-10-27T18:54:21+05:00",
      "k": "ticket",
      "ids": [
        "14"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T19:11:48+05:00",
      "k": "ticket",
      "ids": [
        "14"
      ],
      "act": "repair",
      "note": "метка «Ты:» → «Человек:»/«Person:»; mentions_goal по основам"
    },
    {
      "t": "2026-10-27T19:38:28+05:00",
      "k": "ticket",
      "ids": [
        "14"
      ],
      "act": "done",
      "tests": {
        "passed": 432,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T19:38:37+05:00",
      "k": "ask",
      "kind": "action",
      "note": "рабочий OPENAI_API_KEY в progress-backend/.env для прогона эталонов (шаг 5), затем оценка отчёта"
    },
    {
      "t": "2026-10-27T19:47:32+05:00",
      "k": "answered",
      "kind": "action"
    },
    {
      "t": "2026-10-27T19:49:48+05:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-27T19:49:48+05:00",
      "k": "ask",
      "kind": "action",
      "note": "оценка владельцем отчёта v2.0 → v2.1 перед памятью (шаг 5 брифа)"
    },
    {
      "t": "2026-10-27T21:49:18+05:00",
      "k": "answered",
      "kind": "action"
    },
    {
      "t": "2026-10-27T21:49:19+05:00",
      "k": "ticket",
      "ids": [
        "15"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T22:07:35+05:00",
      "k": "ticket",
      "ids": [
        "15"
      ],
      "act": "done",
      "tests": {
        "passed": 447,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T22:07:36+05:00",
      "k": "ticket",
      "ids": [
        "15"
      ],
      "act": "review"
    },
    {
      "t": "2026-10-27T22:07:36+05:00",
      "k": "add",
      "key": "concerns",
      "n": 3
    },
    {
      "t": "2026-10-27T22:07:37+05:00",
      "k": "ticket",
      "ids": [
        "16"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-27T22:09:36+05:00",
      "k": "ticket",
      "ids": [
        "15"
      ],
      "act": "done",
      "tests": {
        "passed": 447,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T22:09:36+05:00",
      "k": "add",
      "key": "concerns",
      "n": 3
    },
    {
      "t": "2026-10-27T22:26:36+05:00",
      "k": "ticket",
      "ids": [
        "16"
      ],
      "act": "done",
      "tests": {
        "passed": 464,
        "failed": 0
      }
    },
    {
      "t": "2026-10-27T22:26:37+05:00",
      "k": "add",
      "key": "concerns",
      "n": 3
    },
    {
      "t": "2026-10-27T22:26:38+05:00",
      "k": "stage",
      "id": "review",
      "act": "start"
    },
    {
      "t": "2026-10-27T22:30:53+05:00",
      "k": "add",
      "key": "report",
      "n": 6
    },
    {
      "t": "2026-10-27T22:30:59+05:00",
      "k": "stage",
      "id": "final",
      "act": "start"
    },
    {
      "t": "2026-10-27T22:39:10+05:00",
      "k": "gate",
      "g": "G4",
      "ok": false,
      "checked": 23,
      "matched": 20
    },
    {
      "t": "2026-10-27T22:39:55+05:00",
      "k": "tests",
      "passed": 464,
      "failed": 0
    },
    {
      "t": "2026-10-27T22:39:55+05:00",
      "k": "finish",
      "result": "v2.1: живой разговор на gpt-6-sol, память о жизни с разделом «Что я помню», ИИ пишет первым как приглашение"
    }
  ],
  "reqList": [
    {
      "id": "R001",
      "text": "«Каждый календарный день человека — отдельный разговор.»",
      "status": "done"
    },
    {
      "id": "R002",
      "text": "«Человек говорит или пишет, ИИ сразу отвечает и доказывает рост его же словами с датами.»",
      "status": "done"
    },
    {
      "id": "R003",
      "text": "«Из каждого разговора в фоне извлекаются факты, и у каждого есть дословная цитата, найденная в тексте.»",
      "status": "done"
    },
    {
      "id": "R004",
      "text": "«ИИ ссылается на прошлое только через такие факты. Цитаты в ответ подставляет код, а не модель.»",
      "status": "done"
    },
    {
      "id": "R005",
      "text": "«Трудность, которую назвал человек, отслеживается, пока он не скажет, что справился. Тогда ИИ показывает «было → стало».»",
      "status": "done"
    },
    {
      "id": "R006",
      "text": "«Раз в день в выбранное время ИИ начинает разговор вопросом по открытой нити, по цели или по вчерашнему разговору.»",
      "status": "done"
    },
    {
      "id": "R007",
      "text": "«Онбординг тоже происходит в разговоре»",
      "status": "done"
    },
    {
      "id": "R008",
      "text": "«Разговор может касаться любой темы жизни (усталость, учёба, сон), но память и доказательства собираются вокруг цели.»",
      "status": "done"
    },
    {
      "id": "R009",
      "text": "«Навигация — три вкладки и шестерёнка»",
      "status": "done"
    },
    {
      "id": "R010",
      "text": "«Сегодня — лента дней сверху (дни с разговорами подсвечены зелёным, свайп листает недели) и разговор дня под ней.»",
      "status": "done"
    },
    {
      "id": "R011",
      "text": "«История — все дни с разговорами и поиск; тап по зелёному дню на ленте открывает этот день здесь.»",
      "status": "done"
    },
    {
      "id": "R012",
      "text": "«Прогресс — цель и финиш, карточки «было → стало» по мере появления, нити, месячная сводка.»",
      "status": "done"
    },
    {
      "id": "R013",
      "text": "«Шестерёнка справа сверху — профиль и настройки.»",
      "status": "done"
    },
    {
      "id": "R014",
      "text": "«Чего в v2 нет: недельных отчётов, критериев прогресса (их заменяет один финиш), задач-намерений, шага проверки расшифровки, нескольких целей одновременно, процентов «пройдено к финишу».»",
      "status": "done"
    },
    {
      "id": "R015",
      "text": "«Бэкенд эволюционирует в том же репозитории: новый модуль разговоров рядом со старым кодом, затем удаление ненужного.»",
      "status": "done"
    },
    {
      "id": "R016",
      "text": "«Фронтенд пишется заново внутри progress-frontend/: старые экраны удаляются, несколько библиотек из lib/ переносятся.»",
      "status": "done"
    },
    {
      "id": "R017",
      "text": "«Работа идёт в новой ветке v2 от main.»",
      "status": "done"
    },
    {
      "id": "R018",
      "text": "«Стек остаётся прежним»",
      "status": "done"
    },
    {
      "id": "R019",
      "text": "«Фоновые задачи остаются в процессе API через BackgroundTasks и asyncio-циклы в lifespan, один воркер.»",
      "status": "done"
    },
    {
      "id": "R020",
      "text": "«Аутентификация … Регистрация, вход, подтверждение почты, JWT с token_version, защита от перебора» (оставить как есть)",
      "status": "done"
    },
    {
      "id": "R021",
      "text": "«Удаление и восстановление аккаунта … Добавить в список стирания новые таблицы»",
      "status": "done"
    },
    {
      "id": "R022",
      "text": "«Проверка цитат … Ядро v2: NFKC, без пунктуации и регистра, точное вхождение или SequenceMatcher ≥ 0.90, минимум 8 символов»",
      "status": "done"
    },
    {
      "id": "R023",
      "text": "«Вызов модели … JSON-ответы для памяти, безопасности, тем сообщений; учёт стоимости»",
      "status": "done"
    },
    {
      "id": "R024",
      "text": "«Время … Локальный день человека = разговор»",
      "status": "done"
    },
    {
      "id": "R025",
      "text": "«Push … Доставка сообщений ИИ первым»",
      "status": "done"
    },
    {
      "id": "R026",
      "text": "«Телеметрия и админка … Аналитика v2 пишется в events»",
      "status": "done"
    },
    {
      "id": "R027",
      "text": "«Сохранять слова с таймкодами из ответа Deepgram (words[]: word, start, end). Для смешанной речи использовать STT_MULTILINGUAL»",
      "status": "done"
    },
    {
      "id": "R028",
      "text": "«Аудио принадлежит сообщению: AUDIO_DIR/<user_id>/<message_id>.<ext>. Те же проверки MIME и размера»",
      "status": "done"
    },
    {
      "id": "R029",
      "text": "«Новая схема (achievement / struggle / learned, нити, выжимка дня), та же обязательная проверка цитат и счётчик отброшенных»",
      "status": "done"
    },
    {
      "id": "R030",
      "text": "«Рефлексия … Не вызывается. Фильтр похвалы и диагнозов (BANNED) переносится в пост-обработку ответа разговора»",
      "status": "done"
    },
    {
      "id": "R031",
      "text": "«Становится целью-якорем с финишем: одна активная цель, критерии не используются»",
      "status": "done"
    },
    {
      "id": "R032",
      "text": "«Становятся сообщениями ИИ первым (раздел «Логика»). Сохраняются правила локального часа и «не чаще раза в день»»",
      "status": "done"
    },
    {
      "id": "R033",
      "text": "«Добавить потоковую функцию stream_chat() для ответа в разговоре»",
      "status": "done"
    },
    {
      "id": "R034",
      "text": "«Недельные отчёты и старый дайджест … services/reports.py, aggregate.py, summary.py, monthly.py, routers/reports.py, таблица reports.» (удалить на этапе 10)",
      "status": "done"
    },
    {
      "id": "R035",
      "text": "«Критерии: таблица criteria, POST /api/goals/suggest-criteria, CRITERIA_ в prompts.py.» (удалить)",
      "status": "done"
    },
    {
      "id": "R036",
      "text": "«Задачи: services/tasks.py, routers/tasks.py, таблицы tasks, task_mentions, поле users.tasks_declined_on.» (удалить)",
      "status": "done"
    },
    {
      "id": "R037",
      "text": "«Шаг проверки расшифровки: статус awaiting_review, POST /api/entries/{id}/confirm.» (удалить)",
      "status": "done"
    },
    {
      "id": "R038",
      "text": "«Старые чек-ины: routers/entries.py и таблицы entries, activities — только после импорта их данных (раздел «Модель данных») и с подтверждением владельца.»",
      "status": "done"
    },
    {
      "id": "R039",
      "text": "«Квоты на записи: MAX_VOICE_ENTRIES_PER_DAY, MAX_TEXT_ENTRIES_PER_DAY. Их заменяет лимит разговоров.»",
      "status": "done"
    },
    {
      "id": "R040",
      "text": "«Все старые экраны фронтенда.» (удалить)",
      "status": "done"
    },
    {
      "id": "R041",
      "text": "«Новые таблицы и поля добавляются миграцией 0014_v2_core … Все PK — UUID, все FK на users.id — ON DELETE CASCADE … JSON-поля — тип JsonB из models.py»",
      "status": "done"
    },
    {
      "id": "R042",
      "text": "«users (существующая; новые и переименованные поля) skill … country … outreach_channel … telegram_chat_id … telegram_link_token … outreach_unanswered … plus_until … first_conversation_done»",
      "status": "done"
    },
    {
      "id": "R043",
      "text": "«goals … why_message_id … finish_line … finish_set_on … baseline_message_id»",
      "status": "done"
    },
    {
      "id": "R044",
      "text": "«conversations … local_date … unique (user_id, local_date) … kind … started_by … state … summary … safety_level … counts_for_limit … memory_extracted_at»",
      "status": "done"
    },
    {
      "id": "R045",
      "text": "«messages … role … source … content_raw … content … words … audio_path … quick_replies … used_fact_ids … intent … safety_level … rating … model_name, llm_ms, stt_ms, cost_usd»",
      "status": "done"
    },
    {
      "id": "R046",
      "text": "«facts … message_id … origin … local_date … type … text … quote … audio_start_ms, audio_end_ms … thread_id … embedding … flagged_at»",
      "status": "done"
    },
    {
      "id": "R047",
      "text": "«threads … title … status … opened_fact_id, closed_fact_id … opened_on, closed_on, last_mentioned_on»",
      "status": "done"
    },
    {
      "id": "R048",
      "text": "«pairs — карточки «было → стало» … then_fact_id, now_fact_id … theme … recalled … source … hidden_at … unique (then_fact_id, now_fact_id)»",
      "status": "done"
    },
    {
      "id": "R049",
      "text": "«monthly_summaries … month … unique (user_id, month) … status … stats … content … viewed_at»",
      "status": "done"
    },
    {
      "id": "R050",
      "text": "«outreach … topic … thread_id … channel … sent_at, delivered (bool), opened_at, replied_at»",
      "status": "done"
    },
    {
      "id": "R051",
      "text": "«Эмбеддинги фактов хранятся в facts.embedding как JSON, а косинусное сходство считается в Python по фактам одного пользователя.»",
      "status": "done"
    },
    {
      "id": "R052",
      "text": "«Если эмбеддинг не удалось получить, факт сохраняется без него, а поиск откатывается на последние по дате факты.»",
      "status": "done"
    },
    {
      "id": "R053",
      "text": "«Импорт данных v1 — скрипт scripts/import_v1.py, идемпотентный»",
      "status": "done"
    },
    {
      "id": "R054",
      "text": "«Для каждой записи entries со статусом done создать или найти разговор за local_date (kind=daily, started_by=user) и сообщение role=user с raw_transcript, аудио и source.»",
      "status": "done"
    },
    {
      "id": "R055",
      "text": "«wins → факты achievement, friction → struggle, цитаты activities.quote → achievement без дублей по цитате. intentions не переносить.»",
      "status": "done"
    },
    {
      "id": "R056",
      "text": "«Каждую цитату повторно прогнать через verify.py по тексту сообщения; не прошедшие — пропустить и посчитать.»",
      "status": "done"
    },
    {
      "id": "R057",
      "text": "«Цель с why_text оставить целью-якорем.»",
      "status": "done"
    },
    {
      "id": "R058",
      "text": "«В конце вывести сводку: сколько разговоров, сообщений, фактов создано и сколько цитат отброшено.»",
      "status": "done"
    },
    {
      "id": "R059",
      "text": "«Старые таблицы скрипт не меняет.»",
      "status": "done"
    },
    {
      "id": "R060",
      "text": "«Все новые эндпоинты требуют Bearer-токен, как в v1, и фильтруют данные по current_user.id.»",
      "status": "done"
    },
    {
      "id": "R061",
      "text": "«Ошибки новых эндпоинтов возвращаются с машинным кодом: {\"detail\": {\"code\": \"limit_reached\", \"message\": \"...\"}}. Фронтенд переводит ошибки по code, а не по тексту.»",
      "status": "done"
    },
    {
      "id": "R062",
      "text": "«GET /api/conversations/today … Если у человека ещё нет разговоров, создаёт первый разговор с первым вопросом ИИ … limit {used, free, plus}»",
      "status": "done"
    },
    {
      "id": "R063",
      "text": "«POST /api/conversations/today/messages … JSON {text} или multipart audio … До начала потока: 402 limit_reached, 403 email_not_verified, 413, 415, 400 empty_audio»",
      "status": "done"
    },
    {
      "id": "R064",
      "text": "«POST /api/conversations/today/plateau … «Кажется, я стою на месте» по кнопке … только ответ ассистента»",
      "status": "done"
    },
    {
      "id": "R065",
      "text": "«GET /api/conversations?before=&limit=30 … Лента: дата, выжимка, кто начал, нити дня»",
      "status": "done"
    },
    {
      "id": "R066",
      "text": "«GET /api/conversations/{local_date} … Разговор дня целиком»",
      "status": "done"
    },
    {
      "id": "R067",
      "text": "«DELETE /api/conversations/{local_date} … Удалить разговор: сообщения, аудиофайлы и факты из него; ссылки нитей на удалённые факты обнуляются»",
      "status": "done"
    },
    {
      "id": "R068",
      "text": "«GET /api/search?q= … Поиск по сообщениям человека»",
      "status": "done"
    },
    {
      "id": "R069",
      "text": "«GET /api/messages/{id}/audio … Аудио сообщения, только владельцу»",
      "status": "done"
    },
    {
      "id": "R070",
      "text": "«POST /api/messages/{id}/rating … helped … not_it … 204»",
      "status": "done"
    },
    {
      "id": "R071",
      "text": "«POST /api/facts/{id}/flag … «Это неточно»: факт больше не используется в ответах»",
      "status": "done"
    },
    {
      "id": "R072",
      "text": "«PATCH /api/threads/{id} … {status?: \"closed\" | \"deleted\", title?}»",
      "status": "done"
    },
    {
      "id": "R073",
      "text": "«GET /api/memory … Цель, открытые и закрытые нити, последние 50 фактов (Should)»",
      "status": "done"
    },
    {
      "id": "R074",
      "text": "«POST /api/paywall/click … Нажатие на фейковой двери: plus_until = сегодня + 30 дней»",
      "status": "done"
    },
    {
      "id": "R075",
      "text": "«POST /api/telegram/link … Ссылка привязки бота»",
      "status": "done"
    },
    {
      "id": "R076",
      "text": "«POST /api/telegram/webhook … Входящие от Telegram; проверка секретного заголовка»",
      "status": "done"
    },
    {
      "id": "R077",
      "text": "«GET /api/me/export … Выгрузка: разговоры, сообщения, факты, нити, цель»",
      "status": "done"
    },
    {
      "id": "R078",
      "text": "«PATCH /api/auth/me … Существующий эндпоинт + поля skill, country, outreach_channel»",
      "status": "done"
    },
    {
      "id": "R079",
      "text": "«GET /api/calendar?from=&to= … какие дни зелёные (counts_for_limit = true) … диапазон до 62 дней»",
      "status": "done"
    },
    {
      "id": "R080",
      "text": "«GET /api/progress … цель, мотивация, финиш, последние 3 факта level с датами, карточки «было → стало», открытые и закрытые нити, последняя месячная сводка»",
      "status": "done"
    },
    {
      "id": "R081",
      "text": "«GET /api/progress/monthly?month=YYYY-MM … Месячная сводка; при первом открытии ставит viewed_at»",
      "status": "done"
    },
    {
      "id": "R082",
      "text": "«POST /api/pairs/{id}/hide … Скрыть карточку «было → стало»»",
      "status": "done"
    },
    {
      "id": "R083",
      "text": "«PATCH /api/goal … Изменить цель, мотивацию или финиш из профиля: {title?, why_text?, finish_line?} (finish_line: null — «без финиша»)»",
      "status": "done"
    },
    {
      "id": "R084",
      "text": "«Ответ — Server-Sent Events. Клиент собирает сегменты сообщения ассистента в порядке прихода событий.» (user_message, delta, quote, done, error)",
      "status": "done"
    },
    {
      "id": "R085",
      "text": "«Для голосового сообщения сервер сначала синхронно распознаёт речь и отправляет user_message с расшифровкой, затем начинает ответ. Если распознавание вернуло меньше 10 символов, поток завершается событием error с кодом no_speech.»",
      "status": "done"
    },
    {
      "id": "R086",
      "text": "«Новый код домена разговоров кладётся в services/conversation.py … services/memory.py … services/outreach.py … services/safety.py и routers/conversations.py. Промпты — в services/prompts.py … на английском, с блоком _write_in для русского»",
      "status": "done"
    },
    {
      "id": "R087",
      "text": "«В лимит засчитывается день, где человек отправил хотя бы одно сообщение. Сообщение ИИ первым без ответа не засчитывается.»",
      "status": "done"
    },
    {
      "id": "R088",
      "text": "«В ответы попадают только проверенные факты без flagged_at.»",
      "status": "done"
    },
    {
      "id": "R089",
      "text": "«Пара «тогда → сейчас» — факт struggle и более поздний факт achievement той же нити или близкие по смыслу (косинус ≥ 0,8), разница не меньше 7 дней.»",
      "status": "done"
    },
    {
      "id": "R090",
      "text": "«Проверить лимит … При превышении — 402 до начала потока.»",
      "status": "done"
    },
    {
      "id": "R091",
      "text": "«Отметить counts_for_limit = true, сбросить users.outreach_unanswered = 0, проставить outreach.replied_at, если сегодня было сообщение ИИ первым.»",
      "status": "done"
    },
    {
      "id": "R092",
      "text": "«Если разговор kind=first и не завершён — передать в сценарий первого разговора (ниже) и выйти.»",
      "status": "done"
    },
    {
      "id": "R093",
      "text": "«safety_check(text) → уровень 0–3. При уровне 2 и выше — ответ по протоколу безопасности, шаги 6–8 пропускаются.»",
      "status": "done"
    },
    {
      "id": "R094",
      "text": "«Собрать контекст: системный промпт; навык и язык; цитата цели; до 5 открытых нитей с id; до 5 проверенных фактов, ближайших по смыслу к сообщению, с id и датами; выжимки 3 последних разговоров; сообщения текущего разговора.»",
      "status": "done"
    },
    {
      "id": "R095",
      "text": "«Модель пишет обычный текст с плейсхолдерами {{quote:<fact_id>}}, затем строку-разделитель <<<META>>> и JSON»",
      "status": "done"
    },
    {
      "id": "R096",
      "text": "«если fact_id был в контексте, отправить событие quote с цитатой и датой из базы, иначе молча выбросить … Ошибка парсинга META не ломает ответ: quick_replies = [], intent = normal.»",
      "status": "done"
    },
    {
      "id": "R097",
      "text": "«Сохранить сообщение ассистента: content_raw, content, quick_replies, used_fact_ids, intent, стоимость и время. Отправить done.»",
      "status": "done"
    },
    {
      "id": "R098",
      "text": "«Если intent = plateau, следующий ответ строится по сценарию «Кажется, я стою на месте».»",
      "status": "done"
    },
    {
      "id": "R099",
      "text": "«После ответа проверить правила (до 120 слов или до 250 … не больше одного ?; нет слов из BANNED) … нарушение пишется событием reply_rule_violation»",
      "status": "dropped",
      "why": "пользователь, бриф v2.1: «Убрать жёсткие проверки длины, числа вопросов и слов из BANNED вместе с событием reply_rule_violation» → R231"
    },
    {
      "id": "R100",
      "text": "«Черновик системного промпта … В prompts.py хранится на английском; ниже — смысл, который нужно сохранить.»",
      "status": "done"
    },
    {
      "id": "R101",
      "text": "«Первый разговор заменяет экраны онбординга: после регистрации человек сразу попадает на «Сегодня», где ИИ начинает разговор.»",
      "status": "done"
    },
    {
      "id": "R102",
      "text": "«Состояние хранится в conversations.state … Вопросы — строки из i18n, ответы ИИ отдаются тем же потоком: одно событие delta с полным текстом и done с быстрыми ответами.»",
      "status": "done"
    },
    {
      "id": "R103",
      "text": "«Создание … «Привет! Я помогу тебе замечать, как ты растёшь, — твоими же словами. Что ты сейчас развиваешь?» Быстрые ответы: «Программирование», «Геймдев», «Иностранный язык», «Спорт», «Музыка».»",
      "status": "done"
    },
    {
      "id": "R104",
      "text": "«skill. Ответ сохраняется в users.skill и goals.title (до 120 символов; длинный ответ complete_json сокращает до короткого названия).»",
      "status": "done"
    },
    {
      "id": "R105",
      "text": "«motivation. complete_json возвращает дословную цитату мотивации и 4 варианта финиша … Цитата проверяется verify.py … Если цитата не прошла проверку — «Запомнил. Когда ты скажешь, что цель достигнута?»»",
      "status": "done"
    },
    {
      "id": "R106",
      "text": "«finish. Текст варианта или свой ответ сохраняется в goals.finish_line и finish_set_on. «Без финиша» → finish_line = null, no_finish = true.»",
      "status": "done"
    },
    {
      "id": "R107",
      "text": "«baseline … до 3 пар. Все цитаты проверяются; по каждой паре создаются факты struggle и achievement и запись pairs с recalled = true … level_quote → факт level … Без пар или при just_started: «Ты в самом начале …»»",
      "status": "done"
    },
    {
      "id": "R108",
      "text": "«schedule. Ответ задаёт reminder_hour … Фронтенд запрашивает разрешение на уведомления, а при отказе или на iPhone без установленного PWA предлагает Telegram.»",
      "status": "done"
    },
    {
      "id": "R109",
      "text": "«Если ответ пустой или не по теме, ИИ переспрашивает один раз мягче (retries), затем переходит к следующему шагу.»",
      "status": "done"
    },
    {
      "id": "R110",
      "text": "«Цель, мотивацию и финиш потом можно изменить в профиле.»",
      "status": "done"
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
      "status": "done"
    },
    {
      "id": "R113",
      "text": "«Второй цикл закрывает день в 04:00 по времени человека и запускает извлечение для ещё не обработанных разговоров.»",
      "status": "done"
    },
    {
      "id": "R114",
      "text": "«На вход модели — сообщения человека за день с id, открытые нити с id. Ответ по JSON-схеме» (facts, threads open/mention/close, day_summary)",
      "status": "done"
    },
    {
      "id": "R115",
      "text": "«Каждую цитату проверить verify.py по тексту своего сообщения. Не прошла — факт отброшен, счётчик пишется в событие memory_dropped_facts. message_id не из этого разговора — факт отброшен.»",
      "status": "done"
    },
    {
      "id": "R116",
      "text": "«Для голосовых сообщений найти цитату в messages.words и записать audio_start_ms, audio_end_ms. Не нашлось точное выравнивание — оставить null.»",
      "status": "done"
    },
    {
      "id": "R117",
      "text": "«open: создать нить, только если ссылка на факт struggle прошла проверку. mention и close принимаются только для thread_id из переданных открытых нитей. close требует факт achievement или learned. Обновить last_mentioned_on.»",
      "status": "done"
    },
    {
      "id": "R118",
      "text": "«Получить эмбеддинги новых фактов одним запросом. Ошибка не ломает извлечение.»",
      "status": "done"
    },
    {
      "id": "R119",
      "text": "«Записать summary (до 200 символов) и memory_extracted_at.»",
      "status": "done"
    },
    {
      "id": "R120",
      "text": "«Тип level — факт, в котором человек говорит о своём уровне относительно финиша»",
      "status": "done"
    },
    {
      "id": "R121",
      "text": "«Закрытая нить → пара из факта открытия и факта закрытия, если между ними не меньше PAIR_MIN_DAYS (7) дней (source = thread_closed).»",
      "status": "done"
    },
    {
      "id": "R122",
      "text": "«Для каждого нового факта achievement с эмбеддингом — поиск самого близкого факта struggle … старше 7 дней с косинусом не ниже PAIR_MIN_SIMILARITY (0,8) … Не больше одной новой пары на факт.»",
      "status": "done"
    },
    {
      "id": "R123",
      "text": "«theme — короткая тема из названия нити или из complete_json по двум цитатам.»",
      "status": "done"
    },
    {
      "id": "R124",
      "text": "«Пары с фактами, у которых есть flagged_at, не показываются.»",
      "status": "done"
    },
    {
      "id": "R125",
      "text": "«Цикл раз в 15 минут выбирает пользователей с reminders_on, каналом не none, у которых сейчас локальный час reminder_hour и last_reminded_on не сегодня.»",
      "status": "done"
    },
    {
      "id": "R126",
      "text": "«Не отправлять, если человек уже писал сегодня, если сегодня был уровень безопасности 3 или если сработали правила паузы.»",
      "status": "done"
    },
    {
      "id": "R127",
      "text": "«Тема по приоритету: открытая нить с last_mentioned_on за последние 3 дня → цель-якорь, если человек молчит 2 дня и больше → вчерашний разговор → общий вопрос из i18n»",
      "status": "done"
    },
    {
      "id": "R128",
      "text": "«Текст: complete_json со схемой {\"text\", \"quick_replies\"}, до 25 слов, один вопрос, цитата плейсхолдером. Проверка длины в коде; при нарушении — шаблон из i18n по теме.»",
      "status": "done"
    },
    {
      "id": "R129",
      "text": "«Запись: создать разговор дня (started_by = ai), если его нет, и сообщение ассистента source = outreach; строку outreach; last_reminded_on = сегодня; outreach_unanswered += 1.»",
      "status": "done"
    },
    {
      "id": "R130",
      "text": "«Доставка: push с телом без плейсхолдеров (цитаты в «ёлочках») и url = /today, либо Telegram … Ошибки доставки обрабатываются как в v1.»",
      "status": "done"
    },
    {
      "id": "R131",
      "text": "«Пауза: при outreach_unanswered ≥ 3 — отправлять раз в 3 дня. При 14 днях без сообщений человека — одно сообщение с темой farewell … затем не отправлять до следующего сообщения человека.»",
      "status": "done"
    },
    {
      "id": "R132",
      "text": "«Проверяется каждое сообщение человека, включая первый разговор. При ошибке модели считать уровень 0 и писать событие safety_check_failed.»",
      "status": "done"
    },
    {
      "id": "R133",
      "text": "«1 — усталость, апатия … пометка «мягче, без давления» … Если уровень 1 был в 5 из последних 14 дней — один раз мягко советовать врача или психолога, не чаще раза в 14 дней (событие safety_suggest_help)»",
      "status": "done"
    },
    {
      "id": "R134",
      "text": "«2 — безнадёжность … Отдельный промпт SAFETY_SYSTEM без памяти и прогресса … conversations.safety_level, событие safety_flag»",
      "status": "done"
    },
    {
      "id": "R135",
      "text": "«3 — риск для жизни … Шаблон из i18n без вызова модели + контакты из SAFETY_RESOURCES для users.country … сообщения ИИ первым не отправляются до следующего сообщения человека»",
      "status": "done"
    },
    {
      "id": "R136",
      "text": "«Не придумывай номера телефонов и названия служб: оставь значения пустыми … Шаблон уровня 3 не обещает конфиденциальность и не говорит, кого и когда известят.»",
      "status": "done"
    },
    {
      "id": "R137",
      "text": "«Система отбирает цель-якорь, до 3 пар «тогда → сейчас» с наибольшей разницей во времени, закрытые нити и число разговоров … Если доказательств меньше двух, ИИ опирается на точку старта и говорит, через сколько дней появится что сравнить.»",
      "status": "done"
    },
    {
      "id": "R138",
      "text": "«Экран «Прогресс» (GET /api/progress) собирается из готовых данных, без вызова модели» (цель, мотивация, финиш или «Без финиша — расту», 3 факта level, карточки новые сверху с «по твоим воспоминаниям», нити, непросмотренная сводка сверху)",
      "status": "done"
    },
    {
      "id": "R139",
      "text": "«Месячная сводка — цикл раз в час: для каждого человека, у которого сейчас 1-е число и наступил CLOSE_DAY_HOUR по его времени … Идемпотентно: unique (user_id, month).»",
      "status": "done"
    },
    {
      "id": "R140",
      "text": "«Не собирать, если в прошлом месяце не было ни одного разговора с сообщением человека.»",
      "status": "done"
    },
    {
      "id": "R141",
      "text": "«Код считает stats: дни с разговорами, закрытые нити, новые пары за месяц, факты level за месяц.»",
      "status": "done"
    },
    {
      "id": "R142",
      "text": "«Если разговоров меньше MONTHLY_MIN_CONVERSATIONS (8) и новых пар меньше MONTHLY_MIN_PAIRS (2) — status = thin, без вызова модели.»",
      "status": "done"
    },
    {
      "id": "R143",
      "text": "«complete_json пишет только три поля: intro … open_struggle … next_step … Ошибка модели → status = failed, повтор при следующем запуске цикла.»",
      "status": "done"
    },
    {
      "id": "R144",
      "text": "«После сборки — push или Telegram: «Сводка за {месяц} готова» (outreach.topic = monthly), не считается сообщением ИИ первым за день.»",
      "status": "done"
    },
    {
      "id": "R145",
      "text": "«Первые 7 дней с регистрации — без ограничений.»",
      "status": "done"
    },
    {
      "id": "R146",
      "text": "«Дальше бесплатно FREE_CONVERSATIONS_PER_WEEK (3) разговоров за календарную неделю в часовом поясе человека.»",
      "status": "done"
    },
    {
      "id": "R147",
      "text": "«Первое сообщение в новом дне сверх лимита → 402 limit_reached. Сообщения в уже засчитанном сегодняшнем разговоре разрешены.»",
      "status": "done"
    },
    {
      "id": "R148",
      "text": "«Без лимита, если plus_until ≥ сегодня.»",
      "status": "done"
    },
    {
      "id": "R149",
      "text": "«Фронтенд на 402 показывает пейволл. Нажатие «Продолжить с Plus» … экран «Мы в бете — тебе месяц бесплатно». События paywall_viewed, paywall_clicked.»",
      "status": "done"
    },
    {
      "id": "R150",
      "text": "«Память, цитаты и «Кажется, я стою на месте» доступны всем; в Plus — только безлимит и недельная выжимка.»",
      "status": "done"
    },
    {
      "id": "R151",
      "text": "«Бот работает через вебхук с секретным заголовком. POST /api/telegram/link выдаёт одноразовую ссылку; /start <token> привязывает telegram_chat_id и ставит outreach_channel = telegram.»",
      "status": "done"
    },
    {
      "id": "R152",
      "text": "«Сообщения ИИ первым приходят в бот текстом с кнопкой «Ответить», которая открывает приложение.»",
      "status": "done"
    },
    {
      "id": "R153",
      "text": "«Желательно: текстовый или голосовой ответ боту обрабатывается как сообщение в сегодняшний разговор, ответ ИИ уходит одним сообщением без потока.»",
      "status": "done"
    },
    {
      "id": "R154",
      "text": "«все цвета, отступы, радиусы и шрифты — CSS-переменные в одном файле (app/tokens.css), тёмная и светлая темы»",
      "status": "done"
    },
    {
      "id": "R155",
      "text": "«сначала мобильная вёрстка (375 px), затем десктоп»",
      "status": "done"
    },
    {
      "id": "R156",
      "text": "«только Tailwind, без библиотек компонентов, если владелец не одобрит другое»",
      "status": "done"
    },
    {
      "id": "R157",
      "text": "«все строки интерфейса — через i18n, русский и английский.»",
      "status": "done"
    },
    {
      "id": "R158",
      "text": "«api.ts … Оставить клиент с Bearer и обновлением токена. Добавить streamPost() на fetch + ReadableStream для SSE»",
      "status": "done"
    },
    {
      "id": "R159",
      "text": "«useRecorder.ts … Перенести без изменений: выбор формата для iOS, определение тишины, выбор микрофона»",
      "status": "done"
    },
    {
      "id": "R160",
      "text": "«push.ts, pwa.ts … Перенести без изменений»",
      "status": "done"
    },
    {
      "id": "R161",
      "text": "«i18n.ts, theme.ts … Перенести механизм; строки написать заново»",
      "status": "done"
    },
    {
      "id": "R162",
      "text": "«PlayAudio … Перенести загрузку аудио blob'ом; добавить проигрывание фрагмента от start_ms до end_ms»",
      "status": "done"
    },
    {
      "id": "R163",
      "text": "«serverErrors.ts … Удалить: ошибки переводятся по detail.code»",
      "status": "done"
    },
    {
      "id": "R164",
      "text": "«/login, /register, /verify, /restore … Логика из v1, новая вёрстка; после входа — /today»",
      "status": "done"
    },
    {
      "id": "R165",
      "text": "«/today … Сверху WeekStrip и шестерёнка справа. Ниже — разговор дня … быстрые ответы, микрофон и поле ввода, цитаты с датами, «помогло / не то» под ответами ИИ, кнопка «Кажется, я стою на месте». После первого разговора — запрос уведомлени…",
      "status": "done"
    },
    {
      "id": "R166",
      "text": "«/history … Дни с разговорами: дата, выжимка, нити дня; поиск»",
      "status": "done"
    },
    {
      "id": "R167",
      "text": "«/history/[date] … Разговор дня целиком, проигрывание голосовых, удаление разговора с подтверждением»",
      "status": "done"
    },
    {
      "id": "R168",
      "text": "«/progress … Новая месячная сводка сверху; цель, мотивация и финиш; путь к финишу (факты level с датами); карточки «было → стало»; нити — открытые и закрытые, закрыть или удалить»",
      "status": "done"
    },
    {
      "id": "R169",
      "text": "«/progress/monthly/[month] … Сводка целиком»",
      "status": "done"
    },
    {
      "id": "R170",
      "text": "«/profile … Почта; цель, мотивация и финиш с редактированием; час и канал сообщений ИИ, привязка Telegram; язык, тема, установка PWA; выгрузка, удаление аккаунта, выход»",
      "status": "done"
    },
    {
      "id": "R171",
      "text": "«/ … Лендинг … Остаётся статическим; текст обновляется на этапе 10»",
      "status": "done"
    },
    {
      "id": "R172",
      "text": "«Навигация: после входа всегда /today … Нижняя панель: Сегодня, История, Прогресс. Шестерёнка в шапке открывает /profile.»",
      "status": "done"
    },
    {
      "id": "R173",
      "text": "«WeekStrip — неделя с днями и числами … сегодня выделен, будущие дни приглушены, дни с active = true подсвечены зелёным. Свайп листает недели с анимацией … Тап по зелёному дню → /history/[date]; по сегодняшнему → прокрутка к разговору; по…",
      "status": "done"
    },
    {
      "id": "R174",
      "text": "«ChatThread — список сообщений с автопрокруткой; загрузка через GET /api/conversations/today.»",
      "status": "done"
    },
    {
      "id": "R175",
      "text": "«MessageBubble — отрисовка сегментов content: текст и QuoteChip.»",
      "status": "done"
    },
    {
      "id": "R176",
      "text": "«QuoteChip — цитата в «ёлочках» и дата; тап открывает /history/[date]; если есть аудиофрагмент — кнопка проигрывания; меню — «Это неточно». Цитаты с recalled: true подписаны «по твоим воспоминаниям».»",
      "status": "done"
    },
    {
      "id": "R177",
      "text": "«QuickReplies — до 5 кнопок; нажатие отправляет текст как сообщение.»",
      "status": "done"
    },
    {
      "id": "R178",
      "text": "«Composer — кнопка записи и поле текста; во время ответа ИИ ввод заблокирован.»",
      "status": "done"
    },
    {
      "id": "R179",
      "text": "«PairCard — карточка «было → стало»: тема, две цитаты с датами, проигрывание, скрыть.»",
      "status": "done"
    },
    {
      "id": "R180",
      "text": "«FinishPath — финиш и последние факты level в виде короткой ленты с датами, без процентов и шкал.»",
      "status": "done"
    },
    {
      "id": "R181",
      "text": "«MonthlySummaryCard — превью сводки на «Прогрессе»; тап → /progress/monthly/[month].»",
      "status": "done"
    },
    {
      "id": "R182",
      "text": "«PaywallSheet — открывается по ошибке limit_reached.»",
      "status": "done"
    },
    {
      "id": "R183",
      "text": "«DayCard, ThreadChip — для истории и прогресса.»",
      "status": "done"
    },
    {
      "id": "R184",
      "text": "«существующие и новые тесты проходят (python -m pytest из progress-backend); у фронтенда проходят npm run build и проверка типов; LLM и STT в тестах замоканы … каждый новый эндпоинт имеет тест изоляции данных между пользователями.»",
      "status": "done"
    },
    {
      "id": "R185",
      "text": "«config.py: убрать дубли полей; приложение отказывается стартовать, если JWT_SECRET равен значению по умолчанию (кроме тестового окружения).»",
      "status": "done"
    },
    {
      "id": "R186",
      "text": "«Смена пароля проверяет ограничение 72 байта, как регистрация.»",
      "status": "done"
    },
    {
      "id": "R187",
      "text": "«.gitignore: правило .md заменить так, чтобы документация в корне и в docs/ попадала в git.»",
      "status": "done"
    },
    {
      "id": "R188",
      "text": "«.env.example: убрать дубли разделов и несуществующий generate_vapid_keys.py.»",
      "status": "done"
    },
    {
      "id": "R189",
      "text": "«миграция применяется на чистой базе и на базе с данными v1; импорт на тестовых данных создаёт разговоры и факты, повторный запуск ничего не дублирует; стирание аккаунта не оставляет строк и файлов.»",
      "status": "done"
    },
    {
      "id": "R190",
      "text": "«тесты проверяют: порядок событий SSE; неизвестный fact_id не попадает в ответ; сломанный META не ломает ответ; голос с пустой речью даёт no_speech; удаление разговора удаляет файлы; чужой разговор недоступен.»",
      "status": "done"
    },
    {
      "id": "R191",
      "text": "«До этапа 3 факты для контекста берутся по дате, без эмбеддингов.»",
      "status": "done"
    },
    {
      "id": "R192",
      "text": "«тесты проверяют: непроверенная цитата отброшена и посчитана; нить нельзя закрыть чужим или выдуманным thread_id; ошибка эмбеддингов не ломает извлечение; выравнивание даёт верные audio_start_ms и audio_end_ms на фикстуре; закрытая нить ст…",
      "status": "done"
    },
    {
      "id": "R193",
      "text": "«тесты покрывают все шаги; варианты финиша приходят быстрыми ответами; свой вариант финиша и «Без финиша» сохраняются верно; ветку «только начал»; повторный вопрос при пустом ответе; непрошедшую проверку цитаты мотивации; сравнение без пар…",
      "status": "done"
    },
    {
      "id": "R194",
      "text": "«в браузере шириной 375 px проходит путь: регистрация → первый разговор голосом и текстом с выбором финиша кнопкой → сравнение «тогда → сейчас» → выбор часа → разрешение уведомлений → сегодняшний день зелёный на ленте → свайп недель → тап…",
      "status": "done"
    },
    {
      "id": "R195",
      "text": "«тесты проверяют выбор темы, «не отправлять, если человек уже писал», паузы после 3 неотвеченных и после 14 дней тишины, подавление после уровня безопасности 3, сброс счётчика при ответе.»",
      "status": "done"
    },
    {
      "id": "R196",
      "text": "«тесты проверяют: на уровнях 2 и 3 не используются память и прогресс; на уровне 3 ответ — шаблон без вызова модели; лимит корректно считается на границе недели и в разных часовых поясах; plus_until снимает лимит; выгрузка содержит только д…",
      "status": "done"
    },
    {
      "id": "R197",
      "text": "«Набор эталонных диалогов: tests/eval/dialogs.yaml (заготовка на 50 диалогов, из них 10 сценариев дистресса; владелец дописывает содержание) и scripts/eval_dialogs.py … проверяет длину, один вопрос, отсутствие BANNED, только известные fact…",
      "status": "placeholder",
      "why": "изменено вторым брифом → R265–R272"
    },
    {
      "id": "R198",
      "text": "«тесты проверяют: сводка собирается один раз за месяц в 1-е число по времени человека; при малом числе данных — thin без вызова модели; в тексте сводки нет цитат вне переданных фактов; скрытые карточки и факты с «это неточно» не показывают…",
      "status": "done"
    },
    {
      "id": "R199",
      "text": "«События: onboarding_completed, first_conversation_step, … monthly_summary_viewed. Каждое несёт номер дня с регистрации, язык и канал.»",
      "status": "done"
    },
    {
      "id": "R200",
      "text": "«Админка: D1 и D7 по когортам, доля ответивших на сообщения ИИ первым, доля «помогло» у ответов с цитатой и без, доля цитат с «это неточно», список разговоров с флагом безопасности со ссылкой на разговор, средняя стоимость разговора.»",
      "status": "done"
    },
    {
      "id": "R201",
      "text": "«Удалить модули из списка «Удалить» и миграцией удалить их таблицы. Таблицы entries и activities — только после подтверждения владельца, что импорт проверен.»",
      "status": "done"
    },
    {
      "id": "R202",
      "text": "«Обновить текст лендинга на русском и английском под разговорный формат: черновик подготовить, финальный текст согласовать с владельцем.»",
      "status": "placeholder"
    },
    {
      "id": "R203",
      "text": "«Обновить README.md и DOCUMENTATION.md.»",
      "status": "done"
    },
    {
      "id": "R204",
      "text": "«Новые переменные добавляются в config.py и .env.example. Все числа из этого документа — стартовые значения, их не хардкодить.» (таблица «Конфигурация»)",
      "status": "done"
    },
    {
      "id": "R205",
      "text": "«Если в services/costs.py нет цен для CHAT_MODEL, SAFETY_MODEL или EMBEDDING_MODEL, добавь место под них и пометь в отчёте этапа, что цены нужно заполнить.»",
      "status": "placeholder"
    },
    {
      "id": "R206",
      "text": "«Работай строго по этапам … В начале каждого этапа коротко напиши план изменений … В конце этапа — что сделано, какие тесты добавлены, что осталось открытым.»",
      "status": "done"
    },
    {
      "id": "R207",
      "text": "«Фоновые циклы идемпотентны и переживают рестарт»",
      "status": "done"
    },
    {
      "id": "R208",
      "text": "«Не меняй способ хранения токенов и схему аутентификации без согласия владельца.»",
      "status": "done"
    },
    {
      "id": "R209",
      "text": "«Не добавляй платные внешние сервисы. Новые зависимости — только если без них нельзя; Telegram и SSE реализуются на httpx и StreamingResponse без отдельных библиотек.»",
      "status": "done"
    },
    {
      "id": "R210",
      "text": "«Остановись и спроси владельца: перед удалением таблиц entries, activities или любых данных пользователей; если для выполнения этапа нужно изменить что-то из раздела «Оставить как есть»; если код v1 серьёзно расходится с DOCUMENTATION.md»",
      "status": "done"
    },
    {
      "id": "R211",
      "text": "«Пока владелец не решил иначе, используй значения по умолчанию и упоминай их в отчётах этапов.» (PWA основной; localStorage; OPENAI_MODEL; эмбеддинги не заданы; функциональный дизайн; почта как в v1; контакты пустые)",
      "status": "done"
    },
    {
      "id": "G01",
      "text": "«Всегда обращаться на вы»",
      "status": "done"
    },
    {
      "id": "R212",
      "text": "«В начале каждого пункта коротко напиши план (какие файлы меняешь), в конце — что сделано и какие тесты добавлены.»",
      "status": "done"
    },
    {
      "id": "R213",
      "text": "«Тесты, которые проверяли старые правила (ровно один вопрос, до 120 слов, обязательные быстрые ответы), удали или перепиши.»",
      "status": "done"
    },
    {
      "id": "R214",
      "text": "«Заменить системный промпт разговора целиком. Старые правила («закончи одним вопросом», «затем маленький следующий шаг», «до 120 слов», «начни с конкретики») удалить.»",
      "status": "done"
    },
    {
      "id": "R215",
      "text": "«Промпт разговора можно хранить по-русски в services/prompts.py … для англоязычных людей нужна английская версия того же текста.»",
      "status": "done"
    },
    {
      "id": "R216",
      "text": "«Служебные промпты (память, безопасность, темы сообщений) остаются как есть.»",
      "status": "done"
    },
    {
      "id": "R217",
      "text": "Текст промпта из брифа («Ты — ForwardTrace, личный собеседник человека … intent = plateau, если человек сомневается, что вообще продвигается.») с подстановками {goal}, {anchor_quote}, {finish_line или «без финиша»}, {threads}, {facts}, {da…",
      "status": "done"
    },
    {
      "id": "R218",
      "text": "«После ответа выведи строку <<<META>>> и JSON: {\"quick_replies\": [], \"intent\": \"normal\" | \"plateau\"}.»",
      "status": "done"
    },
    {
      "id": "R219",
      "text": "«Создать services/prompt_examples.py со списком пар и подставлять 6–8 из них в {examples}. Первые пять:» (достижение, тяжёлый день, смена темы, сомнение в прогрессе, возвращение после перерыва — тексты из брифа)",
      "status": "done"
    },
    {
      "id": "R220",
      "text": "«Оставь в файле места ещё под четыре примера с пометкой TODO(owner): человек делится забавным событием; просит совета; рассказывает о неудаче по цели; размышляет вслух о будущем.»",
      "status": "done"
    },
    {
      "id": "R221",
      "text": "«В примерах плейсхолдеры f_12, f_87 — условные; в промпт они уходят как примеры формы, а не как настоящие факты.»",
      "status": "done"
    },
    {
      "id": "R222",
      "text": "«тест проверяет, что в собранном промпте нет старых правил и есть блок примеров.»",
      "status": "done"
    },
    {
      "id": "R223",
      "text": "«Текущий разговор → {recent_messages}. Последние сообщения человека и ИИ дословно, по порядку, с авторством и датой, в пределах бюджета CONTEXT_RECENT_TOKENS, но не меньше чем за CONTEXT_RECENT_MIN_DAYS последних дня. Сообщения вчерашних и…",
      "status": "done"
    },
    {
      "id": "R224",
      "text": "«Продолжающиеся темы → {threads}. Открытые нити любого вида (изменение 3), до CONTEXT_THREADS, сначала недавно упомянутые.»",
      "status": "done"
    },
    {
      "id": "R225",
      "text": "«до CONTEXT_FACTS проверенных фактов, ближайших по смыслу к текущему сообщению, каждый с id, датой и типом; выжимки дней, которые не попали в уровень 1.»",
      "status": "done"
    },
    {
      "id": "R226",
      "text": "«Факты передаются как утверждения на свою дату: более новый факт по той же теме важнее старого. Если цель менялась, в контекст идёт только текущая.»",
      "status": "done"
    },
    {
      "id": "R227",
      "text": "«Разговор — CHAT_MODEL с CHAT_REASONING_EFFORT = medium … по умолчанию — значение OPENAI_MODEL.»",
      "status": "done"
    },
    {
      "id": "R228",
      "text": "«Служебные вызовы (извлечение памяти, safety_check, темы сообщений, сводки) остаются на прежней модели и уровне low.»",
      "status": "done"
    },
    {
      "id": "R229",
      "text": "«В обычном разговоре quick_replies пустые по умолчанию. Модель возвращает их, только если задала вопрос с явными вариантами действия.»",
      "status": "done"
    },
    {
      "id": "R230",
      "text": "«Первый разговор не меняется: там быстрые ответы нужны (навыки, варианты финиша, время).»",
      "status": "done"
    },
    {
      "id": "R231",
      "text": "«Убрать жёсткие проверки длины, числа вопросов и слов из BANNED вместе с событием reply_rule_violation. Ответы не обрезаются, не перегенерируются и не правятся после генерации.»",
      "status": "done"
    },
    {
      "id": "R232",
      "text": "«Жёсткие проверки остаются … формат META, существование и принадлежность fact_id, протокол безопасности, лимит контекста, обработка ошибок модели.»",
      "status": "done"
    },
    {
      "id": "R233",
      "text": "«Мягкая диагностика пишется в свойства события ai_reply: длина в словах, число вопросительных знаков, упоминается ли цель, есть ли цитата, есть ли быстрые ответы.»",
      "status": "done"
    },
    {
      "id": "R234",
      "text": "«тесты проверяют: в контекст попадают дословные сообщения вчерашнего дня при достаточном бюджете; бюджет соблюдается при длинных сообщениях; пустые quick_replies по умолчанию; длинный ответ с двумя вопросами не обрезается; неизвестный fact…",
      "status": "done"
    },
    {
      "id": "R235",
      "text": "«facts.type + event | decision к существующим achievement | struggle | learned | level» (новая миграция)",
      "status": "done"
    },
    {
      "id": "R236",
      "text": "«threads.kind varchar(16) 'struggle' struggle | topic; существующие нити получают struggle»",
      "status": "done"
    },
    {
      "id": "R237",
      "text": "«outreach.topic: значения thread | yesterday заменить на follow_up | day; итоговый набор: follow_up | day | anchor | farewell | monthly»",
      "status": "done"
    },
    {
      "id": "R238",
      "text": "«Факт — всегда то, что человек сказал, с дословной цитатой. Интерпретации вроде «стал дисциплинированнее» фактами не сохраняются.»",
      "status": "done"
    },
    {
      "id": "R239",
      "text": "«struggle — трудность в навыке или цели, как раньше. Только из таких нитей получаются пары «было → стало».»",
      "status": "done"
    },
    {
      "id": "R240",
      "text": "«topic — продолжающаяся тема жизни … Открывается на любом проверенном факте, закрывается, когда человек говорит, что вопрос решён или больше не актуален.»",
      "status": "done"
    },
    {
      "id": "R241",
      "text": "«В контекст разговора идут открытые нити обоих видов (изменение 2), но промпт не требует возвращаться к ним каждый день.»",
      "status": "done"
    },
    {
      "id": "R242",
      "text": "Схема ответа extract_memory расширяется: facts[].type с event, threads.open[].kind, follow_up, day_summary (JSON из брифа)",
      "status": "done"
    },
    {
      "id": "R243",
      "text": "«follow_up — то, к чему человек сам собирался вернуться … или null. Цитата проверяется verify.py и сохраняется в conversations.state.follow_up.»",
      "status": "done"
    },
    {
      "id": "R244",
      "text": "«Нить struggle по-прежнему открывается только на факте struggle; нить topic — на любом проверенном факте.»",
      "status": "done"
    },
    {
      "id": "R245",
      "text": "«GET /api/memory — цель, мотивация, финиш, открытые и закрытые нити обоих видов, последние 50 фактов.»",
      "status": "done"
    },
    {
      "id": "R246",
      "text": "«DELETE /api/facts/{id} — удалить факт: связанные пары удаляются, ссылки нитей на факт обнуляются. 204.»",
      "status": "done"
    },
    {
      "id": "R247",
      "text": "«PATCH /api/threads/{id} — уже есть; проверить, что работает для topic.»",
      "status": "done"
    },
    {
      "id": "R248",
      "text": "«В /profile — раздел «Что я о тебе помню»: цель и финиш (с переходом к редактированию), темы с кнопками «закрыть» и «удалить», факты с кнопкой «удалить».»",
      "status": "done"
    },
    {
      "id": "R249",
      "text": "«миграция применяется на базе с данными первой сборки; тесты проверяют: факты event и decision сохраняются с проверкой цитаты; нить topic открывается на факте event; пара не создаётся из нити topic; follow_up с непроверенной цитатой отбрас…",
      "status": "done"
    },
    {
      "id": "R250",
      "text": "«В services/outreach.py заменить выбор темы и текст; расписание, паузы и доставка остаются как есть.»",
      "status": "done"
    },
    {
      "id": "R251",
      "text": "«follow_up — … из conversations.state.follow_up последнего разговора, не старше 3 дней. Формулировка — интерес, а не проверка»",
      "status": "done"
    },
    {
      "id": "R252",
      "text": "«day — открытый вопрос о дне, с лёгкой опорой на контекст, если она естественна»",
      "status": "done"
    },
    {
      "id": "R253",
      "text": "«anchor — цель-якорь, только если человек молчит 3 дня и больше, мягко и без упрёка.»",
      "status": "done"
    },
    {
      "id": "R254",
      "text": "«farewell и monthly — как раньше.»",
      "status": "done"
    },
    {
      "id": "R255",
      "text": "«Никогда: «Удалось выполнить?», «Ты планировал…», «Ты пропустил N дней», упоминание открытой нити struggle как невыполненной задачи.»",
      "status": "done"
    },
    {
      "id": "R256",
      "text": "«Текст: complete_json со схемой {\"text\"}, на «ты», коротко и естественно, один вопрос, цитата плейсхолдером — по желанию. Если длиннее OUTREACH_MAX_WORDS — шаблон из i18n по теме. Шаблоны i18n тоже переписать по этим правилам.»",
      "status": "done"
    },
    {
      "id": "R257",
      "text": "«Первое сообщение: «Привет! Я помогу тебе замечать, как ты растёшь, — твоими же словами. Что ты сейчас развиваешь?» Все остальные строки первого разговора — тоже на «ты».»",
      "status": "done"
    },
    {
      "id": "R258",
      "text": "«Если человек уже назвал финиш на шаге skill или motivation … complete_json на шаге motivation получает это и ставит такой финиш первым из четырёх вариантов»",
      "status": "done"
    },
    {
      "id": "R259",
      "text": "«Сравнение — одной фразой. «Смотри: в начале — «…». Сейчас — «…». Ты прошёл больше, чем кажется.»»",
      "status": "done"
    },
    {
      "id": "R260",
      "text": "«тесты проверяют: при наличии follow_up выбирается он; без него — day; anchor — только после 3 дней молчания; сгенерированный текст на «ты»; финиш, названный на шаге skill, оказывается первым вариантом.»",
      "status": "done"
    },
    {
      "id": "R261",
      "text": "Тройная отправка: «Клиент генерирует client_msg_id (UUID) на каждое сообщение и блокирует кнопку отправки сразу после нажатия до ответа сервера.»",
      "status": "done"
    },
    {
      "id": "R262",
      "text": "«Сервер хранит client_msg_id у сообщения (уникальный индекс (user_id, client_msg_id)) и на повтор возвращает уже сохранённое сообщение без нового ответа ИИ» — «Тест: три одинаковых запроса с одним client_msg_id создают одно сообщение и оди…",
      "status": "done"
    },
    {
      "id": "R263",
      "text": "«QuoteChip отрисовывается внутри строки текста (inline), с датой мелким шрифтом рядом или во всплывающей подсказке, а не отдельным блоком» — «читается одной фразой на ширине 375 px»",
      "status": "done"
    },
    {
      "id": "R264",
      "text": "«Все строки интерфейса, i18n и шаблоны ИИ — на «ты» (английская версия — обычное you). Промпты требуют «ты»» — «Поиск по i18n не находит обращений на «вы»»",
      "status": "done"
    },
    {
      "id": "R265",
      "text": "«Если tests/eval/dialogs.yaml и scripts/eval_dialogs.py уже есть, переделать их» — заготовка на 20 многоходовых сценариев (3–6 сообщений человека) и 10 сценариев дистресса",
      "status": "done"
    },
    {
      "id": "R266",
      "text": "Обязательные типы сценариев: достижение; тяжёлый день; сомнение в прогрессе; проблема, не связанная с целью; резкая смена темы; интересное событие; возвращение после молчания; просьба о совете",
      "status": "done"
    },
    {
      "id": "R267",
      "text": "«В каждом сценарии — заранее подготовленная память (цель, факты с цитатами и датами, нити) … первые 3 сценария агент пишет сам по примерам из изменения 1, остальные — заготовки с TODO(owner).»",
      "status": "done"
    },
    {
      "id": "R268",
      "text": "«Прогоняет каждый сценарий целиком через настоящую модель с той же сборкой контекста, что в приложении, и сохраняет ответы.»",
      "status": "done"
    },
    {
      "id": "R269",
      "text": "«Умеет прогнать одни и те же сценарии с двумя версиями промпта (--prompt-a, --prompt-b) или двумя моделями (--model-a, --model-b) … и вывести ответы рядом.»",
      "status": "done"
    },
    {
      "id": "R270",
      "text": "«Строит HTML- или Markdown-отчёт для ручной оценки по пяти критериям от 1 до 5» (попадание в контекст, естественность, работа с памятью, отсутствие шаблонности, полезность)",
      "status": "done"
    },
    {
      "id": "R271",
      "text": "«Автоматически проверяет только жёсткие вещи: формат, известные fact_id, ожидаемый уровень безопасности в сценариях дистресса.»",
      "status": "done"
    },
    {
      "id": "R272",
      "text": "«Рядом с текстом выводит диагностику: долю ответов с вопросом, среднюю длину, упоминания цели без повода. Это не оценка»",
      "status": "done"
    },
    {
      "id": "R273",
      "text": "«Прогнать их со старым промптом и сохранить отчёт как точку отсчёта.» (порядок, шаг 2)",
      "status": "done"
    },
    {
      "id": "R274",
      "text": "«Повторный прогон эталонных диалогов и отчёт со сравнением «старый промпт → новый». Отправить отчёт владельцу и дождаться его оценки, прежде чем продолжать.» (шаг 5)",
      "status": "done"
    },
    {
      "id": "R275",
      "text": "Порядок выполнения: баги → эталонные диалоги → промпт → контекст → повторный прогон → память → сообщения ИИ первым и первый разговор → документация",
      "status": "done"
    },
    {
      "id": "R276",
      "text": "«Документация: обновить DOCUMENTATION.md — промпт, сборку контекста, новые поля и эндпоинты.»",
      "status": "done"
    },
    {
      "id": "R277",
      "text": "«Если после шага 5 разговор всё ещё звучит плоско … прогнать те же сценарии с двумя-тремя моделями … Архитектуру памяти до этого не трогать.»",
      "status": "done"
    },
    {
      "id": "R278",
      "text": "Конфигурация: CHAT_REASONING_EFFORT low → medium; CONTEXT_RECENT_TOKENS = 6000; CONTEXT_RECENT_MIN_DAYS = 2; REPLY_MAX_WORDS — удалить",
      "status": "done"
    },
    {
      "id": "R279",
      "text": "«Цитаты в ответах — только через плейсхолдеры, которые отрисовывает код; модель не пишет цитаты сама.» · «Ни один факт не сохраняется без проверки verify.py.»",
      "status": "done"
    },
    {
      "id": "R280",
      "text": "«Не придумывай номера служб помощи, юридические формулировки и содержание сценариев за владельца там, где стоит TODO(owner).»",
      "status": "done"
    },
    {
      "id": "R281",
      "text": "«Не удаляй данные пользователей и не меняй схему аутентификации без согласия владельца.» · «Не добавляй платные внешние сервисы.»",
      "status": "done"
    },
    {
      "id": "R282",
      "text": "«Остановись и спроси владельца, если для выполнения пункта нужно изменить что-то, чего нет в этом документе и прошлом задании.»",
      "status": "done"
    },
    {
      "id": "R283i",
      "text": "(подразумевается) строки сервера (texts.py: протокол безопасности, первый разговор, письма, push) тоже переходят на «ты» — бриф прямо называет только интерфейс, i18n и шаблоны ИИ",
      "status": "done"
    },
    {
      "id": "G02",
      "text": "«в диалоге мы используем ты как более дружескую часть. Когда к примеру пользователю приходит сообщение на почту, там мы всегда используем вы» · «Пусть все будет на вы кроме диалога» · «логика с перефразировкой для обоих родов это классно»",
      "status": "done"
    },
    {
      "id": "G03",
      "text": "«обрыв сети посреди ответа предлагает повторить уже сохранённое сообщение» (хвост прошлой сборки) — взять",
      "status": "done"
    },
    {
      "id": "G04",
      "text": "«Шаг «во сколько написать» первого разговора принимает ответ с цифрой не по теме («уровень B1») как час 01:00 без переспроса» (хвост прошлой сборки) — взять",
      "status": "done"
    },
    {
      "id": "G05",
      "text": "«Лендинг вообще не трогай он нормально написан»",
      "status": "done"
    }
  ],
  "gates": {
    "G1": {
      "ok": false,
      "at": "2026-10-27T18:07:05+05:00",
      "open": 76,
      "total": 288
    },
    "G2": {
      "ok": true,
      "at": "2026-10-27T18:19:39+05:00",
      "found": 5,
      "fixed": 5,
      "deferred": 0
    },
    "G3": {
      "ok": true,
      "at": "2026-10-27T18:22:06+05:00",
      "problems": 0
    },
    "G4": {
      "ok": false,
      "at": "2026-10-27T22:39:10+05:00",
      "checked": 23,
      "matched": 20
    }
  },
  "result": "v2.1: живой разговор на gpt-6-sol, память о жизни с разделом «Что я помню», ИИ пишет первым как приглашение",
  "report": [
    "Путь этапа 5 в браузере 375 px не проверен глазами: в сессии нет инструмента браузера. Путь пройден тестом через API, чек-лист «пройти руками» — в docs/v2/stages.md",
    "Telegram: вебхук владелец регистрирует сам (setWebhook с секретом) — шаги в docs/v2/stages.md",
    "Импорт v1 (scripts/import_v1.py) был сделан и проверен на этапе 1, а на этапе 10 удалён вместе с таблицами v1: миграции 0014 и 0015 проходят одним запуском при деплое, и импорт негде запускать; пользователей v1 нет",
    "Первый деплой v2 на базу v1 удалит таблицы v1 с их данными (DOCUMENTATION.md §14)",
    "Текст лендинга — черновик, нужно согласовать",
    "Загрузка аудио любого размера сначала целиком пишется во временные файлы, лимит MAX_AUDIO_MB проверяется только после (routers/conversations.py:60) — стоит отсекать по Content-Length",
    "Шаг «финиш» первого разговора принимает любой текст как финиш — «не по теме» там не ловится",
    "Извлечение памяти при постоянной ошибке модели повторяется без ограничения попыток (расход)",
    "Месячная сводка собирается только 1-го числа: если сервер лежал весь день, месяц пропускается; thin-сводка тоже шлёт «Сводка готова», ссылка ведёт на /today",
    "outreach не пишет тем, кто не завершил первый разговор — подтвердите, что так и задумано",
    "Telegram: повторные апдейты не дедуплицируются по update_id; голосовой ответ боту не покрыт тестом",
    "POST /api/events принимает любые типы, включая серверные (outreach_sent, safety_flag) — статистику можно исказить",
    "PATCH /api/auth/me с null в outreach_channel/timezone/locale даёт 500 на Postgres",
    "Страна, выбранная вручную, перезаписывается при смене часового пояса, если совпала со страной старого пояса",
    "Имена FK в models.py и миграции 0014 расходятся (goals, threads) — drop_all на Postgres и autogenerate спотыкаются",
    "Без .env с JWT_SECRET не стартуют и alembic, и скрипты; локальный docker-compose требует JWT_SECRET",
    "Средняя стоимость разговора в админке не включает фоновые вызовы модели",
    "mail.py: тексты писем переписаны под v2 (модуль из «Оставить как есть»), на «вы»",
    "Первый разговор пишет model_name даже на шагах без вызова модели",
    "Фронтенд: обрыв сети посреди ответа предлагает «повторить» уже сохранённое сообщение (дубль или 409); уход со «Сегодня» не прерывает поток",
    "Фронтенд: если обновление токена не удалось посреди сессии, экран не уводит на /login",
    "Фронтенд: быстрый ответ во время записи голоса молча теряет запись",
    "Фронтенд: неверная дата в /history/foo или /progress/monthly/foo роняет страницу (RangeError)",
    "Фронтенд: выгрузка без сети зависает в «выгружаем»; PlayAudio молчит при ошибке загрузки",
    "Фронтенд: «Позже» в предложении уведомлений показывает «Уведомления не включились»; aria-label цитаты прячет саму цитату; поиск показывает старые результаты во время нового запроса",
    "Фронтенд: lib/types.ts держит Criterion и Goal.criteria, которых API больше не шлёт; window.open для t.me не обнуляет opener",
    "Лендинг (черновик): «стоял прежде… его собственные даты» в тексте для скринридера — формы с родом",
    "Тема: ручное переключение темы меняет только первую meta theme-color — полоса браузера может остаться цвета системной темы (lib/theme.ts)",
    "Точка отсчёта эталонов: OPENAI_API_KEY в локальном .env отклонён OpenAI (401) — прогон не состоялся; снимается позже из коммита T13 (git worktree), после того как владелец обновит ключ",
    "Если повтор сообщения совпадает с первой отправкой до миллисекунды (две вкладки), второй может получить «ИИ ещё отвечает» вместо тихого повтора; такие повторы не попадают в аналитику (conversation.py:286-326, 590-614)",
    "На каждый ответ из базы читается вся недавняя история до 24 000 сообщений — у давних пользователей это лишняя нагрузка; читать порциями (conversation.py:305)",
    "Если связь оборвалась и ответ ИИ не получился, «Повторить» больше не даёт нового ответа на это сообщение — нужно написать заново (conversation.py:537-553)",
    "Окно удаления факта обещает «больше не будет использоваться», но прошлые ответы с цитатой остаются и модель их видит в недавнем разговоре — уточнить текст (lib/i18n.ts:612, en :302)",
    "Три сохранённых отчёта эталонов со старой таблицей оценок; скрипт исправлен — для оценки перезапустить",
    "Тест тона test_v2_dialogue_tone.py:80-99 проверяет старый промпт v2.0; новый покрыт другим тестом"
  ]
}
