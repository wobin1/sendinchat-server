import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate():
    print(f"Connecting to {DATABASE_URL}...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Add wallet_account to users table
        print("Adding wallet_account to users table...")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_account VARCHAR(20) UNIQUE;")
        
        # Add message_type to messages table
        print("Adding message_type to messages table...")
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(20) DEFAULT 'text';")
        
        # Add transaction_id to messages table
        print("Adding transaction_id to messages table...")
        await conn.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS transaction_id VARCHAR(100);")
        
        print("\nVerifying columns...")
        user_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users';")
        user_col_names = [c['column_name'] for c in user_cols]
        print(f"Users columns: {user_col_names}")
        
        msg_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'messages';")
        msg_col_names = [c['column_name'] for c in msg_cols]
        print(f"Messages columns: {msg_col_names}")
        
        if 'wallet_account' in user_col_names and 'message_type' in msg_col_names:
            print("\nMigration verified successful!")
        else:
            print("\nMigration FAILED verification.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
