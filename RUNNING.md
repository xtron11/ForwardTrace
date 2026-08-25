# Running the whole thing

Two processes: the API on `:8000`, the web app on `:3000`. Postgres in Docker.

Assumed: Python 3.11+, Node 20+, Docker.

---

## 1. Keys

You need two, both free to obtain.

**Deepgram** (speech to text) — sign up at `console.deepgram.com`, copy the API key.
New accounts get $200 of credit and no card is required. At ten users recording a minute
a day that is roughly 300 minutes a month, so the credit outlasts the experiment.

**A language model.** Two options:

- *Ollama, local and free.* Install from `ollama.com`, then `ollama pull qwen2.5:7b-instruct`.
  Needs about 8 GB of RAM. Expect 5–20 seconds per call on CPU. Do not substitute a 3B
  model — they are unreliable at structured extraction and that is the one job here.
- *OpenAI.* Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`. Costs cents per month at
  this volume.

Start with Ollama. If extraction quality disappoints, switch providers by editing one
line — nothing else in the code changes.

---

## 2. Database

```bash
cd progress-backend
docker compose up -d db
docker compose ps          # wait for "healthy"
```

---

## 3. Backend

```bash
cd progress-backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` and set four things:

```bash
JWT_SECRET=          # openssl rand -hex 32
DEEPGRAM_API_KEY=    # from step 1
ADMIN_EMAILS=you@example.com   # the account that may read /api/admin/*
LLM_PROVIDER=ollama
```

Run it:

```bash
uvicorn app.main:app --reload
```

Confirm it is wired up:

```bash
curl localhost:8000/health
# {"api":"ok","database":"ok","stt_provider":"deepgram","llm_provider":"ollama"}
```

If `database` is not `ok`, Postgres has not finished starting. Interactive API docs are
at `http://localhost:8000/docs`.

Tables are created on first start (`AUTO_CREATE_TABLES=true`). See "Before real users"
at the end.

---

## 4. Frontend

New terminal:

```bash
cd progress-frontend
cp .env.local.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open `http://localhost:3000`.

The first build downloads three typefaces from Google Fonts. Behind a restrictive proxy
this fails — swap `next/font/google` for `next/font/local` in `app/layout.tsx`.

---

## 5. Walk through it once

1. Create an account. The browser's timezone is sent automatically and every "day" and
   "week" boundary is computed from it.
2. Set a goal, say why it matters, pick what progress means.
3. Record a check-in. Say something with a duration in it — *"I coded for about two hours
   and finished the API"* — so you can see `minutes_explicit` working.
4. The card that comes back shows each extracted fact above the words it came from.

Then check what the verifier did:

```bash
curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/admin/entries | python -m json.tool
```

`dropped_facts` counts claims the model made that could not be traced to your transcript.
They were discarded. If this is above zero often, read those transcripts — either the
model is drifting or your speech-to-text is mangling words.

---

## 6. The report

A report needs seven days elapsed since the goal started, and at least three check-ins.
While testing you will not want to wait a week:

```bash
curl -X POST localhost:8000/api/reports \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"period_end": "2026-08-19"}'
```

Passing `period_end` explicitly builds the seven days ending on that date. Or lower
`MIN_ENTRIES_FOR_REPORT` in `.env` and back-date a few check-ins.

To get a token for these calls:

```bash
curl -s -X POST localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}' | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])"
```

---

## Running the tests

The backend test uses SQLite and mocks both AI providers, so it needs no keys and no
database server:

```bash
cd progress-backend && python smoke_test.py
```

It asserts, among other things, that a deliberately hallucinated activity is rejected by
the quote check and that a fabricated criterion id is dropped from the report.

---

## Concierge mode

Before automating the analysis, find out whether a genuinely good report is something
people want. Overwrite a generated report with one you wrote yourself:

```bash
curl -X PUT localhost:8000/api/admin/reports/$REPORT_ID/content \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"content": {"what_you_did": "...", "what_changed": [{"text":"...","evidence":"..."}],
       "pattern": {"text":"...","confidence":"high"}, "friction":"...",
       "recommendation":"...", "closing":"...", "criteria_progress":[], "criteria_labels":{}}}'
```

It is stored with `generated_by: "human"` and the report screen labels it. If a
hand-written report also gets a shrug, the problem is the product, not the model — and
you have learned that without building anything else.

`GET /api/admin/overview` gives entries per user, average latency, how many facts the
verifier rejected, and the feedback distribution.

---

## Deploying for the ten users

The cheapest arrangement that works: one small VPS running `docker compose up` for the
API and Postgres, and the frontend on Vercel's free tier pointed at it.

Three things to change before anyone real signs up:

- Set `CORS_ORIGINS` to the deployed frontend URL, not `localhost:3000`.
- Put the API behind HTTPS. Tokens travel in headers and audio in request bodies.
- Set `AUTO_CREATE_TABLES=false` and switch to Alembic. Right now the schema is created
  from the models at startup, which is fine while the database is disposable and stops
  being fine the moment it holds someone's month of check-ins.

Also absent by design, and worth adding when the signup page is public: rate limiting,
and a password reset flow. With ten hand-picked users you can reset a password yourself.
