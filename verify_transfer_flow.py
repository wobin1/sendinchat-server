import asyncio
import asyncpg
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from app.db.database import init_db, get_pool
from app.users import service as user_service
from app.packages.chat import service as chat_service
from app.packages.fintech import service as fintech_service

load_dotenv()

async def verify_flow():
    print("Starting verification flow...")
    
    # helper for wallet verification
    async def get_wallet(conn, acc):
        record = await conn.fetchrow(
            "SELECT balance, locked_balance FROM wallet_balances WHERE wallet_account = $1",
            acc
        )
        return dict(record) if record else None

    # 1. Initialize DB
    await init_db()
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # 2. Setup test users
        print("Setting up test users...")
        try:
            user_a = await user_service.create_user(conn, "sender_test", "password123")
        except ValueError:
            user_a = await user_service.get_user_by_username(conn, "sender_test")
            
        try:
            user_b = await user_service.create_user(conn, "receiver_test", "password123")
        except ValueError:
            user_b = await user_service.get_user_by_username(conn, "receiver_test")
            
        # 3. Assign wallets (using demo wallet from mock_db for sender)
        # Demo wallet in mock_db.json is "1000000001"
        await user_service.assign_wallet_account(conn, user_a.id, "1000000001")
        await user_service.assign_wallet_account(conn, user_b.id, "0987654321") # Another mock account
        
        # Ensure wallets exist in PostgreSQL wallet_balances table
        print("Ensuring mock accounts exist in wallet_balances table...")
        await conn.execute(
            """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
               VALUES ('1000000001', 5000.0, 0.0, NOW())
               ON CONFLICT (wallet_account) DO UPDATE SET balance = 5000.0, locked_balance = 0.0""",
        )
        await conn.execute(
            """INSERT INTO wallet_balances (wallet_account, balance, locked_balance, last_synced_at)
               VALUES ('0987654321', 1000.0, 0.0, NOW())
               ON CONFLICT (wallet_account) DO UPDATE SET balance = 1000.0, locked_balance = 0.0""",
        )

        # Ensure wallets exist in mock_db.json (for simulate API calls if they ever use it)
        db = fintech_service.JsonDatabase.read()
        # Find or create sender
        if not any(w['accountNo'] == "1000000001" for w in db['wallets']):
            db['wallets'].append({
                "accountNo": "1000000001",
                "balance": 5000.0,
                "locked_balance": 0.0,
                "createdAt": datetime.utcnow().isoformat() + "Z"
            })
        
        # Find or create receiver
        if not any(w['accountNo'] == "0987654321" for w in db['wallets']):
            db['wallets'].append({
                "accountNo": "0987654321",
                "balance": 1000.0,
                "locked_balance": 0.0,
                "createdAt": datetime.utcnow().isoformat() + "Z"
            })
        fintech_service.JsonDatabase.write(db)
            
        # 4. Set transaction PIN for sender
        print("Setting transaction PIN for sender...")
        await user_service.set_transaction_pin(conn, user_a.id, "1234")
        
        # 5. Create direct chat
        chat = await chat_service.create_or_get_direct_chat(conn, user_a.id, user_b.id)
        chat_id = chat['id']
        print(f"Chat created: {chat_id}")
        
        # 6. Test Initiate Transfer with INCORRECT PIN
        print("Testing initiation with INCORRECT PIN (9999)...")
        try:
            await chat_service.initiate_transfer_in_chat(conn, chat_id, user_a.id, 200.0, "9999")
            print("❌ Error: Transfer initiated with incorrect PIN!")
            return
        except ValueError as e:
            print(f"✅ Success: Caught expected error: {str(e)}")
            assert str(e) == "Invalid transaction PIN"

        # 7. Test Initiate Transfer with CORRECT PIN
        print("Testing initiation with CORRECT PIN (1234)...")
        msg = await chat_service.initiate_transfer_in_chat(conn, chat_id, user_a.id, 200.0, "1234")
        print(f"✅ Success: Transfer initiated. Message ID: {msg['id']}, Transaction ID: {msg['transaction_id']}")
        
        # 8. Verify Hold
        wallet_a = await get_wallet(conn, "1000000001")
        print(f"Sender Wallet - Balance: {wallet_a['balance']}, Locked: {wallet_a['locked_balance']}")
        # In the new model, balance (total) stays the same during hold
        assert wallet_a['locked_balance'] >= 200.0
        
        # 9. Reject Transfer (Verification of rejection)
        print("Rejecting transfer...")
        await chat_service.handle_transfer_action(conn, msg['id'], user_b.id, "reject")
        
        wallet_a_after_reject = await get_wallet(conn, "1000000001")
        print(f"After Reject - Balance: {wallet_a_after_reject['balance']}, Locked: {wallet_a_after_reject['locked_balance']}")
        # In the new model, balance (total) stays the same during release
        assert wallet_a_after_reject['locked_balance'] == wallet_a['locked_balance'] - 200.0
        assert wallet_a_after_reject['balance'] == wallet_a['balance']
        
        # 10. Initiate second Transfer
        print("Initiating second transfer of 150 units...")
        msg2 = await chat_service.initiate_transfer_in_chat(conn, chat_id, user_a.id, 150.0, "1234")
        
        # 11. Accept Transfer
        print("Accepting transfer...")
        sender_pre_accept_data = await get_wallet(conn, "1000000001")
        sender_pre_accept_balance = sender_pre_accept_data['balance']
        await chat_service.handle_transfer_action(conn, msg2['id'], user_b.id, "accept")
        
        wallet_a_final = await get_wallet(conn, "1000000001")
        wallet_b_final = await get_wallet(conn, "0987654321")
        print(f"Final Sender Wallet - Balance: {wallet_a_final['balance']}, Locked: {wallet_a_final['locked_balance']}")
        # In the new model, balance (total) decreases ONLY on completion
        assert wallet_a_final['balance'] == sender_pre_accept_balance - 150.0
        assert wallet_a_final['locked_balance'] == 0.0
        print(f"Final Sender Wallet - Balance: {wallet_a_final['balance']}, Locked: {wallet_a_final['locked_balance']}")
        print(f"Final Receiver Wallet - Balance: {wallet_b_final['balance']}")
        
        # Verify message retrieval
        messages = await chat_service.get_chat_messages(conn, chat_id)
        for m in messages:
            if m['message_type'] == 'transfer':
                print(f"Message {m['id']}: Status {m['transaction_status']}")

    print("Verification complete!")

if __name__ == "__main__":
    asyncio.run(verify_flow())
