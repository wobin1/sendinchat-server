import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT id, content, message_type, transaction_id FROM messages WHERE message_type = 'transfer' ORDER BY id DESC LIMIT 5")
    for r in res:
        print(dict(r))
    await conn.close()
asyncio.run(check())
