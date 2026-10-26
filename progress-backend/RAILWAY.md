# Deploying on Railway

No server to administer, no SSH, no certificates. Railway builds the Dockerfile from
your repository, runs a managed Postgres next to it, and hands out an HTTPS address.
Roughly $5/month, which is the plan minimum rather than the usage.

If you would rather run your own VPS, `DEPLOY.md` covers that. This is the shorter path.

---

## 1. The API

At [railway.com](https://railway.com), sign in with GitHub, then **New Project → Deploy
from GitHub repo** and pick your repository.

Railway will try to build from the repository root and find nothing. Open the service,
go to **Settings → Source**, and set:

- **Root Directory:** `progress-backend`

It then finds the Dockerfile and builds. The first build takes a few minutes.

In **Settings → Region**, choose a US region if your users are mostly American. Both
Deepgram and OpenAI run there, so every message makes round trips that get shorter.

---

## 2. The database

In the project canvas: **New → Database → Add PostgreSQL**. That is the whole setup.

Railway injects `DATABASE_URL` into your services automatically. It arrives as
`postgresql://`, which SQLAlchemy would map to a synchronous driver; the app rewrites
it to `postgresql+asyncpg://` on startup, so nothing is needed from you.

Migrations run on every deploy — that is what `docker-entrypoint.sh` does before
starting the server.

---

## 3. Variables

On the API service, **Variables**, add:

```
JWT_SECRET=            # generate a NEW one, not your local value
DEEPGRAM_API_KEY=      # same key as local
OPENAI_API_KEY=        # same key as local
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=low
STT_PROVIDER=deepgram
STT_LANGUAGE=
ADMIN_EMAILS=you@example.com
AUTO_CREATE_TABLES=false
CORS_ORIGINS=https://your-app.vercel.app
```

Generate the secret locally with `python -c "import secrets; print(secrets.token_hex(32))"`.

Leave `CORS_ORIGINS` as a placeholder for now; you will not know the frontend URL until
the next step.

---

## 4. A public address

**Settings → Networking → Generate Domain.** You get something like
`forwardtrace-production.up.railway.app`, with HTTPS already working.

Check it:

```
https://YOUR-APP.up.railway.app/health
```

Expect `{"api":"ok","database":"ok"}`. Which speech-to-text provider and model the server
picked up is shown to admins only: `/admin`, or `GET /api/admin/overview`.

If `database` is not ok, open **Deployments → View Logs**. A missing migration or a bad
variable says so in one line — the app refuses to start on an out-of-date schema rather
than failing later on a request.

---

## 5. Audio storage

**Settings → Volumes → Add Volume**, mount path `/app/data`.

Without this, recordings live in the container filesystem and vanish on every deploy.
They are not needed for the app to work — the transcript is in the database — but being
able to listen back to what someone actually said is half the value of a small test.

---

## 6. The frontend

On [vercel.com](https://vercel.com): **Add New → Project**, import the same repository.

- **Root Directory:** `progress-frontend`
- **Environment variable:** `NEXT_PUBLIC_API_URL` = `https://YOUR-APP.up.railway.app`

Deploy. Then go back to Railway and set `CORS_ORIGINS` to the Vercel URL Vercel gave
you, exactly, including `https://`. The service restarts on its own.

A mismatch here shows up in the browser as a generic network error rather than as the
CORS refusal it is, so it is worth copying rather than typing.

---

## 7. Checks worth doing once

- Sign up and go through the first conversation (skill, why, finish line, where you are
  now), then send a voice message. Microphone access requires HTTPS, which you now have.
- `GET /api/admin/overview` with your admin account: retention, replies to the AI's first
  message, "helped" share, inaccurate quotes, cost per conversation.
- Railway's **Usage** tab after a day, to see what it is actually costing.

---

## Backups

Railway's Postgres has no point-in-time recovery on the default tier, so take your own
dumps. Locally, with the Railway CLI:

```bash
npm i -g @railway/cli
railway login
railway link
railway run pg_dump '$DATABASE_URL' | gzip > backup-$(date +%F).sql.gz
```

Worth doing weekly once real people are using it. A month of someone's conversations is not
reconstructible.

---

## What to know before trusting this

Railway has had real outages, including an eight-hour platform incident in May 2026.
For a ten-person experiment that is an acceptable trade for not administering a server.
If the product survives its first users, revisit the question then — the Dockerfile runs
anywhere, so moving costs a day, not a rewrite.
