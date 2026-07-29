from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.conversations import router as conversations_router
from app.api.v1.endpoints.feedback import router as feedback_router

api_router = APIRouter()
api_router.include_router(conversations_router)
api_router.include_router(chat_router)
api_router.include_router(feedback_router)

v1_router = APIRouter()
v1_router.include_router(auth_router)
v1_router.include_router(api_router)
