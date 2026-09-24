"""Create an account without going through registration.

For handing someone access when the letter cannot reach them - a corporate mail server
that eats it, a tester on an address you do not control, or yourself while debugging.

Run from progress-backend:

    python scripts/make_account.py tester@example.com somepassword
    python scripts/make_account.py tester@example.com somepassword --name "Ilya" --tz Asia/Almaty

The account comes out verified, so it can be used straight away. Run it against
whichever database DATABASE_URL points at: locally that is Docker, and with the Railway
CLI it is production.

    railway run python scripts/make_account.py tester@example.com somepassword
"""

import argparse
import asyncio
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

# Python puts scripts/ on the path, not the backend root, so `import app` needs the
# root added by hand. .env is still read from the working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


async def create(email: str, password: str, name: str | None, tz: str, locale: str) -> int:
    email = email.strip().lower()

    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        print(f"Unknown timezone: {tz}")
        return 1

    async with SessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if existing is not None:
            # Rather than refuse: the usual reason for running this is that someone
            # signed up and never got the letter.
            existing.password_hash = hash_password(password)
            existing.email_verified = True
            existing.is_active = True
            await db.commit()
            print(f"Updated {email}: password reset, address marked verified.")
            return 0

        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                display_name=name,
                timezone=tz,
                locale=locale,
                email_verified=True,
            )
        )
        await db.commit()
        print(f"Created {email} — verified, ready to sign in.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset a verified account.")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--name", default=None, help="Display name")
    parser.add_argument(
        "--tz",
        default="Asia/Almaty",
        help="IANA timezone. Every day and week boundary is computed from it.",
    )
    parser.add_argument("--locale", default="ru", choices=["ru", "en"])
    args = parser.parse_args()

    return asyncio.run(create(args.email, args.password, args.name, args.tz, args.locale))


if __name__ == "__main__":
    sys.exit(main())
