from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.auth_router import auth_router
from app.api.middleware import SecurityMiddleware
from app.config import settings
from app.logger import logger
from generation.pipeline import GenerationPipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Vietnamese Legal RAG Assistant API Server...")
    from app.database import initialize_database
    initialize_database()
    logger.info("Initializing Generation Pipeline (Loading Models into RAM)...")
    app.state.generation_pipeline = GenerationPipeline()
    logger.info("Pipeline ready!")
    yield
    logger.info("Shutting down API Server...")

app = FastAPI(
    title="Vietnamese Legal RAG Assistant API",
    description="REST API cho hệ thống Vietnamese Legal Retrieval-Augmented Generation",
    version="1.0.0",
    lifespan=lifespan
)

# Prometheus Monitoring
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityMiddleware)
app.include_router(auth_router)
app.include_router(api_router)

@app.get("/health")
def health_check(request: Request):
    pipeline = getattr(request.app.state, "generation_pipeline", None)
    
    status = {
        "status": "ok",
        "services": {
            "qdrant": "unknown",
            "ollama": "unknown",
        }
    }
    
    if pipeline:
        try:
            # Check Qdrant availability
            from retrieval.repository import QdrantRepository
            with QdrantRepository() as repo:
                repo.client.get_collections()
            status["services"]["qdrant"] = "ok"
        except Exception as e:
            logger.warning("Health check failed for qdrant: %s", e)
            status["services"]["qdrant"] = "down"
            status["status"] = "degraded"
            
        try:
            # BUG-08 FIX: pipeline.generator không tồn tại; dùng pipeline.llm đúng.
            # Thêm is_avail = False mặc định để tránh UnboundLocalError nếu llm là None.
            is_avail = False
            if pipeline.llm and hasattr(pipeline.llm, "is_available"):
                is_avail = pipeline.llm.is_available()
            status["services"]["ollama"] = "ok" if is_avail else "down"
            if not is_avail:
                status["status"] = "degraded"
        except Exception as e:
            logger.warning("Health check failed for ollama: %s", e)
            status["services"]["ollama"] = "down"
            status["status"] = "degraded"
            
    return JSONResponse(
        status_code=200 if status["status"] == "ok" else 503,
        content=status
    )
