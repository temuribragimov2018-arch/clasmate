from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: Optional[str] = None
    reply_to_id: Optional[int] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None


class MessageUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class ReactionCreate(BaseModel):
    emoji: str = Field(..., max_length=20)


class MessageOut(BaseModel):
    id: int
    chat_id: int
    sender_id: Optional[int] = None
    content: Optional[str] = None
    reply_to_id: Optional[int] = None
    is_edited: bool = False
    is_deleted: bool = False
    is_pinned: bool = False
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sender: Optional[dict] = None
    reactions: List[dict] = []

    class Config:
        from_attributes = True


class ChatOut(BaseModel):
    id: int
    name: Optional[str]
    chat_type: str
    class_id: Optional[int]
    created_at: datetime
    unread_count: int = 0
    last_message: Optional[MessageOut] = None

    class Config:
        from_attributes = True


class ChatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    member_ids: List[int] = []
