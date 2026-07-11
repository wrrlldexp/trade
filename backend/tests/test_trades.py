"""Тесты trades API."""


def test_list_trades_empty(client, auth_headers, seeded_users) -> None:
    """Trades list returns empty when no trades."""
    resp = client.get("/api/trades/", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_trades_viewer_access(client, auth_headers, seeded_users) -> None:
    """Viewer can list trades."""
    resp = client.get("/api/trades/", headers=auth_headers["viewer"])
    assert resp.status_code == 200


def test_list_trades_no_auth(client, seeded_users) -> None:
    """Trades require auth."""
    resp = client.get("/api/trades/")
    assert resp.status_code in (401, 403)


def test_list_trades_with_filters(client, auth_headers, seeded_users) -> None:
    """Trades list accepts filter parameters."""
    resp = client.get(
        "/api/trades/?event_type=fill&offset=0&limit=10",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200


def test_list_trades_pagination(client, auth_headers, seeded_users) -> None:
    """Trades list accepts pagination."""
    resp = client.get("/api/trades/?offset=0&limit=5", headers=auth_headers["admin"])
    assert resp.status_code == 200

    resp2 = client.get("/api/trades/?offset=5&limit=5", headers=auth_headers["admin"])
    assert resp2.status_code == 200
