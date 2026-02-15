import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    users = await conn.fetch("SELECT id, username, wallet_account FROM users")
    
    print(f"Users with Wallet Accounts: {len(users)}")
    for u in users:
        print(f"  - ID: {u['id']}, Username: {u['username']}, Wallet: {u['wallet_account']}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
