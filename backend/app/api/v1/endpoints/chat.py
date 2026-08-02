from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.schemas.chat import QueryRequest
from app.api.deps import get_current_user
from app.db.session import get_db
from app.core.logging import logger
from app.db.models import User
from app.services.chat_service import run_chat, stream_chat, validate_query_content

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _error_response(exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@router.post("/chat")
def chat_endpoint(
    request: QueryRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req_id = getattr(req.state, "request_id", "unknown")
    try:
        return run_chat(request, req.app.state.generation_pipeline, db, current_user, req_id)
    except HTTPException as exc:
        return _error_response(exc)
    except Exception:
        logger.exception("[Req=%s] Error during RAG pipeline execution", req_id)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error during execution", "code": "ERR_PIPELINE"},
        )


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: QueryRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    req_id = getattr(req.state, "request_id", "unknown")
    try:
        validate_query_content(request.query, req_id)
        stream = stream_chat(request, req.app.state.generation_pipeline, db, current_user, req_id)
        return StreamingResponse(stream, media_type="text/event-stream")
    except HTTPException as exc:
        return _error_response(exc)
    except Exception:
        logger.exception("[Req=%s] Error during RAG pipeline execution", req_id)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error during execution", "code": "ERR_PIPELINE"},
        )
