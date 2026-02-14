"""
Chat service layer - handles all chat-related business logic.
"""
import asyncpg
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


async def send_message(
    conn: asyncpg.Connection,
    chat_id: int,
    sender_id: int,
    message: str,
    message_type: str = "text",
    transaction_id: Optional[str] = None
) -> dict:
    """
    Send a message to a chat.
    """
    logger.info(f"User {sender_id} sending {message_type} message to chat {chat_id}")
    
    # Validate user has access to chat
    has_access = await validate_chat_access(conn, chat_id, sender_id)
    if not has_access:
        raise ValueError("User does not have access to this chat")
    
    # Insert message into database
    record = await conn.fetchrow(
        """
        INSERT INTO messages (chat_id, sender_id, content, message_type, transaction_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, chat_id, sender_id, content, message_type, transaction_id, created_at
        """,
        chat_id, sender_id, message, message_type, transaction_id
    )
    
    return dict(record)


async def get_chat_messages(
    conn: asyncpg.Connection,
    chat_id: int,
    limit: int = 50,
    offset: int = 0
) -> list:
    """
    Retrieve messages from a chat.
    """
    logger.info(f"Retrieving messages for chat {chat_id}")
    
    records = await conn.fetch(
        """
        SELECT m.id, m.chat_id, m.sender_id, u.username as sender_username, 
               m.content, m.message_type, m.transaction_id, t.status as transaction_status,
               m.created_at
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        LEFT JOIN transactions t ON m.transaction_id = t.id::text
        WHERE m.chat_id = $1
        ORDER BY m.created_at ASC
        LIMIT $2 OFFSET $3
        """,
        chat_id, limit, offset
    )
    
    return [dict(record) for record in records]


async def initiate_transfer_in_chat(
    conn: asyncpg.Connection,
    chat_id: int,
    sender_id: int,
    amount: float,
    narration: str = "Chat transfer"
) -> dict:
    """
    Initiate a transfer within a chat.
    1. Find recipient in chat
    2. Create pending transaction
    3. Hold funds in fintech service
    4. Send transfer message
    """
    # For direct chats only for now
    partner = await get_direct_chat_partner(conn, chat_id, sender_id)
    if not partner:
        raise ValueError("Transfer only supported in direct chats for now")
    
    receiver_id = partner['id']
    
    # Get wallet accounts
    sender = await conn.fetchrow("SELECT wallet_account FROM users WHERE id = $1", sender_id)
    receiver = await conn.fetchrow("SELECT wallet_account FROM users WHERE id = $1", receiver_id)
    
    if not sender['wallet_account'] or not receiver['wallet_account']:
        raise ValueError("Both users must have wallet accounts linked")
        
    from app.packages.fintech import service as fintech_service
    
    # Create transaction record first (pending)
    txn_record = await conn.fetchrow(
        """
        INSERT INTO transactions (sender_id, receiver_id, amount, status)
        VALUES ($1, $2, $3, 'pending')
        RETURNING id, status
        """,
        sender_id, receiver_id, amount
    )
    
    # Hold funds
    await fintech_service.hold_funds(sender['wallet_account'], amount)
    
    # Send system message about transfer
    message = await send_message(
        conn=conn,
        chat_id=chat_id,
        sender_id=sender_id,
        message=f"Sent {amount}",
        message_type="transfer",
        transaction_id=str(txn_record['id'])
    )
    
    message['transaction_status'] = txn_record['status']
    return message


