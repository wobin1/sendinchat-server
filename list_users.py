import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT id, username, wallet_account FROM users")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(check())
