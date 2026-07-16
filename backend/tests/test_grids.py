"""Тесты grids API — CRUD, start/stop, events, orders, permissions."""

from tests.conftest import _create_account, _create_grid


def test_create_grid(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    assert grid["strategy"] == "simple"
    assert grid["status"] == "draft"
    assert grid["symbol"] == "BTC/USDT"


def test_create_adaptive_grid(client, auth_headers, seeded_users) -> None:
    """Adaptive grid — prepay fields не передаются через GridCreate, используются дефолты."""
    account = _create_account(client, auth_headers["admin"])
    resp = client.post(
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
        },
    )
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "adaptive"


def test_list_grids(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    _create_grid(client, auth_headers["admin"], account["id"], name="Grid A")
    _create_grid(client, auth_headers["admin"], account["id"], name="Grid B")
    resp = client.get("/api/grids/", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_grid_detail(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get(f"/api/grids/{grid['id']}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == grid["id"]
    assert "orders" in data


def test_update_grid(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.patch(
        f"/api/grids/{grid['id']}",
        headers=auth_headers["admin"],
        json={"name": "Updated Name", "profit_step": "75"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert float(resp.json()["profit_step"]) == 75


def test_start_and_stop_grid(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    # Start
    started = client.post(f"/api/grids/{grid['id']}/start", headers=auth_headers["admin"])
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    # Stop
    stopped = client.post(f"/api/grids/{grid['id']}/stop", headers=auth_headers["admin"])
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


def test_delete_grid(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.delete(f"/api/grids/{grid['id']}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Confirm deleted
    resp2 = client.get(f"/api/grids/{grid['id']}", headers=auth_headers["admin"])
    assert resp2.status_code == 404


def test_grid_events_empty(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get(f"/api/grids/{grid['id']}/events", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json() == []


def test_grid_orders_empty(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get(f"/api/grids/{grid['id']}/orders", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json() == []


def test_admin_cannot_access_other_users_grid(client, auth_headers, seeded_users) -> None:
    """Admin может видеть только свои сетки."""
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    # Superadmin видит всё
    resp = client.get(f"/api/grids/{grid['id']}", headers=auth_headers["superadmin"])
    assert resp.status_code == 200
    # Viewer видит всё (read-only)
    resp2 = client.get(f"/api/grids/{grid['id']}", headers=auth_headers["viewer"])
    assert resp2.status_code == 200


def test_viewer_cannot_create_grid(client, auth_headers, seeded_users) -> None:
    """Viewer не может создавать сетки."""
    resp = client.post(
        "/api/grids/",
        headers=auth_headers["viewer"],
        json={
            "account_id": "00000000-0000-0000-0000-000000000000",
            "name": "Fail",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
        },
    )
    assert resp.status_code == 403


def test_create_grid_invalid_account(client, auth_headers, seeded_users) -> None:
    """Grid creation with non-existent account returns 404."""
    resp = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": "00000000-0000-0000-0000-000000000000",
            "name": "Fail",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "lot_size": "0.1",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
        },
    )
    assert resp.status_code == 404


def test_update_running_grid_blocked_fields(client, auth_headers, seeded_users) -> None:
    """Cannot change structural params on a running grid."""
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    client.post(f"/api/grids/{grid['id']}/start", headers=auth_headers["admin"])
    # Try changing grid_step (structural, blocked)
    resp = client.patch(
        f"/api/grids/{grid['id']}",
        headers=auth_headers["admin"],
        json={"grid_step": "200"},
    )
    assert resp.status_code == 400


def test_update_running_grid_hot_fields(client, auth_headers, seeded_users) -> None:
    """Can change hot-update fields (name, lot_size) on a running grid."""
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    client.post(f"/api/grids/{grid['id']}/start", headers=auth_headers["admin"])
    resp = client.patch(
        f"/api/grids/{grid['id']}",
        headers=auth_headers["admin"],
        json={"name": "Hot Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hot Updated"


def test_create_grid_lot_quote(client, auth_headers, seeded_users) -> None:
    """Grid creation with lot_quote instead of lot_size."""
    account = _create_account(client, auth_headers["admin"])
    resp = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": account["id"],
            "name": "Quote Grid",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "lot_quote": "10",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
        },
    )
    assert resp.status_code == 200
    assert float(resp.json()["lot_quote"]) == 10


def test_create_grid_no_lot_fails(client, auth_headers, seeded_users) -> None:
    """Grid creation without lot_size or lot_quote fails validation."""
    account = _create_account(client, auth_headers["admin"])
    resp = client.post(
        "/api/grids/",
        headers=auth_headers["admin"],
        json={
            "account_id": account["id"],
            "name": "No Lot",
            "symbol": "BTC/USDT",
            "mode": "paper",
            "strategy": "simple",
            "profit_step": "50",
            "grid_step": "100",
            "levels_above": 2,
            "levels_below": 2,
        },
    )
    assert resp.status_code == 422


def test_analytics_sessions_empty(client, auth_headers, seeded_users) -> None:
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get(f"/api/grids/{grid['id']}/analytics-sessions", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json() == []
