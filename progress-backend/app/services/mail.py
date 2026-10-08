"""Sending mail, through Resend's HTTP API.

Two letters exist: the one that confirms an address, and the one sent when an account
is deleted, which carries the link to restore it. Everything else the product has to
say goes to a push notification, because a reminder that lands in an inbox alongside
forty marketing messages is not a reminder.

Without an API key nothing is sent and verification is skipped, so local development
and the test suite need no mail server.
"""

import html
import logging
from datetime import date

import httpx

from ..config import settings

log = logging.getLogger(__name__)

API = "https://api.resend.com/emails"


def configured() -> bool:
    return bool(settings.resend_api_key)


SUBJECTS = {
    "en": "ForwardTrace: confirm your email address",
    "ru": "ForwardTrace: подтверждение адреса электронной почты",
}

# Formal and courteous, the way service mail from established products reads: the
# person has not met us yet, and the first letter sets the tone.
BODIES = {
    "en": {
        "greeting": "Hello, {name}!",
        "greeting_anon": "Hello!",
        "lead": "Thank you for signing up for ForwardTrace.",
        "prompt": (
            "To finish creating your account and start recording check-ins, please "
            "confirm your email address by clicking the button below."
        ),
        "button": "Confirm email address",
        "expiry": "This link is valid for {hours}.",
        "fallback": "If the button does not work, copy this link into your browser's address bar:",
        "ignore": (
            "If you did not create a ForwardTrace account, you can safely ignore this "
            "email. No further action is required."
        ),
        "signoff": "Best regards,<br>The ForwardTrace team",
    },
    "ru": {
        "greeting": "Здравствуйте, {name}!",
        "greeting_anon": "Здравствуйте!",
        "lead": "Благодарим вас за регистрацию в ForwardTrace.",
        "prompt": (
            "Чтобы завершить регистрацию и начать записывать чек-ины, пожалуйста, "
            "подтвердите адрес электронной почты, нажав на кнопку ниже."
        ),
        "button": "Подтвердить адрес",
        "expiry": "Ссылка действительна в течение {hours}.",
        "fallback": "Если кнопка не работает, скопируйте эту ссылку в адресную строку браузера:",
        "ignore": (
            "Если вы не регистрировались в ForwardTrace, просто проигнорируйте это "
            "письмо. Никаких действий с вашей стороны не требуется."
        ),
        "signoff": "С уважением,<br>команда ForwardTrace",
    },
}

DELETED_SUBJECTS = {
    "en": "ForwardTrace: your account has been deleted",
    "ru": "ForwardTrace: ваш аккаунт удалён",
}

DELETED_BODIES = {
    "en": {
        "lead": "Your ForwardTrace account has been deleted at your request.",
        "prompt": (
            "All of your data - check-ins, recordings, goals and reports - will be "
            "permanently erased on {date}. Until then, you can restore your account "
            "with everything in it by clicking the button below."
        ),
        "button": "Restore account",
        "expiry": "After {date} the account cannot be restored.",
        "ignore": (
            "If you meant to delete your account, no action is required: the data will "
            "be erased automatically."
        ),
    },
    "ru": {
        "lead": "Ваш аккаунт ForwardTrace удалён по вашему запросу.",
        "prompt": (
            "Все ваши данные - записи, аудио, цели и отчёты - будут безвозвратно "
            "удалены {date}. До этого момента вы можете восстановить аккаунт со всеми "
            "данными, нажав на кнопку ниже."
        ),
        "button": "Восстановить аккаунт",
        "expiry": "После {date} восстановить аккаунт будет невозможно.",
        "ignore": (
            "Если вы действительно хотели удалить аккаунт, ничего делать не нужно: "
            "данные будут удалены автоматически."
        ),
    },
}

MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _lang(locale: str) -> str:
    return locale[:2] if locale[:2] in BODIES else "en"


def _hours(n: int, lang: str) -> str:
    if lang != "ru":
        return f"{n} hour" if n == 1 else f"{n} hours"
    # "в течение" takes the genitive: 1 часа, 2-4 часов, 21 часа, but 11 часов.
    # In the genitive only numbers ending in 1 (not 11) differ from the rest.
    word = "часа" if n % 10 == 1 and n % 100 != 11 else "часов"
    return f"{n} {word}"


