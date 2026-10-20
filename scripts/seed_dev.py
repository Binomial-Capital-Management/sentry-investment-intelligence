#!/usr/bin/env python3
"""
Development seed script - creates test user and sample portfolio.
For local development without Clerk authentication.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from core.database.postgres_client import get_postgres_client


async def seed_dev_data():
    """Create development user and sample portfolio."""
    
    # Check if we're in dev mode
    if os.getenv('ENABLE_AUTH', 'true').lower() == 'true':
        print("WARNING: Auth is enabled. This script is for dev mode only.")
        print("Set ENABLE_AUTH=false in .env to use this script.")
        return False
    
    # Get or set dev user ID
    dev_user_id = os.getenv('DEV_INTERNAL_USER_ID', 'dev_user_001')
    print(f"Using development user ID: {dev_user_id}")
    
    try:
        # Connect to database
        pg = await get_postgres_client()
        await pg.connect()
        
        # Create dev user if doesn't exist
        print("\nCreating development user...")
        user = await pg.upsert_user(
            clerk_user_id=f"dev_{dev_user_id}",
            email="dev@binomial.test",
            name="Dev User"
        )
        
        if user:
            internal_user_id = user['id']
            print(f"✅ User created/updated with internal ID: {internal_user_id}")
            
            # Create sample portfolios
            print("\nCreating sample portfolios...")
            
            # Tech portfolio
            tech_portfolio = await pg.create_portfolio(
                user_id=internal_user_id,
                name="Tech Growth Portfolio",
                tickers=["AAPL", "MSFT", "GOOGL", "NVDA", "META"],
                weights=[0.25, 0.20, 0.20, 0.20, 0.15]
            )
            if tech_portfolio:
                print(f"✅ Created: Tech Growth Portfolio")
                
                # Set as default
                await pg.set_default_portfolio(
                    user_id=internal_user_id,
                    portfolio_id=tech_portfolio
                )
                print("   Set as default portfolio")
            
            # Balanced portfolio
            balanced_portfolio = await pg.create_portfolio(
                user_id=internal_user_id,
                name="Balanced 60/40",
                tickers=["SPY", "AGG"],
                weights=[0.60, 0.40]
            )
            if balanced_portfolio:
                print(f"✅ Created: Balanced 60/40")
            
            # Risk parity portfolio
            risk_portfolio = await pg.create_portfolio(
                user_id=internal_user_id,
                name="Risk Parity Strategy",
                tickers=["VTI", "TLT", "GLD", "VNQ"],
                weights=[0.25, 0.25, 0.25, 0.25]
            )
            if risk_portfolio:
                print(f"✅ Created: Risk Parity Strategy")
            
            # Create a sample chat session
            print("\nCreating sample chat session...")
            session = await pg.create_chat_session(
                user_id=internal_user_id,
                title="Risk Analysis Demo"
            )
            if session:
                print(f"✅ Created chat session: {session['id']}")
                
                # Add sample messages
                await pg.save_chat_message(
                    user_id=internal_user_id,
                    session_id=session['id'],
                    role='user',
                    content='Calculate VaR for my default portfolio'
                )
                
                await pg.save_chat_message(
                    user_id=internal_user_id,
                    session_id=session['id'],
                    role='assistant',
                    content='I\'ll calculate the Value at Risk for your Tech Growth Portfolio...'
                )
                print("   Added sample messages")
            
            print("\n" + "="*60)
            print("DEVELOPMENT SEED COMPLETE!")
            print("="*60)
            print(f"\nTo use this data in development:")
            print(f"1. Set these environment variables:")
            print(f"   export ENABLE_AUTH=false")
            print(f"   export DEV_INTERNAL_USER_ID={dev_user_id}")
            print(f"   export DATABASE_URL=<your_postgres_url>")
            print(f"\n2. Start the backend:")
            print(f"   python app_fastapi.py")
            print(f"\n3. Your requests will automatically use user: {internal_user_id}")
            print("="*60)
            
        else:
            print("❌ Failed to create user")
            return False
        
        # Disconnect
        await pg.disconnect()
        return True
        
    except Exception as e:
        print(f"\n❌ Seed failed: {e}")
        print("\nMake sure:")
        print("1. PostgreSQL is running")
        print("2. DATABASE_URL is set correctly")
        print("3. Migrations have been run")
        return False


if __name__ == "__main__":
    success = asyncio.run(seed_dev_data())
    sys.exit(0 if success else 1)