import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT wallet_account, balance FROM wallet_balances WHERE balance = 20.0")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(check())
