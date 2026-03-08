"""
Migration script to add wallet_balances table
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate():
    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Create wallet_balances table
        print("Creating wallet_balances table...")
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
        
        # Create index
        print("Creating index...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wallet_balances_account 
            ON wallet_balances(wallet_account);
        """)
        
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
