"""
Database migration system - automatically runs pending migrations on startup
"""
import asyncpg
import logging
from pathlib import Path
from typing import List, Dict
import importlib.util
import sys

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


async def ensure_migrations_table(conn: asyncpg.Connection):
    """Create migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    logger.info("Migrations table ensured")


async def get_applied_migrations(conn: asyncpg.Connection) -> List[str]:
    """Get list of already applied migration versions."""
    records = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
    return [record['version'] for record in records]


async def mark_migration_applied(conn: asyncpg.Connection, version: str):
    """Mark a migration as applied."""
    await conn.execute(
        "INSERT INTO schema_migrations (version) VALUES ($1)",
        version
    )
    logger.info(f"✅ Marked migration {version} as applied")


def get_pending_migrations(applied: List[str]) -> List[Dict[str, str]]:
    """Get list of migration files that haven't been applied yet."""
    if not MIGRATIONS_DIR.exists():
        logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []
    
    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))
    pending = []
    
    for migration_file in migration_files:
        if migration_file.name.startswith("__"):
            continue
        
        version = migration_file.stem  # filename without .py
        if version not in applied:
            pending.append({
                "version": version,
                "path": str(migration_file)
            })
    
    return pending


async def run_migration(conn: asyncpg.Connection, migration: Dict[str, str]):
    """Run a single migration file."""
    version = migration['version']
    path = migration['path']
    
    logger.info(f"🔄 Running migration: {version}")
    
    try:
        # Dynamically import the migration module
        spec = importlib.util.spec_from_file_location(version, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[version] = module
        spec.loader.exec_module(module)
        
        # Run the migration's up() function
        if hasattr(module, 'up'):
            await module.up(conn)
        else:
            raise ValueError(f"Migration {version} missing up() function")
        
        # Mark as applied
        await mark_migration_applied(conn, version)
        
        logger.info(f"✅ Migration {version} completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration {version} failed: {str(e)}")
        raise


async def run_pending_migrations(conn: asyncpg.Connection):
    """Run all pending migrations in order."""
    logger.info("🔍 Checking for pending migrations...")
    
    # Ensure migrations table exists
    await ensure_migrations_table(conn)
    
    # Get applied and pending migrations
    applied = await get_applied_migrations(conn)
    pending = get_pending_migrations(applied)
    
    if not pending:
        logger.info("✅ No pending migrations")
        return
    
    logger.info(f"📋 Found {len(pending)} pending migration(s)")
    
    # Run each pending migration
    for migration in pending:
        await run_migration(conn, migration)
    
    logger.info(f"✅ All {len(pending)} migration(s) completed successfully")
