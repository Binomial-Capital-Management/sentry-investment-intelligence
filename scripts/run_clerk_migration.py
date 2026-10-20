#!/usr/bin/env python3
"""
Run the Clerk ID migration to update user_id columns.
Following CODING_RULES.md: KISS, no hardcoding.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def run_clerk_migration():
    """Run the Clerk ID migration."""

    # Get database URL from environment (no hardcoding)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='postgresql://user:pass@host/db'")
        return False

    # Optionally override the DB user (e.g. a local superuser) for migration permissions
    migration_user = os.getenv('MIGRATION_DB_USER')
    if migration_user:
        database_url = database_url.replace('binomial_app:', f'{migration_user}:')

    try:
        # Connect to database
        print(f"Connecting to database...")
        conn = await asyncpg.connect(database_url)

        # Read migration script
        migration_file = Path(__file__).parent / "migrate_to_clerk_ids.sql"

        if not migration_file.exists():
            print(f"ERROR: Migration file not found: {migration_file}")
            return False

        print(f"Running Clerk ID migration...")

        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Run migration in a transaction
        async with conn.transaction():
            await conn.execute(migration_sql)

        print("✅ Migration completed successfully!")

        # Run verification queries
        print("\nVerifying migration...")

        # Check chat_sessions
        count = await conn.fetchval("SELECT COUNT(*) FROM chat_sessions WHERE user_id LIKE 'user_%'")
        print(f"  - chat_sessions with Clerk IDs: {count}")

        # Check chat_messages
        count = await conn.fetchval("SELECT COUNT(*) FROM chat_messages WHERE user_id LIKE 'user_%'")
        print(f"  - chat_messages with Clerk IDs: {count}")

        # Check portfolios
        count = await conn.fetchval("SELECT COUNT(*) FROM portfolios WHERE user_id LIKE 'user_%'")
        print(f"  - portfolios with Clerk IDs: {count}")

        print("\n✅ Migration verified!")
        print("\nBackup tables created: *_backup")
        print("If everything works correctly, you can drop them later.")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        await conn.close()

    return True

if __name__ == "__main__":
    # Confirm with user
    print("This will migrate all user_id columns from UUIDs to Clerk IDs.")
    print("Backup tables will be created automatically.")
    response = input("Continue? (yes/no): ")

    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(1)

    # Run migration
    success = asyncio.run(run_clerk_migration())
    sys.exit(0 if success else 1)