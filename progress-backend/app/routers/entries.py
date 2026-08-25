import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Activity, Entry, Goal, Status
from ..schemas import (
    ActivityOut,
    ConfirmTranscriptIn,
    EntryAccepted,
    EntryOut,
    ReassignActivityIn,
    TextEntryIn,
    TranscribeOut,
)
from ..services.extraction import process_entry, transcribe_entry
from ..services.stt import STTError, transcribe
from ..time_utils import local_today

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/entries", tags=["entries"])

# MediaRecorder emits webm/opus on Chrome and Firefox but mp4/aac on iOS Safari,
# so accepting only webm silently breaks every iPhone user.
ALLOWED_AUDIO = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
}


def _extension_for(content_type: str | None) -> str:
    base = (content_type or "").split(";")[0].strip().lower()
    if base not in ALLOWED_AUDIO:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported audio type {base!r}. Allowed: {', '.join(sorted(ALLOWED_AUDIO))}",
        )
    return ALLOWED_AUDIO[base]


async def _save_upload(file: UploadFile, user_id: uuid.UUID, entry_id: uuid.UUID) -> tuple[str, str]:
    extension = _extension_for(file.content_type)
    limit = settings.max_audio_mb * 1024 * 1024

    target_dir = Path(settings.audio_dir) / str(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{entry_id}{extension}"

    written = 0
    with target.open("wb") as handle:
        while chunk := await file.read(1024 * 256):
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, detail=f"Audio exceeds {settings.max_audio_mb} MB"
                )
            handle.write(chunk)

    if written == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty audio file")

    return str(target), (file.content_type or "").split(";")[0].strip().lower()


async def _resolve_goal(db, user, goal_id: uuid.UUID | None) -> uuid.UUID | None:
    """Only pins an entry to a goal when the client explicitly asked for it.

    Leaving this null is the normal case: the person talks about their whole day and the
    extractor routes each item to the goal it serves. Defaulting to "their one goal"
    would silently collapse a multi-goal check-in into a single goal.
    """
    if goal_id is None:
        return None
    goal = (
        await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    ).scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal.id


@router.post("/voice", response_model=EntryAccepted, status_code=202)
async def create_voice_entry(
    background: BackgroundTasks,
    user: CurrentUser,
    db: Db,
    audio: UploadFile = File(...),
    goal_id: uuid.UUID | None = Form(default=None),
    review: bool = Form(default=True),
) -> EntryAccepted:
    """Accepts the recording and returns immediately.

    With review=true (the default) the entry stops at 'awaiting_review' once the
    transcript exists, so the person can correct mishearings before any fact is derived
    from them. Confirm via POST /api/entries/{id}/confirm.

    With review=false it runs straight through to extraction.

    Either way the client polls GET /api/entries/{id}.
    """
    resolved_goal = await _resolve_goal(db, user, goal_id)

    entry = Entry(
        user_id=user.id,
        goal_id=resolved_goal,
        local_date=local_today(user.timezone),
        source="voice",
        status=Status.pending.value,
    )
    db.add(entry)
    await db.flush()

    path, mime = await _save_upload(audio, user.id, entry.id)
    entry.audio_path, entry.audio_mime = path, mime
    await db.commit()

    background.add_task(transcribe_entry if review else process_entry, entry.id)

    return EntryAccepted(
        id=entry.id,
        status=entry.status,
        local_date=entry.local_date,
        poll_url=f"/api/entries/{entry.id}",
    )


