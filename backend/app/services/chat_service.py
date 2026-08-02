import json

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import User
from app.services.conversation_service import load_history_and_save_user_message, save_ai_message
from app.services.security_policy import detect_prompt_injection


def validate_query_content(query: str, request_id: str) -> None:
    pattern = detect_prompt_injection(query)
    if pattern:
        logger.warning("[Req=%s] Prompt Injection Detected! Pattern: %s", request_id, pattern)
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid request content", "code": "ERR_SECURITY_VIOLATION"},
        )


def run_chat(request, pipeline, db: Session, current_user: User, request_id: str) -> dict:
    logger.info("[Req=%s] Received API query (length=%s)", request_id, len(request.query))
    validate_query_content(request.query, request_id)

    history = load_history_and_save_user_message(
        db,
        current_user,
        request.conversation_id,
        request.query,
    )

    if request.retrieval_only:
        result = pipeline.retrieval.run(request.query, history=history)
        return result.to_dict()

    answer, retrieval_result = pipeline.run(request.query, history=history)
    if answer is None:
        logger.error("[Req=%s] Generator returned None.", request_id)
        raise HTTPException(
            status_code=503,
            detail={"error": "LLM Service Unavailable or Timeout", "code": "ERR_LLM_TIMEOUT"},
        )

    if request.conversation_id:
        save_ai_message(db, request.conversation_id, answer.to_dict())

    return {
        "answer": answer.to_dict(),
        "retrieval": retrieval_result.to_dict(),
    }


async def stream_chat(request, pipeline, db: Session, current_user: User, request_id: str):
    logger.info("[Req=%s] Received API query stream (length=%s)", request_id, len(request.query))
    # Keep the service safe even when called outside the HTTP endpoint. The
    # endpoint also validates for defense in depth, but this check must happen
    # before history persistence, retrieval, or generation.
    validate_query_content(request.query, request_id)

    history = load_history_and_save_user_message(
        db,
        current_user,
        request.conversation_id,
        request.query,
    )

    if request.retrieval_only:
        result = pipeline.retrieval.run(request.query, history=history)
        yield json.dumps(jsonable_encoder(result.to_dict()))
        return

    ai_answer_data: dict | None = None

    async for chunk in pipeline.run_stream(request.query, history=history):
        yield chunk
        if request.conversation_id and '"type": "answer"' in chunk:
            try:
                data = json.loads(chunk[6:])
                if "data" in data:
                    ai_answer_data = data["data"]
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                logger.error("Failed to capture AI answer data: %s", exc)

    try:
        save_ai_message(db, request.conversation_id, ai_answer_data)
    except Exception as exc:
        logger.error("Failed to save AI message after stream: %s", exc)
