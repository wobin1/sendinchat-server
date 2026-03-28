import asyncio, json, os; from dotenv import load_dotenv; load_dotenv();
from app.packages.fintech import service as fintech_service
async def check():
    res = await fintech_service.get_wallet_balance_api('1100079089')
    print(f'Sync result for 1100079089: {res}')
    
    res2 = await fintech_service.get_wallet_balance_api('1100073795')
    print(f'Sync result for 1100073795: {res2}')
    
asyncio.run(check())
