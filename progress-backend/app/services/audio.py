"""Uploaded recordings: which formats are accepted, how large, and where they live.

A v2 recording belongs to a message: AUDIO_DIR/<user_id>/<message_id>.<ext>. The same
checks guard the v1 uploads (check-ins, the goal's "why"), which import from here.
Errors are the v2 shape (services/errors.py), raised before anything is spent.
"""

import logging
import uuid
from collections.abc import Iterable
from pathlib import Path

from fastapi import UploadFile

from ..config import settings
from .errors import AUDIO_TOO_LARGE, EMPTY_AUDIO, UNSUPPORTED_AUDIO, api_error

log = logging.getLogger(__name__)

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

_CHUNK = 1024 * 256


def base_mime(content_type: str | None) -> str:
    """'audio/webm;codecs=opus' -> 'audio/webm'."""
    return (content_type or "").split(";")[0].strip().lower()


def extension_for(content_type: str | None) -> str:
    base = base_mime(content_type)
    if base not in ALLOWED_AUDIO:
        raise api_error(
            415,
            UNSUPPORTED_AUDIO,
            f"Unsupported audio type {base!r}. Allowed: {', '.join(sorted(ALLOWED_AUDIO))}",
        )
    return ALLOWED_AUDIO[base]


async def save_upload(file: UploadFile, user_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, str]:
    """Write the upload to AUDIO_DIR/<user_id>/<file_id>.<ext>; returns (path, mime).

    The type is checked before a byte is written; the size while writing, so an
    oversized upload never sits on disk whole.
    """
    extension = extension_for(file.content_type)
    limit = settings.max_audio_mb * 1024 * 1024

    target_dir = Path(settings.audio_dir) / str(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{file_id}{extension}"

    written = 0
    with target.open("wb") as handle:
        while chunk := await file.read(_CHUNK):
            written += len(chunk)
            if written > limit:
                handle.close()
                target.unlink(missing_ok=True)
                raise api_error(413, AUDIO_TOO_LARGE, f"Audio exceeds {settings.max_audio_mb} MB")
            handle.write(chunk)

    if written == 0:
        target.unlink(missing_ok=True)
        raise api_error(400, EMPTY_AUDIO, "Empty audio file")

    return str(target), base_mime(file.content_type)


async def save_message_audio(
    file: UploadFile, user_id: uuid.UUID, message_id: uuid.UUID
) -> tuple[str, str]:
    """A message's recording: AUDIO_DIR/<user_id>/<message_id>.<ext> -> (path, mime)."""
    return await save_upload(file, user_id, message_id)


def delete_files(paths: Iterable[str | None]) -> None:
    """Remove recordings; a file already gone is not an error."""
    for path in paths:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            log.warning("could not delete audio file %s", path, exc_info=True)
