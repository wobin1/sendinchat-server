import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT wallet_account, balance FROM wallet_balances")
    for r in res:
        print(f"'{r['wallet_account']}': {r['balance']}")
    await conn.close()
asyncio.run(check())
