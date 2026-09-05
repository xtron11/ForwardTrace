"""Sending mail, through Resend's HTTP API.

Only one letter exists: the one that confirms an address. Everything else the product
has to say goes to a push notification, because a reminder that lands in an inbox
alongside forty marketing messages is not a reminder.

Without an API key nothing is sent and verification is skipped, so local development
and the test suite need no mail server.
"""

import logging

import httpx

from ..config import settings

log = logging.getLogger(__name__)

API = "https://api.resend.com/emails"


def configured() -> bool:
    return bool(settings.resend_api_key)


SUBJECTS = {
    "en": "Confirm your address",
    "ru": "Подтверди адрес",
}

BODIES = {
    "en": (
        "You created an account in ForwardTrace.",
        "Confirm the address to start recording check-ins:",
        "Confirm",
        "If this was not you, ignore this letter — nothing will happen.",
        "The link is good for {hours} hours.",
    ),
    "ru": (
        "Ты создал аккаунт в ForwardTrace.",
        "Подтверди адрес, чтобы начать записывать чек-ины:",
        "Подтвердить",
        "Если это был не ты — просто не отвечай, ничего не произойдёт.",
        "Ссылка действует {hours} часов.",
    ),
}


def _html(link: str, locale: str) -> str:
    lead, prompt, button, ignore, expiry = BODIES.get(locale[:2], BODIES["en"])
    hours = settings.email_verification_ttl_hours
    # Deliberately plain: a letter that looks like a newsletter gets treated as one.
    return f"""<!doctype html>
<html><body style="margin:0;padding:32px;background:#0E1116;
  font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#F2EDE3">
  <div style="max-width:480px;margin:0 auto">
    <p style="font:600 12px/1 ui-monospace,monospace;letter-spacing:.16em;
      text-transform:uppercase;color:#6E757E;margin:0 0 28px">ForwardTrace</p>
    <p style="font-size:17px;line-height:1.6;margin:0 0 8px">{lead}</p>
    <p style="font-size:17px;line-height:1.6;margin:0 0 28px;color:#A9AFB8">{prompt}</p>
    <a href="{link}" style="display:inline-block;background:#FFB020;color:#0E1116;
      text-decoration:none;padding:14px 28px;border-radius:6px;
      font:600 12px/1 ui-monospace,monospace;letter-spacing:.14em;
      text-transform:uppercase">{button}</a>
    <p style="font-size:13px;line-height:1.7;color:#6E757E;margin:32px 0 0">
      {expiry.format(hours=hours)}<br>{ignore}
    </p>
  </div>
</body></html>"""


async def send_verification(to: str, link: str, locale: str = "en") -> bool:
    """Returns whether it went out. Never raises: a failed letter must not cost
    someone the account they just created."""
    if not configured():
        log.info("email not configured; verification link for %s: %s", to, link)
        return False

    payload = {
        "from": settings.email_from,
        "to": [to],
        "subject": SUBJECTS.get(locale[:2], SUBJECTS["en"]),
        "html": _html(link, locale),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                API,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
        if response.status_code >= 400:
            log.warning("resend refused: %s %s", response.status_code, response.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("could not send verification mail: %s", exc)
        return False
