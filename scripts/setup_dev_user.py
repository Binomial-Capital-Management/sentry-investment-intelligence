#!/usr/bin/env python3
"""
Create a dev user in PostgreSQL for local testing.
Run this after migrations to set up a test user.

Usage:
    python scripts/setup_dev_user.py
    
Then set:
    export DEV_INTERNAL_USER_ID=dev-user-local
"""

import asyncio
import asyncpg
import os
from datetime import datetime
import uuid

async def setup_dev_user():
    """Create a dev user for local testing."""
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set. Please set it first:")
        print("   export DATABASE_URL=postgresql://dev:dev@localhost:5432/binomial")
        return False
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        
        # Check if users table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            )
        """)
        
        if not table_exists:
            print("❌ Users table doesn't exist. Run migrations first:")
            print("   python scripts/migrate_rls.py")
            await conn.close()
            return False
        
        # Create or update dev user
        dev_user_id = "dev-user-local"
        dev_clerk_id = f"clerk_dev_{uuid.uuid4().hex[:8]}"
        dev_email = "dev@localhost"
        dev_name = "Local Dev User"
        
        # Insert or update the dev user
        await conn.execute("""
            INSERT INTO users (id, clerk_user_id, email, name, created_at, updated_at, usage_credits)
            VALUES ($1, $2, $3, $4, $5, $5, 10000)
            ON CONFLICT (id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at,
                usage_credits = EXCLUDED.usage_credits
        """, dev_user_id, dev_clerk_id, dev_email, dev_name, datetime.utcnow())
        
        # Create a default portfolio for the dev user
        portfolio_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO portfolios (id, user_id, name, tickers, weights, is_default, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, true, $6, $6)
            ON CONFLICT DO NOTHING
        """, portfolio_id, dev_user_id, "Dev Tech Portfolio", 
            ["AAPL", "MSFT", "GOOGL"], [0.4, 0.3, 0.3], datetime.utcnow())
        
        # Create a chat session for testing
        session_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO chat_sessions (id, user_id, title, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $4)
            ON CONFLICT DO NOTHING
        """, session_id, dev_user_id, "Dev Test Session", datetime.utcnow())
        
        await conn.close()
        
        print("✅ Dev user created successfully!")
        print("\nTo use in local development, set these environment variables:")
        print(f"   export DEV_INTERNAL_USER_ID={dev_user_id}")
        print("   export ENABLE_AUTH=false")
        print("   export ENABLE_POSTGRES=true")
        print("\nDev user details:")
        print(f"   Internal ID: {dev_user_id}")
        print(f"   Email: {dev_email}")
        print(f"   Default portfolio: Tech Portfolio (AAPL, MSFT, GOOGL)")
        print(f"   Usage credits: 10000")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up dev user: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(setup_dev_user())
    exit(0 if result else 1)