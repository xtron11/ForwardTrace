# Deploying

One small VPS runs the database, the API and a reverse proxy. The frontend goes on
Vercel's free tier. Total cost is about €4/month plus roughly $0.30 of API usage — no
domain purchase required to start.

---

## 1. A server

Any provider works. Hetzner CX22 (2 vCPU, 4 GB, ~€4/mo) is more than enough: the model
runs on OpenAI's hardware, not yours, so the box only shuttles bytes.

Pick Ubuntu 24.04. When it is up, connect and install Docker:

```bash
ssh root@YOUR_SERVER_IP
curl -fsSL https://get.docker.com | sh
```

Do not skip this: create a non-root user and disable password login later. A server
with an open SSH port is found by scanners within minutes of existing.

---

## 2. A hostname, for free

The API needs HTTPS, because a browser will not grant microphone access over plain
HTTP, and an HTTPS page cannot call an HTTP API. HTTPS needs a hostname.

[DuckDNS](https://www.duckdns.org) gives one away. Sign in, create a subdomain, point it
at your server's IP. You get something like `forwardtrace.duckdns.org`, and Let's
Encrypt issues certificates for it happily.

Buy a real domain later, when the product has earned it. For sending to friends a
DuckDNS address is fine; for posting in public it looks like what it is, and some
people will not sign up to something that looks temporary.

---

## 3. The backend

```bash
git clone https://github.com/YOU/forwardtrace.git
cd forwardtrace/progress-backend
cp .env.example .env
nano .env
```

Set these:

```bash
POSTGRES_PASSWORD=       # openssl rand -hex 16
JWT_SECRET=              # openssl rand -hex 32   (a NEW one, not your local value)
API_DOMAIN=forwardtrace.duckdns.org
DEEPGRAM_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
ADMIN_EMAILS=you@example.com
CORS_ORIGINS=https://your-app.vercel.app
AUTO_CREATE_TABLES=false
```

`CORS_ORIGINS` must be the exact frontend URL, scheme included. A mismatch here is the
most common reason a deployed frontend cannot talk to its backend, and the browser
reports it as a network error rather than as the CORS refusal it is.

Then:

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api
```

Migrations run automatically on start. Wait for the certificate (a few seconds), then:

```bash
curl https://forwardtrace.duckdns.org/health
```

Expect `{"api":"ok","database":"ok","stt_provider":"deepgram","llm_model":"gpt-5.6-luna"}`.

---

## 4. The frontend

On Vercel: **Add New → Project**, import the repository, and set

- Root Directory: `progress-frontend`
- Environment variable: `NEXT_PUBLIC_API_URL` = `https://forwardtrace.duckdns.org`

Deploy. You get `your-app.vercel.app` with HTTPS included.

If you set `CORS_ORIGINS` before knowing the Vercel URL, go back and correct it now,
then `docker compose -f docker-compose.prod.yml restart api`.

---

## 5. Backups

Skipping this is the mistake you only make once. Once ten people have a month of
check-ins, losing the volume means losing the experiment, not just the data.

```bash
# /root/backup.sh
docker compose -f /root/forwardtrace/progress-backend/docker-compose.prod.yml \
  exec -T db pg_dump -U progress progress | gzip > /root/backups/$(date +%F).sql.gz
find /root/backups -name '*.sql.gz' -mtime +14 -delete
```

```bash
mkdir -p /root/backups && chmod +x /root/backup.sh
crontab -e   # 0 3 * * * /root/backup.sh
```

A backup nobody has restored is a hope, not a backup. Try it once:

```bash
gunzip -c /root/backups/SOME_DATE.sql.gz | head -40
```

---

## 6. Updating

```bash
cd forwardtrace && git pull
cd progress-backend
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations apply on start. The frontend redeploys itself when you push.

---

## What this setup deliberately does not have

**Only Caddy is exposed.** Postgres and the API have no published ports, so neither is
reachable from the internet — only from inside the compose network.

**One API worker.** Background tasks run in-process; a second worker would duplicate
every scheduled job. Fine well past ten users, and the point where that stops being
true is the point where a real task queue is worth having.

**No monitoring.** For ten users, `docker compose logs` and `GET /api/admin/overview`
are enough, and the latter shows what actually matters: entries per user, latency, how
many facts the verifier rejected, and the feedback distribution.

**Open registration.** Anyone with the URL can sign up, held in check only by the daily
quotas. Before posting the link anywhere public, add invite codes — they also filter for
people who will actually answer your questions at the end of the week.
