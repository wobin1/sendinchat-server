# Database Migrations

This directory contains database migration files that are automatically run on application startup.

## How It Works

1. **Automatic Execution**: Migrations run automatically when the app starts
2. **Tracking**: The `schema_migrations` table tracks which migrations have been applied
3. **Ordering**: Migrations run in alphabetical order by filename
4. **Idempotent**: Already-applied migrations are skipped

## Creating a New Migration

1. Create a new file with format: `{version}_{description}.py`
   - Example: `002_add_user_preferences.py`
   - Use sequential numbering (001, 002, 003, etc.)

2. Add `up()` and `down()` functions:

```python
"""
Migration: Description of what this migration does
Version: 002_add_user_preferences
Created: 2026-03-08
"""
import asyncpg


async def up(conn: asyncpg.Connection):
    """Apply the migration."""
    await conn.execute("""
        CREATE TABLE user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            theme VARCHAR(20) DEFAULT 'light',
            notifications BOOLEAN DEFAULT TRUE
        );
    """)
    print("✅ Created user_preferences table")


async def down(conn: asyncpg.Connection):
    """Rollback the migration."""
    await conn.execute("DROP TABLE IF EXISTS user_preferences CASCADE;")
    print("✅ Dropped user_preferences table")
```

3. Restart the app - the migration will run automatically

## Existing Migrations

- `001_create_wallet_balances.py` - Creates wallet_balances table for tracking wallet balances and locked funds

## Best Practices

- Always use `IF NOT EXISTS` for CREATE statements
- Always use `IF EXISTS` for DROP statements
- Test migrations locally before deploying
- Keep migrations small and focused
- Never modify existing migration files after they've been deployed
- Add descriptive comments explaining what the migration does
