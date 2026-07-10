"""Создание первого суперадмина."""

import asyncio
import getpass
import re
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db import AsyncSessionLocal
from app.models import User, UserRole

configure_logging()
log = get_logger("cli.create_superadmin")


async def create_superadmin() -> None:
    print("=== Создание первого суперадмина ===\n")

    email = input("Email: ").strip()
    try:
        email = validate_email(email).normalized
    except EmailNotValidError:
        print("Некорректный email")
        sys.exit(1)

    full_name = input("Полное имя: ").strip()
    if not full_name:
        print("✗ Имя не может быть пустым")
        sys.exit(1)

    password = getpass.getpass("Пароль: ")
    password2 = getpass.getpass("Повторите пароль: ")
    if password != password2:
        print("Пароли не совпадают")
        sys.exit(1)
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        print("Пароль должен быть не короче 8 символов и содержать буквы и цифры")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"Пользователь {email} уже существует")
            sys.exit(1)

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=UserRole.SUPERADMIN,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    print(f"\n✓ Суперадмин создан: {user.email} (id={user.id})")


if __name__ == "__main__":
    asyncio.run(create_superadmin())
