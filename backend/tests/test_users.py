"""Тесты users API — CRUD, invites, permissions."""


def test_superadmin_can_invite(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/users/invites",
        headers=auth_headers["superadmin"],
        json={"email": "new@example.com", "role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["token"]


def test_viewer_can_list_users(client, auth_headers, seeded_users) -> None:
    """Viewer has read access to user list."""
    response = client.get("/api/users/", headers=auth_headers["viewer"])
    assert response.status_code == 200


def test_superadmin_can_list_users(client, auth_headers, seeded_users) -> None:
    response = client.get("/api/users/", headers=auth_headers["superadmin"])
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 3


def test_superadmin_can_create_user(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/users/",
        headers=auth_headers["superadmin"],
        json={
            "email": "created@example.com",
            "password": "SecurePass123",
            "full_name": "Created User",
            "role": "viewer",
        },
    )
    assert response.status_code == 200
    assert response.json()["email"] == "created@example.com"


def test_admin_cannot_create_user(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/users/",
        headers=auth_headers["admin"],
        json={
            "email": "fail@example.com",
            "password": "SecurePass123",
            "full_name": "Fail",
            "role": "viewer",
        },
    )
    assert response.status_code == 403


def test_admin_cannot_invite(client, auth_headers, seeded_users) -> None:
    response = client.post(
        "/api/users/invites",
        headers=auth_headers["admin"],
        json={"email": "fail@example.com", "role": "viewer"},
    )
    assert response.status_code == 403


def test_no_auth_cannot_list_users(client, seeded_users) -> None:
    response = client.get("/api/users/")
    assert response.status_code in (401, 403)
