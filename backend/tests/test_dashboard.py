"""Тесты dashboard API."""

from tests.conftest import _create_account, _create_grid


def test_dashboard_empty(client, auth_headers, seeded_users) -> None:
    """Dashboard without grids returns zeroes."""
    resp = client.get("/api/dashboard/", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_grids"] == 0
    assert data["active_grids"] == 0
    assert data["total_pnl"] == 0
    assert data["total_trades"] == 0
    assert data["strategies"] == []
    assert data["positions"] == []


def test_dashboard_with_grid(client, auth_headers, seeded_users) -> None:
    """Dashboard reflects created grids."""
    account = _create_account(client, auth_headers["admin"])
    _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get("/api/dashboard/", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_grids"] == 1
    assert data["active_grids"] == 0
    assert len(data["strategies"]) == 1
    assert data["strategies"][0]["strategy"] == "simple"
    assert len(data["positions"]) == 1


def test_dashboard_with_running_grid(client, auth_headers, seeded_users) -> None:
    """Dashboard counts active grids correctly."""
    account = _create_account(client, auth_headers["admin"])
    grid = _create_grid(client, auth_headers["admin"], account["id"])
    client.post(f"/api/grids/{grid['id']}/start", headers=auth_headers["admin"])
    resp = client.get("/api/dashboard/", headers=auth_headers["admin"])
    data = resp.json()
    assert data["active_grids"] == 1


def test_dashboard_viewer_access(client, auth_headers, seeded_users) -> None:
    """Viewer can access dashboard (read-only)."""
    resp = client.get("/api/dashboard/", headers=auth_headers["viewer"])
    assert resp.status_code == 200


def test_dashboard_no_auth(client, seeded_users) -> None:
    """Dashboard requires authentication."""
    resp = client.get("/api/dashboard/")
    assert resp.status_code in (401, 403)


def test_analytics_empty(client, auth_headers, seeded_users) -> None:
    """Analytics without grids returns empty."""
    resp = client.get("/api/dashboard/analytics?days=30", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["grids"] == []
    assert data["total_stats"]["total_rounds"] == 0
    assert data["grid_comparison"] == []


def test_analytics_with_grid(client, auth_headers, seeded_users) -> None:
    """Analytics reflects created grids."""
    account = _create_account(client, auth_headers["admin"])
    _create_grid(client, auth_headers["admin"], account["id"])
    resp = client.get("/api/dashboard/analytics?days=30", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["grids"]) == 1
    assert data["grids"][0]["symbol"] == "BTC/USDT"
    assert len(data["grid_comparison"]) == 1


def test_analytics_days_validation(client, auth_headers, seeded_users) -> None:
    """Analytics rejects invalid days parameter."""
    resp = client.get("/api/dashboard/analytics?days=0", headers=auth_headers["admin"])
    assert resp.status_code == 422
    resp2 = client.get("/api/dashboard/analytics?days=500", headers=auth_headers["admin"])
    assert resp2.status_code == 422


def test_analytics_viewer_access(client, auth_headers, seeded_users) -> None:
    """Viewer can access analytics."""
    resp = client.get("/api/dashboard/analytics?days=7", headers=auth_headers["viewer"])
    assert resp.status_code == 200
