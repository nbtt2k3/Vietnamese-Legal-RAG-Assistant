from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import SecurityMiddleware
from app.core.config import settings


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.post("/api/v1/ping")
    def ping():
        return {"ok": True}

    return app


def test_redis_lua_script_is_registered_once(monkeypatch):
    import redis.asyncio as redis

    class FakeScript:
        def __init__(self):
            self.calls = 0

        async def __call__(self, **kwargs):
            self.calls += 1
            return 1

    class FakePool:
        def __init__(self):
            self.register_calls = 0
            self.script = FakeScript()

        def register_script(self, source):
            self.register_calls += 1
            assert "redis.call(\"hget\", key, \"tokens\")" in source
            return self.script

    pool = FakePool()
    monkeypatch.setattr(redis, "from_url", lambda *args, **kwargs: pool)

    with TestClient(_build_app()) as client:
        headers = {"x-api-key": settings.api_key}
        assert client.post("/api/v1/ping", headers=headers).status_code == 200
        assert client.post("/api/v1/ping", headers=headers).status_code == 200

    assert pool.register_calls == 1
    assert pool.script.calls == 2


def test_redis_failure_keeps_in_memory_fallback(monkeypatch):
    import redis.asyncio as redis

    def raise_offline(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(redis, "from_url", raise_offline)

    with TestClient(_build_app()) as client:
        headers = {"x-api-key": settings.api_key}
        first = client.post("/api/v1/ping", headers=headers)
        second = client.post("/api/v1/ping", headers=headers)

    assert first.status_code == 200
    assert second.status_code in (200, 429)
