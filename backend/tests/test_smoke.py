"""Smoke-тесты на скелет приложения."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    """Healthcheck отвечает 200 и содержит ожидаемые поля."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "moneybot-backend"


def test_root():
    """Root endpoint доступен."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "docs" in data


def test_openapi_available():
    """OpenAPI docs генерируются."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "MoneyBot v2"
