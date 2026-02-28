
import asyncio
import asyncpg
import os
import sys
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

async def test_search_users():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    try:
        # We need a user to search for. Let's find one that has a wallet.
        user_with_wallet = await conn.fetchrow("SELECT username, wallet_account FROM users WHERE wallet_account IS NOT NULL LIMIT 1")
        if not user_with_wallet:
            print("No users found with a wallet account.")
            return

        username = user_with_wallet['username']
        wallet_account = user_with_wallet['wallet_account']
        print(f"Searching for user: {username} (Expected wallet: {wallet_account})")

        # Mock the items needed for the search_users logic
        # Actually, let's just test the service layer directly or the router logic manually.
        # Since I'm on the server, I can just query the DB and see if the records returned by service.search_users have the field.
        
        from app.users import service as user_service
        
        users = await user_service.search_users(conn, username, limit=10)
        
        found = False
        for u in users:
            if u.username == username:
                print(f"Found user: {u.username}")
                print(f"Wallet account in User object: {u.wallet_account}")
                if u.wallet_account == wallet_account:
                    print("✅ Wallet account correctly found in search results.")
                    found = True
        
        if not found:
            print("❌ User not found in search results or wallet account mismatch.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_search_users())
