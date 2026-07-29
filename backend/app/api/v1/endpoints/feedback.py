from typing import Any

from fastapi import APIRouter, Request

from app.api.v1.schemas.chat import FeedbackRequest
from app.services.feedback_service import record_feedback

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/feedback")
async def feedback_endpoint(request: FeedbackRequest, req: Request) -> dict[str, Any]:
    req_id = getattr(req.state, "request_id", "unknown")
    return record_feedback(
        message_id=request.message_id,
        query=request.query,
        rating=request.rating,
        comment=request.comment,
        request_id=req_id,
    )
