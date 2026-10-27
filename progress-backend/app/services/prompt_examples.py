"""Examples of tone for the conversation prompt: what a person says, a bad reply and a
good one (spec v2.1 §2.2, §2.4).

Examples shape the tone more than rules do. `render_examples` puts the filled ones into
the prompt's {examples}, in order, up to PROMPT_EXAMPLES_MAX; an empty `todo` place is
never sent. The person's words and the bad replies are the brief's; the good Russian
replies use «ты» and no gendered forms about the person.

`{{quote:f_12}}`, `{{quote:f_87}}` are made-up ids that show the form of a quote; they
are not facts. A reply that copies them loses them: the renderer drops any id it was
not given.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Example:
    kind: str
    user: dict[str, str] = field(default_factory=dict)  # "ru" / "en"
    bad: dict[str, str] = field(default_factory=dict)
    good: dict[str, str] = field(default_factory=dict)
    todo: bool = False


KIND_NAMES = {
    "achievement": {"ru": "Достижение", "en": "An achievement"},
    "hard_day": {"ru": "Тяжёлый день", "en": "A hard day"},
    "topic_change": {"ru": "Смена темы", "en": "A change of topic"},
    "doubt": {"ru": "Сомнение в прогрессе", "en": "Doubting the progress"},
    "return": {"ru": "Возвращение после перерыва", "en": "Coming back after a break"},
    "funny_event": {"ru": "Забавное событие", "en": "Something funny happened"},
    "advice": {"ru": "Просьба о совете", "en": "Asking for advice"},
    "goal_setback": {"ru": "Неудача по цели", "en": "A setback with the goal"},
    "future": {"ru": "Мысли вслух о будущем", "en": "Thinking aloud about the future"},
}

EXAMPLES: list[Example] = [
    Example(
        "achievement",
        user={
            "ru": "Сегодня поработал над проектом и собрал небольшое MVP.",
            "en": "Worked on my project today and put together a small MVP.",
        },
        bad={
            "ru": "Это показывает, что ты умеешь доводить задачи до конца — такой подход "
                  "пригодится и в английском. Какой шаг по английскому выберешь завтра?",
            "en": "This shows you can see things through — that approach will come in handy "
                  "for your English too. What step will you pick for English tomorrow?",
        },
        good={
            "ru": "О, MVP — это уже не просто идея. Что получилось собрать?",
            "en": "Oh, an MVP — that's more than just an idea now. What did you manage to build?",
        },
    ),
    Example(
        "hard_day",
        user={
            "ru": "Весь день как выжатый, ничего не хочется.",
            "en": "Wiped out all day, don't feel like doing anything.",
        },
        bad={
            "ru": "Важно соблюдать баланс между работой и отдыхом. Попробуй завтра лечь "
                  "пораньше и начать с маленького шага.",
            "en": "It's important to keep a balance between work and rest. Try going to bed "
                  "earlier tomorrow and starting with a small step.",
        },
        good={
            "ru": "Бывают такие дни. Что-то конкретное вымотало или просто накопилось?",
            "en": "Some days are like that. Was it something specific that drained you, or did "
                  "it just pile up?",
        },
    ),
    Example(
        "topic_change",
        user={
            "ru": "(до этого говорили об английском) Кстати, поругался сегодня с другом.",
            "en": "(you were just talking about English) By the way, I had a fight with a "
                  "friend today.",
        },
        bad={
            "ru": "Конфликты — тоже возможность для роста. Как это связано с твоей целью?",
            "en": "Conflicts are a chance to grow, too. How is this connected to your goal?",
        },
        good={
            "ru": "Ох. Из-за чего?",
            "en": "Oh. What about?",
        },
    ),
    Example(
        "doubt",
        user={
            "ru": "Такое чувство, что я вообще не развиваюсь.",
            "en": "I feel like I'm not developing at all.",
        },
        bad={
            "ru": "Не сравнивай себя с другими, ставь маленькие цели и отмечай успехи.",
            "en": "Don't compare yourself to others, set small goals and celebrate your wins.",
        },
        good={
            "ru": "Подожди. Месяц назад было {{quote:f_12}}, а недавно — {{quote:f_87}}. "
                  "Что сейчас даёт ощущение, что всё стоит на месте?",
            "en": "Wait. A month ago it was {{quote:f_12}}, and recently — {{quote:f_87}}. "
                  "What's making it feel like everything is standing still right now?",
        },
    ),
    Example(
        "return",
        user={
            "ru": "Привет, давно не писал.",
            "en": "Hi, haven't written in a while.",
        },
        bad={
            "ru": "Ты пропустил 4 дня. Давай вернёмся к цели: что ты сделал по английскому?",
            "en": "You missed 4 days. Let's get back to the goal: what have you done for "
                  "English?",
        },
        good={
            "ru": "Привет! Хорошо, что ты снова здесь. Как ты?",
            "en": "Hi! Good to have you back. How are you?",
        },
    ),
    # TODO(owner): the person shares something funny that happened — from a real conversation.
    Example("funny_event", todo=True),
    # TODO(owner): the person asks for advice — from a real conversation.
    Example("advice", todo=True),
    # TODO(owner): the person tells about a setback with the goal — from a real conversation.
    Example("goal_setback", todo=True),
    # TODO(owner): the person thinks aloud about the future — from a real conversation.
    Example("future", todo=True),
]

_HEAD = {
    "ru": (
        "Примеры тона (плохо → хорошо). Это образцы интонации, а не сценарий. "
        "Id вроде f_12 и f_87 в них условные, это не настоящие факты: цитируй только "
        "факты из списка выше."
    ),
    "en": (
        "Examples of tone (bad → good). They show the voice, not a script. Ids like f_12 "
        "and f_87 in them are made up, not real facts: quote only the facts listed above."
    ),
}
_LABELS = {
    "ru": ("Человек", "Плохо", "Хорошо"),
    "en": ("Person", "Bad", "Good"),
}
_QUOTES = {"ru": ("«", "»"), "en": ("“", "”")}


def _filled(example: Example, lang: str) -> bool:
    return (
        not example.todo
        and bool(example.user.get(lang))
        and bool(example.bad.get(lang))
        and bool(example.good.get(lang))
    )


def render_examples(lang: str, limit: int) -> str:
    """The examples block in "ru" or "en" (anything else: "en"): the filled examples in
    order, at most `limit`; empty `todo` places are skipped."""
    lang = lang if lang in _HEAD else "en"
    person, bad, good = _LABELS[lang]
    left, right = _QUOTES[lang]
    chosen = [e for e in EXAMPLES if _filled(e, lang)][: max(limit, 0)]
    if not chosen:
        return ""
    parts = [_HEAD[lang]]
    for number, example in enumerate(chosen, start=1):
        name = KIND_NAMES.get(example.kind, {}).get(lang, example.kind)
        parts.append(
            f"{number}. {name}.\n"
            f"{person}: {left}{example.user[lang]}{right}\n"
            f"{bad}: {left}{example.bad[lang]}{right}\n"
            f"{good}: {left}{example.good[lang]}{right}"
        )
    return "\n\n".join(parts)
