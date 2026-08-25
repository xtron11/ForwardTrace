"""Weekly report generation.

The model never sees raw audio or raw transcripts here. It sees verified facts and
precomputed numbers, and its job is narration only. Its output is then validated
against the criteria it was given before anything is stored.
"""

import json
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import Criterion, Goal, Report, Status, User
from . import prompts
from .aggregate import compute_stats
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)

VALID_STATUSES = {"no_evidence", "some_evidence", "clear_evidence"}

# Phrases that mean "nothing supports this". A model that writes one of these while
# claiming evidence has contradicted itself inside a single report, which reads worse
# to the person than either answer on its own. Cheap to catch, so catch it.
DENIAL_MARKERS = (
    "no evidence", "not present", "nothing in", "there is no", "no sign of",
    "was not", "did not", "no facts", "no mention",
    "нет факта", "нет фактов", "не было", "отсутству", "нет признак",
    "не представлен", "ничего не", "не зафиксирован", "нет упоминан",
)


def _is_denial(evidence: str) -> bool:
    lowered = evidence.lower()
    return any(marker in lowered for marker in DENIAL_MARKERS)


def _build_prompt(goal: Goal, criteria: list[Criterion], stats: dict) -> str:
    block = {
        "is_first_report": stats.get("is_first_report", False),
        "goal": goal.title,
        "why_it_matters": goal.why_text or "(not stated)",
        "their_definition_of_progress": [
            {"id": str(c.id), "criterion": c.text} for c in criteria
        ],
        "computed_statistics": {
            "days_logged": stats["days_logged"],
            "days_in_period": stats["period_days"],
            "longest_streak": stats["longest_streak"],
            "total_time": stats["total_human"],
            "counted_totals": [
                {
                    "what": m["name"],
                    "total": m["total"],
                    "unit": m["unit"],
                    "on_days": m["occasions"],
                }
                for m in stats.get("metrics", [])
            ],
            "by_category": [
                {
                    "category": c["category"],
                    "time": c["total_human"],
                    "sessions": c["sessions"],
                    "days_active": c["days_active"],
                    "time_coverage": c["time_coverage"],
                }
                for c in stats["categories"]
            ],
        },
        "reported_wins": stats["wins"],
        "reported_friction": stats["friction"],
        "moods": stats["moods"],
        "day_by_day": stats["daily"],
    }
    notes = [
        "Use only the numbers in computed_statistics. Do not recompute or estimate.",
        "time_coverage below 0.6 means most sessions had no stated duration; treat the "
        "total as a floor and avoid leaning on it.",
    ]
    if stats.get("is_first_report"):
        notes.append(
            "This is the person's FIRST report, covering only the first few days. Three "
            "days is not enough to show change, and claiming otherwise would be the "
            "first thing they read from you and a lie. Describe what they have started "
            "and what the record now contains; leave what_changed empty unless something "
            "genuinely happened for the first time. Say plainly that the picture gets "
            "sharper with more days. Do not compensate with warmth."
        )
    return json.dumps(block, ensure_ascii=False, indent=2) + "\n\nNotes:\n- " + "\n- ".join(notes)


