"""Общие фикстуры backend-тестов."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import User, UserRole


@pytest.fixture()
async def session_factory(tmp_path: Path) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture()
def client(session_factory: async_sessionmaker[AsyncSession]) -> Generator[TestClient, None, None]:
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    # Disable rate limiting in tests
    with patch("app.api.auth.check_rate_limit", new_callable=AsyncMock, return_value=True):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
async def seeded_users(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, User]:
    async with session_factory() as session:
        superadmin = User(
            email="root@example.com",
            password_hash=hash_password("Password123"),
            full_name="Root",
            role=UserRole.SUPERADMIN,
        )
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("Password123"),
            full_name="Admin",
            role=UserRole.ADMIN,
        )
        viewer = User(
            email="viewer@example.com",
            password_hash=hash_password("Password123"),
            full_name="Viewer",
            role=UserRole.VIEWER,
        )
        session.add_all([superadmin, admin, viewer])
        await session.commit()
        await session.refresh(superadmin)
        await session.refresh(admin)
        await session.refresh(viewer)
        return {"superadmin": superadmin, "admin": admin, "viewer": viewer}


@pytest.fixture()
def auth_headers(client: TestClient, seeded_users: dict[str, User]) -> dict[str, dict[str, str]]:
    users = {}
    for key, email in {
        "superadmin": "root@example.com",
        "admin": "admin@example.com",
        "viewer": "viewer@example.com",
    }.items():
        response = client.post("/api/auth/login", json={"email": email, "password": "Password123"})
        token = response.json()["tokens"]["access_token"]
        users[key] = {"Authorization": f"Bearer {token}"}
    return users


def _create_account(client: TestClient, headers: dict, name: str = "Paper") -> dict:
    """Helper: create an exchange account and return JSON."""
    return client.post(
        "/api/accounts/",
        headers=headers,
        json={
            "name": name,
            "exchange": "binance",
            "api_key": "testkey",
            "api_secret": "testsecret",
            "is_testnet": True,
        },
    ).json()


def _create_grid(
    client: TestClient,
    headers: dict,
    account_id: str,
    name: str = "Test Grid",
    strategy: str = "simple",
) -> dict:
    """Helper: create a grid and return JSON."""
    resp = client.post(
        "/api/grids/",
        headers=headers,
        json={
            "account_id": account_id,
            "name": name,
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": strategy,
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
            "rebuild_timeout_sec": 60,
        },
    )
    assert resp.status_code == 200
    return resp.json()
