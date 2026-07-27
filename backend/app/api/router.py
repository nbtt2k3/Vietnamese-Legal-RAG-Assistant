from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.logger import logger
from app.database import get_db
from app.models import Conversation, ChatMessage, User
from app.auth import get_current_user

api_router = APIRouter()

class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12_000)
    retrieval_only: bool = False
    conversation_id: str | None = None


class Message(BaseModel):
    role: str
    content: str

@api_router.get("/api/v1/conversations")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conversations = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.created_at.desc()).all()
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in conversations]

@api_router.post("/api/v1/conversations")
def create_conversation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = Conversation(user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}

@api_router.delete("/api/v1/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"status": "success"}

@api_router.get("/api/v1/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    import json
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at).all()
    results = []
    for m in messages:
        msg_dict = {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        if m.role == "ai" and m.msg_metadata:
            try:
                msg_dict["data"] = {"answer": json.loads(m.msg_metadata)}
            except:
                pass
        results.append(msg_dict)
    return results

@api_router.post("/api/v1/chat")
async def chat_endpoint(request: QueryRequest, req: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    req_id = getattr(req.state, "request_id", "unknown")
    logger.info(f"[Req={req_id}] Received API query (length={len(request.query)})")
    
    # 4. Prompt Injection & Input Boundary Check
    dangerous_patterns = [
        r"bỏ\s*qua\s*các\s*lệnh", r"ignore\s*previous\s*instructions",
        r"hãy\s*đóng\s*vai", r"act\s*as\s*", r"system\s*prompt",
        r"tiết\s*lộ\s*hướng\s*dẫn", r"quên\s*tất\s*cả"
    ]
    import re
    query_lower = request.query.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, query_lower):
            logger.warning(f"[Req={req_id}] Prompt Injection Detected! Pattern: {pattern}")
            return JSONResponse(
                status_code=400, 
                content={"error": "Invalid request content", "code": "ERR_SECURITY_VIOLATION"}
            )
            
    try:
        pipeline = req.app.state.generation_pipeline
        
        history = []
        if request.conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == request.conversation_id, Conversation.user_id == current_user.id).first()
            if not conv:
                return JSONResponse(status_code=404, content={"error": "Conversation not found"})
                
            db_msgs = db.query(ChatMessage).filter(ChatMessage.conversation_id == request.conversation_id).order_by(ChatMessage.created_at).all()
            class SimpleMsg:
                def __init__(self, role, content):
                    self.role = role
                    self.content = content
            history = [SimpleMsg(m.role, m.content) for m in db_msgs]
            
            # Save new user message
            user_msg = ChatMessage(conversation_id=request.conversation_id, role="user", content=request.query)
            db.add(user_msg)
            db.commit()

        if request.retrieval_only:
            result = pipeline.retrieval.run(request.query, history=history)
            return result.to_dict()
            
        answer, retrieval_result = pipeline.run(request.query, history=history)
        if answer is None:
            # Safe error taxonomy
            logger.error(f"[Req={req_id}] Generator returned None.")
            return JSONResponse(
                status_code=503, 
                content={"error": "LLM Service Unavailable or Timeout", "code": "ERR_LLM_TIMEOUT"}
            )
            
        if request.conversation_id:
            import json
            ai_msg = ChatMessage(
                conversation_id=request.conversation_id, 
                role="ai", 
                content=answer.short_answer,
                msg_metadata=json.dumps(answer.to_dict())
            )
            db.add(ai_msg)
            db.commit()
            
        return {
            "answer": answer.to_dict(),
            "retrieval": retrieval_result.to_dict(),
        }
    except Exception as e:
        logger.exception(f"[Req={req_id}] Error during RAG pipeline execution")
        # Do not leak raw exception trace
        return JSONResponse(
            status_code=500, 
            content={"error": "Internal Server Error during execution", "code": "ERR_PIPELINE"}
        )

@api_router.post("/api/v1/chat/stream")
async def chat_stream_endpoint(request: QueryRequest, req: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req_id = getattr(req.state, "request_id", "unknown")
    logger.info(f"[Req={req_id}] Received API query stream (length={len(request.query)})")
    
    # 4. Prompt Injection & Input Boundary Check
    dangerous_patterns = [
        r"bỏ\s*qua\s*các\s*lệnh", r"ignore\s*previous\s*instructions",
        r"hãy\s*đóng\s*vai", r"act\s*as\s*", r"system\s*prompt",
        r"tiết\s*lộ\s*hướng\s*dẫn", r"quên\s*tất\s*cả"
    ]
    import re
    query_lower = request.query.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, query_lower):
            logger.warning(f"[Req={req_id}] Prompt Injection Detected! Pattern: {pattern}")
            return JSONResponse(
                status_code=400, 
                content={"error": "Invalid request content", "code": "ERR_SECURITY_VIOLATION"}
            )
            
    try:
        pipeline = req.app.state.generation_pipeline
        
        history = []
        if request.conversation_id:
            conv = db.query(Conversation).filter(Conversation.id == request.conversation_id, Conversation.user_id == current_user.id).first()
            if not conv:
                return JSONResponse(status_code=404, content={"error": "Conversation not found"})
                
            db_msgs = db.query(ChatMessage).filter(ChatMessage.conversation_id == request.conversation_id).order_by(ChatMessage.created_at).all()
            # We must use a generic object that has role/content
            class SimpleMsg:
                def __init__(self, role, content):
                    self.role = role
                    self.content = content
            history = [SimpleMsg(m.role, m.content) for m in db_msgs]
            
            user_msg = ChatMessage(conversation_id=request.conversation_id, role="user", content=request.query)
            db.add(user_msg)
            db.commit()
            
        if request.retrieval_only:
            result = pipeline.retrieval.run(request.query, history=history)
            return result.to_dict()
            
        async def stream_wrapper():
            import json
            async for chunk in pipeline.run_stream(request.query, history=history):
                yield chunk
                if request.conversation_id and chunk.startswith("data: ") and '"type": "answer"' in chunk:
                    try:
                        data = json.loads(chunk[6:])
                        if "data" in data and "short_answer" in data["data"]:
                            ai_msg = ChatMessage(
                                conversation_id=request.conversation_id, 
                                role="ai", 
                                content=data["data"]["short_answer"],
                                msg_metadata=json.dumps(data["data"])
                            )
                            db.add(ai_msg)
                            db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save AI message: {e}")

        return StreamingResponse(stream_wrapper(), media_type="text/event-stream")
    except Exception as e:
        logger.exception(f"[Req={req_id}] Error during RAG pipeline execution")
        return JSONResponse(
            status_code=500, 
            content={"error": "Internal Server Error during execution", "code": "ERR_PIPELINE"}
        )

class FeedbackRequest(BaseModel):
    message_id: str | int = Field(..., description="ID của tin nhắn")
    query: str = Field(..., description="Câu hỏi của user")
    rating: int = Field(..., description="1 cho thumbs up, -1 cho thumbs down, 0 cho neutral")
    comment: str | None = Field(None, description="Nhận xét chi tiết")

@api_router.post("/api/v1/feedback")
async def feedback_endpoint(request: FeedbackRequest, req: Request) -> Dict[str, Any]:
    req_id = getattr(req.state, "request_id", "unknown")
    
    # Ở Phase này, ghi log ra file để thu thập dataset (vì chưa có DB schema riêng cho Feedback)
    log_msg = f"[FEEDBACK] Req={req_id} | MsgID={request.message_id} | Rating={request.rating} | Query='{request.query}' | Comment='{request.comment or ''}'"
    logger.info(log_msg)
    
    return {"status": "success", "message": "Cảm ơn bạn đã đóng góp ý kiến!"}
