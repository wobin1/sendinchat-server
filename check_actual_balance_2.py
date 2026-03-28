import asyncio, json, os; from dotenv import load_dotenv; load_dotenv();
from app.packages.fintech.third_party_client import wallet_api_client
async def check():
    res = await wallet_api_client.get_wallet_balance('1100073795')
    print(json.dumps(res, indent=2))
asyncio.run(check())
