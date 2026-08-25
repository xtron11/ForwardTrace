"""Post-hoc verification of model output against the source transcript.

The model is asked to quote. This module checks that it actually did, and throws away
anything it cannot find. This is the difference between "we told it not to hallucinate"
and "a hallucination cannot reach the database".
"""

import re
import unicodedata
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")

# A quote shorter than this is meaningless as evidence ("I", "did", "the").
MIN_QUOTE_CHARS = 8
# Speech-to-text is imperfect and models normalise filler words, so demand
# near-identity rather than exact identity.
FUZZY_THRESHOLD = 0.90


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = _PUNCT.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def quote_supported(quote: str, transcript_norm: str) -> bool:
    """True when the quote genuinely appears in the transcript."""
    q = normalize(quote)
    if len(q) < MIN_QUOTE_CHARS:
        return False
    if q in transcript_norm:
        return True
    # Sliding comparison over same-length windows, stepping by a word at a time.
    words = transcript_norm.split()
    span = max(1, len(q.split()))
    for i in range(0, max(1, len(words) - span + 1)):
        window = " ".join(words[i : i + span])
        if SequenceMatcher(None, q, window).ratio() >= FUZZY_THRESHOLD:
            return True
    return False


def normalize_category(raw: str, known: dict[str, str]) -> tuple[str, str]:
    """Collapse 'coding' / 'Coding ' / 'code' onto one key so weekly stats don't split.

    Returns (display, key). `known` maps key -> display for this user's history.
    """
    display = (raw or "Other").strip()[:80] or "Other"
    key = normalize(display)[:80] or "other"
    if key in known:
        return known[key], key
    for existing_key, existing_display in known.items():
        if SequenceMatcher(None, key, existing_key).ratio() >= 0.88:
            return existing_display, existing_key
    return display.title() if display.islower() else display, key


def clean_facts(
    items: list[dict],
    transcript_norm: str,
    valid_goal_ids: set[str] | None = None,
    limit: int = 6,
) -> tuple[list[dict], int]:
    """Keep {text, quote} items whose quote checks out. Returns (kept, dropped_count)."""
    kept, dropped = [], 0
    for item in items or []:
        text = (item.get("text") or "").strip()
        quote = (item.get("quote") or "").strip()
        if not text:
            continue
        if not quote_supported(quote, transcript_norm):
            dropped += 1
            continue
        goal_id = (item.get("goal_id") or "").strip()
        if valid_goal_ids is not None and goal_id not in valid_goal_ids:
            goal_id = ""  # invented id -> unrouted rather than misfiled
        kept.append({"text": text[:400], "quote": quote[:400], "goal_id": goal_id or None})
        if len(kept) >= limit:
            break
    return kept, dropped


def clean_metrics(items: list[dict], transcript_norm: str, limit: int = 4) -> tuple[list[dict], int]:
    """Keep quantities whose quote checks out. Returns (kept, dropped_count).

    A fabricated number is worse than a missing one: it gets summed across the week and
    presented back as measured growth.
    """
    kept, dropped = [], 0
    for item in items or []:
        name = (item.get("name") or "").strip()
        unit = (item.get("unit") or "").strip()
        quote = (item.get("quote") or "").strip()
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError):
            dropped += 1
            continue
        if not name or value <= 0 or value > 1_000_000:
            dropped += 1
            continue
        if not quote_supported(quote, transcript_norm):
            dropped += 1
            continue
        kept.append(
            {
                "name": name[:60],
                "value": int(value) if value.is_integer() else round(value, 2),
                "unit": unit[:24],
                "quote": quote[:300],
            }
        )
        if len(kept) >= limit:
            break
    return kept, dropped
