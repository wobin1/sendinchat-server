import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    chats = await conn.fetch("SELECT id, chat_type, creator_id, name FROM chats")
    contacts = await conn.fetch("SELECT * FROM contacts")
    users = await conn.fetch("SELECT id, username FROM users")
    chat_members = await conn.fetch("SELECT * FROM chat_members")
    
    print(f"Users: {len(users)}")
    for u in users:
        print(f"  - ID: {u['id']}, Username: {u['username']}")
        
    print(f"\nChats: {len(chats)}")
    for c in chats:
        members = await conn.fetch("SELECT u.username, m.user_id FROM chat_members m JOIN users u ON m.user_id = u.id WHERE m.chat_id = $1", c['id'])
        member_list = [f"{m['username']} ({m['user_id']})" for m in members]
        print(f"  - ID: {c['id']}, Type: {c['chat_type']}, Name: {c['name']}, Members: {member_list}")
        
    print(f"\nContacts: {len(contacts)}")
    for cn in contacts:
        u1 = await conn.fetchval("SELECT username FROM users WHERE id = $1", cn['user_id'])
        u2 = await conn.fetchval("SELECT username FROM users WHERE id = $1", cn['contact_id'])
        print(f"  - {u1} ({cn['user_id']}) has contact {u2} ({cn['contact_id']})")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
