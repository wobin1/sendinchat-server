import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT m.id, m.message_type, m.transaction_id, t.status FROM messages m LEFT JOIN transactions t ON m.transaction_id = t.id::text WHERE m.message_type = 'transfer' ORDER BY m.id DESC LIMIT 5")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(check())
