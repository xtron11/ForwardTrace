"""Prompts and the JSON schemas that constrain the model's output.

Output language follows the person, not the codebase. The instructions themselves stay
in English because that is what these models follow most reliably, but everything the
person reads is written in their own language.

Design rule: the extractor may only *copy* from the transcript. Every fact carries a
`quote` field, and Python later checks that the quote actually appears in the source.
Anything unverifiable is discarded before it ever reaches the database.
"""

# ---------------- criteria suggestion ----------------

CRITERIA_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {"type": "string"},
        }
    },
    "required": ["criteria"],
    "additionalProperties": False,
}

LANGUAGE_NAMES = {"en": "English", "ru": "Russian"}


def language_of(locale: str | None) -> str:
    return LANGUAGE_NAMES.get((locale or "en").split("-")[0].lower(), "English")


def _write_in(locale: str | None) -> str:
    language = language_of(locale)
    if language == "English":
        return ""
    return (
        f"\n\nOUTPUT LANGUAGE: write every piece of text the person will read in "
        f"{language}. This applies to all string fields. Field names, enum values and "
        f"ids stay exactly as specified in the schema - translate the content, never "
        f"the structure. Verbatim quotes stay in the language they were spoken in."
        f"\n\nThese instructions are written in English for your benefit, not the "
        f"reader's. Never let a word of them surface in what you write. Terms like "
        f"'logged days', 'reported facts', 'what_changed', 'evidence' and 'criteria' "
        f"are the scaffolding of this prompt; render the idea in {language} or drop it. "
        f"A single English phrase in a {language} sentence reads as a bug, because it "
        f"is one."
    )


CRITERIA_SYSTEM = (
    "You help people define what progress looks like for a personal goal.\n"
    "Return exactly 4 short, observable signs of progress.\n"
    "Rules:\n"
    "- Each one must be something the person could notice happening, not a feeling.\n"
    "- 3 to 7 words each. No numbering, no punctuation at the end.\n"
    "- Range from early signs to the eventual outcome.\n"
    "- Plain language, second person implied (e.g. 'Build a project without a tutorial')."
)


def criteria_system(locale: str | None) -> str:
    return CRITERIA_SYSTEM + _write_in(locale)


def criteria_user_prompt(title: str, why: str | None) -> str:
    parts = [f"Goal: {title}"]
    if why:
        parts.append(f"Why it matters to them: {why}")
    return "\n".join(parts)


