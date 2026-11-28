"""Bootstrap the first administrator.

Run on the server:  python -m app.modules.users.create_admin --email you@example.com --full-name "Your Name"

The password is read from the ADMIN_PASSWORD environment variable (for automation) or
prompted for interactively. It is never accepted as a command-line argument, because
arguments end up in shell history and process listings.

If the user already exists they are promoted to admin; their password is left untouched.
"""

import argparse
import asyncio
import getpass
import logging
import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import setup_logging
from app.core.permissions import ROLE_ADMIN
from app.core.security import hash_password
from app.modules.auth.repository import RoleRepository
from app.modules.auth.seed import seed_rbac
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


async def ensure_admin(
    session: AsyncSession, email: str, full_name: str, password: str | None
) -> tuple[User, bool]:
    """Create the user (or promote the existing one) and give them the admin role.

    Returns (user, created). `password` is only needed when the user does not exist yet.
    """
    await seed_rbac(session)  # idempotent: guarantees the admin role exists
    email = email.strip().lower()
    users, roles = UserRepository(session), RoleRepository(session)
    admin_role = await roles.get_by_name(ROLE_ADMIN)
    assert admin_role is not None  # seed_rbac just created it

    user = await users.get_by_email(email)
    created = user is None
    if user is None:
        if password is None or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        user = User(email=email, password_hash=hash_password(password), full_name=full_name)
        users.add(user)

    if admin_role not in user.roles:
        user.roles.append(admin_role)
    user.is_active = True
    await session.commit()
    return user, created


def _read_password() -> str:
    from_env = os.environ.get("ADMIN_PASSWORD")
    if from_env:
        return from_env
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords do not match")
    return first


async def _main(email: str, full_name: str) -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            existing = await UserRepository(session).get_by_email(email)
            password = None if existing else _read_password()
            user, created = await ensure_admin(session, email, full_name, password)
        print(f"{'Created' if created else 'Promoted'} admin: {user.email}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()
    try:
        asyncio.run(_main(args.email, args.full_name))
    except ValueError as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
