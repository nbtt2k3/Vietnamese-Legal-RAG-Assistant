import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware import SecurityMiddleware
from app.api.v1.router import api_router
from app.server import app as server_app
from app.core.config import settings
from app.services.security_policy import sanitize_log_value as _sanitize_log_value


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


def test_cors_preflight_is_not_blocked_by_api_key_auth(monkeypatch):
    _disable_redis(monkeypatch)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "api_key", "expected-secret")

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware)

    @app.post("/api/v1/ping")
    def api_ping():
        return {"ok": True}

    response = TestClient(app).options(
        "/api/v1/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


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


def test_database_initialization_imports_models(monkeypatch):
    from app.db import init as db_init

    class FakeDBSettings:
        db_url = "postgresql://unit-test"

    monkeypatch.setattr(db_init.Base.metadata, "create_all", lambda bind: None)
    monkeypatch.setattr(db_init, "db_settings", FakeDBSettings())

    db_init.initialize_database()


def test_readiness_reports_ready_when_dependencies_are_available(monkeypatch):
    from types import SimpleNamespace

    class FakeClient:
        def get_collection(self, collection_name):
            return SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(vectors=SimpleNamespace(size=1024))
                )
            )

        def count(self, collection_name, exact):
            return SimpleNamespace(count=10)

        def scroll(self, collection_name, limit, with_payload, with_vectors):
            return [SimpleNamespace(payload={"chunk_id": "c1", "text": "Điều 1"})], None

    class FakeRepository:
        collection_name = "legal_docs"

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

    import rag.retrieval.repository as repository_module

    monkeypatch.setattr(repository_module, "QdrantRepository", FakeRepository)
    import app.services.health_service as health_service

    monkeypatch.setattr(health_service, "_check_database", lambda: None)
    monkeypatch.setattr(health_service, "_check_redis", lambda: None)
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


def test_health_is_degraded_when_database_or_redis_is_down(monkeypatch):
    from types import SimpleNamespace

    class FakeClient:
        def get_collection(self, collection_name):
            return SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(vectors=SimpleNamespace(size=1024))
                )
            )

        def count(self, collection_name, exact):
            return SimpleNamespace(count=10)

        def scroll(self, collection_name, limit, with_payload, with_vectors):
            return [SimpleNamespace(payload={"chunk_id": "c1", "text": "Điều 1"})], None

    class FakeRepository:
        collection_name = "legal_docs"

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

    import rag.retrieval.repository as repository_module
    import app.services.health_service as health_service

    monkeypatch.setattr(repository_module, "QdrantRepository", FakeRepository)
    monkeypatch.setattr(health_service, "_check_database", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(health_service, "_check_redis", lambda: (_ for _ in ()).throw(RuntimeError("redis down")))

    previous_pipeline = getattr(server_app.state, "generation_pipeline", None)
    server_app.state.generation_pipeline = FakePipeline()
    try:
        response = TestClient(server_app).get("/ready")
    finally:
        if previous_pipeline is not None:
            server_app.state.generation_pipeline = previous_pipeline
        elif hasattr(server_app.state, "generation_pipeline"):
            delattr(server_app.state, "generation_pipeline")

    assert response.status_code == 503
    body = response.json()
    assert body["services"]["qdrant"] == "ok"
    assert body["services"]["postgres"] == "down"
    assert body["services"]["redis"] == "down"


def test_readiness_is_degraded_when_qdrant_collection_is_empty(monkeypatch):
    from types import SimpleNamespace

    class FakeClient:
        def get_collection(self, collection_name):
            return SimpleNamespace(
                config=SimpleNamespace(
                    params=SimpleNamespace(vectors=SimpleNamespace(size=1024))
                )
            )

        def count(self, collection_name, exact):
            return SimpleNamespace(count=0)

    class FakeRepository:
        collection_name = "legal_docs"

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

    import rag.retrieval.repository as repository_module

    monkeypatch.setattr(repository_module, "QdrantRepository", FakeRepository)
    previous_pipeline = getattr(server_app.state, "generation_pipeline", None)
    server_app.state.generation_pipeline = FakePipeline()

    try:
        response = TestClient(server_app).get("/ready")
    finally:
        if previous_pipeline is not None:
            server_app.state.generation_pipeline = previous_pipeline
        elif hasattr(server_app.state, "generation_pipeline"):
            delattr(server_app.state, "generation_pipeline")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["qdrant"] == "down"


def test_health_is_degraded_without_pipeline():
    previous_pipeline = getattr(server_app.state, "generation_pipeline", None)
    if hasattr(server_app.state, "generation_pipeline"):
        delattr(server_app.state, "generation_pipeline")

    try:
        response = TestClient(server_app).get("/health")
    finally:
        if previous_pipeline is not None:
            server_app.state.generation_pipeline = previous_pipeline

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