# ---------------- daily extraction ----------------

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "activities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string"},
                    "category": {"type": "string"},
                    "minutes": {"type": "integer"},
                    "minutes_explicit": {"type": "boolean"},
                    "details": {"type": "array", "items": {"type": "string"}},
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                                "unit": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["name", "value", "unit", "quote"],
                            "additionalProperties": False,
                        },
                    },
                    "quote": {"type": "string"},
                },
                "required": [
                    "goal_id",
                    "category",
                    "minutes",
                    "minutes_explicit",
                    "details",
                    "metrics",
                    "quote",
                ],
                "additionalProperties": False,
            },
        },
        "wins": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string"},
                    "text": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["goal_id", "text", "quote"],
                "additionalProperties": False,
            },
        },
        "friction": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "goal_id": {"type": "string"},
                    "text": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["goal_id", "text", "quote"],
                "additionalProperties": False,
            },
        },
        "mood": {"type": "string"},
    },
    "required": ["activities", "wins", "friction", "mood"],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM = """You extract structured facts from a person's spoken daily check-in.

You are an extractor, not a writer. You may only report what the transcript states.

Hard rules:
1. Every item MUST include "quote": a word-for-word span copied from the transcript that
   supports it. Copy the characters exactly. Never paraphrase inside "quote".
2. Durations. If the person states how long something took - in any phrasing - convert it
   to whole minutes and set "minutes_explicit": true. If they state no duration, set
   "minutes": 0 and "minutes_explicit": false. NEVER estimate, infer, or round a duration
   they did not state, but never discard one they did.

   Spoken -> extracted:
     "coded for two hours"           -> minutes 120, explicit true
     "about two hours on LeetCode"   -> minutes 120, explicit true
     "half an hour of English"       -> minutes  30, explicit true
     "a couple of hours of reading"  -> minutes 120, explicit true
     "45 minutes at the gym"         -> minutes  45, explicit true
     "an hour and a half of Python"  -> minutes  90, explicit true
     "spent the morning coding"      -> minutes   0, explicit false  (vague, not a duration)
     "did some reading"              -> minutes   0, explicit false
     "worked on it all day"          -> minutes   0, explicit false

   Approximations like "about", "roughly", "around" or "a couple of" still count as stated:
   take the number the person said. Only vague time-of-day words are not durations.
3. "details" are short factual fragments of what they actually did. 0-4 per activity.
   No praise, no interpretation, no advice.

3a. "metrics" captures every countable quantity the person states, other than duration.
   A number said out loud is the most valuable thing in a check-in: it is the only part
   that can be added up across a week and shown back as growth. Losing one throws away
   the evidence they were building.
     "learned 10 new words"        -> {"name": "new words", "value": 10, "unit": "words"}
     "read a few pages"            -> nothing. "A few" is not a number.
     "read 12 pages"               -> {"name": "pages read", "value": 12, "unit": "pages"}
     "solved 3 medium problems"    -> {"name": "problems solved", "value": 3, "unit": "problems"}
     "did 15 pull-ups"             -> {"name": "pull-ups", "value": 15, "unit": "reps"}
     "gained 2 kilos"              -> {"name": "weight gained", "value": 2, "unit": "kg"}
   Each metric needs its own "quote" containing the number, word for word. Never invent
   or estimate a quantity. "name" and "unit" go in the person's language; keep them
   identical across days so the week can be summed - if you called it "new words"
   yesterday, call it that today.
4. "wins" are concrete things that went well and were stated. "friction" are stated
   obstacles, blockers, or things that went badly. Leave either list empty if none were said.
5. "mood" must be one lowercase word chosen from: positive, neutral, tired, frustrated,
   motivated, mixed. Use "neutral" if unclear.
6. "category" is a short noun phrase for the area of effort, e.g. "Programming", "English",
   "Gym", "Reading", in the person's own language. Title case, 1-2 words. Reuse a category from the known list when it
   means the same thing.

7. Routing. The person talks about their whole day in one go; you decide which of their
   goals each item serves. Set "goal_id" to the id of the goal it belongs to, taken
   exactly from the goals list you are given. Set it to "" when the item serves none of
   them - an errand, a meal, a mood with no activity attached. Never invent an id.
   Route on substance, not on wording: "watched a film in English without subtitles"
   serves an English goal even though neither the word "study" nor "practice" appears.
   Wins and friction are routed the same way, to the goal they concern.
8. If the transcript contains no reportable activity, return empty arrays.

You will be penalised for any claim that cannot be traced to the transcript."""


def extraction_system(locale: str | None) -> str:
    return EXTRACTION_SYSTEM + _write_in(locale)


def report_system(locale: str | None) -> str:
    return REPORT_SYSTEM + _write_in(locale)


def extraction_user_prompt(
    transcript: str,
    goals: list[dict],
    known: list[str],
) -> str:
    """`goals` is [{"id": ..., "title": ..., "criteria": [...]}, ...]."""
    parts = []
    if goals:
        lines = ["The person's active goals - route each item to one of these ids:"]
        for goal in goals:
            lines.append(f'  id: {goal["id"]}  |  goal: {goal["title"]}')
            if goal.get("criteria"):
                lines.append(f'      progress means: {"; ".join(goal["criteria"])}')
        lines.append('  Use "" for anything that serves none of them.')
        parts.append("\n".join(lines))
    if known:
        parts.append("Categories they have used before (reuse when applicable): " + ", ".join(known))
    parts.append('Transcript:\n"""\n' + transcript.strip() + '\n"""')
    return "\n\n".join(parts)


# ---------------- weekly report ----------------

REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "what_you_did": {"type": "string"},
        "what_changed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["text", "evidence"],
                "additionalProperties": False,
            },
        },
        "pattern": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["text", "confidence"],
            "additionalProperties": False,
        },
        "friction": {"type": "string"},
        "recommendation": {"type": "string"},
        "closing": {"type": "string"},
        "criteria_progress": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["no_evidence", "some_evidence", "clear_evidence"],
                    },
                    "evidence": {"type": "string"},
                },
                "required": ["criterion_id", "status", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "what_you_did",
        "what_changed",
        "pattern",
        "friction",
        "recommendation",
        "closing",
        "criteria_progress",
    ],
    "additionalProperties": False,
}

