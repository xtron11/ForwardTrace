"""One shape for every error a v2 endpoint returns: {"detail": {"code", "message"}}.

The frontend translates by `code`; `message` is English and only for people reading
logs or the API directly. Endpoints from v1 (auth, push) keep their plain strings.
"""

from fastapi import HTTPException

# Codes returned as HTTP errors, with their status.
LIMIT_REACHED = "limit_reached"  # 402
EMAIL_NOT_VERIFIED = "email_not_verified"  # 403
AUDIO_TOO_LARGE = "audio_too_large"  # 413
UNSUPPORTED_AUDIO = "unsupported_audio"  # 415
EMPTY_AUDIO = "empty_audio"  # 400
EMPTY_TEXT = "empty_text"  # 422
TEXT_TOO_LONG = "text_too_long"  # 422
BAD_CLIENT_MSG_ID = "bad_client_msg_id"  # 422
REPLY_IN_PROGRESS = "reply_in_progress"  # 409
NOT_FOUND = "not_found"  # 404
TELEGRAM_DISABLED = "telegram_disabled"  # 503
BAD_RANGE = "bad_range"  # 400

# Codes sent as an `error` event inside an SSE stream, after it has started.
NO_SPEECH = "no_speech"
STT_FAILED = "stt_failed"
LLM_FAILED = "llm_failed"


def api_error(status: int, code: str, message: str) -> HTTPException:
    """Raise the result: `raise api_error(402, LIMIT_REACHED, "...")`."""
    return HTTPException(status_code=status, detail={"code": code, "message": message})
