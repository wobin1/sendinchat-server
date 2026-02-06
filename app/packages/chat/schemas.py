from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CreateChatRequest(BaseModel):
    """Request model for creating a new chat"""
    name: Optional[str] = None  # Optional for direct chats
    chat_type: str = "group"    # "direct" or "group"

class MessageOut(BaseModel):
    """Response model for chat messages"""
    id: int
    chat_id: int
    sender_id: int
    sender_username: str
    content: str
    created_at: datetime

class SendMessageRequest(BaseModel):
    """Request model for sending a message"""
    content: str

class ChatOut(BaseModel):
    """Response model for chat details"""
    id: int
    name: Optional[str]
    chat_type: str
    creator_id: Optional[int]
    created_at: datetime
    members: List[int]  # List of user IDs
