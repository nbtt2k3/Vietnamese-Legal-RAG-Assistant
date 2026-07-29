from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import logger
from rag.generation.pipeline import GenerationPipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Vietnamese Legal RAG Assistant API Server...")
    from app.db.init import initialize_database

    initialize_database()
    logger.info("Initializing Generation Pipeline (Loading Models into RAM)...")
    app.state.generation_pipeline = GenerationPipeline()
    logger.info("Pipeline ready!")
    yield
    logger.info("Shutting down API Server...")
