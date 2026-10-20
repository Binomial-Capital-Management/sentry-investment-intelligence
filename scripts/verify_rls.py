#!/usr/bin/env python3
"""
Verify PostgreSQL RLS (Row-Level Security) Configuration

This script verifies that:
1. The database role is not a superuser
2. The database role does not bypass RLS
3. RLS policies are properly enforced
"""

import asyncio
import asyncpg
import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'


async def verify_role_security(conn):
    """Verify the database role has proper security settings"""
    print(f"\n{BOLD}Checking database role security...{RESET}")
    
    # Check current role and its privileges
    role_info = await conn.fetchrow("""
        SELECT current_user as role_name,
               rolsuper,
               rolbypassrls,
               rolcreatedb,
               rolcreaterole
        FROM pg_roles
        WHERE rolname = current_user
    """)
    
    if not role_info:
        print(f"{RED}✗ Could not fetch role information{RESET}")
        return False
    
    role_name = role_info['role_name']
    is_superuser = role_info['rolsuper']
    bypasses_rls = role_info['rolbypassrls']
    can_create_db = role_info['rolcreatedb']
    can_create_role = role_info['rolcreaterole']
    
    print(f"Connected as: {BOLD}{role_name}{RESET}")
    print(f"  Superuser: {RED if is_superuser else GREEN}{is_superuser}{RESET}")
    print(f"  Bypasses RLS: {RED if bypasses_rls else GREEN}{bypasses_rls}{RESET}")
    print(f"  Create Database: {YELLOW if can_create_db else GREEN}{can_create_db}{RESET}")
    print(f"  Create Role: {YELLOW if can_create_role else GREEN}{can_create_role}{RESET}")
    
    if is_superuser:
        print(f"\n{RED}✗ SECURITY ERROR: Role is a SUPERUSER!{RESET}")
        print(f"  Superusers bypass all RLS policies.")
        return False
    
    if bypasses_rls:
        print(f"\n{RED}✗ SECURITY ERROR: Role has BYPASSRLS privilege!{RESET}")
        print(f"  This role bypasses Row-Level Security.")
        return False
    
    print(f"\n{GREEN}✓ Role security settings are correct{RESET}")
    return True


async def verify_rls_policies(conn):
    """Verify RLS policies are enabled on user tables"""
    print(f"\n{BOLD}Checking RLS policies...{RESET}")
    
    # Check which tables have RLS enabled (excluding users table which is managed by Clerk)
    tables = await conn.fetch("""
        SELECT 
            t.schemaname,
            t.tablename,
            t.rowsecurity as rls_enabled,
            c.relforcerowsecurity as force_rls
        FROM pg_tables t
        JOIN pg_class c ON c.relname = t.tablename
        WHERE t.schemaname = 'public'
        AND t.tablename IN ('portfolios', 'chat_sessions', 'chat_messages', 
                         'risk_analyses', 'workflows', 'workflow_runs', 'workflow_run_steps')
        ORDER BY t.tablename
    """)
    
    all_good = True
    for table in tables:
        tablename = table['tablename']
        rls_enabled = table['rls_enabled']
        force_rls = table['force_rls']
        
        if not rls_enabled:
            print(f"  {RED}✗ {tablename}: RLS DISABLED{RESET}")
            all_good = False
        elif not force_rls:
            print(f"  {YELLOW}⚠ {tablename}: RLS enabled but not FORCED{RESET}")
        else:
            print(f"  {GREEN}✓ {tablename}: RLS enabled and forced{RESET}")
    
    if all_good:
        print(f"\n{GREEN}✓ All tables have proper RLS configuration{RESET}")
    else:
        print(f"\n{RED}✗ Some tables are missing RLS configuration{RESET}")
    
    return all_good


async def run_rls_isolation_test(conn):
    """Run a canary test to verify RLS isolation actually works"""
    print(f"\n{BOLD}Running RLS isolation test...{RESET}")
    
    test_user_a = f"test_user_a_{uuid.uuid4().hex[:8]}"
    test_user_b = f"test_user_b_{uuid.uuid4().hex[:8]}"
    test_portfolio_id = None
    
    # Use a transaction for the test
    async with conn.transaction():
        try:
            # Create test portfolio as user A
            await conn.execute(f"SET LOCAL app.current_user_id = '{test_user_a}'")
            test_portfolio_id = await conn.fetchval(
                """
                INSERT INTO portfolios (user_id, name, tickers, weights, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING id
                """,
                test_user_a, "RLS_TEST", ["TEST"], [1.0], datetime.utcnow()
            )
            print(f"  Created test portfolio as {test_user_a[:20]}...")
            
            # Try to read as user B (should fail/return nothing)
            await conn.execute(f"SET LOCAL app.current_user_id = '{test_user_b}'")
            leaked_data = await conn.fetch(
                "SELECT * FROM portfolios WHERE id = $1",
                test_portfolio_id
            )
            
            if leaked_data:
                print(f"  {RED}✗ RLS BREACH: User B could see User A's data!{RESET}")
                return False
            else:
                print(f"  {GREEN}✓ User B cannot see User A's portfolio{RESET}")
            
            # Verify user A can still see it
            await conn.execute(f"SET LOCAL app.current_user_id = '{test_user_a}'")
            owned_data = await conn.fetch(
                "SELECT * FROM portfolios WHERE id = $1",
                test_portfolio_id
            )
            
            if not owned_data:
                print(f"  {RED}✗ RLS ERROR: User A cannot see their own data!{RESET}")
                return False
            else:
                print(f"  {GREEN}✓ User A can see their own portfolio{RESET}")
            
            # Clean up test data
            if test_portfolio_id:
                await conn.execute("DELETE FROM portfolios WHERE id = $1", test_portfolio_id)
                print(f"  Cleaned up test data")
            
            print(f"\n{GREEN}✓ RLS isolation test PASSED{RESET}")
            return True
            
        except Exception as e:
            print(f"  {RED}✗ Test failed: {e}{RESET}")
            return False


async def main():
    """Main verification routine"""
    print(f"{BOLD}=== Binomial Risk Analyst RLS Verification ==={RESET}")
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print(f"{RED}ERROR: DATABASE_URL not set in environment{RESET}")
        print("Please set DATABASE_URL or create a .env file")
        sys.exit(1)
    
    try:
        # Connect to database
        print(f"\nConnecting to database...")
        conn = await asyncpg.connect(database_url)
        
        try:
            # Run all verification checks
            role_ok = await verify_role_security(conn)
            policies_ok = await verify_rls_policies(conn)
            
            # Only run isolation test if basic checks pass
            isolation_ok = True
            if role_ok and policies_ok:
                isolation_ok = await run_rls_isolation_test(conn)
            
            # Final summary
            print(f"\n{BOLD}=== Verification Summary ==={RESET}")
            if role_ok and policies_ok and isolation_ok:
                print(f"{GREEN}✓ All security checks PASSED{RESET}")
                print("Your database is properly configured for RLS")
                sys.exit(0)
            else:
                print(f"{RED}✗ Some security checks FAILED{RESET}")
                print("Please fix the issues above before running the application")
                sys.exit(1)
                
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"{RED}ERROR: {e}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())