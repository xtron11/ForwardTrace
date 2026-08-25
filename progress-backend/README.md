# Progress API

Backend for the progress-report MVP: minimal daily input by voice, verified extraction,
one weekly report that shows evidence of change.

The hypothesis under test is not technical. It is whether a person will keep giving a
small amount of input in exchange for proof they are moving. Everything here is shaped
to answer that and nothing more.

## Run it

```bash
cp .env.example .env
# set JWT_SECRET (openssl rand -hex 32), DEEPGRAM_API_KEY, ADMIN_EMAILS
docker compose up -d db
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`. Health check at `/health` reports
which providers are wired up.

The end-to-end test runs against SQLite with the AI providers mocked, so it needs no
API keys and no database server:

```bash
python smoke_test.py
```

## Providers

Both AI dependencies sit behind one interface each, chosen in `.env`.

**Speech to text** — `STT_PROVIDER`

| Value | What it is | Speed on 60s audio | Cost |
|---|---|---|---|
| `deepgram` | Nova-3 batch, purpose-built STT | under a second | $0.0043/min, $200 starting credit (~46,000 min) |
| `local` | faster-whisper on your machine | 8–30s on CPU by model size | free, needs ffmpeg |

At ten users recording a minute a day, the Deepgram starting credit lasts years and no
card is required. Switch to `local` if you would rather keep audio off third-party
infrastructure; nothing else in the code changes.

**Language model** — `LLM_PROVIDER`: `ollama` (local, free, 5–20s per call) or `openai`
(pennies per month at this volume). Use `qwen2.5:7b-instruct` or larger with Ollama —
3B models are not reliable at structured extraction.

## How a check-in flows

```
POST /api/entries/voice
  -> save audio, create entry, return 202 + entry_id     (immediate)
  -> background: speech to text
  -> background: extraction under a JSON schema
  -> background: verify every fact against the transcript
  -> background: write verified facts as activity rows
GET /api/entries/{id}   (client polls until status leaves pending/processing)
```

Nothing long-running happens inside a request. A mobile connection will not hold open
for thirty seconds, and neither will most proxies.

## Where the numbers come from

The language model never does arithmetic. `services/aggregate.py` computes every total,
count and streak in SQL, and the model receives them as read-only input. A model asked
to add up a week of durations will get it wrong occasionally and you will not notice.

## Why the reports do not regenerate

A report is built once and stored. Requesting the same period returns the same text.
It is a research artefact: if it rewrites itself on every refresh, you cannot compare
what one user saw against what another user saw, and you cannot trust the feedback
attached to it.

## Guards against invented facts

Four layers, in order of how much they actually do:

1. **JSON schema as a grammar.** Ollama's `format` and OpenAI's `json_schema` constrain
   the sampler. Malformed output is not a possibility, so no parsing heuristics are needed.
2. **Quote verification.** Every extracted fact must carry a verbatim span from the
   transcript. `services/verify.py` checks it is really there, allowing for speech-to-text
   noise. Anything unverifiable is discarded before it reaches the database, and the count
   lands in `entries.dropped_facts`. This is the layer that does the heavy lifting: it is
   a check, not a request.
3. **`minutes_explicit`.** If a duration was not spoken aloud, minutes are stored as NULL.
   Otherwise the model quietly rounds every session to a plausible number and your weekly
   totals become fiction.
4. **Separation of stages.** The daily extractor sees one short transcript. The weekly
   narrator never sees raw transcripts at all — only verified facts and computed numbers.

Report output is validated too: invented criterion ids are dropped, a claim of evidence
with no evidence attached is downgraded to `no_evidence`, and a behavioural pattern
cannot be asserted with confidence on fewer than four logged days.

## Timezones

`users.timezone` holds an IANA name, sent by the browser as
`Intl.DateTimeFormat().resolvedOptions().timeZone`. Every entry stores both `created_at`
(the real instant) and `local_date` (the user's day), and all grouping uses `local_date`.

Without this, a check-in at 23:40 in Los Angeles is recorded as the following day,
streaks break, and week boundaries land in different places for different users.

## Concierge mode

Before automating the analysis, confirm that a genuinely good report is something people
want. `PUT /api/admin/reports/{id}/content` replaces a generated report with one you
wrote by hand, flagged `generated_by: human`. If a hand-written report also gets a shrug,
the problem is the product, not the model.

`GET /api/admin/entries` shows every transcript next to what was extracted from it and
what the verifier rejected. Read these weekly. `GET /api/admin/overview` gives
retention, latency and the feedback distribution at a glance.

## Endpoints

| | |
|---|---|
| `POST /api/auth/register`, `/login`, `/refresh` | JWT access + refresh |
| `POST /api/auth/change-password`, `/logout-everywhere` | bumps `token_version`, invalidating issued tokens |
| `GET`/`PATCH /api/auth/me` | profile, timezone, intake answers |
| `POST /api/goals/suggest-criteria` | AI suggestions the user is free to reject |
| `POST`/`GET`/`PATCH /api/goals` | goal, motivation, criteria |
| `POST /api/entries/voice` | 202, processed in background |
| `POST /api/entries/text` | typed fallback |
| `POST /api/entries/transcribe` | synchronous, for the onboarding "why" field only |
| `GET /api/entries`, `/{id}`, `POST /{id}/retry` | timeline, polling, recovery |
| `POST /api/reports`, `GET /latest`, `/{id}` | generate once, then cached |
| `POST /api/reports/{id}/feedback` | the research instrument |
| `POST /api/events` | client-side telemetry |
| `/api/admin/*` | concierge tools, gated by `ADMIN_EMAILS` |

## Schema changes

Alembic owns the schema. After changing a model:

```bash
alembic revision --autogenerate -m "what changed"
# read the generated file before running it - autogenerate is a good first draft,
# not a finished migration
alembic upgrade head
```

`create_all` is not used, because it can only create missing *tables*. A column added to
an existing table is silently skipped, and the failure surfaces later as a 500 on
whichever endpoint touches it. Startup now checks the schema against the models and
refuses to boot with one readable line instead.

An existing database created before Alembic was introduced should be marked as already
at the baseline, then upgraded:

```bash
alembic stamp 0001_baseline
alembic upgrade head
```

## Before real users

- `AUTO_CREATE_TABLES` is off and should stay off outside tests.
- Audio is stored on local disk under `AUDIO_DIR`. Move to object storage when you
  outgrow one machine.
- Background tasks run in-process, which is right for ten users. If a deploy restarts
  mid-task the entry stays `pending` — `POST /api/entries/{id}/retry` recovers it.
  Reach for a real queue when that stops being acceptable, not before.
- There is no password reset flow yet. With ten hand-picked users, reset it yourself.
- Rate limiting is absent. Add it before the signup page is public.
