import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

import httpx

from ..config import settings

log = logging.getLogger(__name__)

_llm_gate = asyncio.Semaphore(settings.llm_concurrency)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(slots=True)
class LLMResult:
    data: dict
    model: str
    elapsed_ms: int


class LLMError(RuntimeError):
    pass


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
    raise LLMError(f"model did not return JSON: {raw[:300]}")


async def _call_ollama(system: str, user: str, schema: dict) -> tuple[str, str]:
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        # `format` is a real grammar constraint in Ollama, not a prompt hint:
        # the sampler cannot emit tokens that break the schema.
        "format": schema,
        "options": {"temperature": 0, "top_p": 0.9, "num_ctx": 8192},
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
    if resp.status_code >= 400:
        raise LLMError(f"Ollama {resp.status_code}: {resp.text[:300]}")
    return resp.json()["message"]["content"], settings.ollama_model


async def _call_openai(system: str, user: str, schema: dict) -> tuple[str, str]:
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set but LLM_PROVIDER=openai")
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
    async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
        resp = await client.post(
            f"{settings.openai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
    if resp.status_code >= 400:
        raise LLMError(f"OpenAI {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"], settings.openai_model


async def complete_json(system: str, user: str, schema: dict) -> LLMResult:
    provider = settings.llm_provider.lower()
    caller = {"ollama": _call_ollama, "openai": _call_openai}.get(provider)
    if caller is None:
        raise LLMError(f"unknown LLM_PROVIDER={settings.llm_provider!r}")

    started = time.perf_counter()
    last_error: Exception | None = None

    async with _llm_gate:
        for attempt in range(settings.llm_max_retries + 1):
            try:
                raw, model = await caller(system, user, schema)
                return LLMResult(
                    data=_parse_json(raw),
                    model=model,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                )
            except (LLMError, httpx.HTTPError) as exc:
                last_error = exc
                log.warning("llm attempt %s failed: %s", attempt + 1, exc)
                if attempt < settings.llm_max_retries:
                    await asyncio.sleep(1.5 * (attempt + 1))

    raise LLMError(str(last_error))
