import asyncio, json, os, httpx; from datetime import datetime; from dotenv import load_dotenv; load_dotenv();
from app.packages.fintech.third_party_client import wallet_api_client
async def check():
    headers = await wallet_api_client._get_auth_headers()
    # Test 1: totalAmount instead of amount
    txn_id_credit = 'TXN20260328012507875652-credit'
    payload_totalAmount = {'transactionId': txn_id_credit, 'totalAmount': 4, 'transactionType': 'CREDIT', 'transactionDate': '2026-03-28', 'accountNo': '1100078367'}
    print('Testing totalAmount for credit...')
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(f'{wallet_api_client.base_url}/wallet_requery', json=payload_totalAmount, headers=headers)
        print(f'Credit Result (totalAmount): {res.text}')
    
    # Test 2: Successful debit requery (to check what worked)
    txn_id_debit = 'TXN20260328012507875652-debit'
    payload_debit = {'transactionId': txn_id_debit, 'amount': 4, 'transactionType': 'DEBIT', 'transactionDate': '2026-03-28', 'accountNo': '1100079089'}
    print('Testing known good debit requery...')
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(f'{wallet_api_client.base_url}/wallet_requery', json=payload_debit, headers=headers)
        print(f'Debit Result: {res.text}')
asyncio.run(check())
