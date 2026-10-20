"""
Test slug availability endpoint after RLS fix
Verifies that the SECURITY DEFINER function bypasses RLS correctly
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database.postgres_client import get_postgres_client


async def test_slug_function():
    """Test the SECURITY DEFINER function for slug checking"""
    print("Testing slug availability function...")

    pg = await get_postgres_client()

    # Test 1: Check non-existent slug (should be available)
    async with pg.pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT public.check_organization_slug_available($1)",
            "test-org-12345"
        )
        print(f"✓ Non-existent slug check: {result} (should be True)")
        assert result is True, "Non-existent slug should be available"

    # Test 2: Create a test organization
    async with pg.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, creator_id)
            VALUES ('test-org-id', 'Test Org', 'existing-slug', NULL)
            ON CONFLICT (slug) DO NOTHING
            """
        )
        print("✓ Created test organization with slug 'existing-slug'")

    # Test 3: Check existing slug (should NOT be available)
    async with pg.pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT public.check_organization_slug_available($1)",
            "existing-slug"
        )
        print(f"✓ Existing slug check: {result} (should be False)")
        assert result is False, "Existing slug should not be available"

    # Test 4: Verify no recursion error occurs
    try:
        async with pg.pool.acquire() as conn:
            # This should not cause infinite recursion anymore
            result = await conn.fetchval(
                "SELECT public.check_organization_slug_available($1)",
                "another-test-slug"
            )
            print(f"✓ No recursion error: {result}")
    except Exception as e:
        if "infinite recursion" in str(e).lower():
            print(f"✗ FAILED: Infinite recursion still occurring: {e}")
            raise
        else:
            print(f"✗ FAILED: Unexpected error: {e}")
            raise

    # Cleanup
    async with pg.pool.acquire() as conn:
        await conn.execute("DELETE FROM organizations WHERE id = 'test-org-id'")
        print("✓ Cleaned up test data")

    print("\n✓ All slug availability tests passed!")


async def test_endpoint_simulation():
    """Simulate the actual endpoint call"""
    print("\nSimulating endpoint call...")

    pg = await get_postgres_client()

    slug = "my-new-org"

    # Simulate the exact query from the endpoint
    async with pg.pool.acquire() as conn:
        is_available = await conn.fetchval(
            "SELECT public.check_organization_slug_available($1)",
            slug
        )

    if is_available:
        print(f"✓ Slug '{slug}' is available")
    else:
        print(f"✓ Slug '{slug}' is taken")

    print("✓ Endpoint simulation successful (no recursion error)")


if __name__ == "__main__":
    asyncio.run(test_slug_function())
    asyncio.run(test_endpoint_simulation())
