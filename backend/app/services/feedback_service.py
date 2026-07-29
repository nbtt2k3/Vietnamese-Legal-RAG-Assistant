from app.core.logging import logger
from app.services.security_policy import sanitize_log_value


def record_feedback(message_id: str | int, query: str, rating: int, comment: str | None, request_id: str) -> dict:
    log_msg = (
        f"[FEEDBACK] Req={request_id} "
        f"| MsgID={sanitize_log_value(message_id, max_length=80)} "
        f"| Rating={rating} "
        f"| Query='{sanitize_log_value(query)}' "
        f"| Comment='{sanitize_log_value(comment or '')}'"
    )
    logger.info(log_msg)
    return {"status": "success", "message": "Cam on ban da dong gop y kien!"}
