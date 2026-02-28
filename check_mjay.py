
import asyncio
import asyncpg
import os

async def check():
    url = "postgresql://owner:password@localhost:5432/sendinchat"
    conn = await asyncpg.connect(url)
    try:
        row = await conn.fetchrow("SELECT id, username, wallet_account FROM users WHERE username = 'MJay'")
        print(f"User MJay: {dict(row) if row else 'Not found'}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
