from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from typing import Dict, List, Set, Tuple
import logging
import asyncpg
import json

from app.db.database import get_connection
from app.users.routers import get_current_user
from app.users.models import User
from app.users import service as user_service
from app.packages.chat.schemas import (
    CreateChatRequest, ChatOut, SendMessageRequest, MessageOut,
    StandardMessageResponse, StandardMessagesResponse,
    StandardChatResponse, StandardChatsResponse, StandardMemberResponse,
    InitiateTransferRequest, HandleTransferRequest
)
from app.packages.chat import service as chat_service
from app.core.security import verify_token

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)

# Store active WebSocket connections: {chat_id: {(websocket, user_id), ...}}
active_connections: Dict[int, Set[Tuple[WebSocket, int]]] = {}


async def broadcast_to_chat(chat_id: int, message_data: dict):
    """
    Broadcast a message to all connected users in a chat.
    """
    if chat_id in active_connections:
        disconnected = set()
        for ws, _ in active_connections[chat_id]:
            try:
                await ws.send_json(message_data)
            except:
                disconnected.add((ws, _))
        
        # Clean up disconnected clients
        active_connections[chat_id] -= disconnected
        if not active_connections[chat_id]:
            del active_connections[chat_id]


@router.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: int,
    token: str = Query(...)
):
    """
    Authenticated WebSocket endpoint for real-time chat.
    """
    # Get database connection for authentication
    from app.db.database import get_pool
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
                "message_type": message_record.get("message_type", "text"),
                "transaction_id": message_record.get("transaction_id"),
                "created_at": message_record["created_at"].isoformat()
            }
            
            await broadcast_to_chat(chat_id, message_data)
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


@router.post("/transfer/initiate", response_model=StandardMessageResponse)
async def initiate_transfer(
    request: InitiateTransferRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Initiate a money transfer within a chat.
    """
    try:
        message = await chat_service.initiate_transfer_in_chat(
            conn=conn,
            chat_id=request.chat_id,
            sender_id=current_user.id,
            amount=request.amount,
            narration=request.narration
        )
        
        # Broadcast via WebSocket
        message_data = {
            "type": "transfer_initiated",
            "id": message["id"],
            "chat_id": request.chat_id,
            "sender_id": current_user.id,
            "sender_username": current_user.username,
            "content": message["content"],
            "message_type": "transfer",
            "transaction_id": message["transaction_id"],
            "transaction_status": message["transaction_status"],
            "created_at": message["created_at"].isoformat()
        }
        await broadcast_to_chat(request.chat_id, message_data)
        
        # Format response
        message["sender_username"] = current_user.username
        return {
            "status": "success",
            "message": "Transfer initiated successfully",
            "data": message
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )


@router.post("/transfer/handle", response_model=StandardMessageResponse)
async def handle_transfer(
    request: HandleTransferRequest,
    current_user: User = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_connection)
):
    """
    Accept or reject a money transfer.
    """
    try:
        result = await chat_service.handle_transfer_action(
            conn=conn,
            message_id=request.message_id,
            user_id=current_user.id,
            action=request.action
        )
        
        # Broadcast the update
        update_data = {
            "type": "transfer_updated",
            "message_id": request.message_id,
            "chat_id": result["chat_id"],
            "transaction_id": result["transaction_id"],
            "status": result["status"]
        }
        await broadcast_to_chat(result["chat_id"], update_data)
        
        return {
            "status": "success",
            "message": f"Transfer {request.action}ed successfully",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": str(e), "data": None}
        )


@router.post("/send_message", response_model=StandardMessageResponse)
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
    
    return {
        "status": "success",
        "message": "Message sent successfully",
        "data": result
    }


@router.get("/messages/{chat_id}", response_model=StandardMessagesResponse)
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
            detail={"status": "error", "message": "You don't have access to this chat", "data": None}
        )
    
    messages = await chat_service.get_chat_messages(
        conn=conn,
        chat_id=chat_id,
        limit=limit,
        offset=offset
    )
    
    return {
        "status": "success",
        "message": "Messages retrieved successfully",
        "data": {"chat_id": chat_id, "messages": messages}
    }


@router.post("/start_direct_chat", response_model=StandardChatResponse)
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
            detail={"status": "error", "message": "Cannot create chat with yourself", "data": None}
        )
    
    # Verify other user exists
    other_user = await user_service.get_user_by_id(conn, other_user_id)
    if not other_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "message": "User not found", "data": None}
        )
    
    chat = await chat_service.create_or_get_direct_chat(
        conn, current_user.id, other_user_id
    )
    
    return {
        "status": "success",
        "message": "Direct chat created/retrieved successfully",
        "data": chat
    }


@router.get("/my_chats", response_model=StandardChatsResponse)
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
    
    return {
        "status": "success",
        "message": "Chats retrieved successfully",
        "data": {"chats": chats}
    }


@router.post("/create_room", response_model=StandardChatResponse)
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
    
    return {
        "status": "success",
        "message": "Chat room created successfully",
        "data": result
    }


@router.post("/add_member", response_model=StandardMemberResponse)
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
            detail={"status": "error", "message": "Chat not found", "data": None}
        )
    
    if chat["creator_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "message": "Only the chat creator can add members", "data": None}
        )
    
    if chat["chat_type"] != "group":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "Cannot add members to direct chats", "data": None}
        )
    
    success = await chat_service.add_chat_member(conn, chat_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "error", "message": "User is already a member", "data": None}
        )
    
    return {
        "status": "success",
        "message": "Member added successfully",
        "data": {"chat_id": chat_id, "user_id": user_id}
    }
