"""Dictation: a recording becomes text in the message box before it is sent.

The person records, the transcript lands in the text field, they fix it and send. The
recording is kept until then as a draft, so the sent message still has its audio and
word timings and quotes from it play back in the person's voice.

One draft per person, in the memory of the process (the worker is single, like the
busy flag in conversation.py). A newer recording replaces the older one; a draft not
sent within VOICE_DRAFT_TTL_MINUTES is dropped with its file. A message that names a
draft the process no longer has is sent as plain text.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import User
from . import audio as audio_store
from . import costs, limits
from .errors import EMAIL_NOT_VERIFIED, NO_SPEECH, STT_FAILED, api_error
from .stt import transcribe

log = logging.getLogger(__name__)


@dataclass
class VoiceDraft:
    id: uuid.UUID
    user_id: uuid.UUID
    text: str
    audio_path: str
    audio_mime: str
    seconds: float | None
    language: str | None
    stt_ms: int
    words: list[dict]
    # Spent on speech-to-text; charged to the message the draft is sent with.
    usage: costs.Usage
    created: float = field(default_factory=time.monotonic)


_drafts: dict[uuid.UUID, VoiceDraft] = {}


def _drop(draft: VoiceDraft) -> None:
    _drafts.pop(draft.user_id, None)
    audio_store.delete_files([draft.audio_path])


def _sweep() -> None:
    deadline = time.monotonic() - settings.voice_draft_ttl_minutes * 60
    for draft in [d for d in _drafts.values() if d.created < deadline]:
        _drop(draft)


async def dictate(db: AsyncSession, user: User, upload: UploadFile) -> VoiceDraft:
    """Save and transcribe a recording; the transcript goes back to the message box.

    The checks of a voice message run here, before anything is spent: a confirmed
    email, the limit, the type and size of the file."""
    from .conversation import get_or_create_today  # conversation imports this module

    if settings.require_verified_email and not user.email_verified:
        raise api_error(403, EMAIL_NOT_VERIFIED, "Confirm your email address first.")
    audio_store.extension_for(upload.content_type)
    conversation = await get_or_create_today(db, user)
    await limits.ensure_can_message(db, user, conversation, conversation.local_date)

    _sweep()
    draft_id = uuid.uuid4()
    path, mime = await audio_store.save_upload(upload, user.id, draft_id)
    with costs.track() as usage:
        try:
            result = await transcribe(path, mime, user.locale)
        except Exception:  # noqa: BLE001 - STTError or anything the provider threw
            log.exception("speech-to-text failed for dictation %s", draft_id)
            audio_store.delete_files([path])
            raise api_error(502, STT_FAILED, "Speech recognition failed.")
    text = (result.text or "").strip()
    if len(text) < settings.no_speech_min_chars:
        audio_store.delete_files([path])
        raise api_error(422, NO_SPEECH, "No speech detected in the recording.")

    previous = _drafts.get(user.id)
    if previous is not None:
        _drop(previous)
    draft = VoiceDraft(
        id=draft_id,
        user_id=user.id,
        text=text,
        audio_path=path,
        audio_mime=mime,
        seconds=result.seconds,
        language=result.language,
        stt_ms=result.elapsed_ms,
        words=result.words or [],
        usage=usage,
    )
    _drafts[user.id] = draft
    return draft


def take(user_id: uuid.UUID, draft_id: uuid.UUID | None) -> VoiceDraft | None:
    """The person's draft with this id, removed from the store (its file stays: it now
    belongs to the message). None if it is gone or is not theirs."""
    _sweep()
    draft = _drafts.get(user_id)
    if draft is None or draft_id is None or draft.id != draft_id:
        return None
    del _drafts[user_id]
    return draft


def reset() -> None:
    """Tests: forget every draft."""
    _drafts.clear()
