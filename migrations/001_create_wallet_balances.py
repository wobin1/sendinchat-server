"""
Migration: Create wallet_balances table
Version: 001_create_wallet_balances
Created: 2026-03-08
"""
import asyncpg


async def up(conn: asyncpg.Connection):
    """Create wallet_balances table to track wallet balances and locked funds."""
    
    # Create wallet_balances table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet_balances (
            wallet_account VARCHAR(20) PRIMARY KEY,
            balance NUMERIC(12, 2) DEFAULT 0.00 NOT NULL,
            locked_balance NUMERIC(12, 2) DEFAULT 0.00 NOT NULL,
            last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT check_non_negative_balance CHECK (balance >= 0),
            CONSTRAINT check_non_negative_locked CHECK (locked_balance >= 0)
        );
    """)
    
    # Create index for wallet balance lookups
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_wallet_balances_account 
        ON wallet_balances(wallet_account);
    """)
    
    print("✅ Created wallet_balances table and index")


async def down(conn: asyncpg.Connection):
    """Rollback: Drop wallet_balances table."""
    await conn.execute("DROP TABLE IF EXISTS wallet_balances CASCADE;")
    print("✅ Dropped wallet_balances table")
