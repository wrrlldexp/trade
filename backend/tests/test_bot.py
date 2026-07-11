"""Тесты bot API — status, emergency stop, stop-all, restart."""

from unittest.mock import AsyncMock, patch


def test_bot_status(client, auth_headers, seeded_users) -> None:
    """Bot status returns offline when no worker heartbeat."""
    resp = client.get("/api/bot/status", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["online"] is False
    assert data["active_grids"] == 0


def test_bot_status_no_auth(client, seeded_users) -> None:
    """Bot status requires auth."""
    resp = client.get("/api/bot/status")
    assert resp.status_code in (401, 403)


def test_bot_emergency_stop(client, auth_headers, seeded_users) -> None:
    """Emergency stop requires admin role."""
    with patch("app.api.bot.publish", new_callable=AsyncMock), \
         patch("app.api.bot.emergency_stop_all", new_callable=AsyncMock, return_value={"stopped_grids": 0, "cancelled_orders": 0}), \
         patch("app.core.bot_logger.critical", new_callable=AsyncMock):
        resp = client.post("/api/bot/emergency-stop", headers=auth_headers["admin"])
        assert resp.status_code == 200
        assert "stopped_grids" in resp.json()


def test_bot_emergency_stop_viewer_denied(client, auth_headers, seeded_users) -> None:
    """Viewer cannot trigger emergency stop."""
    resp = client.post("/api/bot/emergency-stop", headers=auth_headers["viewer"])
    assert resp.status_code == 403


def test_bot_stop_all(client, auth_headers, seeded_users) -> None:
    """Stop all requires admin role."""
    with patch("app.api.bot.publish", new_callable=AsyncMock), \
         patch("app.core.bot_logger.warning", new_callable=AsyncMock):
        resp = client.post("/api/bot/stop-all", headers=auth_headers["admin"])
        assert resp.status_code == 200


def test_bot_stop_all_viewer_denied(client, auth_headers, seeded_users) -> None:
    """Viewer cannot stop all."""
    resp = client.post("/api/bot/stop-all", headers=auth_headers["viewer"])
    assert resp.status_code == 403


def test_bot_restart_superadmin_only(client, auth_headers, seeded_users) -> None:
    """Restart requires superadmin."""
    with patch("app.api.bot.publish", new_callable=AsyncMock), \
         patch("app.core.bot_logger.warning", new_callable=AsyncMock):
        resp = client.post("/api/bot/restart", headers=auth_headers["superadmin"])
        assert resp.status_code == 200


def test_bot_restart_admin_denied(client, auth_headers, seeded_users) -> None:
    """Admin cannot restart worker."""
    resp = client.post("/api/bot/restart", headers=auth_headers["admin"])
    assert resp.status_code == 403


def test_bot_health_check(client, auth_headers, seeded_users) -> None:
    """Health check endpoint returns system info."""
    resp = client.get("/api/bot/health-check", headers=auth_headers["viewer"])
    assert resp.status_code == 200
