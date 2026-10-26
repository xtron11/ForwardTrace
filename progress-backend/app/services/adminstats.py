"""Queries behind the admin panel, on v2 data (conversations, messages, facts, outreach,
events).

They answer research questions, not "show me a table": do people come back (D1 and D7 by
cohort), do they answer the AI's first message, do replies with a quotation help more
than replies without, how often is a quotation called inaccurate, who hit a safety flag,
and what a conversation costs.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Conversation, Event, Fact, Message, Outreach, Pair, Thread, User
from ..time_utils import local_today, tz_of


def _utc(moment: datetime | None) -> datetime | None:
    """SQLite hands timestamps back without a zone."""
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _registered_on(user: User) -> date | None:
    created = _utc(user.created_at)
    return created.astimezone(tz_of(user.timezone)).date() if created else None


async def retention(db: AsyncSession, now: datetime | None = None) -> list[dict]:
    """D1 and D7 by registration week. Dn: the person talked (a counted conversation) on
    the local day N days after registering. Only people for whom that day has already
    come are counted, or the newest cohort would always look empty."""
    now = now or datetime.now(timezone.utc)
    users = (await db.execute(select(User))).scalars().all()
    days: dict[uuid.UUID, set[date]] = {}
    for user_id, day in (
        await db.execute(
            select(Conversation.user_id, Conversation.local_date).where(
                Conversation.counts_for_limit.is_(True)
            )
        )
    ).all():
        days.setdefault(user_id, set()).add(day)

    cohorts: dict[date, dict] = {}
    for user in users:
        start = _registered_on(user)
        if start is None:
            continue
        week = start - timedelta(days=start.weekday())
        row = cohorts.setdefault(week, {"size": 0, "d1": [0, 0], "d7": [0, 0]})  # [back, eligible]
        row["size"] += 1
        today = local_today(user.timezone, now)
        for key, offset in (("d1", 1), ("d7", 7)):
            target = start + timedelta(days=offset)
            if target <= today:
                row[key][1] += 1
                if target in days.get(user.id, ()):
                    row[key][0] += 1
    return [
        {
            "week": week.isoformat(),
            "size": cohorts[week]["size"],
            "d1": _share(*cohorts[week]["d1"]),
            "d1_of": cohorts[week]["d1"][1],
            "d7": _share(*cohorts[week]["d7"]),
            "d7_of": cohorts[week]["d7"][1],
        }
        for week in sorted(cohorts, reverse=True)
    ]


async def outreach_reply_share(db: AsyncSession) -> dict:
    """Of the messages the AI wrote first (and that were delivered), how many were
    answered the same day."""
    sent, replied, opened = (
        await db.execute(
            select(
                func.count(Outreach.id),
                func.count(Outreach.replied_at),
                func.count(Outreach.opened_at),
            ).where(Outreach.delivered.is_(True))
        )
    ).one()
    return {"sent": sent, "replied": replied, "opened": opened, "share": _share(replied, sent)}


async def helped_share(db: AsyncSession) -> dict:
    """Share of "helped" among rated replies, with a quotation and without one."""
    rated = (
        await db.execute(
            select(Message.rating, Message.used_fact_ids).where(
                Message.role == "assistant", Message.rating.isnot(None)
            )
        )
    ).all()
    counts = {"with_quote": [0, 0], "without_quote": [0, 0]}  # [helped, rated]
    for rating, used in rated:
        bucket = counts["with_quote" if used else "without_quote"]
        bucket[1] += 1
        bucket[0] += rating == "helped"
    return {
        key: {"helped": helped, "rated": total, "share": _share(helped, total)}
        for key, (helped, total) in counts.items()
    }


async def flagged_quote_share(db: AsyncSession) -> dict:
    """Of the facts that were shown to people as quotations, how many they called
    inaccurate."""
    used: set[uuid.UUID] = set()
    for (ids,) in (
        await db.execute(
            select(Message.used_fact_ids).where(
                Message.role == "assistant", Message.used_fact_ids.isnot(None)
            )
        )
    ).all():
        for fact_id in ids or []:
            try:
                used.add(uuid.UUID(str(fact_id)))
            except ValueError:
                continue
    flagged = 0
    if used:
        flagged = (
            await db.execute(
                select(func.count(Fact.id)).where(Fact.id.in_(used), Fact.flagged_at.isnot(None))
            )
        ).scalar_one()
    return {"shown": len(used), "flagged": flagged, "share": _share(flagged, len(used))}


async def safety_conversations(db: AsyncSession, limit: int = 100) -> list[dict]:
    """Conversations that reached safety level 2 or 3, newest first, with a link."""
    rows = (
        await db.execute(
            select(Conversation, User.email)
            .join(User, User.id == Conversation.user_id)
            .where(Conversation.safety_level >= 2)
            .order_by(Conversation.local_date.desc(), Conversation.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(c.id),
            "email": email,
            "local_date": c.local_date.isoformat(),
            "level": c.safety_level,
            "url": f"/admin/conversations/{c.id}",
        }
        for c, email in rows
    ]


async def average_conversation_cost(db: AsyncSession) -> dict:
    """Mean USD per conversation (speech-to-text plus every model call), over the
    conversations that have a cost recorded."""
    per_conversation = (
        select(func.sum(Message.cost_usd).label("cost"))
        .group_by(Message.conversation_id)
        .having(func.sum(Message.cost_usd).isnot(None))
        .subquery()
    )
    count, total = (
        await db.execute(select(func.count(), func.coalesce(func.sum(per_conversation.c.cost), 0)))
    ).one()
    return {
        "conversations": count,
        "total_usd": round(float(total), 6),
        "average_usd": round(float(total) / count, 6) if count else None,
    }


async def event_counts(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(Event.type, func.count(Event.id), func.count(func.distinct(Event.user_id)))
            .group_by(Event.type)
            .order_by(func.count(Event.id).desc(), Event.type)
        )
    ).all()
    return [{"type": t, "count": n, "people": p} for t, n, p in rows]


async def overview(db: AsyncSession, now: datetime | None = None) -> dict:
    """The six numbers of the brief (also `GET /api/admin/overview`)."""
    users = (await db.execute(select(func.count(User.id)))).scalar_one()
    return {
        "users": users,
        "retention": await retention(db, now),
        "ai_first": await outreach_reply_share(db),
        "helped": await helped_share(db),
        "flagged_quotes": await flagged_quote_share(db),
        "safety": await safety_conversations(db),
        "cost": await average_conversation_cost(db),
        "stt_provider": settings.stt_provider,
        "llm_model": settings.chat_model or settings.openai_model,
    }


async def user_rows(db: AsyncSession) -> list[dict]:
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    stats = {
        user_id: (days, last)
        for user_id, days, last in (
            await db.execute(
                select(
                    Conversation.user_id,
                    func.count(Conversation.id),
                    func.max(Conversation.local_date),
                )
                .where(Conversation.counts_for_limit.is_(True))
                .group_by(Conversation.user_id)
            )
        ).all()
    }
    costs = dict(
        (
            await db.execute(
                select(Message.user_id, func.sum(Message.cost_usd)).group_by(Message.user_id)
            )
        ).all()
    )
    rows = []
    for user in users:
        days, last = stats.get(user.id, (0, None))
        rows.append(
            {
                "id": str(user.id),
                "email": user.email,
                "skill": user.skill,
                "locale": user.locale,
                "channel": user.outreach_channel,
                "days": days,
                "last": last.isoformat() if last else None,
                "silent_for": (local_today(user.timezone) - last).days if last else None,
                "cost_usd": float(costs.get(user.id) or 0),
            }
        )
    return rows


async def user_detail(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    conversations = (
        await db.execute(
            select(Conversation, func.count(Message.id), func.sum(Message.cost_usd))
            .join(Message, Message.conversation_id == Conversation.id, isouter=True)
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.id)
            .order_by(Conversation.local_date.desc())
        )
    ).all()
    threads = (
        await db.execute(
            select(Thread).where(Thread.user_id == user_id).order_by(Thread.opened_on.desc())
        )
    ).scalars().all()
    facts = (
        await db.execute(select(func.count(Fact.id)).where(Fact.user_id == user_id))
    ).scalar_one()
    pairs = (
        await db.execute(select(func.count(Pair.id)).where(Pair.user_id == user_id))
    ).scalar_one()
    events = (
        await db.execute(
            select(Event.type, func.count(Event.id))
            .where(Event.user_id == user_id)
            .group_by(Event.type)
        )
    ).all()
    return {
        "id": str(user.id),
        "email": user.email,
        "skill": user.skill,
        "locale": user.locale,
        "country": user.country,
        "channel": user.outreach_channel,
        "registered": _registered_on(user),
        "plus_until": user.plus_until,
        "facts": facts,
        "pairs": pairs,
        "threads": [
            {"title": t.title, "status": t.status, "opened_on": t.opened_on, "closed_on": t.closed_on}
            for t in threads
        ],
        "conversations": [
            {
                "id": str(c.id),
                "local_date": c.local_date.isoformat(),
                "kind": c.kind,
                "started_by": c.started_by,
                "safety_level": c.safety_level,
                "messages": n,
                "cost_usd": float(cost or 0),
                "summary": c.summary,
            }
            for c, n, cost in conversations
        ],
        "events": [{"type": t, "count": n} for t, n in sorted(events, key=lambda e: -e[1])],
    }


async def conversation_detail(db: AsyncSession, conversation_id: uuid.UUID) -> dict | None:
    row = (
        await db.execute(
            select(Conversation, User.email)
            .join(User, User.id == Conversation.user_id)
            .where(Conversation.id == conversation_id)
        )
    ).one_or_none()
    if row is None:
        return None
    conversation, email = row
    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
    ).scalars().all()
    return {
        "id": str(conversation.id),
        "user_id": str(conversation.user_id),
        "email": email,
        "local_date": conversation.local_date.isoformat(),
        "kind": conversation.kind,
        "started_by": conversation.started_by,
        "safety_level": conversation.safety_level,
        "messages": [
            {
                "role": m.role,
                "source": m.source,
                "text": m.content_raw,
                "safety_level": m.safety_level,
                "rating": m.rating,
                "quotes": len(m.used_fact_ids or []),
                "cost_usd": m.cost_usd,
                "created_at": _utc(m.created_at).isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