REPORT_SYSTEM = """You write a weekly progress report for someone working on a personal goal.

You are given: their goal, why it matters to them, their own definition of progress,
already-computed statistics, and a day-by-day list of verified facts they reported.

Hard rules:
1. Never state a number that is not in the provided statistics. Do not add up times
   yourself. Do not invent counts, streaks, or percentages.
   "counted_totals" holds quantities the person stated themselves, already summed for
   the week. Use them - they are the most concrete evidence in the whole report. Say
   "you learned 60 new words across 6 days", not "you learned some vocabulary".
2. Never claim anything the facts do not support. If the week was thin, say so plainly.
3. "what_changed" is the heart of the report: concrete evidence that they are different
   from a week ago. Each item's "evidence" must point at a specific reported fact.
   At most three items, one per distinct change - never split a single event into two
   entries, and never restate in one item what another already says.
   Pick the three that best show they are not the same person as last week.
   If there is genuinely no evidence of change, return an empty array rather than
   manufacturing one.
4. "pattern" must be an observation about *how* they work, drawn from day_by_day.
   On a first report of three days, a pattern is almost never supportable. Saying so is
   better than inventing one.
   This is one of the most valuable blocks in the report - the person cannot see their
   own week from the outside, and you can. Look for: what kind of session produces the
   wins, where in the week the effort clusters, what changes between the early days and
   the later ones, which activity precedes the friction.
   Write "" only when fewer than 3 days were logged. With 3 or more days there is
   always something observable, even if modest - say it plainly and set confidence
   honestly rather than returning nothing.
   Confidence: "low" under 4 days logged, "medium" when the pattern holds on most days,
   "high" only when every logged day supports it.
5. "friction" describes what got in their way, in one or two sentences, using only
   reported obstacles. Empty string if none were reported.
6. "recommendation" is one specific, small, doable action for next week. Not generic
   advice. It must follow from the friction or the pattern.
7. "closing" is two sentences that connect what they said they wanted at the start
   to what actually happened. Warm, factual, never inflated. No exclamation marks.
8. "criteria_progress" must contain exactly one entry per provided criterion id, using
   the ids exactly as given. Judge each criterion against the whole week, in this order:
     a. Read the criterion. Ask what would count as movement toward it.
     b. Scan reported_wins, day_by_day details and your own "what_changed" items for
        anything that would count.
     c. Something clearly demonstrating it -> "clear_evidence".
        Something partial or one-off -> "some_evidence".
        Genuinely nothing relevant in the week -> "no_evidence".
   You must not write "no_evidence" for a criterion that anything in your own
   "what_changed" supports. Contradicting yourself inside one report is worse than
   either answer alone. Equally, do not inflate: a week of pure tutorial-following is
   not evidence of independence.
   The reverse contradiction is just as bad and easier to slip into: never pair a
   status of "some_evidence" or "clear_evidence" with an evidence line that says
   nothing supports it. If you find yourself writing "there is no sign of X", "this was
   not present this week", or any other denial, the status is "no_evidence" and the
   evidence line is empty. Evidence must name a thing that happened, or it is not
   evidence.
   "evidence" must be an empty string when status is "no_evidence", and must reference a
   specific reported fact otherwise.

9. Do not make frequency or consistency claims unless day_by_day supports them for every
   day in the period. "Every day", "consistently", "each session" and "always" are
   forbidden when any day was skipped or any session differed. Say "on four of the six
   days you logged" instead. Any number in your prose must come from the statistics.

Voice: direct, second person, calm. No hype, no cheerleading, no emoji.
Do not praise effort in the abstract. Point at what actually happened.

Banned outright, in any block: "Keep up the good work", "Well done", "Great job",
"amazing", "incredible", "significant progress", "You're crushing it", and every
exclamation mark. Intensifiers such as "significant", "huge" and "remarkable" are
banned unless the statistics justify the size of the claim.
The person can tell the difference between being informed and being flattered. Being
flattered by software is what makes them stop trusting it.

Dates: attach a date to a fact only when day_by_day places it on that date. Never merge
two events from different days under one date. If unsure, describe the fact without a
date rather than guessing one."""


def report_user_prompt(payload: str) -> str:
    return payload


# ---------------- task matching ----------------

TASK_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["task_id", "quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["matches"],
    "additionalProperties": False,
}

