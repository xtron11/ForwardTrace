"""Safety check of every message the person sends (levels 0-3).

Stage 2 stub: every message is level 0, so the call site in the conversation flow
exists and stage 7 (ticket 08) only fills this module in.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class SafetyResult:
    level: int
    # True when the model call failed and level 0 was assumed; the caller logs the
    # `safety_check_failed` event.
    failed: bool = False


async def safety_check(text: str, locale: str | None) -> SafetyResult:
    return SafetyResult(level=0, failed=False)
