"""What each provider call cost, and which check-in it was spent on.

Every speech-to-text and model call reports its usage here. The call sites do not know
which entry they are working for - reflection and task matching are three layers below
the worker - so the worker opens a meter with `track()` and everything awaited inside
it is charged to that meter through a context variable.

Tokens are kept alongside dollars on purpose. Prices change and are configured by hand;
token counts are what the provider actually billed, and a wrong price can be corrected
after the fact from them.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import sentry_sdk

from ..config import settings

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Usage:
    stt_seconds: float = 0.0
    stt_usd: float = 0.0
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_cached_tokens: int = 0
    llm_output_tokens: int = 0
    llm_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        return self.stt_usd + self.llm_usd

    @property
    def empty(self) -> bool:
        return not (self.stt_seconds or self.llm_calls)


_meter: ContextVar[Usage | None] = ContextVar("cost_meter", default=None)


@contextmanager
def track() -> Iterator[Usage]:
    """Charge every provider call awaited inside this block to one Usage."""
    usage = Usage()
    token = _meter.set(usage)
    try:
        yield usage
    finally:
        _meter.reset(token)


def llm_price(input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """Dollars for one call. Cached tokens are a subset of input tokens, billed lower."""
    per = 1_000_000
    cached_rate = (
        settings.llm_price_cached_input_per_1m
        if settings.llm_price_cached_input_per_1m is not None
        else settings.llm_price_input_per_1m
    )
    fresh = max(input_tokens - cached_tokens, 0)
    return (
        fresh * settings.llm_price_input_per_1m
        + cached_tokens * cached_rate
        + output_tokens * settings.llm_price_output_per_1m
    ) / per


def stt_price(provider: str, seconds: float | None) -> float:
    if provider != "deepgram" or not seconds:
        return 0.0
    return seconds / 60 * settings.stt_price_per_min


def record_llm(model: str, usage: dict | None) -> float:
    """Take the `usage` block of a Chat Completions response. Returns the dollar cost.

    Called for every response that came back, including ones whose JSON then failed to
    parse and were retried: those tokens were billed all the same.
    """
    usage = usage or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)  # includes reasoning tokens
    cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    reasoning = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
    usd = llm_price(input_tokens, cached, output_tokens)

    meter = _meter.get()
    if meter is not None:
        meter.llm_calls += 1
        meter.llm_input_tokens += input_tokens
        meter.llm_cached_tokens += cached
        meter.llm_output_tokens += output_tokens
        meter.llm_usd += usd

    # Attribute names Sentry's AI monitoring reads, so calls show up there as LLM spans.
    span = sentry_sdk.get_current_span()
    if span is not None:
        span.set_data("gen_ai.system", "openai")
        span.set_data("gen_ai.request.model", model)
        span.set_data("gen_ai.usage.input_tokens", input_tokens)
        span.set_data("gen_ai.usage.input_tokens.cached", cached)
        span.set_data("gen_ai.usage.output_tokens", output_tokens)
        span.set_data("gen_ai.usage.output_tokens.reasoning", reasoning)
        span.set_data("cost_usd", usd)

    log.info(
        "llm usage model=%s in=%s cached=%s out=%s reasoning=%s cost=$%.6f",
        model, input_tokens, cached, output_tokens, reasoning, usd,
    )
    return usd


def record_stt(provider: str, seconds: float | None) -> float:
    usd = stt_price(provider, seconds)
    meter = _meter.get()
    if meter is not None:
        meter.stt_seconds += seconds or 0.0
        meter.stt_usd += usd

    span = sentry_sdk.get_current_span()
    if span is not None:
        span.set_data("stt.provider", provider)
        span.set_data("stt.audio_seconds", seconds)
        span.set_data("cost_usd", usd)

    log.info("stt usage provider=%s seconds=%s cost=$%.6f", provider, seconds, usd)
    return usd


def charge(entry, usage: Usage) -> None:
    """Add a meter to an entry's running totals.

    Added, never overwritten: a voice entry is transcribed in one job and extracted in
    another after the person reviews the text, and a retry spends money again.
    """
    if usage.empty:
        return
    entry.stt_cost_usd = (entry.stt_cost_usd or 0.0) + usage.stt_usd
    entry.llm_cost_usd = (entry.llm_cost_usd or 0.0) + usage.llm_usd
    entry.llm_input_tokens = (entry.llm_input_tokens or 0) + usage.llm_input_tokens
    entry.llm_cached_tokens = (entry.llm_cached_tokens or 0) + usage.llm_cached_tokens
    entry.llm_output_tokens = (entry.llm_output_tokens or 0) + usage.llm_output_tokens
    entry.llm_calls = (entry.llm_calls or 0) + usage.llm_calls

    log.info(
        "entry %s cost: stt $%.6f (%.1fs) + llm $%.6f (%s calls, %s in / %s cached / %s out)"
        " = $%.6f; entry total $%.6f",
        entry.id, usage.stt_usd, usage.stt_seconds, usage.llm_usd, usage.llm_calls,
        usage.llm_input_tokens, usage.llm_cached_tokens, usage.llm_output_tokens,
        usage.total_usd, entry.stt_cost_usd + entry.llm_cost_usd,
    )
    sentry_sdk.set_context(
        "cost",
        {
            "stt_usd": usage.stt_usd,
            "stt_seconds": usage.stt_seconds,
            "llm_usd": usage.llm_usd,
            "llm_calls": usage.llm_calls,
            "llm_input_tokens": usage.llm_input_tokens,
            "llm_output_tokens": usage.llm_output_tokens,
            "entry_total_usd": entry.stt_cost_usd + entry.llm_cost_usd,
        },
    )
