import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories import conversation_repository


class ChatHistoryMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


def serialize_conversation(conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
    }


def list_user_conversations(db: Session, user: User) -> list[dict]:
    return [
        serialize_conversation(conversation)
        for conversation in conversation_repository.list_conversations(db, user.id)
    ]


def create_user_conversation(db: Session, user: User) -> dict:
    conversation = conversation_repository.create_conversation(db, user.id)
    return serialize_conversation(conversation)


def delete_user_conversation(db: Session, user: User, conversation_id: str) -> dict:
    conversation = conversation_repository.get_conversation_for_user(db, conversation_id, user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation_repository.delete_conversation(db, conversation)
    return {"status": "success"}


def list_conversation_messages(db: Session, user: User, conversation_id: str) -> list[dict]:
    conversation = conversation_repository.get_conversation_for_user(db, conversation_id, user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    results = []
    for message in conversation_repository.list_messages(db, conversation_id):
        payload = {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        if message.role == "ai" and message.msg_metadata:
            try:
                payload["data"] = {"answer": json.loads(message.msg_metadata)}
            except (json.JSONDecodeError, ValueError):
                pass
        results.append(payload)
    return results


def load_history_and_save_user_message(
    db: Session,
    user: User,
    conversation_id: str | None,
    query: str,
) -> list[ChatHistoryMessage]:
    if not conversation_id:
        return []

    conversation = conversation_repository.get_conversation_for_user(db, conversation_id, user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversation_repository.list_messages(db, conversation_id)
    history = [ChatHistoryMessage(message.role, message.content) for message in messages]
    conversation_repository.add_message(db, conversation_id, role="user", content=query)
    return history


def save_ai_message(db: Session, conversation_id: str | None, answer_data: dict | None) -> None:
    if not conversation_id or answer_data is None:
        return
    conversation_repository.add_message(
        db,
        conversation_id,
        role="ai",
        content=answer_data.get("short_answer", ""),
        msg_metadata=json.dumps(answer_data),
    )
