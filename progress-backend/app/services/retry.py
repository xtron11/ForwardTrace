"""When a failed provider call is worth repeating, and how long to wait first.

Shared by speech-to-text and the model client. The rule is the one the official SDKs
follow: repeat what might succeed a moment later - rate limits, server errors, dropped
connections - and never repeat what is wrong with the request itself. A 400 sent three
times is three identical answers and three times the wait before the person sees an
error.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

log = logging.getLogger(__name__)

T = TypeVar("T")

# First pause when the server gives no Retry-After; doubles on each attempt.
BASE_DELAY_SEC = 1.5
# A server asking for longer than this is out of capacity, not briefly busy. Waiting
# would hold a background slot for nothing, so the call fails instead.
MAX_WAIT_SEC = 60.0


class ProviderError(RuntimeError):
    """A failed call to an external provider, with what the retry loop needs to know."""

    def __init__(
        self, message: str, *, retryable: bool = False, retry_after: float | None = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def is_retryable_status(status: int) -> bool:
    # 408 timeout, 409 conflict (lock contention on the provider side), 429 rate limit,
    # 5xx server trouble - except 501, which means the feature does not exist.
    return status in (408, 409, 429) or (status >= 500 and status != 501)


def retry_after(resp: httpx.Response) -> float | None:
    """Seconds the server asked us to wait, if it said.

    OpenAI sends retry-after-ms alongside the standard header; the standard one may be
    either a number of seconds or an HTTP date.
    """
    ms = resp.headers.get("retry-after-ms")
    if ms:
        try:
            return max(float(ms) / 1000, 0.0)
        except ValueError:
            pass
    value = resp.headers.get("retry-after")
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max((when - datetime.now(timezone.utc)).total_seconds(), 0.0)


def delay(attempt: int, server_asked: float | None) -> float | None:
    """Pause before the next attempt, or None when it is not worth waiting at all."""
    if server_asked is not None:
        return None if server_asked > MAX_WAIT_SEC else server_asked
    # Jitter keeps several stalled jobs from hitting the provider again in lockstep.
    return min(BASE_DELAY_SEC * 2**attempt * random.uniform(0.75, 1.25), MAX_WAIT_SEC)


async def pause(seconds: float) -> None:
    """Separate so the tests can skip the waiting without touching asyncio.sleep."""
    await asyncio.sleep(seconds)


async def run(call: Callable[[], Awaitable[T]], *, retries: int, label: str) -> T:
    """Call, repeating up to `retries` more times on a retryable ProviderError."""
    attempt = 0
    while True:
        try:
            return await call()
        except ProviderError as exc:
            if not exc.retryable or attempt >= retries:
                raise
            wait = delay(attempt, exc.retry_after)
            if wait is None:
                log.warning(
                    "%s: server asked to wait %.0fs, giving up: %s", label, exc.retry_after, exc
                )
                raise
            attempt += 1
            log.warning(
                "%s attempt %s failed, retrying in %.1fs: %s", label, attempt, wait, exc
            )
            await pause(wait)
