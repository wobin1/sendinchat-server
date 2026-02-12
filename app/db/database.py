import asyncpg
from typing import AsyncGenerator
from app.core.config import settings

# Global connection pool
pool: asyncpg.Pool = None


async def get_pool() -> asyncpg.Pool:
    """Get the database connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
    return pool


async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency for getting database connections."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def close_pool():
    """Close the database connection pool."""
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def init_db():
    """Initialize database tables using raw SQL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                wallet_account VARCHAR(20) UNIQUE,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create transactions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                sender_id INTEGER NOT NULL REFERENCES users(id),
                receiver_id INTEGER NOT NULL REFERENCES users(id),
                amount NUMERIC(10, 2) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending' NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create chats table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                chat_type VARCHAR(20) NOT NULL DEFAULT 'direct',
                name VARCHAR(255),
                creator_id INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT check_chat_type CHECK (chat_type IN ('direct', 'group'))
            )
        """)
        
        # Create messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                sender_id INTEGER NOT NULL REFERENCES users(id),
                content TEXT NOT NULL,
                message_type VARCHAR(20) DEFAULT 'text',
                transaction_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create chat_members table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_members (
                chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id),
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        
        # --- Automatic Migrations (for existing tables) ---
        # Ensure users table has wallet_account
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_account VARCHAR(20) UNIQUE;")
        
        # Ensure messages table has new columns
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text';")
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS transaction_id VARCHAR(100);")
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chats_creator ON chats(creator_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chats_type ON chats(chat_type)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_members_user ON chat_members(user_id)
        """)
