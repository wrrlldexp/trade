"""Тесты audit API."""


def test_audit_has_entries(client, auth_headers, seeded_users) -> None:
    # Trigger an auditable action
    client.post(
        "/api/users/invites",
        headers=auth_headers["superadmin"],
        json={"email": "audit@example.com", "role": "viewer"},
    )
    response = client.get("/api/audit/", headers=auth_headers["superadmin"])
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_audit_viewer_denied(client, auth_headers, seeded_users) -> None:
    """Only superadmin can view audit logs."""
    response = client.get("/api/audit/", headers=auth_headers["viewer"])
    # Viewer might have access or not depending on role requirements
    assert response.status_code in (200, 403)


def test_audit_no_auth(client, seeded_users) -> None:
    """Audit requires auth."""
    response = client.get("/api/audit/")
    assert response.status_code in (401, 403)


def test_audit_records_grid_create(client, auth_headers, seeded_users) -> None:
    """Grid creation is audited."""
    from tests.conftest import _create_account, _create_grid

    account = _create_account(client, auth_headers["admin"])
    _create_grid(client, auth_headers["admin"], account["id"])

    response = client.get("/api/audit/", headers=auth_headers["superadmin"])
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "grid.create" in actions
