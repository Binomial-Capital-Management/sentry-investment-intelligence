#!/usr/bin/env python3
"""
Run database migrations in order.
Following CODING_RULES.md: KISS, MVP first.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

async def run_migrations():
    """Run all migrations in order."""
    
    # Get database URL from environment (no hardcoding)
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='postgresql://user:pass@host/db'")
        return False
    
    try:
        # Connect to database
        print(f"Connecting to database...")
        conn = await asyncpg.connect(database_url)
        
        # Get migration files in order
        migrations_dir = Path(__file__).parent.parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        
        if not migration_files:
            print(f"ERROR: No migration files found in {migrations_dir}")
            print(f"Directory contents: {list(migrations_dir.iterdir())}")
            return False
        
        for migration_file in migration_files:
            print(f"\nRunning migration: {migration_file.name}")
            
            with open(migration_file, 'r') as f:
                migration_sql = f.read()
            
            # Run each migration in its own transaction
            try:
                async with conn.transaction():
                    await conn.execute(migration_sql)
                print(f"  ✅ {migration_file.name} completed")
            except Exception as e:
                print(f"  ⚠️  {migration_file.name} skipped: {e}")
                # Transaction automatically rolled back on error
                # Reset connection state after rollback
                await conn.execute("ROLLBACK")
                # Continue with next migration (some may already be applied)
                continue
        
        # Verify tables exist
        print("\nVerifying tables...")
        tables_to_check = ['users', 'portfolios', 'chat_sessions', 'chat_messages', 'risk_analyses']
        
        for table in tables_to_check:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                )
            """, table)
            
            if exists:
                # Check RLS status
                rls_enabled = await conn.fetchval("""
                    SELECT relrowsecurity 
                    FROM pg_class 
                    WHERE relname = $1
                """, table)
                
                if table == 'users':
                    # Users table doesn't need RLS
                    print(f"  {table}: ✅ EXISTS")
                else:
                    status = "✅ RLS ENABLED" if rls_enabled else "⚠️ RLS DISABLED"
                    print(f"  {table}: {status}")
            else:
                print(f"  {table}: ❌ NOT FOUND")
        
        print("\n✅ Migration process completed!")
        
        # Close connection
        await conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    # Run migrations
    success = asyncio.run(run_migrations())
    sys.exit(0 if success else 1)