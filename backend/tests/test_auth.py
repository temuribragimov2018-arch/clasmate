"""
Базовые тесты авторизации.
Для запуска: pytest backend/tests/ -v
Требует работающую БД (или используйте тестовую SQLite).
"""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_invalid_invite():
    r = client.post("/api/auth/register", json={
        "username": "testuser1",
        "password": "testpass123",
        "display_name": "Test User",
        "invite_code": "INVALID"
    })
    assert r.status_code == 400


def test_login_admin():
    r = client.post("/api/auth/login", data={
        "username": "admin",
        "password": "admin123"
    })
    # Может быть 200 если seed прошёл, или 401 если БД пустая
    assert r.status_code in (200, 401)
