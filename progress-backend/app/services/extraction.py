"""The daily pipeline: audio -> transcript -> verified facts -> rows.

Runs as a background task. Nothing here blocks an HTTP response.
"""

import logging
import uuid

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Activity, Criterion, Entry, Goal, Status, User
from . import prompts, verify
from .llm import LLMError, complete_json
from .stt import STTError, transcribe

log = logging.getLogger(__name__)

MOODS = {"positive", "neutral", "tired", "frustrated", "motivated", "mixed"}
MAX_ACTIVITIES = 6
MAX_MINUTES_PER_ACTIVITY = 16 * 60  # a sanity ceiling; nobody codes for 20 hours


async def _known_categories(db, user_id: uuid.UUID) -> dict[str, str]:
    """Categories this user has used before, so 'coding' and 'Coding' stay one bucket."""
    rows = await db.execute(
        select(Activity.category_key, Activity.category)
        .where(Activity.user_id == user_id)
        .distinct()
        .limit(40)
    )
    return {key: display for key, display in rows.all()}


def _build_activities(
    raw_items: list[dict],
    transcript_norm: str,
    known: dict[str, str],
    valid_goal_ids: set[str],
) -> tuple[list[dict], int]:
    """Verify each extracted activity against the transcript. Returns (kept, dropped)."""
    kept: list[dict] = []
    dropped = 0

    for item in raw_items or []:
        quote = (item.get("quote") or "").strip()
        if not verify.quote_supported(quote, transcript_norm):
            dropped += 1
            continue

        display, key = verify.normalize_category(item.get("category", ""), known)
        known.setdefault(key, display)

        # A hallucinated goal id would file real work under the wrong goal, which is
        # worse than leaving it unrouted for the person to assign.
        routed = (item.get("goal_id") or "").strip()
        goal_id = uuid.UUID(routed) if routed in valid_goal_ids else None

        explicit = bool(item.get("minutes_explicit"))
        minutes = item.get("minutes")
        try:
            minutes = int(minutes) if minutes is not None else 0
        except (TypeError, ValueError):
            minutes = 0
        # The model is told to set 0 when no duration was spoken. Enforce it: a
        # guessed number would silently become a real number in the weekly totals.
        if not explicit or minutes <= 0 or minutes > MAX_MINUTES_PER_ACTIVITY:
            minutes, explicit = None, False

        details = [
            str(d).strip()[:200]
            for d in (item.get("details") or [])
            if str(d).strip()
        ][:4]

        metrics, dropped_metrics = verify.clean_metrics(item.get("metrics"), transcript_norm)
        dropped += dropped_metrics

        kept.append(
            {
                "goal_id": goal_id,
                "category": display,
                "category_key": key,
                "minutes": minutes,
                "minutes_explicit": explicit,
                "details": details,
                "metrics": metrics,
                "quote": quote[:400],
            }
        )
        if len(kept) >= MAX_ACTIVITIES:
            break

    return kept, dropped


