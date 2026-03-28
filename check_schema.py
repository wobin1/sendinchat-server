import asyncio, asyncpg, os; from dotenv import load_dotenv; load_dotenv();
async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    res = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    print([r['table_name'] for r in res])
    for table in ['messages', 'transactions']:
        print(f'Schema for {table}:')
        schema = await conn.fetch(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
        for s in schema:
            print(f"  {s['column_name']}: {s['data_type']}")
    await conn.close()
asyncio.run(check())
