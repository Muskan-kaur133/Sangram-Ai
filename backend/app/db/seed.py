"""Development-only demo data seeder.

Creates a normal, password-backed demo user so local ownership checks can be
exercised through the real authentication endpoints. This is NOT an auth
bypass: the demo user logs in with the same JWT/cookie flow as any other user.

Usage:
    python -m app.db.seed
"""

import asyncio

from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.db.session import close_db_engine, get_session_factory
from app.proposals.entities import Profile, User

DEMO_EMAIL = "demo@sangram.ai"
DEMO_PASSWORD = "SangramDemo123!"
DEMO_NAME = "Demo User"


async def seed_demo_user() -> None:
    """Idempotently creates the local demo account and its profile."""
    settings = get_settings()
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("Refusing to seed the demo user in production.")

    factory = get_session_factory()
    try:
        async with factory() as db:
            user = (
                await db.execute(select(User).where(User.email == DEMO_EMAIL))
            ).scalar_one_or_none()

            if user is None:
                user = User(
                    email=DEMO_EMAIL,
                    password_hash=security.hash_password(DEMO_PASSWORD),
                    is_verified=True,
                )
                db.add(user)
                await db.flush()
                print(f"Created demo user {DEMO_EMAIL}")
            else:
                print(f"Demo user {DEMO_EMAIL} already exists; leaving it unchanged.")

            profile = (
                await db.execute(select(Profile).where(Profile.user_id == user.id))
            ).scalar_one_or_none()

            if profile is None:
                db.add(
                    Profile(
                        user_id=user.id,
                        name=DEMO_NAME,
                        onboarding_completed=True,
                        default_models=["chatgpt", "claude"],
                        default_archetype="logician",
                    )
                )
                print(f"Created profile for {DEMO_EMAIL}")

            await db.commit()
    finally:
        await close_db_engine()

    print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")


def main() -> None:
    try:
        asyncio.run(seed_demo_user())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
