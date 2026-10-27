"""Run the reference dialogs through the real model and write a report for a human.

    python scripts/eval_dialogs.py                                  # one version, v2.0
    python scripts/eval_dialogs.py --prompt-a v2.0 --prompt-b v2.1  # A/B of two prompts
    python scripts/eval_dialogs.py --prompt-a v2.1 --prompt-b path/to/draft.txt
    python scripts/eval_dialogs.py --model-a MODEL1 --model-b MODEL2   # A/B of two models
    python scripts/eval_dialogs.py --only normal-01 --out tests/eval/reports/try.md

For each scenario (tests/eval/dialogs.yaml) every human turn goes through the app's own
path: the safety check, then the level-3 template, the level-2 safety prompt, or the
messages that `prompts.compose_messages` builds from the scenario's prepared memory (the
same function the app calls) and `llm.stream_chat(model=...)`. The history grows with the
replies of the same version. Without -b there is one run; with it, A and B go through
identical scenarios and settings and are shown side by side.

The report (Markdown, plus a .json with the raw replies next to it) holds the summary
with per-version diagnostics, every scenario's memory and A | B table, an empty table
for the manual scores and the owner's main manual test. Only hard things are checked
automatically: the META line parsed, every {{quote:<id>}} is a known fact, and the
highest safety level equals `expected_safety`. Length, questions and tone are judged by
reading. `todo` scenarios and those without turns are skipped.

Exit code: 0 all good, 1 hard problems, 2 no OPENAI_API_KEY. Costs money: every turn is
two model calls per version.
"""

import argparse
import asyncio
import inspect
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402  (installed with uvicorn[standard])

from app.config import settings  # noqa: E402
from app.models import Fact, Message, User  # noqa: E402
from app.services import conversation, llm, prompts, safety  # noqa: E402

DEFAULT_PATH = ROOT / "tests" / "eval" / "dialogs.yaml"
REPORTS_DIR = ROOT / "tests" / "eval" / "reports"
# Until the prompt task registers "v2.1", the app's prompt is "v2.0".
DEFAULT_VERSION = "v2.0"
_PLACEHOLDER = re.compile(r"\{\{\s*quote\s*:\s*([^}]*?)\s*\}\}")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

CRITERIA = (
    "Естественность (звучит как живой собеседник)",
    "Попадание в то, что человек сказал",
    "Нет давления и навязанной пользы",
    "Память к месту (цитата и цель только по поводу)",
    "Хочется продолжать разговор",
)
MAIN_TEST = (
    "Главный ручной тест: можно ли провести 10 сообщений подряд (сценарий "
    "`ten_in_a_row`), не чувствуя, что ИИ ведёт к выполнению задачи."
)


