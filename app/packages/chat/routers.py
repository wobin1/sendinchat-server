from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from typing import Dict, List, Set, Tuple
import logging
import asyncpg
import json

from app.db.database import get_connection
from app.users.routers import get_current_user
from app.users.models import User
from app.users import service as user_service
from app.packages.chat.schemas import CreateChatRequest, ChatOut, SendMessageRequest, MessageOut
from app.packages.chat import service as chat_service
from app.core.security import verify_token

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)

# Store active WebSocket connections: {chat_id: {(websocket, user_id), ...}}
active_connections: Dict[int, Set[Tuple[WebSocket, int]]] = {}


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: int,
    token: str = Query(...)
):
    """
    Authenticated WebSocket endpoint for real-time chat.
    
    Authenticates user via JWT token passed as query parameter,
    validates chat access, and broadcasts messages to all connected users.
    """
    # Get database connection for authentication
    from db.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Authenticate user
        username = verify_token(token)
        if not username:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        user = await user_service.get_user_by_username(conn, username)
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        # Validate chat access
        has_access = await chat_service.validate_chat_access(conn, chat_id, user.id)
        if not has_access:
            await websocket.close(code=1008, reason="Access denied")
            return
    
    await websocket.accept()
    
    # Add connection to active connections
    if chat_id not in active_connections:
        active_connections[chat_id] = set()
    active_connections[chat_id].add((websocket, user.id))
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected",
            "chat_id": chat_id,
            "user_id": user.id,
            "username": user.username
        })
        
        logger.info(f"WebSocket connection established for user {user.username} in chat {chat_id}")
        
        # Listen for messages
        while True:
            data = await websocket.receive_json()
            
            # Get fresh connection for each message
            async with pool.acquire() as conn:
                # Persist message to database
                message_record = await chat_service.send_message(
                    conn=conn,
                    chat_id=chat_id,
                    sender_id=user.id,
                    message=data.get("content", "")
                )
            
            # Broadcast to all connected users in this chat
            message_data = {
                "type": "message",
                "id": message_record["id"],
                "chat_id": chat_id,
                "sender_id": user.id,
                "sender_username": user.username,
                "content": message_record["content"],
                "created_at": message_record["created_at"].isoformat()
            }
            
            # Send to all connections in this chat
            if chat_id in active_connections:
                disconnected = set()
                for ws, _ in active_connections[chat_id]:
                    try:
                        await ws.send_json(message_data)
                    except:
                        disconnected.add((ws, _))
                
                # Clean up disconnected clients
                active_connections[chat_id] -= disconnected
                
            logger.info(f"Message from {user.username} in chat {chat_id}: {data.get('content', '')}")
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for user {user.username} in chat {chat_id}: {str(e)}")
    finally:
        # Remove connection
        if chat_id in active_connections:
            active_connections[chat_id].discard((websocket, user.id))
            if not active_connections[chat_id]:
                del active_connections[chat_id]
        logger.info(f"WebSocket connection closed for user {user.username} in chat {chat_id}")


@router.post("/send_message")
async def send_message(
    chat_id: int,
    message: str,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Send a text message to a chat via REST API.
    
    This is a placeholder endpoint. In production, this would persist
    the message and notify connected WebSocket users.
    """
    # Use service layer to send message
    result = await chat_service.send_message(
        conn=conn,
        chat_id=chat_id,
        sender_id=current_user.id,
        message=message
    )
    
    # Add username to response
    result["sender_username"] = current_user.username
    
    return result


@router.get("/messages/{chat_id}")
async def get_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get messages from a chat room.
    
    This is a placeholder endpoint. In production, this would retrieve
    messages from the database.
    """
    # Validate user has access to this chat
    has_access = await chat_service.validate_chat_access(
        conn=conn,
        chat_id=chat_id,
        user_id=current_user.id
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this chat"
        )
    
    messages = await chat_service.get_chat_messages(
        conn=conn,
        chat_id=chat_id,
        limit=limit,
        offset=offset
    )
    
    return {"chat_id": chat_id, "messages": messages}


@router.post("/start_direct_chat")
async def start_direct_chat(
    other_user_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Start or get existing direct chat with another user.
    """
    if other_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create chat with yourself"
        )
    
    # Verify other user exists
    other_user = await user_service.get_user_by_id(conn, other_user_id)
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    chat = await chat_service.create_or_get_direct_chat(
        conn, current_user.id, other_user_id
    )
    
    return chat


@router.get("/my_chats")
async def get_my_chats(
    chat_type: str = Query(None, regex="^(direct|group)$"),
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Get all chats the current user is a member of, optionally filtered by type.
    """
    chats = await chat_service.get_user_chats(conn, current_user.id)
    
    # Filter by chat type if specified
    if chat_type:
        chats = [c for c in chats if c['chat_type'] == chat_type]
    
    return {"chats": chats}


@router.post("/create_room")
async def create_room(
    name: str = None,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Create a new group chat room.
    """
    result = await chat_service.create_chat_room(
        conn=conn,
        creator_id=current_user.id,
        name=name
    )
    
    return result


@router.post("/add_member")
async def add_member(
    chat_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Add a member to a group chat room (only creator can add).
    """
    # Verify current user is the creator
    chat = await conn.fetchrow(
        "SELECT creator_id, chat_type FROM chats WHERE id = $1", chat_id
    )
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    if chat["creator_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the chat creator can add members"
        )
    
    if chat["chat_type"] != "group":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add members to direct chats"
        )
    
    success = await chat_service.add_chat_member(conn, chat_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member"
        )
    
    return {"status": "success", "chat_id": chat_id, "user_id": user_id}
