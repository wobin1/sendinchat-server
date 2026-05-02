"""
Migration: Add last_seen to users table
Version: 002_add_user_status
Created: 2026-05-02
"""
import asyncpg

async def up(conn: asyncpg.Connection):
    """Add last_seen column to users table."""
    await conn.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP;
    """)
    print("✅ Added last_seen column to users table")

async def down(conn: asyncpg.Connection):
    """Rollback: Remove last_seen column."""
    await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_seen;")
    print("✅ Dropped last_seen column from users table")
