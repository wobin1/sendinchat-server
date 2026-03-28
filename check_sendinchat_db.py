import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    try:
        conn = await asyncpg.connect('postgresql://owner:password@localhost:5432/sendinchat_db')
        res = await conn.fetch("SELECT id, username, wallet_account FROM users")
        for r in res:
            print(dict(r))
        await conn.close()
    except Exception as e:
        print(f'Error connecting to sendinchat_db: {e}')
asyncio.run(check())
