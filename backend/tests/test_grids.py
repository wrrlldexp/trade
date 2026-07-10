"""Тесты grids."""


def test_create_and_start_grid(client, auth_headers, seeded_users) -> None:
    account = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Paper",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    ).json()

    created = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": account["id"],
            "name": "BTC Grid",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
            "rebuild_timeout_sec": 60,
        },
    )
    assert created.status_code == 200
    grid_id = created.json()["id"]
    assert created.json()["strategy"] == "simple"

    started = client.post(f"/api/grids/{grid_id}/start", headers=auth_headers["admin"])
    assert started.status_code == 200
    assert started.json()["status"] == "running"


def test_create_adaptive_grid(client, auth_headers, seeded_users) -> None:
    account = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Adaptive Paper",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    ).json()

    created = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": account["id"],
            "name": "Adaptive Grid",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "adaptive",
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 3,
            "levels_below": 3,
            "rebuild_timeout_sec": 60,
            "adaptive_timer_sec": 15,
            "prepay_base": "0.5",
            "prepay_quote": "5000",
            "prepay_amount": "0.05",
        },
    )
    assert created.status_code == 200
    assert created.json()["strategy"] == "adaptive"
    assert float(created.json()["prepay_amount"]) == 0.05


def test_admin_cannot_access_other_users_grid(client, auth_headers, seeded_users) -> None:
    owner_account = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Owner Paper",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    ).json()

    grid = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": owner_account["id"],
            "name": "Private Grid",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
            "rebuild_timeout_sec": 60,
        },
    ).json()

    foreign_login = client.post("/api/auth/login", json={"email": "root@example.com", "password": "Password123"})
    foreign_headers = {"Authorization": f"Bearer {foreign_login.json()['tokens']['access_token']}"}
    forbidden = client.get(f"/api/grids/{grid['id']}", headers=foreign_headers)
    assert forbidden.status_code == 404
