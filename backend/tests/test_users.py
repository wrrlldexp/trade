"""Тесты users."""


def test_superadmin_can_invite(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/users/invites",
        headers=auth_headers["superadmin"],
        json={"email": "new@example.com", "role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["token"]


def test_viewer_cannot_list_users(client, auth_headers, seeded_users) -> None:
    response = client.get("/api/users/", headers=auth_headers["viewer"])
    assert response.status_code == 403
