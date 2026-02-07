"""
User service layer - handles all user-related business logic.
"""
import asyncpg
from typing import Optional, List
import logging

from app.users.models import User
from app.core.security import hash_password, verify_password

logger = logging.getLogger(__name__)


async def get_user_by_username(conn: asyncpg.Connection, username: str) -> Optional[User]:
    """
    Retrieve a user by username.
    
    Args:
        conn: Database connection
        username: Username to search for
        
    Returns:
        User object if found, None otherwise
    """
    record = await conn.fetchrow(
        "SELECT id, username, hashed_password, is_active, created_at FROM users WHERE username = $1",
        username
    )
    
    if record is None:
        return None
    
    return User.from_record(record)


async def get_user_by_id(conn: asyncpg.Connection, user_id: int) -> Optional[User]:
    """
    Retrieve a user by ID.
    
    Args:
        conn: Database connection
        user_id: User ID to search for
        
    Returns:
        User object if found, None otherwise
    """
    record = await conn.fetchrow(
        "SELECT id, username, hashed_password, is_active, created_at FROM users WHERE id = $1",
        user_id
    )
    
    if record is None:
        return None
    
    return User.from_record(record)


async def search_users(conn: asyncpg.Connection, query: str, limit: int = 20) -> List[User]:
    """
    Search for users by username.
    
    Args:
        conn: Database connection
        query: Search query (username)
        limit: Maximum number of results to return
        
    Returns:
        List of User objects matching the search query
    """
    # Search for users where username contains the query (case-insensitive)
    records = await conn.fetch(
        """
        SELECT id, username, hashed_password, is_active, created_at 
        FROM users 
        WHERE username ILIKE $1 AND is_active = TRUE
        ORDER BY username
        LIMIT $2
        """,
        f"%{query}%",
        limit
    )
    
    return [User.from_record(record) for record in records]


async def create_user(conn: asyncpg.Connection, username: str, password: str) -> User:
    """
    Create a new user account.
    
    Args:
        conn: Database connection
        username: Desired username
        password: Plain text password (will be hashed)
        
    Returns:
        Created User object
        
    Raises:
        ValueError: If username already exists
    """
    # Check if username already exists
    existing_user = await get_user_by_username(conn, username)
    if existing_user:
        raise ValueError("Username already registered")
    
    # Hash password
    hashed_pwd = hash_password(password)
    
    # Create user with raw SQL
    record = await conn.fetchrow(
        """
        INSERT INTO users (username, hashed_password, is_active)
        VALUES ($1, $2, $3)
        RETURNING id, username, hashed_password, is_active, created_at
        """,
        username,
        hashed_pwd,
        True
    )
    
    user = User.from_record(record)
    logger.info(f"User created: {user.username} (ID: {user.id})")
    
    return user


async def authenticate_user(conn: asyncpg.Connection, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        conn: Database connection
        username: Username
        password: Plain text password
        
    Returns:
        User object if authentication successful, None otherwise
    """
    user = await get_user_by_username(conn, username)
    
    if not user:
        logger.warning(f"Authentication failed: User not found - {username}")
        return None
    
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Authentication failed: Invalid password - {username}")
        return None
    
    if not user.is_active:
        logger.warning(f"Authentication failed: Inactive user - {username}")
        return None
    
    logger.info(f"User authenticated: {username}")
    return user


async def deactivate_user(conn: asyncpg.Connection, user_id: int) -> bool:
    """
    Deactivate a user account.
    
    Args:
        conn: Database connection
        user_id: ID of user to deactivate
        
    Returns:
        True if successful, False if user not found
    """
    result = await conn.execute(
        "UPDATE users SET is_active = FALSE WHERE id = $1",
        user_id
    )
    
    # Check if any rows were affected
    rows_affected = int(result.split()[-1])
    
    if rows_affected > 0:
        logger.info(f"User deactivated: ID {user_id}")
        return True
    
    return False


async def activate_user(conn: asyncpg.Connection, user_id: int) -> bool:
    """
    Activate a user account.
    
    Args:
        conn: Database connection
        user_id: ID of user to activate
        
    Returns:
        True if successful, False if user not found
    """
    result = await conn.execute(
        "UPDATE users SET is_active = TRUE WHERE id = $1",
        user_id
    )
    
    # Check if any rows were affected
    rows_affected = int(result.split()[-1])
    
    if rows_affected > 0:
        logger.info(f"User activated: ID {user_id}")
        return True
    
    return False


async def update_password(conn: asyncpg.Connection, user_id: int, new_password: str) -> bool:
    """
    Update a user's password.
    
    Args:
        conn: Database connection
        user_id: ID of user
        new_password: New plain text password (will be hashed)
        
    Returns:
        True if successful, False if user not found
    """
    hashed_pwd = hash_password(new_password)
    
    result = await conn.execute(
        "UPDATE users SET hashed_password = $1 WHERE id = $2",
        hashed_pwd,
        user_id
    )
    
    # Check if any rows were affected
    rows_affected = int(result.split()[-1])
    
    if rows_affected > 0:
        logger.info(f"Password updated for user ID: {user_id}")
        return True
    
    return False
