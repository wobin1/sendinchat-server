import httpx
import json
import uuid
import asyncio
import sys
import os

# Add the current directory to sys.path to import app
sys.path.append(os.getcwd())

from app.main import app

async def register_user(client, username, password):
    response = await client.post(f"/users/register", json={
        "username": username,
        "password": password
    })
    return response.json()

async def login_user(client, username, password):
    response = await client.post(f"/users/token", data={
        "username": username,
        "password": password
    })
    return response.json()['data']['access_token']

async def start_chat(client, token, other_user_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(f"/chat/start_direct_chat?other_user_id={other_user_id}", headers=headers)
    return response.json()

async def get_contacts(client, token):
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(f"/users/contacts", headers=headers)
    return response.json()

async def main():
    # Use ASGITransport for in-process testing
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register two users
        u1_name = f"user1_{uuid.uuid4().hex[:6]}"
        u2_name = f"user2_{uuid.uuid4().hex[:6]}"
        pwd = "password123"
        
        print(f"Registering {u1_name}...")
        u1 = await register_user(client, u1_name, pwd)
        u1_id = u1['data']['id']
        
        print(f"Registering {u2_name}...")
        u2 = await register_user(client, u2_name, pwd)
        u2_id = u2['data']['id']
        
        # 2. Login as user 1
        print(f"Logging in as {u1_name}...")
        token1 = await login_user(client, u1_name, pwd)
        
        # 3. Check contacts (should be empty)
        print("Checking initial contacts for user 1...")
        contacts1 = await get_contacts(client, token1)
        print(f"User 1 contacts: {len(contacts1['data'])}")
        
        # 4. Start a chat with user 2
        print(f"Starting chat with user 2 (ID: {u2_id})...")
        await start_chat(client, token1, u2_id)
        
        # 5. Check contacts again for both
        print("Checking contacts for user 1 after chat...")
        contacts1 = await get_contacts(client, token1)
        print(f"User 1 contacts count: {len(contacts1['data'])}")
        for c in contacts1['data']:
            print(f" - Contact: {c['username']} (ID: {c['id']})")
            
        print(f"Logging in as {u2_name}...")
        token2 = await login_user(client, u2_name, pwd)
        
        print("Checking contacts for user 2 after chat...")
        contacts2 = await get_contacts(client, token2)
        print(f"User 2 contacts count: {len(contacts2['data'])}")
        for c in contacts2['data']:
            print(f" - Contact: {c['username']} (ID: {c['id']})")

        # Verify
        u1_has_u2 = any(c['id'] == u2_id for c in contacts1['data'])
        u2_has_u1 = any(c['id'] == u1_id for c in contacts2['data'])
        
        if u1_has_u2 and u2_has_u1:
            print("\n✅ SUCCESS: Users automatically added to each other's contacts!")
        else:
            print("\n❌ FAILURE: Automatic contact addition failed.")

if __name__ == "__main__":
    asyncio.run(main())