async def handle_transfer_action(
    conn: asyncpg.Connection,
    message_id: int,
    user_id: int,
    action: str  # "accept" or "reject"
) -> dict:
    """
    Handle recipient action on a transfer message.
    """
    # Get message and transaction details
    msg = await conn.fetchrow(
        """
        SELECT m.id, m.chat_id, m.sender_id, m.transaction_id, t.amount, t.status
        FROM messages m
        JOIN transactions t ON m.transaction_id = t.id::text
        WHERE m.id = $1
        """,
        message_id
    )
    
    if not msg or not msg['transaction_id']:
        raise ValueError("Transfer message not found")
        
    if msg['status'] != 'pending':
        raise ValueError(f"Transfer is already {msg['status']}")
        
    # Verify user is the recipient
    partner = await get_direct_chat_partner(conn, msg['chat_id'], msg['sender_id'])
    if partner['id'] != user_id:
        raise ValueError("Only the recipient can handle the transfer")
        
    from app.packages.fintech import service as fintech_service
    
    sender_wallet = await conn.fetchval("SELECT wallet_account FROM users WHERE id = $1", msg['sender_id'])
    receiver_wallet = await conn.fetchval("SELECT wallet_account FROM users WHERE id = $1", user_id)
    
    amount = float(msg['amount'])
    
    if action == "accept":
        await fintech_service.complete_transfer_from_hold(sender_wallet, receiver_wallet, amount)
        new_status = 'completed'
    elif action == "reject":
        await fintech_service.release_funds(sender_wallet, amount)
        new_status = 'rejected'
    else:
        raise ValueError("Invalid action")
        
    # Update transaction status
    await conn.execute(
        "UPDATE transactions SET status = $1 WHERE id = $2",
        new_status, int(msg['transaction_id'])
    )
    
    return {
        "message_id": message_id,
        "chat_id": msg['chat_id'],
        "transaction_id": msg['transaction_id'],
        "status": new_status
    }


async def create_chat_room(
    conn: asyncpg.Connection,
    creator_id: int,
    name: Optional[str] = None
) -> dict:
    """
    Create a new group chat room.
    
    Args:
        conn: Database connection
        creator_id: ID of the user creating the chat
        name: Optional name for the group chat
        
    Returns:
        Dictionary with chat room details
    """
    logger.info(f"User {creator_id} creating group chat room: {name}")
    
    async with conn.transaction():
        # Create group chat room
        chat_record = await conn.fetchrow(
            """
            INSERT INTO chats (chat_type, creator_id, name)
            VALUES ('group', $1, $2)
            RETURNING id, chat_type, creator_id, name, created_at
            """,
            creator_id, name
        )
        
        # Add creator as member
        await conn.execute(
            """
            INSERT INTO chat_members (chat_id, user_id)
            VALUES ($1, $2)
            """,
            chat_record['id'], creator_id
        )
        
        return dict(chat_record)


async def validate_chat_access(
    conn: asyncpg.Connection,
    chat_id: int,
    user_id: int
) -> bool:
    """
    Validate if a user has access to a chat.
    
    Args:
        conn: Database connection
        chat_id: Chat room ID
        user_id: User ID to check
        
    Returns:
        True if user has access, False otherwise
    """
    record = await conn.fetchrow(
        """
        SELECT 1 FROM chat_members
        WHERE chat_id = $1 AND user_id = $2
        """,
        chat_id, user_id
    )
    
    return record is not None