async def _active_goals(db, user_id: uuid.UUID) -> list[dict]:
    """Goals with their criteria, as the router prompt needs them."""
    goals = (
        (
            await db.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.is_active.is_(True))
                .order_by(Goal.created_at)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for goal in goals:
        criteria = (
            (
                await db.execute(
                    select(Criterion.text)
                    .where(Criterion.goal_id == goal.id, Criterion.is_active.is_(True))
                    .order_by(Criterion.position)
                )
            )
            .scalars()
            .all()
        )
        out.append({"id": str(goal.id), "title": goal.title, "criteria": list(criteria)})
    return out


async def extract_from_transcript(
    db,
    user_id: uuid.UUID,
    transcript: str,
    forced_goal_id: uuid.UUID | None = None,
    locale: str | None = None,
) -> tuple[dict, int, int, str]:
    """Returns (payload, dropped_facts, elapsed_ms, model_name)."""
    known = await _known_categories(db, user_id)
    goals = await _active_goals(db, user_id)

    # When the client pinned the check-in to one goal, don't offer the model a choice.
    if forced_goal_id is not None:
        goals = [g for g in goals if g["id"] == str(forced_goal_id)] or goals

    valid_goal_ids = {g["id"] for g in goals}

    result = await complete_json(
        system=prompts.extraction_system(locale),
        user=prompts.extraction_user_prompt(transcript, goals, list(known.values())),
        schema=prompts.EXTRACTION_SCHEMA,
    )

    transcript_norm = verify.normalize(transcript)
    activities, dropped_a = _build_activities(
        result.data.get("activities", []), transcript_norm, known, valid_goal_ids
    )
    wins, dropped_w = verify.clean_facts(
        result.data.get("wins", []), transcript_norm, valid_goal_ids
    )
    friction, dropped_f = verify.clean_facts(
        result.data.get("friction", []), transcript_norm, valid_goal_ids
    )
    intentions, dropped_i = verify.clean_facts(
        result.data.get("intentions", []), transcript_norm, valid_goal_ids, limit=3
    )

    mood = str(result.data.get("mood", "")).strip().lower()
    if mood not in MOODS:
        mood = "neutral"

    payload = {
        "activities": activities,
        "wins": wins,
        "friction": friction,
        "intentions": intentions,
        "mood": mood,
    }
    dropped = dropped_a + dropped_w + dropped_f + dropped_i
    return payload, dropped, result.elapsed_ms, result.model


async def process_entry(entry_id: uuid.UUID) -> None:
    """Background worker for one check-in. Owns its own DB session."""
    async with SessionLocal() as db:
        entry = await db.get(Entry, entry_id)
        if entry is None or entry.status not in (Status.pending.value, Status.failed.value):
            return

        entry.status = Status.processing.value
        entry.error = None
        await db.commit()

        try:
            # 1. speech to text - skipped when the user typed, and skipped when the
            #    transcript is already present because they reviewed it first
            speaker = await db.get(User, entry.user_id)
            if entry.source == "voice" and not entry.raw_transcript:
                if not entry.audio_path:
                    raise STTError("entry has no audio file")
                stt = await transcribe(
                    entry.audio_path, entry.audio_mime, locale=speaker.locale if speaker else None
                )
                entry.raw_transcript = stt.text
                entry.stt_transcript = stt.text
                entry.audio_seconds = stt.seconds
                entry.stt_ms = stt.elapsed_ms
                entry.detected_language = stt.language
                _warn_on_language_mismatch(entry, speaker)

            transcript = (entry.raw_transcript or "").strip()
            if len(transcript) < 10:
                # Empty recordings are a real failure mode: pocket taps, denied mic,
                # silence. Mark done with nothing extracted rather than erroring out.
                entry.status = Status.done.value
                entry.mood = "neutral"
                entry.wins, entry.friction = [], []
                entry.error = "No speech detected in the recording."
                await db.commit()
                return

            # 2. structured extraction, then verification. Each item is routed to a
            #    goal by the model; one check-in can span several goals.
            payload, dropped, llm_ms, _model = await extract_from_transcript(
                db, entry.user_id, transcript, entry.goal_id,
                locale=speaker.locale if speaker else "en",
            )

            entry.mood = payload["mood"]
            entry.wins = payload["wins"]
            entry.friction = payload["friction"]
            entry.intentions = payload["intentions"]
            entry.llm_ms = llm_ms
            entry.dropped_facts = dropped

            # 3. fan out into rows so weekly stats are plain SQL
            for item in payload["activities"]:
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=entry.user_id,
                        local_date=entry.local_date,
                        **item,
                    )
                )

            # The answer to what they said, built from their own history. A separate
            # model call from extraction: different job, different cost of being wrong,
            # and a failure here must not cost them the facts.
            from .reflection import reflect
            from .summary import daily_summary

            try:
                numbers = await daily_summary(db, entry.user_id, entry.local_date)
                entry.reflection = await reflect(
                    db,
                    entry.user_id,
                    transcript,
                    entry.local_date,
                    {
                        "days_in_journey": numbers["days_in_journey"],
                        "accumulated": numbers["accumulated"],
                        "personal_record": numbers["personal_record"],
                    },
                    locale=speaker.locale if speaker else None,
                )
            except Exception:  # noqa: BLE001
                log.exception("reflection step failed for entry %s", entry.id)
                entry.reflection = []

            # Compare what they said against what they had intended. Runs after the
            # facts are stored, so a failure here cannot cost them the check-in.
            from .tasks import match_entry

            await match_entry(
                db,
                entry.user_id,
                entry.id,
                transcript,
                entry.local_date,
                locale=speaker.locale if speaker else None,
            )

            entry.status = Status.done.value
            await db.commit()

            if dropped:
                log.info("entry %s: dropped %s unverifiable facts", entry.id, dropped)

            if not settings.keep_audio and entry.audio_path:
                _delete_audio(entry.audio_path)

        except (STTError, LLMError) as exc:
            log.warning("entry %s failed: %s", entry_id, exc)
            await _fail(db, entry, str(exc)[:500])
        except Exception as exc:  # noqa: BLE001 - a worker must never die silently
            log.exception("entry %s crashed", entry_id)
            await _fail(db, entry, f"Unexpected error: {type(exc).__name__}")