def _validate(content: dict, criteria: list[Criterion], stats: dict) -> dict:
    valid_ids = {str(c.id) for c in criteria}
    seen: dict[str, dict] = {}

    for item in content.get("criteria_progress") or []:
        cid = str(item.get("criterion_id", ""))
        if cid not in valid_ids:
            continue  # invented id -> discard
        status = item.get("status")
        if status not in VALID_STATUSES:
            status = "no_evidence"
        evidence = (item.get("evidence") or "").strip()
        # Claiming evidence without providing any is the failure mode worth catching -
        # as is providing an "evidence" line that denies the thing it supposedly proves.
        if status != "no_evidence" and (not evidence or _is_denial(evidence)):
            status = "no_evidence"
        if status == "no_evidence":
            evidence = ""
        seen[cid] = {"criterion_id": cid, "status": status, "evidence": evidence[:600]}

    # Every criterion must appear, defaulting to the honest answer.
    ordered = []
    for criterion in criteria:
        cid = str(criterion.id)
        ordered.append(
            seen.get(cid, {"criterion_id": cid, "status": "no_evidence", "evidence": ""})
        )

    # Cap deterministically rather than asking the model to restrain itself. Three
    # strong items read as evidence; six read as padding, and the model will happily
    # split one event across two entries to fill the space.
    changed = [
        {"text": (c.get("text") or "").strip()[:600], "evidence": (c.get("evidence") or "").strip()[:600]}
        for c in (content.get("what_changed") or [])
        if (c.get("text") or "").strip() and (c.get("evidence") or "").strip()
    ][:3]

    pattern = content.get("pattern") or {}
    pattern_text = (pattern.get("text") or "").strip()
    confidence = pattern.get("confidence")
    if confidence not in {"low", "medium", "high"}:
        confidence = "low"
    # Four days is the floor for claiming a behavioural pattern.
    if stats["days_logged"] < 4:
        confidence = "low"

    return {
        "what_you_did": (content.get("what_you_did") or "").strip()[:1500],
        "what_changed": changed,
        "pattern": {"text": pattern_text[:800], "confidence": confidence},
        "friction": (content.get("friction") or "").strip()[:1000],
        "recommendation": (content.get("recommendation") or "").strip()[:1000],
        "closing": (content.get("closing") or "").strip()[:1000],
        "criteria_progress": ordered,
        "criteria_labels": {str(c.id): c.text for c in criteria},
    }


async def build_report(db: AsyncSession, report: Report) -> None:
    """Fills a pending report in place. Caller commits."""
    started = time.perf_counter()

    goal = await db.get(Goal, report.goal_id) if report.goal_id else None
    if goal is None:
        report.status = Status.failed.value
        report.error = "Goal no longer exists."
        return

    criteria = (
        (
            await db.execute(
                select(Criterion)
                .where(Criterion.goal_id == goal.id, Criterion.is_active.is_(True))
                .order_by(Criterion.position)
            )
        )
        .scalars()
        .all()
    )

    first_period = goal.started_on is not None and report.period_start == goal.started_on

    stats = await compute_stats(
        db, report.user_id, report.goal_id, report.period_start, report.period_end
    )
    stats["is_first_report"] = first_period

    # Snapshot the goal as it stood when the report was written. Reading the title live
    # would let a later rename rewrite the meaning of a report the person already read.
    stats["goal_title"] = goal.title
    stats["goal_why"] = goal.why_text
    stats["criteria_snapshot"] = [c.text for c in criteria]
    # Criteria added mid-period cannot have been evaluated over the whole week; say so
    # rather than quietly grading the week against a rule that did not exist for it.
    stats["criteria_changed_midperiod"] = any(
        c.created_at is not None and c.created_at.date() > report.period_start
        for c in criteria
    )
    report.stats = stats

    required = (
        settings.min_entries_first_report if first_period else settings.min_entries_for_report
    )
    if stats["entries"] < required:
        report.status = Status.failed.value
        report.error = (
            f"Only {stats['entries']} check-in(s) in this period; "
            f"{required} are needed for a meaningful report."
        )
        return

    user = await db.get(User, report.user_id)
    try:
        result = await complete_json(
            system=prompts.report_system(user.locale if user else "en"),
            user=_build_prompt(goal, criteria, stats),
            schema=prompts.REPORT_SCHEMA,
        )
    except LLMError as exc:
        report.status = Status.failed.value
        report.error = str(exc)[:500]
        return

    report.content = _validate(result.data, criteria, stats)
    report.model_name = result.model
    report.status = Status.done.value
    report.error = None
    report.generation_ms = int((time.perf_counter() - started) * 1000)


async def generate_report_task(report_id: uuid.UUID) -> None:
    """Background entrypoint. Owns its own session."""
    async with SessionLocal() as db:
        report = await db.get(Report, report_id)
        if report is None or report.status == Status.done.value:
            return
        report.status = Status.processing.value
        await db.commit()

        try:
            await build_report(db, report)
        except Exception as exc:  # noqa: BLE001
            log.exception("report %s crashed", report_id)
            await db.rollback()
            fresh = await db.get(Report, report_id)
            if fresh is not None:
                fresh.status = Status.failed.value
                fresh.error = f"Unexpected error: {type(exc).__name__}"
        await db.commit()
