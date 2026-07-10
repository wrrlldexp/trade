"""Тесты auth."""


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
