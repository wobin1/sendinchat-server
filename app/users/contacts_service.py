"""
Contacts service layer - handles contact-related business logic.
"""
import asyncpg
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

async def add_contact(conn: asyncpg.Connection, user_id: int, contact_id: int) -> bool:
    """
    Add a user to another user's contacts.
    """
    if user_id == contact_id:
        return False
        
    logger.info(f"Adding contact {contact_id} for user {user_id}")
    
    try:
        await conn.execute(
            """
            INSERT INTO contacts (user_id, contact_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, contact_id) DO NOTHING
            """,
            user_id, contact_id
        )
        return True
    except Exception as e:
        logger.error(f"Error adding contact: {str(e)}")
        return False

async def get_user_contacts(conn: asyncpg.Connection, user_id: int) -> List[Dict]:
    """
    Get all contacts for a user.
    """
    logger.info(f"Retrieving contacts for user {user_id}")
    
    records = await conn.fetch(
        """
        SELECT u.id, u.username, u.wallet_account, u.created_at, u.is_active
        FROM contacts c
        JOIN users u ON c.contact_id = u.id
        WHERE c.user_id = $1
        ORDER BY u.username
        """,
        user_id
    )
    
    return [dict(record) for record in records]

async def remove_contact(conn: asyncpg.Connection, user_id: int, contact_id: int) -> bool:
    """
    Remove a user from another user's contacts.
    """
    logger.info(f"Removing contact {contact_id} for user {user_id}")
    
    result = await conn.execute(
        "DELETE FROM contacts WHERE user_id = $1 AND contact_id = $2",
        user_id, contact_id
    )
    
    rows_affected = int(result.split()[-1])
    return rows_affected > 0
