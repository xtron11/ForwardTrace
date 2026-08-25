# Evidence — frontend

Next.js 16 (App Router) + TypeScript + Tailwind v4. Six screens against the Progress API.

```bash
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_URL at the backend
npm install
npm run dev
```

The first build fetches the three typefaces from Google Fonts and caches them. On a
machine without outbound access to `fonts.googleapis.com`, swap `next/font/google` in
`app/layout.tsx` for `next/font/local` and vendor the files.

## Screens

| Route | Job |
|---|---|
| `/` | The thesis: a claim next to the words it came from |
| `/register`, `/login` | Account, plus the browser's timezone |
| `/setup` | Goal, why it matters (typed or spoken), what progress means |
| `/today` | The record button, then what was extracted |
| `/timeline` | Every check-in, with the transcript behind a disclosure |
| `/report` | The weekly report and the feedback question |

## Design

**Palette.** Ledger paper `#EDEFE8`, petrol ink `#1B2A2F`, card `#FAFBF7`, deep green
`#2F5D50` for actions, chartreuse `#C9E265` for the marker.

**Type.** Bricolage Grotesque for headings, Source Serif 4 for reading, JetBrains Mono for
quotes and figures. Serif body under a grotesque display inverts the usual pairing, on the
grounds that the report is the product and the report is something you read.

**The signature is the highlighter.** `.mark` in `globals.css` draws a marker swipe, and
it is used in exactly one situation: verbatim speech from the transcript. Model-written
prose — the report's `evidence` lines — gets italic serif behind a left rule instead. The
distinction is load-bearing. The backend goes to some trouble to separate what you said
from what a model inferred, and the interface would undo that work by styling them alike.

Two things deliberately absent, per the product brief: no streaks and no score. The week
strip on the report states days logged out of days elapsed and stops there.

## Notes for whoever picks this up

**Recording.** `lib/useRecorder.ts` negotiates a container rather than assuming one.
Chrome and Firefox give webm/opus, iOS Safari only gives mp4/aac, and hardcoding webm
means every iPhone silently fails. The backend accepts both.

**Polling, not waiting.** Check-ins return `202` with an id. `pollUntilSettled` in
`lib/api.ts` polls until the entry leaves `pending`/`processing`. Nothing holds a request
open, because mobile connections and proxies will not.

**Token refresh.** A `401` triggers one refresh attempt and one retry. Concurrent 401s
share a single in-flight refresh so they don't each rotate the token and invalidate
each other.

**Typing is a first-class path.** Some people check in from an open-plan office. `/today`
offers it below the fold and it goes through the same extraction pipeline.
