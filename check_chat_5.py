import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetchrow("SELECT * FROM chats WHERE id = 5")
    print(dict(res))
    members = await conn.fetch("SELECT user_id FROM chat_members WHERE chat_id = 5")
    print([dict(m) for m in members])
    await conn.close()
asyncio.run(check())