def load_dialogs(path: Path | str = DEFAULT_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    dialogs = data.get("dialogs") if isinstance(data, dict) else data
    return list(dialogs or [])


def fact_uuid(dialog_id: str, label: str) -> uuid.UUID:
    """A stable id for a fact label of a dialog, so placeholders look like real ones."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"forwardtrace-eval/{dialog_id}/{label}")


def _day(value, today: date) -> date:
    """A memory date: an offset in days from the run day (-14), or an ISO date."""
    if isinstance(value, int):
        return today + timedelta(days=value)
    return date.fromisoformat(str(value))


def to_context_data(dialog: dict, today: date) -> prompts.ContextData:
    """The scenario's prepared memory as the `ContextData` the app builds from the DB."""
    memory = dialog.get("memory") or {}
    did = str(dialog.get("id"))
    known: dict[str, Fact] = {}
    fact_lines = []
    for item in memory.get("facts") or []:
        fid = fact_uuid(did, str(item["id"]))
        quote = str(item.get("quote") or "")
        when = _day(item.get("date", 0), today)
        ftype = str(item.get("type") or "struggle")
        known[str(fid)] = Fact(id=fid, local_date=when, type=ftype, text=quote, quote=quote)
        fact_lines.append(prompts.FactLine(str(fid), when, ftype, quote))
    threads = [
        prompts.ThreadLine(
            str(fact_uuid(did, "thread-" + str(t["id"]))),
            str(t["title"]),
            str(t.get("kind") or "struggle"),
            _day(t.get("since", 0), today),
        )
        for t in memory.get("threads") or []
    ]
    summaries = sorted(
        (_day(s["date"], today), str(s["text"])) for s in memory.get("summaries") or []
    )
    recent = [
        prompts.RecentLine(_day(h["date"], today), str(h["role"]), str(h["text"]))
        for h in memory.get("history") or []
    ]
    goal = memory.get("goal")
    return prompts.ContextData(
        locale=dialog.get("locale") or "en",
        goal_title=goal,
        anchor_quote=memory.get("anchor"),
        finish_line=memory.get("finish"),
        skill=goal,
        threads=threads,
        facts=fact_lines,
        day_summaries=summaries,
        recent=recent,
        current=None,
        known=known,
    )


@dataclass
class VersionRun:
    label: str
    replies: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # "model" | "template" per reply
    safety: int | None = None
    problems: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class DialogResult:
    id: str
    kind: str
    type: str
    expected_safety: int | None
    turns: list[str] = field(default_factory=list)
    memory: dict = field(default_factory=dict)
    skipped: bool = False
    runs: list[VersionRun] = field(default_factory=list)  # [A] or [A, B]

    @property
    def problems(self) -> list[str]:
        return [p for run in self.runs for p in run.problems]


@dataclass
class Report:
    results: list[DialogResult]
    labels: list[str]
    goals: dict[str, str | None] = field(default_factory=dict)  # dialog id -> goal title
    today: date = field(default_factory=date.today)

    @property
    def problems(self) -> int:
        return sum(1 for r in self.results if r.problems)

    def diagnostics(self) -> list[dict]:
        """Per version: the share of replies with "?", the mean length in words, and the
        share of replies naming the goal when the person's turn did not."""
        rows = []
        for index, label in enumerate(self.labels):
            replies, off_goal, off_goal_hits = [], 0, 0
            for r in self.results:
                if r.skipped or index >= len(r.runs):
                    continue
                goal = self.goals.get(r.id)
                for turn, text, source in zip(r.turns, r.runs[index].replies, r.runs[index].sources):
                    if source != "model":
                        continue
                    replies.append(text)
                    if goal and not _mentions_goal(turn, goal):
                        off_goal += 1
                        off_goal_hits += _mentions_goal(text, goal)
            n = len(replies)
            rows.append(
                {
                    "label": label,
                    "replies": n,
                    "question_share": (sum("?" in t for t in replies) / n) if n else None,
                    "mean_words": (sum(len(t.split()) for t in replies) / n) if n else None,
                    "goal_without_cause_share": (off_goal_hits / off_goal) if off_goal else None,
                    "goal_without_cause_n": off_goal,
                }
            )
        return rows

    def text(self) -> str:
        ran = [r for r in self.results if not r.skipped]
        lines = [
            f"Scenarios: {len(self.results)}, run: {len(ran)}, "
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
            levels = ",".join("-" if x.safety is None else str(x.safety) for x in r.runs) or "-"
            lines.append(f"{r.id:<14} {r.kind:<9} safety {levels} (expected {r.expected_safety})  {status}")
        for row in self.diagnostics():
            lines.append(f"{row['label']}: " + _diag_text(row))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "labels": self.labels,
            "date": self.today.isoformat(),
            "with_problems": self.problems,
            "diagnostics": self.diagnostics(),
            "results": [asdict(r) for r in self.results],
        }


# ------------------------------------------------------------------ checks and numbers


def _stem(word: str) -> str:
    return word.lower().strip(".,!?;:«»\"'()")[:5]


def _mentions_goal(text: str, goal: str | None) -> bool:
    """The app's `mentions_goal` once it exists; otherwise the same idea: a word of the
    goal (by its first five letters) occurs in the text."""
    app = getattr(conversation, "mentions_goal", None)
    if app:
        return bool(app(text, goal, goal))
    if not goal:
        return False
    words = {_stem(w) for w in goal.split() if len(w.strip(".,!?;:«»\"'()")) >= 4}
    return any(_stem(w) in words for w in text.split())


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def _diag_text(row: dict) -> str:
    words = "-" if row["mean_words"] is None else f"{row['mean_words']:.1f}"
    return (
        f"replies {row['replies']}, with '?' {_pct(row['question_share'])}, "
        f"mean words {words}, goal without cause {_pct(row['goal_without_cause_share'])} "
        f"(of {row['goal_without_cause_n']})"
    )


def _meta_ok(raw: str) -> bool:
    """The reply ends with <<<META>>> and a JSON object."""
    if prompts.META_SEPARATOR not in raw:
        return False
    tail = _FENCE.sub("", raw.split(prompts.META_SEPARATOR, 1)[1].strip())
    for candidate in (tail, tail[tail.find("{") : tail.rfind("}") + 1]):
        try:
            if isinstance(json.loads(candidate), dict):
                return True
        except json.JSONDecodeError:
            continue
    return False


def _check(raw: str, known: dict[str, Fact]) -> tuple[str, list[str]]:
    """The reply's visible text and its hard problems (META, unknown fact id)."""
    problems = []
    if not _meta_ok(raw):
        problems.append("meta")
    body = raw.split(prompts.META_SEPARATOR, 1)[0]
    for found in _PLACEHOLDER.findall(body):
        try:
            fid = str(uuid.UUID(found))
        except ValueError:
            fid = found
        if fid not in known:
            problems.append("unknown_fact")
            break
    renderer = conversation.ReplyRenderer(known)
    renderer.feed(raw)
    reply = renderer.finish()
    shown = "".join(s["text"] if s["type"] == "text" else f"«{s['quote']}»" for s in reply.segments)
    return shown, problems


# ------------------------------------------------------------------ the run


async def _maybe(value):
    return await value if inspect.isawaitable(value) else value


async def _default_chat(messages: list[dict], model: str | None) -> str:
    return "".join([piece async for piece in llm.stream_chat(messages, model=model)])


async def _default_check(text: str, locale: str | None) -> int:
    return (await safety.safety_check(text, locale)).level


async def _one_version(
    dialog: dict, data: prompts.ContextData, turns: list[str], *, chat, check, version, model,
    levels: dict[str, int], label: str, today: date,
) -> VersionRun:
    run = VersionRun(label=label)
    locale = data.locale
    person = User(locale=locale, country=dialog.get("country"))
    today_lines: list[prompts.RecentLine] = []
    today_messages: list[Message] = []
    past = list(data.recent)
    highest = 0
    for turn in turns:
        if turn not in levels:
            levels[turn] = int(await _maybe(check(turn, locale)))
        level = levels[turn]
        highest = max(highest, level)
        today_messages.append(Message(role="user", content_raw=turn, content=[{"type": "text", "text": turn}]))
        if level >= 3:
            shown, source = safety.level3_text(person), "template"  # nothing to check
        else:
            if level == 2:
                messages = safety.level2_messages(locale, today_messages)
                known: dict[str, Fact] = {}
            else:
                step = replace(data, recent=past + today_lines, current=turn)
                messages = prompts.compose_messages(step, version=version, soft=level == 1)
                known = data.known
            raw = await _maybe(chat(messages, model))
            shown, problems = _check(raw, known)
            if level == 2:  # the safety protocol answers in plain text, no META
                problems = [p for p in problems if p != "meta"]
            source = "model"
            for problem in problems:
                if problem not in run.problems:
                    run.problems.append(problem)
        run.replies.append(shown)
        run.sources.append(source)
        today_lines += [
            prompts.RecentLine(today, "user", turn),
            prompts.RecentLine(today, "assistant", shown),
        ]
        today_messages.append(
            Message(role="assistant", content_raw=shown, content=[{"type": "text", "text": shown}])
        )
    run.safety = highest
    expected = dialog.get("expected_safety")
    if expected is not None and int(expected) != highest:
        run.problems.append(f"safety {highest} != {expected}")
    return run


async def run(
    dialogs: list[dict],
    *,
    chat=None,
    check=None,
    version_a: str = DEFAULT_VERSION,
    version_b: str | None = None,
    model_a: str | None = None,
    model_b: str | None = None,
    today: date | None = None,
) -> Report:
    """`chat(messages, model) -> str` and `check(text, locale) -> int` (plain or async)
    are the seams for tests; by default the real `stream_chat` and `safety_check`.
    B runs when `version_b` or `model_b` is given; the missing half repeats A's."""
    chat = chat or _default_chat
    check = check or _default_check
    today = today or date.today()
    two = version_b is not None or model_b is not None
    # Resolve every version up front: an unknown name fails before any model is called.
    builders = [(prompts.resolve_prompt(version_a), version_a, model_a)]
    if two:
        vb = version_b or version_a
        builders.append((prompts.resolve_prompt(vb), vb, model_b or model_a))
    labels = [
        (Path(name).name if str(name).endswith(".txt") else str(name))
        + (f" @ {model}" if model else "")
        for _, name, model in builders
    ]
    if len(labels) == 2 and labels[0] == labels[1]:
        labels = [labels[0] + " (A)", labels[1] + " (B)"]

    results, goals = [], {}
    for dialog in dialogs:
        turns = [str(t) for t in (dialog.get("turns") or []) if str(t or "").strip()]
        result = DialogResult(
            id=str(dialog.get("id")),
            kind=str(dialog.get("kind") or "normal"),
            type=str(dialog.get("type") or ""),
            expected_safety=dialog.get("expected_safety"),
            turns=turns,
            memory=dialog.get("memory") or {},
        )
        goals[result.id] = (dialog.get("memory") or {}).get("goal")
        if dialog.get("todo") or not turns:
            result.skipped = True
            results.append(result)
            continue
        levels: dict[str, int] = {}  # one safety check per turn, shared by A and B
        data = to_context_data(dialog, today)
        for (builder, name, model), label in zip(builders, labels):
            try:
                result.runs.append(
                    await _one_version(
                        dialog, data, turns, chat=chat, check=check, version=builder,
                        model=model, levels=levels, label=label, today=today,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one broken scenario must not stop the run
                result.runs.append(
                    VersionRun(label=label, problems=["error"], error=f"{type(exc).__name__}: {exc}")
                )
        results.append(result)
    return Report(results, labels, goals, today)


# ------------------------------------------------------------------ the report


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def _memory_lines(memory: dict) -> list[str]:
    if not memory:
        return ["_(память не задана)_"]
    lines = []
    for key, name in (("goal", "Цель"), ("anchor", "Мотивация"), ("finish", "Финиш")):
        if memory.get(key):
            lines.append(f"- {name}: {memory[key]}")
    for f in memory.get("facts") or []:
        lines.append(f"- факт {f['id']} ({f.get('date')}, {f.get('type')}): «{f.get('quote')}»")
    for t in memory.get("threads") or []:
        lines.append(f"- нить {t['id']} ({t.get('kind', 'struggle')}, с {t.get('since')}): {t['title']}")
    for s in memory.get("summaries") or []:
        lines.append(f"- день {s['date']}: {s['text']}")
    for h in memory.get("history") or []:
        lines.append(f"- {h['date']} {h['role']}: {h['text']}")
    return lines or ["_(память пуста)_"]


def render_markdown(report: Report) -> str:
    ran = [r for r in report.results if not r.skipped]
    out = [
        f"# Эталонные диалоги — {report.today.isoformat()}",
        "",
        "Версии: " + "; ".join(f"**{'AB'[i]}** = {label}" for i, label in enumerate(report.labels)),
        "",
        "## Сводка",
        "",
        f"- Сценариев: {len(report.results)}, прогнано: {len(ran)}, заготовок (TODO): "
        f"{len(report.results) - len(ran)}",
        f"- Сценариев с жёсткими проблемами: {report.problems}",
        "",
        "| Версия | Ответов | Доля с «?» | Средняя длина, слов | Цель без повода |",
        "|---|---|---|---|---|",
    ]
    for row in report.diagnostics():
        words = "-" if row["mean_words"] is None else f"{row['mean_words']:.1f}"
        out.append(
            f"| {_cell(row['label'])} | {row['replies']} | {_pct(row['question_share'])} | {words} | "
            f"{_pct(row['goal_without_cause_share'])} (из {row['goal_without_cause_n']}) |"
        )
    out += ["", "Цель без повода — доля ответов с упоминанием цели там, где реплика человека её не касалась.", ""]
    problem_rows = [r for r in ran if r.problems]
    if problem_rows:
        out += ["### Жёсткие проблемы", ""]
        for r in problem_rows:
            for x in r.runs:
                if x.problems:
                    err = f" ({x.error})" if x.error else ""
                    out.append(f"- `{r.id}` {x.label}: {', '.join(x.problems)}{err}")
        out.append("")
    out += ["## Сценарии", ""]
    for r in report.results:
        out.append(f"### {r.id} — {r.type or r.kind}")
        out.append("")
        if r.skipped:
            out += ["_Заготовка (TODO(owner)): сценарий не написан, пропущен._", ""]
            continue
        out += ["Память:", ""] + _memory_lines(r.memory) + [""]
        heads = " | ".join(f"{'AB'[i]}: {_cell(x.label)}" for i, x in enumerate(r.runs))
        out += [f"| Человек | {heads} |", "|---|" + "---|" * len(r.runs)]
        for i, turn in enumerate(r.turns):
            cells = " | ".join(_cell(x.replies[i]) if i < len(x.replies) else "" for x in r.runs)
            out.append(f"| {_cell(turn)} | {cells} |")
        out.append("")
        levels = ", ".join(f"{'AB'[i]}={x.safety}" for i, x in enumerate(r.runs))
        out.append(f"Уровень безопасности: {levels} (ожидался {r.expected_safety}).")
        out.append("")
    out += ["## Оценки (вручную, 1–5)", "", "| Критерий | " + " | ".join("AB"[: len(report.labels)]) + " |",
            "|---|" + "---|" * len(report.labels)]
    out += [f"| {c} | " + " | ".join("" for _ in report.labels) + " |" for c in CRITERIA]
    out += ["", "## Главный ручной тест", "", f"- [ ] {MAIN_TEST}", ""]
    return "\n".join(out)


def _safe(name: str) -> str:
    return re.sub(r"[^\w.-]+", "_", name).strip("_")


def default_out(report: Report) -> Path:
    names = "-vs-".join(_safe(x) for x in report.labels)
    return REPORTS_DIR / f"{report.today.isoformat()}-{names}.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", default=str(DEFAULT_PATH), help="dialogs YAML")
    parser.add_argument("--only", action="append", help="run only this scenario id (repeatable)")
    parser.add_argument("--prompt-a", default=DEFAULT_VERSION, help="version name or path to a .txt")
    parser.add_argument("--prompt-b", help="second version: a name from CHAT_PROMPTS or a .txt path")
    parser.add_argument("--model-a", help="model for A (default CHAT_MODEL)")
    parser.add_argument("--model-b", help="second model; same prompt as A unless --prompt-b")
    parser.add_argument("--out", help="the Markdown report path (a .json goes next to it)")
    args = parser.parse_args(argv)
    try:  # Russian replies in the console; Windows consoles default to a legacy code page
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
    try:
        report = asyncio.run(
            run(
                dialogs,
                version_a=args.prompt_a,
                version_b=args.prompt_b,
                model_a=args.model_a,
                model_b=args.model_b,
            )
        )
    except ValueError as exc:  # an unknown prompt version
        print(f"error: {exc}")
        return 2
    print(report.text())
    out = Path(args.out) if args.out else default_out(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(report), encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nReport: {out}")
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
