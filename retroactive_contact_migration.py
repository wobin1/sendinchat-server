import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def migrate_existing_chats():
    print(f"Connecting to {os.getenv('DATABASE_URL')}...")
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    try:
        # Find all direct chats and their members
        print("Fetching all direct chats...")
        chats = await conn.fetch("""
            SELECT c.id, cm1.user_id as user1, cm2.user_id as user2
            FROM chats c
            JOIN chat_members cm1 ON c.id = cm1.chat_id
            JOIN chat_members cm2 ON c.id = cm2.chat_id
            WHERE c.chat_type = 'direct'
            AND cm1.user_id < cm2.user_id
        """)
        
        print(f"Found {len(chats)} direct chats to process.")
        
        count = 0
        for chat in chats:
            u1, u2 = chat['user1'], chat['user2']
            print(f"Adding contacts for chat {chat['id']} (Users {u1}, {u2})...")
            
            # Add u2 to u1's contacts
            await conn.execute("""
                INSERT INTO contacts (user_id, contact_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, contact_id) DO NOTHING
            """, u1, u2)
            
            # Add u1 to u2's contacts
            await conn.execute("""
                INSERT INTO contacts (user_id, contact_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id, contact_id) DO NOTHING
            """, u2, u1)
            
            count += 2
            
        print(f"Successfully processed {count} contact entries.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_existing_chats())
