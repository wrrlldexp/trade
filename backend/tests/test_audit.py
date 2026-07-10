"""Тесты audit."""


def test_audit_has_entries(client, auth_headers, seeded_users) -> None:
    client.post(
        "/api/users/invites",
        headers=auth_headers["superadmin"],
        json={"email": "audit@example.com", "role": "viewer"},
    )
    response = client.get("/api/audit/", headers=auth_headers["superadmin"])
    assert response.status_code == 200
    assert len(response.json()) >= 1