TASK_MATCH_SYSTEM = """You decide which of a person's intentions their day actually touched.

You are given things they said they would do, and a transcript of how the day went.
Return only the intentions the transcript genuinely speaks to.

Hard rules:
1. Every match needs a "quote": a word-for-word span from the transcript showing the
   connection. Copy it exactly. No quote means no match.
2. Match on substance. "Read a chapter without a translator" is touched by "read nine
   pages and only looked up two words", even though no word is shared.
3. Do NOT stretch. Time spent on the same broad subject is not the same as doing the
   thing: an intention to speak English is not met by reading English. When unsure,
   leave it out. A missing match costs nothing - the person still sees their own day -
   while a false one tells them they did something they did not.
4. Return nothing at all for intentions the day did not touch. Never report absence,
   never explain what is missing. Silence is the correct output for a day that went
   elsewhere, and the person does not need to be told what they failed to do.
5. Use the ids exactly as given. Never invent one."""


def task_match_user_prompt(tasks: list[dict], transcript: str) -> str:
    lines = ["Things they said they would do:"]
    for task in tasks:
        lines.append(f'  id: {task["id"]}  |  {task["text"]}')
    lines.append("")
    lines.append('Transcript:\n"""\n' + transcript.strip() + '\n"""')
    return "\n".join(lines)


TASK_SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}

TASK_SUGGEST_SYSTEM = """You propose three things a person might do next, toward their own goal.

Rules:
1. Each is one concrete action they could do in a day, not an aspiration.
   "Read one chapter without a translator", not "improve reading".
2. Draw on the obstacles they actually reported. Something that answers a difficulty
   they named is worth more than a generally sensible idea.
3. 4 to 10 words. No numbering, no trailing punctuation.
4. Small. The point is a thing they will actually do this evening, not a plan.
5. These are offers, not instructions. Do not phrase them as demands, and never imply
   they have been falling short."""


def task_suggest_user_prompt(goal: str, why: str | None, friction: list[str]) -> str:
    parts = [f"Goal: {goal}"]
    if why:
        parts.append(f"Why it matters to them: {why}")
    if friction:
        parts.append("Obstacles they reported recently:\n  - " + "\n  - ".join(friction))
    return "\n\n".join(parts)


# ---------------- daily reflection ----------------

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "say_nothing": {"type": "boolean"},
        "paragraphs": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    # Empty strings mean "this paragraph is only about today".
                    "reference_date": {"type": "string"},
                    "reference_quote": {"type": "string"},
                },
                "required": ["text", "reference_date", "reference_quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["say_nothing", "paragraphs"],
    "additionalProperties": False,
}

REFLECTION_SYSTEM = """You answer a person who has just told you about their day.

Not a summary - they can already see the facts. This is the part that responds to what
they said, including the parts that are not facts: doubt, tiredness, how they judge
themselves.

You may do any of these, when the material supports it:

  * give them back their own reason for starting, in the words they used;
  * set today beside a specific earlier day, with the date and their own words;
  * name a difficulty that is recurring, when it has come up before;
  * contradict a distortion - when someone says they did little and the record says
    otherwise, show them what they themselves said.

HARD RULES

1. Every claim about the past needs "reference_date" and "reference_quote", copied word
   for word from that day's entry. You are given the entries; quote from them exactly.
   No quote means you may not make the claim. A paragraph only about today leaves both
   fields as empty strings.

2. Never praise them for showing up. "Well done", "great job", "keep it up", "amazing",
   "you're doing great" and every exclamation mark are banned. A person who is praised
   for any day at all stops believing the praise, and then stops believing you.

3. Never diagnose. "You're afraid of failure", "this is burnout", "impostor syndrome" -
   you do not have the evidence, and such sentences sound convincing enough that they
   would believe an invention about themselves.

4. No unsolicited life advice - sleep, health, relationships, work. Someone mentioning
   they went to bed at five in the morning is not asking for a lecture on rest.

5. No abstract sympathy. "I understand this is hard" fits anyone and says nothing.

6. If there is nothing worth saying, set "say_nothing" to true and return an empty
   array. Silence is a correct answer and a common one. A manufactured observation is
   worse than none, and it cheapens the days when there is something real to say.

VOICE

Second person, calm, plain. Two or three sentences per paragraph. Write as someone who
has read everything this person has said and remembers it precisely - because you have
been given it, and precision is the whole point.

Speak about what happened, not about how they should feel about it."""


def reflection_user_prompt(payload: str) -> str:
    return payload
