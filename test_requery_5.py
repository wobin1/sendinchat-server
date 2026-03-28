import asyncio, json, os, httpx; from datetime import datetime; from dotenv import load_dotenv; load_dotenv();
from app.packages.fintech.third_party_client import wallet_api_client
async def check():
    headers = await wallet_api_client._get_auth_headers()
    txn_id = 'TXN20260328012507875652-credit'
    payloads = [
        {'name': 'Amount_in_kobo', 'data': {'transactionId': txn_id, 'Amount': 400, 'transactionType': 'CREDIT', 'transactionDate': '2026-03-28', 'accountNo': '1100078367'}},
        {'name': 'amount_in_kobo', 'data': {'transactionId': txn_id, 'amount': 400, 'transactionType': 'CREDIT', 'transactionDate': '2026-03-28', 'accountNo': '1100078367'}}
    ]
    for p in payloads:
        print(f'Testing {p['name']}...')
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post(f'{wallet_api_client.base_url}/wallet_requery', json=p['data'], headers=headers)
                print(f'Result: {res.status_code} - {res.text}')
        except Exception as e:
            print(f'Error: {e}')
asyncio.run(check())
