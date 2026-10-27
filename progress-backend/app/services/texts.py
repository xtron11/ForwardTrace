"""Every server-side string a person reads, in Russian and English.

Russian: what the AI says in the dialogue - `first.*`, `safety.*` and `outreach.*`
except `outreach.push_title` / `outreach.reply_button` - speaks «ты»; everything else
(Telegram service lines, push, the monthly summary) stays «вы» (spec v2.1 §2.1 #1).
No string uses a gendered form about the person («пройдено», «Выберу время», not
«прошёл» or «Сам выберу»). The AI speaking about itself («запомнил») is allowed.

Values are either a string (`t`) or a list of quick replies (`quick`). Placeholders use
str.format names: `{month}`, `{hour}`, `{title}`. A `{quote}`, `{then}` or `{now}` marks
where code puts a verified quote from the database; the model never writes one.

Add keys to both dictionaries at once: a test checks that they match.
"""

RU: dict[str, str | list[str]] = {
    # ---- first conversation (onboarding inside the chat) ----
    "first.greeting": (
        "Привет! Я помогу тебе замечать, как ты растёшь, — твоими же словами. "
        "Что ты сейчас развиваешь?"
    ),
    "first.skills": ["Программирование", "Геймдев", "Иностранный язык", "Спорт", "Музыка"],
    # Stand-in when the skill could not be understood after the retry.
    "first.skill_placeholder": "мой навык",
    "first.ask_motivation": "Зачем тебе это? Чего хочется добиться?",
    "first.ask_finish_quoted": "«{quote}» — запомнил. Когда ты скажешь, что цель достигнута?",
    "first.ask_finish": "Запомнил. Когда ты скажешь, что цель достигнута?",
    "first.no_finish_option": "Без финиша — хочу просто расти",
    "first.ask_baseline": "Где ты сейчас относительно этого? И с чего всё начиналось?",
    "first.ask_baseline_no_finish": "Где ты сейчас? И с чего всё начиналось?",
    "first.comparison": (
        "Смотри: в начале — {then}. Сейчас — {now}. Пройдено больше, чем кажется."
    ),
    # Asked right after the comparison, in the same message.
    "first.ask_schedule": "Во сколько тебе написать завтра?",
    "first.just_started": (
        "Это самое начало — запомню, где ты сейчас, и через пару недель сравним. "
        "Во сколько тебе написать завтра?"
    ),
    "first.schedule": ["После занятия", "Вечером", "Выберу время"],
    "first.ask_session_end": "Во сколько обычно заканчиваешь?",
    "first.session_end_hours": ["18:00", "19:00", "20:00", "21:00"],
    "first.schedule_set": "Договорились: напишу около {hour}:00.",
    # One softer retry per step, then the conversation moves on with what it has.
    "first.retry.skill": "Можно коротко — одним словом. Что ты развиваешь?",
    "first.retry.motivation": "Можно одной фразой: что для тебя изменится, когда получится?",
    "first.retry.finish": (
        "Можно выбрать вариант ниже или написать свой. Когда ты скажешь, что цель достигнута?"
    ),
    "first.retry.baseline": (
        "Можно в двух словах: что получается сейчас и что было трудно в самом начале?"
    ),
    "first.retry.schedule": "Напиши час, например «20:00», — во сколько тебе написать завтра?",
    # ---- the AI writes first: fallback templates per topic ----
    "outreach.general": "Что сегодня получилось, что раньше не получалось?",
    "outreach.thread": "Как сейчас с темой «{title}»? Что-то сдвинулось?",
    "outreach.anchor": "Как продвигается {goal}? Что получилось за последние дни?",
    "outreach.yesterday": "Вчера мы говорили о том, что у тебя происходит. Как сегодня?",
    "outreach.farewell": "Я тут, когда захочешь поговорить. Всё, о чём мы говорили, никуда не делось.",
    "outreach.push_title": "ForwardTrace",
    "outreach.reply_button": "Ответить",
    # ---- push: the test notification from the profile ----
    "push.test_title": "Уведомления работают",
    "push.test_body": "Так будут приходить сообщения от ForwardTrace.",
    # ---- monthly summary ----
    "monthly.ready": "Сводка за {month} готова",
    "monthly.thin": "Мало данных за {month} — вот что есть",
    "month.names": [
        "январь", "февраль", "март", "апрель", "май", "июнь",
        "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    ],
    # ---- safety ----
    # Level 3: calm, no promise of confidentiality, nothing about who is told what.
    "safety.level3": (
        "Мне очень жаль, что тебе сейчас так тяжело. Твоя жизнь важна, и с этим не нужно "
        "справляться в одиночку. Пожалуйста, прямо сейчас свяжись с теми, кто может "
        "помочь:"
    ),
    "safety.level3_no_resources": (
        "Мне очень жаль, что тебе сейчас так тяжело. Твоя жизнь важна. Пожалуйста, прямо "
        "сейчас позвони в местную экстренную службу и свяжись с близким человеком, "
        "которому доверяешь."
    ),
    "safety.level3_contact_someone": "И, пожалуйста, напиши или позвони близкому человеку.",
    # One help contact from SAFETY_RESOURCES (the owner fills them in).
    "safety.resource_line": "• {name}: {contact}",
    "safety.suggest_help": (
        "Похоже, в последнее время тебе часто бывает тяжело. Возможно, стоит поговорить об "
        "этом с врачом или психологом — это нормальный и полезный шаг."
    ),
    # ---- Telegram ----
    "telegram.linked": "Готово: сообщения будут приходить сюда.",
    "telegram.link_expired": "Ссылка устарела — получите новую в профиле.",
    "telegram.not_linked": "Чтобы переписываться здесь, привяжите Telegram в профиле приложения.",
    "telegram.busy": "Ещё отвечаю на предыдущее сообщение — подождите немного.",
    "telegram.limit_reached": (
        "Бесплатные разговоры на этой неделе закончились — подробности в приложении."
    ),
    "telegram.cannot_reply": "Не получилось ответить здесь — откройте, пожалуйста, приложение.",
    "telegram.unsupported": "Здесь я пока понимаю только текст и голосовые сообщения.",
    "telegram.open_app": "Открыть приложение",
}

EN: dict[str, str | list[str]] = {
    "first.greeting": (
        "Hi! I'll help you notice how you grow — in your own words. "
        "What are you working on right now?"
    ),
    "first.skills": ["Programming", "Game dev", "A foreign language", "Sport", "Music"],
    "first.skill_placeholder": "my skill",
    "first.ask_motivation": "Why does it matter to you? What do you want to achieve?",
    "first.ask_finish_quoted": "“{quote}” — noted. When will you say the goal is reached?",
    "first.ask_finish": "Noted. When will you say the goal is reached?",
    "first.no_finish_option": "No finish line — I just want to grow",
    "first.ask_baseline": "Where are you now relative to that? And where did you start?",
    "first.ask_baseline_no_finish": "Where are you now? And where did you start?",
    "first.comparison": (
        "Look: at the start — {then}. Now — {now}. You've come further than it feels."
    ),
    "first.ask_schedule": "What time should I write to you tomorrow?",
    "first.just_started": (
        "You're at the very start — I'll remember where you are now, and in a couple of "
        "weeks we'll compare. What time should I write to you tomorrow?"
    ),
    "first.schedule": ["After practice", "In the evening", "I'll pick a time"],
    "first.ask_session_end": "What time do you usually finish?",
    "first.session_end_hours": ["18:00", "19:00", "20:00", "21:00"],
    "first.schedule_set": "Deal: I'll write around {hour}:00.",
    "first.retry.skill": "A word or two is enough. What are you working on?",
    "first.retry.motivation": "One sentence is enough: what changes for you when it works out?",
    "first.retry.finish": (
        "Pick an option below or write your own. When will you say the goal is reached?"
    ),
    "first.retry.baseline": (
        "Briefly: what works for you now, and what was hard at the very start?"
    ),
    "first.retry.schedule": "Write an hour, for example “20:00” — when should I write tomorrow?",
    "outreach.general": "What worked today that didn't work before?",
    "outreach.thread": "How is it going with “{title}”? Has anything moved?",
    "outreach.anchor": "How is {goal} going? What worked over the last few days?",
    "outreach.yesterday": "Yesterday we talked about what's going on for you. How is today?",
    "outreach.farewell": "I'm here whenever you feel like talking. Everything we talked about is still here.",
    "outreach.push_title": "ForwardTrace",
    "outreach.reply_button": "Reply",
    "push.test_title": "Notifications work",
    "push.test_body": "This is how messages from ForwardTrace will arrive.",
    "monthly.ready": "Your summary for {month} is ready",
    "monthly.thin": "Not much data for {month} — here's what there is",
    "month.names": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "safety.level3": (
        "I'm really sorry it's this hard for you right now. Your life matters, and you "
        "don't have to carry this alone. Please reach out right now to people who can help:"
    ),
    "safety.level3_no_resources": (
        "I'm really sorry it's this hard for you right now. Your life matters. Please call "
        "your local emergency number right now and reach out to someone close you trust."
    ),
    "safety.level3_contact_someone": "And please message or call someone close to you.",
    "safety.resource_line": "• {name}: {contact}",
    "safety.suggest_help": (
        "It sounds like things have often been hard lately. It might help to talk about "
        "it with a doctor or a therapist — that's a normal and useful step."
    ),
    "telegram.linked": "Done: messages will arrive here.",
    "telegram.link_expired": "This link has expired — get a new one in your profile.",
    "telegram.not_linked": "To talk here, connect Telegram in your profile in the app.",
    "telegram.busy": "Still answering your previous message — one moment, please.",
    "telegram.limit_reached": "This week's free conversations are used up — see the app for details.",
    "telegram.cannot_reply": "I couldn't answer here — please open the app.",
    "telegram.unsupported": "For now I understand only text and voice messages here.",
    "telegram.open_app": "Open the app",
}

_BY_LOCALE = {"ru": RU, "en": EN}


def _dict(locale: str | None) -> dict[str, str | list[str]]:
    return _BY_LOCALE.get((locale or "en").split("-")[0].lower(), EN)


def t(locale: str | None, key: str, **kw) -> str:
    """The string for `key` in the person's language, placeholders filled from `kw`.
    Unknown locales get English. An unknown key raises KeyError: a typo should fail a
    test, not show a person an empty message."""
    value = _dict(locale).get(key, EN[key])
    if not isinstance(value, str):
        raise TypeError(f"{key} is a list of quick replies; use quick()")
    return value.format(**kw) if kw else value


def quick(locale: str | None, key: str) -> list[str]:
    """A list of quick replies (or other list value) for `key`."""
    value = _dict(locale).get(key, EN[key])
    if not isinstance(value, list):
        raise TypeError(f"{key} is a single string; use t()")
    return list(value)


def month_name(locale: str | None, month: int) -> str:
    """Nominative month name: «октябрь», "October" (fits «Сводка за {month}»)."""
    return quick(locale, "month.names")[month - 1]
