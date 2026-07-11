"""Тесты auth API — login, refresh, 2FA, password, edge cases."""


def test_login_and_me(client, seeded_users) -> None:
    response = client.post("/api/auth/login", json={"email": "root@example.com", "password": "Password123"})
    assert response.status_code == 200
    token = response.json()["tokens"]["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "root@example.com"


def test_refresh(client, seeded_users) -> None:
    response = client.post("/api/auth/login", json={"email": "root@example.com", "password": "Password123"})
    refresh_token = response.json()["tokens"]["refresh_token"]
    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()


def test_2fa_setup_and_verify(client, seeded_users) -> None:
    response = client.post("/api/auth/login", json={"email": "root@example.com", "password": "Password123"})
    token = response.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup = client.post("/api/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    import pyotp

    code = pyotp.TOTP(secret).now()
    verify = client.post("/api/auth/2fa/verify", headers=headers, json={"code": code})
    assert verify.status_code == 200


def test_login_wrong_password(client, seeded_users) -> None:
    response = client.post("/api/auth/login", json={"email": "root@example.com", "password": "WrongPass"})
    assert response.status_code == 401


def test_login_nonexistent_user(client, seeded_users) -> None:
    response = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Password123"})
    assert response.status_code == 401


def test_me_invalid_token(client, seeded_users) -> None:
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code in (401, 403)


def test_me_no_token(client, seeded_users) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_refresh_invalid_token(client, seeded_users) -> None:
    resp = client.post("/api/auth/refresh", json={"refresh_token": "invalid"})
    assert resp.status_code in (401, 403)


def test_logout(client, seeded_users) -> None:
    login = client.post("/api/auth/login", json={"email": "root@example.com", "password": "Password123"})
    tokens = login.json()["tokens"]
    resp = client.post(
        "/api/auth/logout",
        json={"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"]},
    )
    assert resp.status_code == 200
