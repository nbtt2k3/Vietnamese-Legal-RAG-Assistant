import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import SecurityMiddleware
from app.config import settings


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.get("/public")
    def public():
        return {"ok": True}

    @app.post("/api/v1/ping")
    def api_ping():
        return {"ok": True}

    return app


def _disable_redis(monkeypatch):
    def fail_from_url(*args, **kwargs):
        raise RuntimeError("redis unavailable in unit test")

    monkeypatch.setattr(redis_asyncio, "from_url", fail_from_url)


def test_security_headers_are_added_to_non_api_responses(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")

    client = TestClient(_build_app())
    response = client.get("/public")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_production_api_key_is_required_and_constant_time_checked(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_key", "expected-secret")

    client = TestClient(_build_app())

    missing = client.post("/api/v1/ping")
    wrong = client.post("/api/v1/ping", headers={"x-api-key": "wrong"})
    valid = client.post("/api/v1/ping", headers={"x-api-key": "expected-secret"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200
    assert missing.headers["X-Request-ID"]


def test_request_body_limit_uses_configured_setting(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "request_body_limit_bytes", 4)

    client = TestClient(_build_app())
    response = client.post("/api/v1/ping", content="12345")

    assert response.status_code == 413
    assert response.json()["error"] == "Payload too large"
    assert response.headers["X-Request-ID"]
