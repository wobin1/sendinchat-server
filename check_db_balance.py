import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetchrow("SELECT balance, locked_balance FROM wallet_balances WHERE wallet_account = '1100079089'")
    print(dict(res) if res else 'Not found')
    await conn.close()
asyncio.run(check())
