from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger


def _check_qdrant() -> None:
    """Validate that Qdrant is readable, not merely reachable."""
    from rag.retrieval.repository import QdrantRepository

    with QdrantRepository() as repo:
        collection_name = repo.collection_name
        collection_info = repo.client.get_collection(collection_name=collection_name)
        point_count = repo.client.count(
            collection_name=collection_name,
            exact=True,
        ).count
        if point_count <= 0:
            raise RuntimeError(f"Qdrant collection/alias '{collection_name}' is empty")

        vector_config = collection_info.config.params.vectors
        vector_size = getattr(vector_config, "size", None)
        if vector_size is not None and int(vector_size) != 1024:
            raise RuntimeError(
                f"Qdrant collection '{collection_name}' has vector size "
                f"{vector_size}; expected 1024"
            )

        # Count and collection metadata can succeed while payload reads fail
        # because of a broken alias, permissions, or corrupted storage. Read a
        # real point and require the fields needed by retrieval/generation.
        points, _ = repo.client.scroll(
            collection_name=collection_name,
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            raise RuntimeError(f"Qdrant collection '{collection_name}' returned no payload point")
        payload = points[0].payload or {}
        if not isinstance(payload, dict) or not payload.get("text"):
            raise RuntimeError("Qdrant payload read succeeded but contains no usable text")


def _check_database() -> None:
    """Execute a minimal SQL query through the application's real DB engine."""
    from app.db.session import engine

    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise RuntimeError("Database returned an unexpected result")


def _check_redis() -> None:
    """Check Redis directly; rate-limit fallback must not mask a dead Redis."""
    import redis

    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    try:
        if not client.ping():
            raise RuntimeError("Redis PING returned false")
    finally:
        client.close()


def _record_dependency(status: dict, name: str, check) -> None:
    try:
        check()
        status["services"][name] = "ok"
    except Exception as exc:
        logger.warning("Health check failed for %s: %s", name, exc)
        status["services"][name] = "down"
        status["status"] = "degraded"


def check_pipeline_dependencies(pipeline) -> dict:
    status = {
        "status": "degraded",
        "services": {
            "qdrant": "unknown",
            "postgres": "unknown",
            "redis": "unknown",
            "ollama": "unknown",
            "pipeline": "ok" if pipeline else "down",
        },
    }

    if not pipeline:
        return status

    _record_dependency(status, "qdrant", _check_qdrant)
    _record_dependency(status, "postgres", _check_database)
    _record_dependency(status, "redis", _check_redis)

    try:
        is_available = bool(
            pipeline.llm
            and hasattr(pipeline.llm, "is_available")
            and pipeline.llm.is_available()
        )
        status["services"]["ollama"] = "ok" if is_available else "down"
        if not is_available:
            status["status"] = "degraded"
    except Exception as exc:
        logger.warning("Health check failed for ollama: %s", exc)
        status["services"]["ollama"] = "down"
        status["status"] = "degraded"

    required = ("qdrant", "postgres", "redis", "ollama", "pipeline")
    if all(status["services"].get(name) == "ok" for name in required):
        status["status"] = "ok"

    return status
