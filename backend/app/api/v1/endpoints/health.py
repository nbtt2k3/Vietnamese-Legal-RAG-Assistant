from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.health_service import check_pipeline_dependencies

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(request: Request):
    pipeline = getattr(request.app.state, "generation_pipeline", None)
    status = check_pipeline_dependencies(pipeline)
    return JSONResponse(
        status_code=200 if status["status"] == "ok" else 503,
        content=status,
    )


@router.get("/live")
def liveness_check():
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(request: Request):
    pipeline = getattr(request.app.state, "generation_pipeline", None)
    if not pipeline:
        return JSONResponse(
            status_code=503,
            content={
                "status": "initializing",
                "services": {
                    "pipeline": "down",
                    "qdrant": "unknown",
                    "postgres": "unknown",
                    "redis": "unknown",
                    "ollama": "unknown",
                },
            },
        )

    status = check_pipeline_dependencies(pipeline)
    ready = status["status"] == "ok"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "services": status["services"]},
    )
