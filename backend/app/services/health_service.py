from app.core.logging import logger


def check_pipeline_dependencies(pipeline) -> dict:
    status = {
        "status": "ok",
        "services": {
            "qdrant": "unknown",
            "ollama": "unknown",
        },
    }

    if not pipeline:
        return status

    try:
        from rag.retrieval.repository import QdrantRepository

        with QdrantRepository() as repo:
            repo.client.get_collections()
        status["services"]["qdrant"] = "ok"
    except Exception as exc:
        logger.warning("Health check failed for qdrant: %s", exc)
        status["services"]["qdrant"] = "down"
        status["status"] = "degraded"

    try:
        is_available = False
        if pipeline.llm and hasattr(pipeline.llm, "is_available"):
            is_available = pipeline.llm.is_available()
        status["services"]["ollama"] = "ok" if is_available else "down"
        if not is_available:
            status["status"] = "degraded"
    except Exception as exc:
        logger.warning("Health check failed for ollama: %s", exc)
        status["services"]["ollama"] = "down"
        status["status"] = "degraded"

    return status
