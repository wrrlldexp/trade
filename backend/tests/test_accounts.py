"""Тесты accounts API — CRUD, permissions."""


def test_create_account(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Paper",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Paper"


def test_create_bybit_account(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Bybit",
            "exchange": "bybit",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["exchange"] == "bybit"


def test_list_accounts(client, auth_headers, seeded_users) -> None:
    client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Acc1",
            "exchange": "binance",
            "api_key": "key1",
            "api_secret": "secret1",
            "is_testnet": True,
        },
    )
    resp = client.get("/api/accounts/", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_delete_account(client, auth_headers, seeded_users) -> None:
    account = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "ToDelete",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    ).json()
    resp = client.delete(f"/api/accounts/{account['id']}", headers=auth_headers["admin"])
    assert resp.status_code == 200


def test_update_account(client, auth_headers, seeded_users) -> None:
    account = client.post(
        "/api/accounts/",
        headers=auth_headers["admin"],
        json={
            "name": "Original",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    ).json()
    resp = client.patch(
        f"/api/accounts/{account['id']}",
        headers=auth_headers["admin"],
        json={"name": "Renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_viewer_cannot_create_account(client, auth_headers, seeded_users) -> None:
    resp = client.post(
        "/api/accounts/",
        headers=auth_headers["viewer"],
        json={
            "name": "Fail",
            "exchange": "binance",
            "api_key": "key",
            "api_secret": "secret",
            "is_testnet": True,
        },
    )
    assert resp.status_code == 403


def test_no_auth_cannot_list_accounts(client, seeded_users) -> None:
    resp = client.get("/api/accounts/")
    assert resp.status_code in (401, 403)
