from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.db.models import User
from app.services.conversation_service import (
    create_user_conversation,
    delete_user_conversation,
    list_conversation_messages,
    list_user_conversations,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_user_conversations(db, current_user)


@router.post("")
def create_conversation(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_user_conversation(db, current_user)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_user_conversation(db, current_user, conversation_id)


@router.get("/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_conversation_messages(db, current_user, conversation_id)
