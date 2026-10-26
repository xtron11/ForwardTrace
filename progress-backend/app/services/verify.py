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
