from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict
from sqlalchemy.orm import Session
from app.logger import logger
from app.database import get_db
from app.models import Conversation, ChatMessage, User
from app.auth import get_current_user
import re
import json

api_router = APIRouter()

# BUG-15 FIX: Precompile security patterns ở module level, tránh compile lại mỗi request.
_INJECTION_PATTERNS = [
    re.compile(r"bỏ\s*qua\s*các\s*lệnh"),
    re.compile(r"ignore\s*previous\s*instructions"),
    re.compile(r"hãy\s*đóng\s*vai"),
    re.compile(r"act\s*as\s*"),
    re.compile(r"system\s*prompt"),
    re.compile(r"tiết\s*lộ\s*hướng\s*dẫn"),
    re.compile(r"quên\s*tất\s*cả"),
]

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
        
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at).all()
    results = []
    for m in messages:
        msg_dict = {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        if m.role == "ai" and m.msg_metadata:
            try:
                # BUG-10 FIX: Dùng exception type cụ thể thay vì bare except:
                # bare except bắt cả SystemExit, KeyboardInterrupt, MemoryError.
                msg_dict["data"] = {"answer": json.loads(m.msg_metadata)}
            except (json.JSONDecodeError, ValueError):
                pass
        results.append(msg_dict)
    return results

@api_router.post("/api/v1/chat")
async def chat_endpoint(request: QueryRequest, req: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    req_id = getattr(req.state, "request_id", "unknown")
    logger.info(f"[Req={req_id}] Received API query (length={len(request.query)})")
    
    query_lower = request.query.lower()
    # BUG-15 FIX: Dùng precompiled module-level patterns thay vì tạo list + import re mỗi request
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query_lower):
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
    
    # BUG-15 FIX: Dùng precompiled module-level patterns (giống chat endpoint)
    query_lower = request.query.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query_lower):
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
            
        # BUG-09 FIX: Không dùng db session bên trong async generator vì FastAPI DI
        # có thể release session trước khi stream hoàn tất.
        # Giải pháp: Lưu AI message VÀO NGOÀI generator sau khi stream kết thúc.
        ai_answer_data: dict | None = None

        async def stream_wrapper():
            nonlocal ai_answer_data
            async for chunk in pipeline.run_stream(request.query, history=history):
                yield chunk
                # Chỉ capture data, KHÔNG ghi DB bên trong generator
                if request.conversation_id and '"type": "answer"' in chunk:
                    try:
                        data = json.loads(chunk[6:])
                        if "data" in data:
                            ai_answer_data = data["data"]
                    except (json.JSONDecodeError, ValueError, KeyError) as e:
                        logger.error(f"Failed to capture AI answer data: {e}")

        async def persist_and_stream():
            """Wrap stream_wrapper để sau khi stream xong thì lưu DB."""
            async for chunk in stream_wrapper():
                yield chunk
            # Stream đã xong → ghi DB ở đây (session vẫn còn valid)
            if request.conversation_id and ai_answer_data is not None:
                try:
                    ai_msg = ChatMessage(
                        conversation_id=request.conversation_id,
                        role="ai",
                        content=ai_answer_data.get("short_answer", ""),
                        msg_metadata=json.dumps(ai_answer_data)
                    )
                    db.add(ai_msg)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to save AI message after stream: {e}")

        return StreamingResponse(persist_and_stream(), media_type="text/event-stream")
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
