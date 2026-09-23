"""Speech-to-text.

Two providers behind one interface:

  deepgram -> Nova-3 pre-recorded (batch). Purpose-built STT, per-second billing,
              sub-second turnaround on a 60s clip. Default.
  local    -> faster-whisper on this box. No external dependency, no per-minute
              cost, but 8-30s per minute of audio on CPU depending on model size.

Neither is hardcoded anywhere else in the codebase: swap STT_PROVIDER in .env.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import sentry_sdk

from ..config import settings
from . import costs, retry

log = logging.getLogger(__name__)

# Whisper on CPU is memory hungry and single-job: never run two at once.
_stt_gate = asyncio.Semaphore(settings.stt_concurrency)
_model = None
_model_lock = asyncio.Lock()


@dataclass(slots=True)
class STTResult:
    text: str
    seconds: float | None
    language: str | None
    elapsed_ms: int
    provider: str


class STTError(retry.ProviderError):
    pass


# Kept open for the life of the process, like the model client: no fresh handshake
# with Deepgram for every recording.
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.stt_timeout_sec)
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------------- deepgram ----------------

async def _transcribe_deepgram(path: str, mime: str | None, language: str | None) -> STTResult:
    if not settings.deepgram_api_key:
        raise STTError("DEEPGRAM_API_KEY is not set but STT_PROVIDER=deepgram")

    started = time.perf_counter()
    params = {
        "model": settings.deepgram_model,
        "smart_format": "true",   # punctuation and casing, so the LLM sees clean sentences
        "punctuate": "true",
        "filler_words": "false",  # drops "uh"/"um" - noise for extraction
    }
    if settings.stt_multilingual:
        language = "multi"
    if language:
        params["language"] = language
    else:
        params["detect_language"] = "true"

    # httpx encodes a list value as repeated query params, which is what Deepgram wants.
    #
    # Keyterms are only sent when the language is pinned. They are a list of words in a
    # specific language, so handing them to language detection biases it: an English
    # keyterm list makes Russian speech get detected as English, and the transcript
    # comes back as fluent English nonsense. Detection alone is reliable; detection
    # plus foreign-language hints is not.
    keyterms = settings.keyterm_list
    if (
        keyterms
        and language
        and language != "multi"
        and settings.deepgram_model.startswith("nova-3")
    ):
        params["keyterm"] = keyterms

    body = await asyncio.to_thread(Path(path).read_bytes)

    async def attempt() -> httpx.Response:
        try:
            resp = await _http().post(
                f"{settings.deepgram_base_url}/v1/listen",
                params=params,
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": mime or "application/octet-stream",
                },
                content=body,
            )
        except httpx.RequestError as exc:
            raise STTError(
                f"Deepgram unreachable: {type(exc).__name__}: {exc}", retryable=True
            ) from exc
        if resp.status_code >= 400:
            # 400 is a file Deepgram cannot decode and 401 a bad key: sending the same
            # bytes again changes nothing. Rate limits and server errors do pass.
            raise STTError(
                f"Deepgram {resp.status_code}: {resp.text[:300]}",
                retryable=retry.is_retryable_status(resp.status_code),
                retry_after=retry.retry_after(resp),
            )
        return resp

    # Without this one hiccup at Deepgram fails the check-in and leaves the person to
    # find the Retry button.
    resp = await retry.run(attempt, retries=settings.stt_max_retries, label="stt")

    payload = resp.json()
    try:
        channel = payload["results"]["channels"][0]
        alt = channel["alternatives"][0]
        text = (alt.get("transcript") or "").strip()
        language = channel.get("detected_language") or settings.stt_language
    except (KeyError, IndexError) as exc:
        raise STTError(f"unexpected Deepgram payload: {exc}") from exc

    return STTResult(
        text=text,
        seconds=payload.get("metadata", {}).get("duration"),
        language=language,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        provider="deepgram",
    )


# ---------------- local: faster-whisper ----------------

def _load_local_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        log.info(
            "loading faster-whisper model=%s device=%s",
            settings.whisper_model,
            settings.whisper_device,
        )
        _model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _model


def _transcribe_local_sync(path: str, language: str | None) -> tuple[str, float | None, str | None]:
    model = _load_local_model()
    segments, info = model.transcribe(
        path,
        language=language,
        vad_filter=True,                   # skips silence, large speedup on rambling audio
        beam_size=1,                       # greedy decode: ~2x faster, negligible loss here
        condition_on_previous_text=False,  # stops the known repetition-loop failure mode
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text, getattr(info, "duration", None), getattr(info, "language", None)


async def _transcribe_local(path: str, language: str | None) -> STTResult:
    started = time.perf_counter()
    async with _stt_gate:
        async with _model_lock:
            if _model is None:
                await asyncio.to_thread(_load_local_model)
        text, seconds, detected = await asyncio.to_thread(_transcribe_local_sync, path, language)
    return STTResult(
        text=text,
        seconds=seconds,
        language=detected,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        provider="local",
    )


async def transcribe(
    path: str,
    mime: str | None = None,
    locale: str | None = None,
) -> STTResult:
    """Transcribe, letting the provider work out the language.

    Detection is the default because forcing the wrong language is the worst failure
    this system has: Russian speech told to be English comes back as fluent English
    nonsense. It reads like a working transcript, so nobody notices until a whole week
    of reports has been built on invented sentences. Detection, by contrast, degrades
    gracefully.

    `locale` is only a hint, used when detection is unavailable. STT_LANGUAGE pins the
    language outright and exists as an escape hatch for noisy audio, where a known
    language does beat detection.
    """
    forced = (settings.stt_language or "").split("-")[0].lower() or None
    language = forced or (None if settings.stt_detect_language else (locale or "").split("-")[0].lower() or None)

    provider = settings.stt_provider.lower()
    with sentry_sdk.start_span(op="ai.stt", name=f"stt {provider}"):
        if provider == "deepgram":
            result = await _transcribe_deepgram(path, mime, language)
        elif provider == "local":
            result = await _transcribe_local(path, language)
        else:
            raise STTError(f"unknown STT_PROVIDER={settings.stt_provider!r}")
        costs.record_stt(result.provider, result.seconds)
    return result
