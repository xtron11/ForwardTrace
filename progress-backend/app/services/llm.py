import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
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


def _error_for(resp: httpx.Response, text: str) -> LLMError:
    retryable = retry.is_retryable_status(resp.status_code)
    # A 429 is either "slow down" or "the account is out of money". The second
    # does not get better in a few seconds.
    if resp.status_code == 429 and "insufficient_quota" in text:
        retryable = False
    return LLMError(
        f"OpenAI {resp.status_code}: {text[:300]}",
        retryable=retryable,
        retry_after=retry.retry_after(resp),
    )


def _base_payload(model: str, messages: list[dict], reasoning_effort: str | None) -> dict:
    """What every Chat Completions call sends: the model, the messages, and either a
    reasoning effort or (for models without reasoning) temperature 0."""
    payload: dict = {"model": model, "messages": messages}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    else:
        # Reasoning models reject an explicit temperature; only send it otherwise.
        payload["temperature"] = 0
    return payload


async def _call_openai(
    system: str,
    user: str,
    schema: dict,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[str, str]:
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set")
    model = model or settings.openai_model
    payload = _base_payload(
        model,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        reasoning_effort,
    )
    # Chat Completions, not the Responses API: structured outputs on the Luna tier
    # have a reported defect there where stray tokens land inside string values
    # while the JSON still validates. Schema-valid garbage is the one failure this
    # codebase is built to avoid.
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": "result", "strict": True, "schema": schema},
    }
    with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {model}"):
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
            raise _error_for(resp, resp.text)

        try:
            body = resp.json()
        except ValueError as exc:
            raise LLMError(f"OpenAI returned non-JSON: {resp.text[:300]}", retryable=True) from exc
        # Recorded before parsing: a reply that fails to parse was still billed.
        costs.record_llm(body.get("model") or model, body.get("usage"))
    try:
        return body["choices"][0]["message"]["content"], model
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected OpenAI payload: {str(body)[:300]}", retryable=True) from exc


async def _complete(
    system: str, user: str, schema: dict, *, model: str, reasoning_effort: str | None
) -> LLMResult:
    started = time.perf_counter()

    async def attempt() -> LLMResult:
        raw, used = await _call_openai(
            system, user, schema, model=model, reasoning_effort=reasoning_effort
        )
        return LLMResult(
            data=_parse_json(raw),
            model=used,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    # The gate stays held through the back-off on purpose: a rate-limited provider is
    # better served by fewer callers waiting than by the next job starting fresh.
    async with _llm_gate:
        return await retry.run(attempt, retries=settings.llm_max_retries, label="llm")


async def complete_json(system: str, user: str, schema: dict) -> LLMResult:
    """A JSON answer from OPENAI_MODEL at OPENAI_REASONING_EFFORT."""
    return await _complete(
        system,
        user,
        schema,
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort,
    )


async def complete_json_with(
    system: str, user: str, schema: dict, *, model: str, reasoning_effort: str | None = None
) -> LLMResult:
    """`complete_json` with another model (SAFETY_MODEL). Effort None: no reasoning
    effort is sent, temperature 0 instead."""
    return await _complete(system, user, schema, model=model, reasoning_effort=reasoning_effort)


async def stream_chat(
    messages: list[dict],
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> AsyncIterator[str]:
    """The conversation reply, piece by piece as the model writes it.

    Defaults: CHAT_MODEL (or OPENAI_MODEL) at CHAT_REASONING_EFFORT. Only opening the
    stream is retried: once text has gone to the person, a retry would repeat it.
    The final usage block is charged to the ambient `costs.track()` meter.
    """
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set")
    model = model or settings.chat_model or settings.openai_model
    effort = reasoning_effort if reasoning_effort is not None else settings.chat_reasoning_effort
    payload = _base_payload(model, messages, effort)
    payload["stream"] = True
    payload["stream_options"] = {"include_usage": True}
    client = _http()

    async def open_stream() -> httpx.Response:
        request = client.build_request(
            "POST",
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
        try:
            resp = await client.send(request, stream=True)
        except httpx.RequestError as exc:
            raise LLMError(
                f"OpenAI unreachable: {type(exc).__name__}: {exc}", retryable=True
            ) from exc
        if resp.status_code >= 400:
            text = (await resp.aread()).decode("utf-8", "replace")
            await resp.aclose()
            raise _error_for(resp, text)
        return resp

    async with _llm_gate:
        with sentry_sdk.start_span(op="gen_ai.chat", name=f"chat {model}"):
            resp = await retry.run(open_stream, retries=settings.llm_max_retries, label="llm")
            usage: dict | None = None
            reported = model
            try:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        log.warning("stream_chat: skipped a malformed chunk")
                        continue
                    if chunk.get("error"):
                        raise LLMError(f"OpenAI stream error: {str(chunk['error'])[:300]}")
                    reported = chunk.get("model") or reported
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    for choice in chunk.get("choices") or []:
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            yield piece
            except httpx.HTTPError as exc:
                raise LLMError(f"OpenAI stream broke: {type(exc).__name__}: {exc}") from exc
            finally:
                await resp.aclose()
                # Billed whether or not the stream ran to the end.
                if usage is not None:
                    costs.record_llm(reported, usage)


async def embed(texts: list[str]) -> list[list[float]]:
    """One vector per text from EMBEDDING_MODEL, in one request, in input order.

    The caller checks `settings.embedding_model` first: with no model there is no search
    by meaning, and facts are found by date instead.
    """
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set")
    model = settings.embedding_model
    if not model:
        raise LLMError("EMBEDDING_MODEL is not set")
    if not texts:
        return []

    async def attempt() -> list[list[float]]:
        with sentry_sdk.start_span(op="gen_ai.embeddings", name=f"embeddings {model}"):
            try:
                resp = await _http().post(
                    f"{settings.openai_base_url}/embeddings",
                    headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                    json={"model": model, "input": texts},
                )
            except httpx.RequestError as exc:
                raise LLMError(
                    f"OpenAI unreachable: {type(exc).__name__}: {exc}", retryable=True
                ) from exc
            if resp.status_code >= 400:
                raise _error_for(resp, resp.text)
            try:
                body = resp.json()
                costs.record_embedding(body.get("model") or model, body.get("usage"))
                rows = sorted(body["data"], key=lambda row: row["index"])
                vectors = [[float(x) for x in row["embedding"]] for row in rows]
            except (ValueError, KeyError, TypeError) as exc:
                raise LLMError(f"unexpected embeddings payload: {resp.text[:300]}") from exc
        if len(vectors) != len(texts):
            raise LLMError(f"embeddings: {len(vectors)} vectors for {len(texts)} texts")
        return vectors

    async with _llm_gate:
        return await retry.run(attempt, retries=settings.llm_max_retries, label="embeddings")