async def transcribe_entry(entry_id: uuid.UUID) -> None:
    """Speech-to-text only, then stop and wait for the person to check the text.

    Extraction is destructive in the sense that a misheard word becomes a stored fact.
    Given how often domain vocabulary is misheard, it is worth one extra tap to let the
    person correct the transcript before anything is derived from it.
    """
    async with SessionLocal() as db:
        entry = await db.get(Entry, entry_id)
        if entry is None or entry.status not in (Status.pending.value, Status.failed.value):
            return

        entry.status = Status.processing.value
        entry.error = None
        await db.commit()

        try:
            if not entry.audio_path:
                raise STTError("entry has no audio file")
            speaker = await db.get(User, entry.user_id)
            stt = await transcribe(
                entry.audio_path, entry.audio_mime, locale=speaker.locale if speaker else None
            )
            entry.raw_transcript = stt.text
            entry.stt_transcript = stt.text
            entry.audio_seconds = stt.seconds
            entry.stt_ms = stt.elapsed_ms
            entry.detected_language = stt.language
            _warn_on_language_mismatch(entry, speaker)
            entry.status = Status.awaiting_review.value
            await db.commit()
        except STTError as exc:
            log.warning("transcription %s failed: %s", entry_id, exc)
            await _fail(db, entry, str(exc)[:500])
        except Exception as exc:  # noqa: BLE001
            log.exception("transcription %s crashed", entry_id)
            await _fail(db, entry, f"Unexpected error: {type(exc).__name__}")


def _warn_on_language_mismatch(entry: Entry, speaker: User | None) -> None:
    """The person's browser said one language, their mouth said another.

    Not an error - people read English interfaces and speak Russian. But their reports
    are written in the profile language, so a persistent mismatch means the profile is
    probably wrong and worth looking at in the admin view.
    """
    detected = (entry.detected_language or "").split("-")[0].lower()
    profile = (speaker.locale if speaker else "").split("-")[0].lower()
    if detected and profile and detected != profile:
        log.info(
            "entry %s: spoken %s but profile is %s", entry.id, detected, profile
        )


async def _fail(db, entry: Entry, message: str) -> None:
    await db.rollback()
    fresh = await db.get(Entry, entry.id)
    if fresh is not None:
        fresh.status = Status.failed.value
        fresh.error = message
        await db.commit()


def _delete_audio(path: str) -> None:
    from pathlib import Path

    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        log.warning("could not delete audio at %s", path)
