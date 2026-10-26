"""Run the reference dialogs through the real models and check every reply.

    python scripts/eval_dialogs.py                       # tests/eval/dialogs.yaml
    python scripts/eval_dialogs.py --only normal-01 --out report.json

For each dialog (tests/eval/dialogs.yaml) every turn goes through the same path as in
the app: the safety check (SAFETY_MODEL), then the level-3 template, the level-2
safety prompt, or the day's conversation prompt with the dialog's facts (CHAT_MODEL).
Each reply is checked for:

- length (REPLY_MAX_WORDS, or REPLY_MAX_WORDS_LONG after a long message),
- at most one question,
- no BANNED word (flattery, diagnoses),
- only known fact ids in {{quote:<id>}} placeholders,
- and the dialog's highest safety level against `expected_safety`.

A report is printed (and written as JSON with --out). Exit code: 0 all good, 1 some
problems, 2 no OPENAI_API_KEY. Dialogs with no turns are skipped as TODO.

Costs money: every turn is two model calls.
"""

import argparse
import asyncio
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  (installed with uvicorn[standard])

from app.config import settings  # noqa: E402
from app.models import Fact, Message, User  # noqa: E402
from app.services import llm, prompts, safety  # noqa: E402
from app.services.conversation import ReplyRenderer, check_reply_rules  # noqa: E402

DEFAULT_PATH = ROOT / "tests" / "eval" / "dialogs.yaml"
_PLACEHOLDER = re.compile(r"\{\{\s*quote\s*:\s*([^}]*?)\s*\}\}")


