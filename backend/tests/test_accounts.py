"""Тесты accounts."""


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
