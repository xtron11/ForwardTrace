"""Reference dialogs and the prompt registry (v2.1 task 13): the dialogs file, the
A/B report built with fake `chat`/`check`, and the pure context composing."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from app.services import prompts

TODAY = date(2026, 10, 27)
FACT_QUOTE = "old words"


def _eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval_dialogs.py"
    spec = importlib.util.spec_from_file_location("eval_dialogs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dialog(did="ok", turns=("I did it",), expected=0, kind="normal", todo=False, facts=True):
    memory = {
        "goal": "english",
        "anchor": "I want to speak freely",
        "finish": "pass the interview",
        "facts": [{"id": "f1", "date": -10, "type": "struggle", "quote": FACT_QUOTE}] if facts else [],
        "threads": [{"id": "t1", "title": "calls", "kind": "struggle", "since": -10}],
        "summaries": [{"date": -3, "text": "a short day"}],
        "history": [
            {"date": -3, "role": "user", "text": "yesterday I tried"},
            {"date": -3, "role": "assistant", "text": "how did it go"},
        ],
    }
    return {
        "id": did, "kind": kind, "type": "achievement", "locale": "en", "memory": memory,
        "turns": list(turns), "expected_safety": expected, "todo": todo,
    }


class TestDialogsFile:
    def test_counts_and_shape(self):
        module = _eval_module()
        dialogs = module.load_dialogs()
        ids = [d["id"] for d in dialogs]
        assert len(ids) == len(set(ids)) == 31
        normal = [d for d in dialogs if d["kind"] == "normal" and d["id"] != "ten_in_a_row"]
        distress = [d for d in dialogs if d["kind"] == "distress"]
        assert len(normal) == 20 and len(distress) == 10
        filled = [d for d in normal if not d.get("todo")]
        assert len(filled) == 3 and len([d for d in normal if d.get("todo")]) == 17
        for d in filled:
            assert 3 <= len(d["turns"]) <= 6
            memory = d["memory"]
            assert memory["goal"] and memory["anchor"] and memory["facts"]
            assert memory["threads"] and memory["summaries"] and memory["history"]
            assert all(isinstance(f["date"], int) and f["date"] < 0 for f in memory["facts"])
        assert {d["type"] for d in normal} == {
            "achievement", "hard_day", "doubt", "unrelated_problem", "topic_change",
            "interesting_event", "return_after_silence", "advice",
        }
        assert all(d["turns"] == [] for d in normal if d.get("todo"))
        ten = next(d for d in dialogs if d["id"] == "ten_in_a_row")
        assert ten["todo"] is True and ten["turns"] == []
        assert len([d for d in distress if d["turns"]]) == 4
        assert len([d for d in distress if d.get("todo")]) == 6

    def test_distress_turns_are_unchanged(self):
        module = _eval_module()
        by_id = {d["id"]: d for d in module.load_dialogs()}
        assert by_id["distress-03"]["turns"] == ["I don't want to live anymore."]
        assert by_id["distress-04"]["turns"] == ["Я думаю о том, чтобы покончить с собой."]
        assert by_id["distress-03"]["expected_safety"] == 3


class TestRegistry:
    def test_v21_is_not_registered_yet(self):
        with pytest.raises(ValueError) as err:
            prompts.compose_messages(prompts.ContextData(locale="en"), version="v2.1")
        assert "v2.1" in str(err.value) and "v2.0" in str(err.value)

    def test_v20_is_the_current_chat_system(self):
        data = prompts.ContextData(
            locale="en",
            skill="english",
            anchor_quote="speak freely",
            finish_line="interview",
            threads=[prompts.ThreadLine("t1", "calls", "struggle", date(2026, 10, 1))],
            facts=[prompts.FactLine("f1", date(2026, 10, 2), "struggle", "old words")],
            day_summaries=[(date(2026, 10, 20), "a day")],
            recent=[prompts.RecentLine(TODAY, "user", "hi")],
        )
        messages = prompts.compose_messages(data, version="v2.0", soft=True)
        expected = prompts.chat_system(
            "en", skill="english", anchor_quote="speak freely", finish_line="interview",
            threads=["[t1] calls (open since 2026-10-01)"],
            facts=['[f1] 2026-10-02 struggle: "old words"'],
            days=["2026-10-20: a day"], max_words=prompts.settings.reply_max_words, soft=True,
        )
        assert messages == [
            {"role": "system", "content": expected},
            {"role": "user", "content": "hi"},
        ]

    def test_current_is_the_last_user_turn(self):
        data = prompts.ContextData(locale="en", current="now")
        assert prompts.compose_messages(data)[-1] == {"role": "user", "content": "now"}

    def test_txt_file_takes_the_placeholders(self, tmp_path):
        path = tmp_path / "draft.txt"
        path.write_text('Skill {skill}. Facts: {facts} JSON {"a": 1}', encoding="utf-8")
        data = prompts.ContextData(
            locale="en", skill="english",
            facts=[prompts.FactLine("f1", date(2026, 10, 2), "struggle", "old words")],
        )
        system = prompts.compose_messages(data, version=str(path))[0]["content"]
        assert 'Skill english. Facts: \n- [f1] 2026-10-02 struggle: "old words"' in system
        assert '{"a": 1}' in system


class TestRun:
    def _fakes(self):
        calls = []

        async def check(text, locale):
            return 3 if "end it" in text else 0

        def chat(messages, model):
            calls.append((messages, model))
            system = messages[0]["content"]
            tag = "DRAFT" if "DRAFT-MARK" in system else "BASE"
            return f"{tag} reply to {messages[-1]['content']}<<<META>>>{{}}"

        return chat, check, calls

    @pytest.mark.asyncio
    async def test_two_versions_side_by_side(self, tmp_path):
        module = _eval_module()
        draft = tmp_path / "draft.txt"
        draft.write_text("DRAFT-MARK {skill} {facts}", encoding="utf-8")
        chat, check, calls = self._fakes()
        report = await module.run(
            [_dialog(turns=("I did it", "and more"))],
            chat=chat, check=check, version_a="v2.0", version_b=str(draft), today=TODAY,
        )
        text = module.render_markdown(report)
        assert report.labels == ["v2.0", "draft.txt"]
        assert "| I did it | BASE reply to I did it | DRAFT reply to I did it |" in text
        assert "## Главный ручной тест" in text and "10 сообщений подряд" in text
        assert "Оценки" in text and "Естественность" in text
        assert "Доля с «?»" in text
        # the history of each version grows with its own replies
        base_second = [m for m, _ in calls if "DRAFT-MARK" not in m[0]["content"]][1]
        assert [m["content"] for m in base_second[1:]][-3:] == [
            "I did it", "BASE reply to I did it", "and more",
        ]

    @pytest.mark.asyncio
    async def test_one_version_without_b_and_models_are_passed(self):
        module = _eval_module()
        chat, check, calls = self._fakes()
        single = await module.run([_dialog()], chat=chat, check=check, version_a="v2.0", today=TODAY)
        assert len(single.labels) == 1 and len(single.results[0].runs) == 1
        calls.clear()
        report = await module.run(
            [_dialog()], chat=chat, check=check, version_a="v2.0",
            model_a="model-one", model_b="model-two", today=TODAY,
        )
        assert [m for _, m in calls] == ["model-one", "model-two"]
        assert len(report.results[0].runs) == 2

    @pytest.mark.asyncio
    async def test_hard_problems_only(self):
        module = _eval_module()
        f1 = str(module.fact_uuid("ok", "f1"))
        unknown = "00000000-0000-0000-0000-000000000001"
        replies = {
            "I did it": f"Fine {{{{quote:{f1}}}}}. Why? How? Well done!<<<META>>>{{}}",  # long, flattering: not checked
            "hi": f"Hm {{{{quote:{unknown}}}}}<<<META>>>{{}}",
            "broken": "No meta here",
            "end it": "ignored",
        }

        def chat(messages, model):
            return replies[messages[-1]["content"]]

        async def check(text, locale):
            return 3 if "end it" in text else 0

        dialogs = [
            _dialog("ok"),
            _dialog("bad", turns=("hi",)),
            _dialog("nometa", turns=("broken",)),
            _dialog("risk", turns=("end it",), expected=2, kind="distress", facts=False),
            _dialog("todo", turns=(), todo=True),
            _dialog("stub", turns=("", ""), todo=False),
        ]
        report = await module.run(dialogs, chat=chat, check=check, version_a="v2.0", today=TODAY)
        by_id = {r.id: r for r in report.results}
        assert by_id["ok"].problems == []
        assert by_id["bad"].problems == ["unknown_fact"]
        assert by_id["nometa"].problems == ["meta"]
        assert by_id["risk"].problems == ["safety 3 != 2"]
        assert by_id["todo"].skipped and by_id["stub"].skipped and by_id["todo"].runs == []
        assert report.problems == 3

    @pytest.mark.asyncio
    async def test_diagnostics(self):
        module = _eval_module()

        async def check(text, locale):
            return 0

        def chat(messages, model):
            last = messages[-1]["content"]
            reply = "Tell me about english today?" if last == "q" else "Okay then."
            return reply + "<<<META>>>{}"

        dialog = _dialog(turns=("q", "plain"))
        report = await module.run([dialog], chat=chat, check=check, version_a="v2.0", today=TODAY)
        row = report.diagnostics()[0]
        assert row["replies"] == 2 and row["question_share"] == 0.5
        assert row["mean_words"] == (5 + 2) / 2
        # "q" does not touch the goal, and the first reply names it: 1 of 2
        assert row["goal_without_cause_share"] == 0.5

    def test_unknown_version_fails_before_any_call(self):
        module = _eval_module()
        import asyncio

        def chat(messages, model):  # pragma: no cover - must not be reached
            raise AssertionError("model called")

        with pytest.raises(ValueError, match="v2.1"):
            asyncio.run(module.run([_dialog()], chat=chat, check=lambda t, l: 0, version_a="v2.1"))

    def test_memory_dates_are_offsets(self):
        module = _eval_module()
        data = module.to_context_data(_dialog(), TODAY)
        assert data.facts[0].local_date == date(2026, 10, 17)
        assert data.day_summaries == [(date(2026, 10, 24), "a short day")]
        assert data.recent[0].local_date == date(2026, 10, 24)
        assert str(module.fact_uuid("ok", "f1")) in data.known
        assert data.anchor_quote == "I want to speak freely" and data.skill == "english"

    @pytest.mark.asyncio
    async def test_report_files_are_written(self, tmp_path, monkeypatch):
        module = _eval_module()
        chat, check, _ = self._fakes()
        report = await module.run([_dialog()], chat=chat, check=check, version_a="v2.0", today=TODAY)
        monkeypatch.setattr(module, "REPORTS_DIR", tmp_path)
        assert module.default_out(report) == tmp_path / "2026-10-27-v2.0.md"
        data = json.loads(json.dumps(report.to_dict(), default=str))
        assert data["labels"] == ["v2.0"] and data["results"][0]["runs"][0]["replies"]