def load_dialogs(path: Path | str = DEFAULT_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    dialogs = data.get("dialogs") if isinstance(data, dict) else data
    return list(dialogs or [])


def fact_uuid(dialog_id: str, label: str) -> uuid.UUID:
    """A stable id for a fact label of a dialog, so placeholders look like real ones."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"forwardtrace-eval/{dialog_id}/{label}")


@dataclass
class DialogResult:
    id: str
    kind: str
    expected_safety: int | None
    safety: int | None = None
    replies: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str | None = None


@dataclass
class Report:
    results: list[DialogResult]

    @property
    def problems(self) -> int:
        return sum(1 for r in self.results if r.problems)

    def text(self) -> str:
        ran = [r for r in self.results if not r.skipped]
        lines = [
            f"Dialogs: {len(self.results)}, run: {len(ran)}, "
            f"TODO: {len(self.results) - len(ran)}, with problems: {self.problems}",
            "",
        ]
        for r in self.results:
            if r.skipped:
                status = "TODO"
            elif r.problems:
                status = "FAIL " + ", ".join(r.problems)
            else:
                status = "ok"
            level = "-" if r.safety is None else str(r.safety)
            lines.append(f"{r.id:<14} {r.kind:<9} safety {level} (expected {r.expected_safety})  {status}")
            if r.error:
                lines.append(f"{'':<14} error: {r.error}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"results": [asdict(r) for r in self.results], "with_problems": self.problems}


def _facts(dialog: dict) -> dict[str, Fact]:
    known: dict[str, Fact] = {}
    for item in dialog.get("facts") or []:
        fid = fact_uuid(dialog["id"], str(item["id"]))
        quote = str(item.get("quote") or "")
        known[str(fid)] = Fact(
            id=fid,
            local_date=date.fromisoformat(str(item.get("date"))),
            type=str(item.get("type") or "struggle"),
            text=quote,
            quote=quote,
        )
    return known


def _check(raw: str, known: dict[str, Fact], user_words: int) -> tuple[str, list[str]]:
    """The reply's visible text and its problems."""
    body = raw.split(prompts.META_SEPARATOR, 1)[0]
    problems = []
    for found in _PLACEHOLDER.findall(body):
        try:
            fid = str(uuid.UUID(found))
        except ValueError:
            fid = found
        if fid not in known:
            problems.append("unknown_fact")
            break
    renderer = ReplyRenderer(known)
    renderer.feed(raw)
    reply = renderer.finish()
    prose = "".join(s["text"] for s in reply.segments if s["type"] == "text")
    shown = "".join(s["text"] if s["type"] == "text" else f"«{s['quote']}»" for s in reply.segments)
    return shown, check_reply_rules(prose, user_words) + problems


async def _one(dialog: dict, chat, check) -> DialogResult:
    turns = [str(t) for t in (dialog.get("turns") or []) if str(t or "").strip()]
    result = DialogResult(
        id=str(dialog.get("id")),
        kind=str(dialog.get("kind") or "normal"),
        expected_safety=dialog.get("expected_safety"),
    )
    if not turns:
        result.skipped = True
        return result

    locale = dialog.get("locale") or "en"
    person = User(locale=locale, country=dialog.get("country"))
    known = _facts(dialog)
    fact_lines = [
        f"[{fid}] {f.local_date.isoformat()} {f.type}: \"{f.quote}\"" for fid, f in known.items()
    ]
    history: list[Message] = []
    highest = 0
    for turn in turns:
        level = (await check(turn, locale)).level
        highest = max(highest, level)
        history.append(Message(role="user", content_raw=turn, content=[{"type": "text", "text": turn}]))
        if level >= 3:
            shown = safety.level3_text(person)  # a template: nothing to check
        else:
            if level == 2:
                messages = safety.level2_messages(locale, history)
                usable: dict[str, Fact] = {}
            else:
                system = prompts.chat_system(
                    locale,
                    skill=dialog.get("skill"),
                    anchor_quote=dialog.get("goal"),
                    finish_line=dialog.get("finish"),
                    threads=[],
                    facts=fact_lines,
                    days=[],
                    max_words=settings.reply_max_words,
                    soft=level == 1,
                )
                messages = [{"role": "system", "content": system}] + [
                    {"role": m.role, "content": m.content_raw} for m in history
                ]
                usable = known
            raw = "".join([piece async for piece in chat(messages)])
            shown, problems = _check(raw, usable, len(turn.split()))
            for problem in problems:
                if problem not in result.problems:
                    result.problems.append(problem)
        result.replies.append(shown)
        history.append(
            Message(role="assistant", content_raw=shown, content=[{"type": "text", "text": shown}])
        )
    result.safety = highest
    expected = result.expected_safety
    if expected is not None and int(expected) != highest:
        result.problems.append(f"safety {highest} != {expected}")
    return result


async def run(dialogs: list[dict], *, chat=None, check=None) -> Report:
    chat = chat or llm.stream_chat
    check = check or safety.safety_check
    results = []
    for dialog in dialogs:
        try:
            results.append(await _one(dialog, chat, check))
        except Exception as exc:  # noqa: BLE001 - one broken dialog must not stop the run
            results.append(
                DialogResult(
                    id=str(dialog.get("id")),
                    kind=str(dialog.get("kind") or "normal"),
                    expected_safety=dialog.get("expected_safety"),
                    problems=["error"],
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return Report(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", default=str(DEFAULT_PATH), help="dialogs YAML")
    parser.add_argument("--only", action="append", help="run only this dialog id (repeatable)")
    parser.add_argument("--out", help="also write the report as JSON here")
    args = parser.parse_args(argv)
    try:  # Russian replies in the report; Windows consoles default to a legacy code page
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is not set: this script talks to the real model. "
            "Put the key in progress-backend/.env and run it again.\n"
            "OPENAI_API_KEY не задан: скрипт обращается к настоящей модели. "
            "Добавьте ключ в progress-backend/.env и запустите снова."
        )
        return 2

    dialogs = load_dialogs(args.file)
    if args.only:
        dialogs = [d for d in dialogs if d.get("id") in set(args.only)]
    report = asyncio.run(run(dialogs))
    print(report.text())
    if args.out:
        Path(args.out).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
