import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetchrow("SELECT id, username, wallet_account FROM users WHERE id = 5")
    print(dict(res))
    await conn.close()
asyncio.run(check())
