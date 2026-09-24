import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

import httpx
import sentry_sdk

from ..config import settings
from . import costs, retry

log = logging.getLogger(__name__)

_llm_gate = asyncio.Semaphore(settings.llm_concurrency)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(slots=True)
class LLMResult:
    data: dict
    model: str
    elapsed_ms: int


class LLMError(retry.ProviderError):
    pass


# One client for the life of the process: it keeps connections to the API open, so a
# check-in's three model calls do not each pay for a fresh TCP and TLS handshake.
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.llm_timeout_sec)
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _parse_json(raw: str) -> dict:
    """Schema-constrained output should already be clean; this is the belt to the braces."""
    text = _FENCE.sub("", raw.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    # Worth another attempt: the next sample may well come back clean.
    raise LLMError(f"model did not return JSON: {raw[:300]}", retryable=True)


async def _call_openai(system: str, user: str, schema: dict) -> tuple[str, str]:
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set")
    payload: dict = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        # Chat Completions, not the Responses API: structured outputs on the Luna tier
        # have a reported defect there where stray tokens land inside string values
        # while the JSON still validates. Schema-valid garbage is the one failure this
        # codebase is built to avoid.
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": schema},
        },
    }
    if settings.openai_reasoning_effort:
        payload["reasoning_effort"] = settings.openai_reasoning_effort
    else:
        # Reasoning models reject an explicit temperature; only send it otherwise.
        payload["temperature"] = 0
    with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {settings.openai_model}"):
        try:
            resp = await _http().post(
                f"{settings.openai_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )
        except httpx.RequestError as exc:
            # Timeouts and dropped connections: the request may never have arrived.
            raise LLMError(f"OpenAI unreachable: {type(exc).__name__}: {exc}", retryable=True) from exc

        if resp.status_code >= 400:
            retryable = retry.is_retryable_status(resp.status_code)
            # A 429 is either "slow down" or "the account is out of money". The second
            # does not get better in a few seconds.
            if resp.status_code == 429 and "insufficient_quota" in resp.text:
                retryable = False
            raise LLMError(
                f"OpenAI {resp.status_code}: {resp.text[:300]}",
                retryable=retryable,
                retry_after=retry.retry_after(resp),
            )

        try:
            body = resp.json()
        except ValueError as exc:
            raise LLMError(f"OpenAI returned non-JSON: {resp.text[:300]}", retryable=True) from exc
        # Recorded before parsing: a reply that fails to parse was still billed.
        costs.record_llm(body.get("model") or settings.openai_model, body.get("usage"))
    try:
        return body["choices"][0]["message"]["content"], settings.openai_model
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected OpenAI payload: {str(body)[:300]}", retryable=True) from exc


async def complete_json(system: str, user: str, schema: dict) -> LLMResult:
    started = time.perf_counter()

    async def attempt() -> LLMResult:
        raw, model = await _call_openai(system, user, schema)
        return LLMResult(
            data=_parse_json(raw),
            model=model,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    # The gate stays held through the back-off on purpose: a rate-limited provider is
    # better served by fewer callers waiting than by the next job starting fresh.
    async with _llm_gate:
        return await retry.run(attempt, retries=settings.llm_max_retries, label="llm")
