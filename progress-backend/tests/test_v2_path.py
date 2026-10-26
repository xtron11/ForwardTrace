"""Stage 5, spec §5 item 1: the browser path of the stage-5 criterion, walked through the
API alone (STT and the step models are the fakes from conftest.py).

registration -> first conversation (text, a finish chosen with a button, the baseline
by voice) -> the "then -> now" comparison -> the hour -> today is green on the week
strip -> the day in the history -> the audio of the quoted message is served, and only
to its owner.
"""

from datetime import timedelta

import pytest

from app.config import settings
from app.time_utils import local_today
from conftest import FIRST_RESULTS, TRANSCRIPT, parse_sse, register

TZ = "America/Los_Angeles"
TODAY = "/api/conversations/today"
MESSAGES = "/api/conversations/today/messages"
AUDIO = b"\x1a\x45\xdf\xa3 fake webm bytes"


@pytest.fixture
def audio_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "audio_dir", str(tmp_path / "audio"))
    return tmp_path / "audio"


async def _text(client, auth, text):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def _done(events) -> dict:
    [done] = [d for e, d in events if e == "done"]
    return done


async def _active(client, auth, day, days_back=6):
    r = await client.get(
        "/api/calendar", params={"from": str(day - timedelta(days=days_back)), "to": str(day)}, headers=auth
    )
    assert r.status_code == 200, r.text
    return {d["local_date"]: d["active"] for d in r.json()}


@pytest.mark.asyncio
async def test_stage_five_path_through_the_api(client, audio_dir, monkeypatch):
    today = local_today(TZ)
    auth = await register(client)

    # 1. the first screen: the AI asks first, and a message from the AI alone paints nothing
    r = await client.get(TODAY, headers=auth)
    assert r.status_code == 200
    first = r.json()
    assert first["kind"] == "first"
    assert [m["role"] for m in first["messages"]] == ["assistant"]
    assert first["messages"][0]["quick_replies"]
    assert (await _active(client, auth, today))[str(today)] is False

    # 2. skill and motivation by text
    await _text(client, auth, "I make a small game in Unity")
    events = await _text(client, auth, "I want to ship my own game one day")

    # 3. the finish is chosen with a button: the reply to motivation offers the options
    options = _done(events)["quick_replies"]
    assert len(options) == 5 and options[0] == "Level B2"
    await _text(client, auth, options[0])

    # 4. the starting point, by voice: quotes come from the transcript and carry the
    #    time span in the recording
    then, now = "Today I finally", "the memory leak in the renderer"
    assert then in TRANSCRIPT and now in TRANSCRIPT
    monkeypatch.setitem(
        FIRST_RESULTS,
        "baseline",
        {
            "on_topic": True,
            "pairs": [{"then_quote": then, "now_quote": now, "theme": "Debugging"}],
            "level_quote": "",
            "just_started": False,
        },
    )
    r = await client.post(MESSAGES, files={"audio": ("note.webm", AUDIO, "audio/webm")}, headers=auth)
    assert r.status_code == 200, r.text
    events = parse_sse(r.text)
    user_message = next(d for e, d in events if e == "user_message")
    assert user_message["source"] == "voice" and user_message["content"] == TRANSCRIPT

    # 5. the comparison "then -> now": two recalled quotes, then the hour question
    quotes = [d for e, d in events if e == "quote"]
    assert [q["quote"] for q in quotes] == [then, now]
    assert all(q["recalled"] is True and q["message_id"] == user_message["id"] for q in quotes)
    assert quotes[0]["audio_start_ms"] is not None and quotes[0]["audio_end_ms"] > quotes[0]["audio_start_ms"]
    assert _done(events)["quick_replies"]

    # 6. the hour, as the picker sends it ("HH:00") -> the first conversation is done
    events = await _text(client, auth, "18:00")
    assert _done(events)["quick_replies"] == []
    me = (await client.get("/api/auth/me", headers=auth)).json()
    assert me["first_conversation_done"] is True and me["reminder_hour"] == 18

    # 7. today is green on the week strip, and a week back is not
    days = await _active(client, auth, today)
    assert days[str(today)] is True
    assert not any(v for k, v in days.items() if k != str(today))

    # 8. the history lists the day, and the day opens with the quotes inside the reply
    feed = (await client.get("/api/conversations", headers=auth)).json()
    assert [d["local_date"] for d in feed] == [str(today)]
    day = (await client.get(f"/api/conversations/{today}", headers=auth)).json()
    segments = [s for m in day["messages"] if m["role"] == "assistant" for s in m["content"]]
    stored = [s for s in segments if s["type"] == "quote"]
    assert [s["quote"] for s in stored] == [then, now]
    assert stored[0]["recalled"] is True and stored[0]["local_date"] == str(today)
    voice = [m for m in day["messages"] if m["role"] == "user" and m["has_audio"]]
    assert len(voice) == 1 and voice[0]["id"] == stored[0]["message_id"]

    # 9. tapping the quote plays the recording of its message: the file comes back whole
    audio = await client.get(f"/api/messages/{stored[0]['message_id']}/audio", headers=auth)
    assert audio.status_code == 200 and audio.content == AUDIO

    # 10. someone else gets nothing: not the audio, not the day, and their strip is empty
    other = await register(client, email="other@example.com")
    assert (await client.get(f"/api/messages/{stored[0]['message_id']}/audio", headers=other)).status_code == 404
    assert (await client.get(f"/api/conversations/{today}", headers=other)).status_code == 404
    assert (await client.get("/api/conversations", headers=other)).json() == []
    assert (await _active(client, other, today))[str(today)] is False
