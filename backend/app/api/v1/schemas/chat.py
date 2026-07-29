from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12_000)
    retrieval_only: bool = False
    conversation_id: str | None = None


class Message(BaseModel):
    role: str
    content: str


class FeedbackRequest(BaseModel):
    message_id: str | int = Field(..., description="ID cua tin nhan")
    query: str = Field(..., min_length=1, max_length=12_000, description="Cau hoi cua user")
    rating: int = Field(..., ge=-1, le=1, description="1 thumbs up, -1 thumbs down, 0 neutral")
    comment: str | None = Field(None, max_length=2_000, description="Nhan xet chi tiet")
