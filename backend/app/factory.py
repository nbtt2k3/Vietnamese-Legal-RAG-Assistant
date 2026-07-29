from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.middleware import SecurityMiddleware
from app.api.v1.router import v1_router
from app.api.v1.endpoints.health import router as health_router
from app.core.config import settings
from app.lifespan import lifespan


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vietnamese Legal RAG Assistant API",
        description="REST API cho he thong Vietnamese Legal Retrieval-Augmented Generation",
        version="1.0.0",
        lifespan=lifespan,
    )

    Instrumentator().instrument(app).expose(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityMiddleware)

    app.include_router(v1_router)
    app.include_router(health_router)
    return app
