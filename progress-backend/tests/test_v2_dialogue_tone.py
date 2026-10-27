"""v2.1, ticket 12: the dialogue speaks «ты», the app and letters stay «вы», and nothing
assumes the person's gender (spec §2.1 #1-#2, §2.4, story 7). Plus the hour parser of
the first conversation's schedule step (story 23)."""

import re

import pytest

from app.services import prompts, texts
from app.services.first_conversation import parse_hour

# Keys the AI says in the dialogue: «ты» (spec §2.1 #1).
SERVICE_OUTREACH = {"outreach.push_title", "outreach.reply_button"}


def _dialogue(key: str) -> bool:
    return key.startswith(("first.", "safety.", "outreach.")) and key not in SERVICE_OUTREACH


def _lines(value) -> list[str]:
    return value if isinstance(value, list) else [value]


VY = re.compile(r"\b(вы|вас|вам|вами|ваш|ваша|ваше|ваши|вашего|вашей|вашу|ваших|вашим|вашими)\b", re.I)
# Plural/formal imperatives: «расскажите», «выберите», «давайте».
VY_IMPERATIVE = re.compile(r"\b\w{2,}(?:ите|йте|итесь|йтесь)\b", re.I)
TY = re.compile(r"\b(ты|тебе|тебя|тобой|твой|твоя|твоё|твои|твоими|твоих|твоего|твоей|твою)\b", re.I)
# Gendered forms about the person, whichever the address.
GENDERED = re.compile(
    r"\b(сам|сама|начинал|начинала|начал|начала|прошёл|прошел|прошла|рассказывал|рассказывала"
    r"|сделал|сделала|справился|справилась|добился|добилась|хотел|хотела|решил|решила"
    r"|пропустил|пропустила|планировал|планировала|заглянул|заглянула|вернулся|вернулась"
    r"|смог|смогла|понял|поняла|устал|устала)\b",
    re.I,
)


class TestDialogueStrings:
    def test_dialogue_keys_are_ty_and_never_vy(self):
        checked = 0
        for key, value in texts.RU.items():
            if not _dialogue(key):
                continue
            for line in _lines(value):
                checked += 1
                assert not VY.search(line), (key, line)
                assert not VY_IMPERATIVE.search(line), (key, line)
        assert checked >= 30

    def test_the_rest_stays_vy(self):
        for key, value in texts.RU.items():
            if _dialogue(key):
                continue
            for line in _lines(value):
                assert not TY.search(line), (key, line)

    def test_no_gendered_forms_in_any_russian_string(self):
        for key, value in texts.RU.items():
            for line in _lines(value):
                # "Как прошёл день?" - the verb agrees with «день», not with the person.
                assert not GENDERED.search(line.replace("прошёл день", "")), (key, line)

    def test_greeting_and_comparison_word_for_word(self):
        assert texts.RU["first.greeting"] == (
            "Привет! Я помогу тебе замечать, как ты растёшь, — твоими же словами. "
            "Что ты сейчас развиваешь?"
        )
        assert texts.RU["first.comparison"] == (
            "Смотри: в начале — {then}. Сейчас — {now}. Пройдено больше, чем кажется."
        )

    def test_farewell_has_no_reproach(self):
        line = texts.RU["outreach.farewell"]
        assert "пропуст" not in line.lower()
        assert "захочешь" in line


class TestDialoguePrompts:
    def _chat(self, locale):
        return prompts.chat_system(
            locale, skill="Гитара", anchor_quote=None, finish_line=None, threads=[], facts=[],
            days=[], max_words=120, soft=False, plateau=False,
        )

    def _outreach(self, locale):
        return prompts.outreach_system(
            locale, topic="general", skill="Гитара", details=[], facts=[], max_words=25
        )

    @pytest.mark.parametrize("build", ["_chat", "_outreach", "_safety"])
    def test_russian_dialogue_prompts_ask_for_ty_without_gender(self, build):
        if build == "_safety":
            system = prompts.safety_system("ru")
        else:
            system = getattr(self, build)("ru")
        assert "«ты»" in system
        assert "gender" in system.lower()
        assert "address the person formally" not in system and "«вы» (вы" not in system

    @pytest.mark.parametrize("build", ["_chat", "_outreach"])
    def test_english_prompts_carry_no_russian_address(self, build):
        assert "«ты»" not in getattr(self, build)("en")
        assert "«ты»" not in prompts.safety_system("en")


class TestParseHour:
    @pytest.mark.parametrize(
        ("text", "hour"),
        [
            ("уровень B1", None),
            ("хочу до B2 к лету", None),
            ("в 9 вечера", 21),
            ("20:00", 20),
            ("8pm", 20),
            ("8 pm", 20),
            ("21", 21),
            ("в 7 утра", 7),
            ("12 am", 0),
            ("не знаю", None),
        ],
    )
    def test_parse_hour(self, text, hour):
        assert parse_hour(text) == hour