@router.post("/{entry_id}/confirm", response_model=EntryAccepted, status_code=202)
async def confirm_transcript(
    entry_id: uuid.UUID,
    payload: ConfirmTranscriptIn,
    background: BackgroundTasks,
    user: CurrentUser,
    db: Db,
) -> EntryAccepted:
    """Approve the transcript, corrected or not, and start extraction."""
    entry = (
        await db.execute(select(Entry).where(Entry.id == entry_id, Entry.user_id == user.id))
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != Status.awaiting_review.value:
        raise HTTPException(status_code=409, detail="This entry is not awaiting review")

    text = payload.text.strip()
    entry.transcript_edited = text != (entry.stt_transcript or "").strip()
    entry.raw_transcript = text
    entry.status = Status.pending.value
    await db.commit()

    background.add_task(process_entry, entry.id)

    return EntryAccepted(
        id=entry.id,
        status=entry.status,
        local_date=entry.local_date,
        poll_url=f"/api/entries/{entry.id}",
    )


@router.post("/text", response_model=EntryAccepted, status_code=202)
async def create_text_entry(
    payload: TextEntryIn, background: BackgroundTasks, user: CurrentUser, db: Db
) -> EntryAccepted:
    """Typed fallback: quiet office, broken mic, or the user simply prefers typing."""
    resolved_goal = await _resolve_goal(db, user, payload.goal_id)

    entry = Entry(
        user_id=user.id,
        goal_id=resolved_goal,
        local_date=local_today(user.timezone),
        source="text",
        raw_transcript=payload.text.strip(),
        status=Status.pending.value,
    )
    db.add(entry)
    await db.commit()

    background.add_task(process_entry, entry.id)

    return EntryAccepted(
        id=entry.id,
        status=entry.status,
        local_date=entry.local_date,
        poll_url=f"/api/entries/{entry.id}",
    )


@router.post("/transcribe", response_model=TranscribeOut)
async def transcribe_only(user: CurrentUser, audio: UploadFile = File(...)) -> TranscribeOut:
    """Synchronous transcription for the 'why does this matter' voice field.

    That is a one-off during onboarding where the user is watching the screen, so a
    couple of seconds inline is better UX than a polling dance. Nothing is stored.
    """
    scratch_id = uuid.uuid4()
    path, mime = await _save_upload(audio, user.id, scratch_id)
    try:
        result = await transcribe(path, mime, locale=user.locale)
    except STTError as exc:
        raise HTTPException(status_code=503, detail=f"Transcription failed: {exc}") from exc
    finally:
        Path(path).unlink(missing_ok=True)

    return TranscribeOut(text=result.text, seconds=result.seconds, stt_ms=result.elapsed_ms)


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
async def reassign_activity(
    activity_id: uuid.UUID,
    payload: ReassignActivityIn,
    user: CurrentUser,
    db: Db,
) -> Activity:
    """Correct the goal an activity was routed to.

    Routing is a judgement call and the model will sometimes get it wrong. Offering a
    quiet correction is better than making the person confirm every item, which would
    reintroduce exactly the form-filling this product exists to avoid.
    """
    activity = (
        await db.execute(
            select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
        )
    ).scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    if payload.goal_id is not None:
        goal = (
            await db.execute(
                select(Goal).where(Goal.id == payload.goal_id, Goal.user_id == user.id)
            )
        ).scalar_one_or_none()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")

    activity.goal_id = payload.goal_id
    await db.commit()
    await db.refresh(activity)
    return activity


@router.get("/{entry_id}", response_model=EntryOut)
async def get_entry(entry_id: uuid.UUID, user: CurrentUser, db: Db) -> Entry:
    entry = (
        await db.execute(
            select(Entry)
            .options(selectinload(Entry.activities))
            .where(Entry.id == entry_id, Entry.user_id == user.id)
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("", response_model=list[EntryOut])
async def list_entries(user: CurrentUser, db: Db, limit: int = 60, offset: int = 0) -> list[Entry]:
    """The timeline screen."""
    rows = await db.execute(
        select(Entry)
        .options(selectinload(Entry.activities))
        .where(Entry.user_id == user.id)
        .order_by(Entry.local_date.desc(), Entry.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    return list(rows.scalars().all())


@router.post("/{entry_id}/retry", response_model=EntryAccepted, status_code=202)
async def retry_entry(
    entry_id: uuid.UUID, background: BackgroundTasks, user: CurrentUser, db: Db
) -> EntryAccepted:
    entry = (
        await db.execute(select(Entry).where(Entry.id == entry_id, Entry.user_id == user.id))
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == Status.done.value:
        raise HTTPException(status_code=409, detail="This entry is already processed")

    entry.status = Status.pending.value
    entry.error = None
    await db.commit()
    background.add_task(process_entry, entry.id)

    return EntryAccepted(
        id=entry.id,
        status=entry.status,
        local_date=entry.local_date,
        poll_url=f"/api/entries/{entry.id}",
    )
