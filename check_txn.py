import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT id, status FROM transactions WHERE id = 8")
    print(res)
    await conn.close()
asyncio.run(check())
