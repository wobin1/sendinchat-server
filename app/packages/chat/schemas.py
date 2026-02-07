from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any

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


# ============= Standard API Response Wrappers =============
class StandardMessageResponse(BaseModel):
    """Standard response wrapper for message operations."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class StandardMessagesResponse(BaseModel):
    """Standard response wrapper for messages list operations."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class StandardChatResponse(BaseModel):
    """Standard response wrapper for chat operations."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class StandardChatsResponse(BaseModel):
    """Standard response wrapper for chats list operations."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


class StandardMemberResponse(BaseModel):
    """Standard response wrapper for member operations."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