async def create_or_get_direct_chat(
    conn: asyncpg.Connection,
    user1_id: int,
    user2_id: int
) -> dict:
    """
    Create or get existing direct chat between two users.
    
    Args:
        conn: Database connection
        user1_id: First user ID
        user2_id: Second user ID
        
    Returns:
        Dictionary with chat details
    """
    logger.info(f"Creating or getting direct chat between users {user1_id} and {user2_id}")
    
    # Check if direct chat already exists between these users
    existing_chat = await conn.fetchrow(
        """
        SELECT c.id, c.chat_type, c.creator_id, c.created_at
        FROM chats c
        JOIN chat_members cm1 ON c.id = cm1.chat_id
        JOIN chat_members cm2 ON c.id = cm2.chat_id
        WHERE c.chat_type = 'direct'
        AND cm1.user_id = $1
        AND cm2.user_id = $2
        """,
        user1_id, user2_id
    )
    
    if existing_chat:
        logger.info(f"Found existing direct chat {existing_chat['id']}")
        # Add to each other's contacts idempotently even for existing chats
        from app.users import contacts_service
        await contacts_service.add_contact(conn, user1_id, user2_id)
        await contacts_service.add_contact(conn, user2_id, user1_id)
        return dict(existing_chat)
    
    # Create new direct chat
    async with conn.transaction():
        chat_record = await conn.fetchrow(
            """
            INSERT INTO chats (chat_type, creator_id, name)
            VALUES ('direct', $1, NULL)
            RETURNING id, chat_type, creator_id, created_at
            """,
            user1_id
        )
        
        # Add both users as members
        await conn.execute(
            """
            INSERT INTO chat_members (chat_id, user_id)
            VALUES ($1, $2), ($1, $3)
            """,
            chat_record['id'], user1_id, user2_id
        )
        
        # Add to each other's contacts automatically
        from app.users import contacts_service
        await contacts_service.add_contact(conn, user1_id, user2_id)
        await contacts_service.add_contact(conn, user2_id, user1_id)
        
        logger.info(f"Created new direct chat {chat_record['id']} and added users to each other's contacts")
        return dict(chat_record)


async def add_chat_member(
    conn: asyncpg.Connection,
    chat_id: int,
    user_id: int
) -> bool:
    """
    Add a user to a chat room.
    
    Args:
        conn: Database connection
        chat_id: Chat room ID
        user_id: User ID to add
        
    Returns:
        True if added successfully, False if already a member
    """
    logger.info(f"Adding user {user_id} to chat {chat_id}")
    
    try:
        await conn.execute(
            """
            INSERT INTO chat_members (chat_id, user_id)
            VALUES ($1, $2)
            """,
            chat_id, user_id
        )
        return True
    except asyncpg.UniqueViolationError:
        logger.warning(f"User {user_id} is already a member of chat {chat_id}")
        return False


async def get_user_chats(
    conn: asyncpg.Connection,
    user_id: int
) -> list:
    """
    Get all chats a user is a member of.
    
    Args:
        conn: Database connection
        user_id: User ID
        
    Returns:
        List of chat dictionaries with member count and other user info for direct chats
    """
    logger.info(f"Retrieving chats for user {user_id}")
    
    records = await conn.fetch(
        """
        SELECT c.id, c.chat_type, c.name, c.creator_id, c.created_at,
               COUNT(DISTINCT cm.user_id) as member_count,
               -- For direct chats, get the other user's info
               CASE 
                   WHEN c.chat_type = 'direct' THEN (
                       SELECT u.username 
                       FROM chat_members cm2 
                       JOIN users u ON cm2.user_id = u.id
                       WHERE cm2.chat_id = c.id AND cm2.user_id != $1
                       LIMIT 1
                   )
                   ELSE NULL
               END as other_user_username
        FROM chats c
        JOIN chat_members cm ON c.id = cm.chat_id
        WHERE c.id IN (
            SELECT chat_id FROM chat_members WHERE user_id = $1
        )
        GROUP BY c.id, c.chat_type, c.name, c.creator_id, c.created_at
        ORDER BY c.created_at DESC
        """,
        user_id
    )
    
    return [dict(record) for record in records]


async def get_direct_chat_partner(
    conn: asyncpg.Connection,
    chat_id: int,
    user_id: int
) -> Optional[Dict]:
    """
    Get the other user in a direct chat.
    
    Args:
        conn: Database connection
        chat_id: Chat room ID
        user_id: Current user ID
        
    Returns:
        Dictionary with partner user info, or None if not found
    """
    record = await conn.fetchrow(
        """
        SELECT u.id, u.username
        FROM chat_members cm
        JOIN users u ON cm.user_id = u.id
        WHERE cm.chat_id = $1 AND cm.user_id != $2
        """,
        chat_id, user_id
    )
    
    return dict(record) if record else None
