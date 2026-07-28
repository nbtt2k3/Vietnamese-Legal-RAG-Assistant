import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import _sanitize_log_value, api_router
from app.api.middleware import SecurityMiddleware
from app.server import app as server_app
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


def _build_api_app() -> FastAPI:
    app = _build_app()
    app.include_router(api_router)
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


def test_feedback_rejects_invalid_rating(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")

    client = TestClient(_build_api_app())
    response = client.post(
        "/api/v1/feedback",
        json={"message_id": "m1", "query": "valid query", "rating": 2},
    )

    assert response.status_code == 422


def test_feedback_rejects_oversized_fields(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")

    client = TestClient(_build_api_app())
    long_comment = "x" * 2_001
    response = client.post(
        "/api/v1/feedback",
        json={"message_id": "m1", "query": "valid query", "rating": 1, "comment": long_comment},
    )

    assert response.status_code == 422


def test_feedback_accepts_valid_payload(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "development")

    client = TestClient(_build_api_app())
    response = client.post(
        "/api/v1/feedback",
        json={"message_id": "m1", "query": "valid query", "rating": -1, "comment": "needs detail"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_log_sanitizer_removes_control_characters_and_truncates():
    sanitized = _sanitize_log_value("line 1\nline\t2\rline 3", max_length=12)

    assert "\n" not in sanitized
    assert "\r" not in sanitized
    assert "\t" not in sanitized
    assert sanitized == "line 1 li..."


def test_liveness_endpoint_does_not_require_rag_dependencies():
    client = TestClient(server_app)

    response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_initializing_without_pipeline():
    previous_pipeline = getattr(server_app.state, "generation_pipeline", None)
    if hasattr(server_app.state, "generation_pipeline"):
        delattr(server_app.state, "generation_pipeline")

    try:
        client = TestClient(server_app)
        response = client.get("/ready")
    finally:
        if previous_pipeline is not None:
            server_app.state.generation_pipeline = previous_pipeline

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "initializing"
    assert body["services"]["pipeline"] == "down"


def test_readiness_reports_ready_when_dependencies_are_available(monkeypatch):
    class FakeClient:
        def get_collections(self):
            return []

    class FakeRepository:
        def __enter__(self):
            self.client = FakeClient()
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    class FakeLLM:
        def is_available(self):
            return True

    class FakePipeline:
        llm = FakeLLM()

    import retrieval.repository as repository_module

    monkeypatch.setattr(repository_module, "QdrantRepository", FakeRepository)
    previous_pipeline = getattr(server_app.state, "generation_pipeline", None)
    server_app.state.generation_pipeline = FakePipeline()

    try:
        client = TestClient(server_app)
        response = client.get("/ready")
    finally:
        if previous_pipeline is not None:
            server_app.state.generation_pipeline = previous_pipeline
        elif hasattr(server_app.state, "generation_pipeline"):
            delattr(server_app.state, "generation_pipeline")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["services"]["pipeline"] == "ok"
    assert body["services"]["qdrant"] == "ok"
    assert body["services"]["ollama"] == "ok"
