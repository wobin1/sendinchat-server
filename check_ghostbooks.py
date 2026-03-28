import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect('postgresql://owner:password@localhost:5432/ghostbooks_db')
    res = await conn.fetch("SELECT id, username, wallet_account FROM users LIMIT 10")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(check())
