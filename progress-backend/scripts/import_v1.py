"""Carry v1 check-ins over into v2 conversations and verified facts.

    python scripts/import_v1.py                      # DATABASE_URL from .env
    python scripts/import_v1.py --database-url URL

What it does (brief, "Импорт данных v1"):

1. Every `entries` row with status `done` becomes a user message (`raw_transcript`, its
   audio and `source`) in the conversation of its `local_date` (`kind=daily`,
   `started_by=user`), created or found.
2. `wins` become `achievement` facts, `friction` becomes `struggle`, and
   `activities.quote` becomes `achievement` unless that quote is already a fact of the
   same message. `intentions` are not carried over.
3. Every quote is checked again with services/verify.py against the message text; one
   that fails is skipped and counted.
4. The goal with its `why_text` stays as it is and is the anchor goal. A person with
   imported history and an active goal is marked `first_conversation_done`, so v2 does
   not walk them through onboarding again, and their `skill` defaults to the goal title.
5. A summary is printed at the end.

Idempotent: a conversation is matched by (user, local_date), a message by its text
inside that conversation, a fact by its normalised quote inside that message. A second
run creates nothing.

The v1 tables are read with plain SQL (`text()`), not through the v1 ORM models, so
this keeps working after those models are deleted, and it never writes to them.
Imported conversations are marked as already processed by memory extraction: their
facts come from v1, and running the model over months of history would cost money for
facts that are already there.
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import Date, DateTime, Float, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.models import Conversation, Fact, Goal, JsonB, Message, PgUUID, User  # noqa: E402
from app.services import verify  # noqa: E402

FACT_TEXT_MAX = 300
SKILL_MAX = 120

ENTRIES = text(
    "SELECT id, user_id, local_date, source, raw_transcript, audio_path, audio_mime,"
    " audio_seconds, detected_language, wins, friction, created_at"
    " FROM entries WHERE status = 'done'"
    " ORDER BY user_id, local_date, created_at"
).columns(
    id=PgUUID,
    user_id=PgUUID,
    local_date=Date,
    audio_seconds=Float,
    wins=JsonB,
    friction=JsonB,
    created_at=DateTime(timezone=True),
)

ACTIVITY_QUOTES = text(
    "SELECT a.entry_id, a.category, a.quote FROM activities a"
    " JOIN entries e ON e.id = a.entry_id"
    " WHERE e.status = 'done' AND a.quote IS NOT NULL"
    " ORDER BY a.created_at"
).columns(entry_id=PgUUID)


@dataclass
class ImportSummary:
    conversations: int = 0
    messages: int = 0
    facts: int = 0
    dropped_quotes: int = 0

    def __str__(self) -> str:
        return (
            f"conversations created: {self.conversations}\n"
            f"messages created:      {self.messages}\n"
            f"facts created:         {self.facts}\n"
            f"quotes dropped:        {self.dropped_quotes} (not found in the message text)"
        )


def _items(raw) -> list[tuple[str, str]]:
    """(text, quote) from a wins/friction list, skipping anything malformed."""
    out = []
    for item in raw or []:
        if isinstance(item, dict) and isinstance(item.get("quote"), str) and item["quote"].strip():
            label = item.get("text") if isinstance(item.get("text"), str) else ""
            out.append(((label or item["quote"]).strip(), item["quote"].strip()))
    return out


async def _conversation(db: AsyncSession, user_id, local_date, created_at, summary) -> Conversation:
    found = (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id, Conversation.local_date == local_date
            )
        )
    ).scalar_one_or_none()
    if found is None:
        found = Conversation(
            user_id=user_id,
            local_date=local_date,
            kind="daily",
            started_by="user",
            state={},
            counts_for_limit=True,
            memory_extracted_at=datetime.now(timezone.utc),
            created_at=created_at,
        )
        db.add(found)
        await db.flush()
        summary.conversations += 1
    return found


async def _message(db: AsyncSession, conversation: Conversation, entry, summary) -> Message:
    transcript = entry.raw_transcript
    found = (
        await db.execute(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == "user",
                Message.content_raw == transcript,
            )
        )
    ).scalars().first()
    if found is None:
        found = Message(
            conversation_id=conversation.id,
            user_id=entry.user_id,
            role="user",
            source=entry.source if entry.source in ("voice", "text") else "text",
            content_raw=transcript,
            content=[{"type": "text", "text": transcript}],
            audio_path=entry.audio_path,
            audio_mime=entry.audio_mime,
            audio_seconds=entry.audio_seconds,
            detected_language=entry.detected_language,
            created_at=entry.created_at,
        )
        db.add(found)
        await db.flush()
        summary.messages += 1
    # A day v2 already had (an AI message nobody answered) now has a message from them.
    conversation.counts_for_limit = True
    return found


async def _import(db: AsyncSession) -> ImportSummary:
    summary = ImportSummary()
    activity_quotes: dict[uuid.UUID, list[tuple[str, str]]] = {}
    for row in (await db.execute(ACTIVITY_QUOTES)).all():
        if row.quote and row.quote.strip():
            activity_quotes.setdefault(row.entry_id, []).append(
                ((row.category or row.quote).strip(), row.quote.strip())
            )

    users: set[uuid.UUID] = set()
    for entry in (await db.execute(ENTRIES)).all():
        if not (entry.raw_transcript or "").strip():
            continue
        users.add(entry.user_id)
        conversation = await _conversation(
            db, entry.user_id, entry.local_date, entry.created_at, summary
        )
        message = await _message(db, conversation, entry, summary)

        transcript_norm = verify.normalize(entry.raw_transcript)
        known = {
            verify.normalize(quote)
            for quote in (
                await db.execute(select(Fact.quote).where(Fact.message_id == message.id))
            ).scalars()
        }
        candidates = (
            [("achievement", label, quote) for label, quote in _items(entry.wins)]
            + [("struggle", label, quote) for label, quote in _items(entry.friction)]
            + [("achievement", label, quote) for label, quote in activity_quotes.get(entry.id, [])]
        )
        for fact_type, label, quote in candidates:
            if not verify.quote_supported(quote, transcript_norm):
                summary.dropped_quotes += 1
                continue
            key = verify.normalize(quote)
            if key in known:
                continue
            known.add(key)
            db.add(
                Fact(
                    user_id=entry.user_id,
                    message_id=message.id,
                    origin="import_v1",
                    local_date=entry.local_date,
                    type=fact_type,
                    text=label[:FACT_TEXT_MAX],
                    quote=quote,
                    created_at=entry.created_at,
                )
            )
            summary.facts += 1
        await db.flush()

    for user_id in users:
        user = await db.get(User, user_id)
        goal = (
            await db.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.is_active.is_(True))
                .order_by(Goal.why_text.is_(None), Goal.created_at.desc())
            )
        ).scalars().first()
        if user is not None and goal is not None:
            user.first_conversation_done = True
            user.skill = user.skill or goal.title[:SKILL_MAX]

    await db.commit()
    return summary


async def run(db_url: str | None = None) -> ImportSummary:
    if db_url is None:
        from app.db import SessionLocal

        async with SessionLocal() as db:
            return await _import(db)

    engine = create_async_engine(db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            return await _import(db)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL")
    args = parser.parse_args()
    url = args.database_url
    if url:
        from app.config import Settings

        url = Settings.use_async_driver(url)
    summary = asyncio.run(run(url))
    print(summary)


if __name__ == "__main__":
    main()