def _date(day: date, lang: str) -> str:
    if lang == "ru":
        return f"{day.day} {MONTHS_RU[day.month - 1]} {day.year} г."
    return f"{day:%B} {day.day}, {day.year}"


def _greeting(lang: str, name: str | None) -> str:
    t = BODIES[lang]
    # The name is typed by whoever registered. Escaped, or anyone could put their own
    # markup - a link, a fake button - into a letter sent under our name.
    clean = html.escape(name.strip()) if name and name.strip() else None
    return t["greeting"].format(name=clean) if clean else t["greeting_anon"]


def _layout(
    *, lang: str, name: str | None, link: str, lead: str, prompt: str, button: str,
    expiry: str, ignore: str,
) -> str:
    t = BODIES[lang]
    safe_link = html.escape(link, quote=True)
    muted = "font-size:13px;line-height:1.7;color:#6E757E"
    # Deliberately plain: a letter that looks like a newsletter gets treated as one.
    return f"""<!doctype html>
<html><body style="margin:0;padding:32px;background:#0E1116;
  font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#F2EDE3">
  <div style="max-width:480px;margin:0 auto">
    <p style="font:600 12px/1 ui-monospace,monospace;letter-spacing:.16em;
      text-transform:uppercase;color:#6E757E;margin:0 0 28px">ForwardTrace</p>
    <p style="font-size:17px;line-height:1.6;margin:0 0 16px">{_greeting(lang, name)}</p>
    <p style="font-size:17px;line-height:1.6;margin:0 0 8px">{lead}</p>
    <p style="font-size:17px;line-height:1.6;margin:0 0 28px;color:#A9AFB8">{prompt}</p>
    <a href="{safe_link}" style="display:inline-block;background:#FFB020;color:#0E1116;
      text-decoration:none;padding:14px 28px;border-radius:6px;
      font:600 12px/1 ui-monospace,monospace;letter-spacing:.14em;
      text-transform:uppercase">{button}</a>
    <p style="{muted};margin:32px 0 0">{expiry}</p>
    <p style="{muted};margin:12px 0 0">{t["fallback"]}<br>
      <a href="{safe_link}" style="color:#A9AFB8;word-break:break-all">{safe_link}</a></p>
    <p style="{muted};margin:12px 0 0">{ignore}</p>
    <p style="font-size:15px;line-height:1.6;color:#A9AFB8;margin:32px 0 0">{t["signoff"]}</p>
  </div>
</body></html>"""


def _html(link: str, locale: str, name: str | None = None) -> str:
    lang = _lang(locale)
    t = BODIES[lang]
    return _layout(
        lang=lang,
        name=name,
        link=link,
        lead=t["lead"],
        prompt=t["prompt"],
        button=t["button"],
        expiry=t["expiry"].format(hours=_hours(settings.email_verification_ttl_hours, lang)),
        ignore=t["ignore"],
    )


def _deleted_html(link: str, locale: str, erase_on: date, name: str | None = None) -> str:
    lang = _lang(locale)
    t = DELETED_BODIES[lang]
    when = _date(erase_on, lang)
    return _layout(
        lang=lang,
        name=name,
        link=link,
        lead=t["lead"],
        prompt=t["prompt"].format(date=when),
        button=t["button"],
        expiry=t["expiry"].format(date=when),
        ignore=t["ignore"],
    )


async def _send(to: str, subject: str, body: str) -> bool:
    payload = {"from": settings.email_from, "to": [to], "subject": subject, "html": body}
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
        log.warning("could not send mail: %s", exc)
        return False


async def send_verification(
    to: str, link: str, locale: str = "en", name: str | None = None
) -> bool:
    """Returns whether it went out. Never raises: a failed letter must not cost
    someone the account they just created."""
    if not configured():
        log.info("email not configured; verification link for %s: %s", to, link)
        return False
    return await _send(to, SUBJECTS.get(locale[:2], SUBJECTS["en"]), _html(link, locale, name))


async def send_account_deleted(
    to: str, link: str, erase_on: date, locale: str = "en", name: str | None = None
) -> bool:
    """The restore link. Returns whether it went out and never raises: the deletion
    itself has already happened, and signing in sends the letter again."""
    if not configured():
        log.info("email not configured; restore link for %s: %s", to, link)
        return False
    return await _send(
        to,
        DELETED_SUBJECTS.get(locale[:2], DELETED_SUBJECTS["en"]),
        _deleted_html(link, locale, erase_on, name),
    )
