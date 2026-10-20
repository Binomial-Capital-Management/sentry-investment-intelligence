"""
Test portfolio delete/update permissions for organization workspaces.

Verifies that:
1. Personal portfolios can only be deleted/updated by creator
2. Org portfolios can be deleted/updated by any org member
3. Org portfolios CANNOT be accessed by non-members
4. Personal portfolios remain isolated from org context
"""

import pytest
import asyncio
from core.database.postgres_client import get_postgres_rls_client


@pytest.mark.asyncio
async def test_personal_portfolio_creator_only():
    """Personal portfolios can only be deleted/updated by creator."""
    pg = await get_postgres_rls_client()

    # User A creates personal portfolio
    async with pg.acquire_with_org_context("user_a", None) as conn:
        result = await conn.fetchrow("""
            INSERT INTO portfolios (id, user_id, org_id, name, tickers, weights)
            VALUES ('port_personal_a', 'user_a', NULL, 'Personal A', ARRAY['AAPL'], ARRAY[1.0])
            RETURNING id
        """)
        assert result is not None

    # User B cannot delete User A's personal portfolio
    deleted = await pg.delete_portfolio("user_b", "port_personal_a", org_id=None)
    assert deleted is False, "User B should NOT be able to delete User A's personal portfolio"

    # User A can delete their own personal portfolio
    deleted = await pg.delete_portfolio("user_a", "port_personal_a", org_id=None)
    assert deleted is True, "User A should be able to delete their own personal portfolio"


@pytest.mark.asyncio
async def test_org_portfolio_any_member_can_delete():
    """Organization portfolios can be deleted by any org member."""
    pg = await get_postgres_rls_client()

    # Setup: Ensure test org exists with 2 members
    async with pg.acquire_with_org_context("user_a", None) as conn:
        await conn.execute("""
            INSERT INTO organizations (id, name, slug, creator_id)
            VALUES ('test_org_123', 'Test Org', 'test-org-123', 'user_a')
            ON CONFLICT (id) DO NOTHING
        """)

        await conn.execute("""
            INSERT INTO organization_members (id, org_id, user_id, role)
            VALUES
                ('mem_test_org_123_user_a', 'test_org_123', 'user_a', 'org:admin'),
                ('mem_test_org_123_user_b', 'test_org_123', 'user_b', 'org:member')
            ON CONFLICT (org_id, user_id) DO NOTHING
        """)

    # User A creates org portfolio
    async with pg.acquire_with_org_context("user_a", "test_org_123") as conn:
        result = await conn.fetchrow("""
            INSERT INTO portfolios (id, user_id, org_id, name, tickers, weights)
            VALUES ('port_org_123', 'user_a', 'test_org_123', 'Org Portfolio', ARRAY['AAPL'], ARRAY[1.0])
            RETURNING id
        """)
        assert result is not None

    # User B (different user, but same org member) CAN delete User A's org portfolio
    deleted = await pg.delete_portfolio("user_b", "port_org_123", org_id="test_org_123")
    assert deleted is True, "User B (org member) should be able to delete User A's org portfolio"


@pytest.mark.asyncio
async def test_org_portfolio_non_member_cannot_delete():
    """Non-members cannot delete organization portfolios."""
    pg = await get_postgres_rls_client()

    # Setup: Create org portfolio
    async with pg.acquire_with_org_context("user_a", None) as conn:
        await conn.execute("""
            INSERT INTO organizations (id, name, slug, creator_id)
            VALUES ('test_org_456', 'Test Org 456', 'test-org-456', 'user_a')
            ON CONFLICT (id) DO NOTHING
        """)

        await conn.execute("""
            INSERT INTO organization_members (id, org_id, user_id, role)
            VALUES ('mem_test_org_456_user_a', 'test_org_456', 'user_a', 'org:admin')
            ON CONFLICT (org_id, user_id) DO NOTHING
        """)

    async with pg.acquire_with_org_context("user_a", "test_org_456") as conn:
        await conn.execute("""
            INSERT INTO portfolios (id, user_id, org_id, name, tickers, weights)
            VALUES ('port_org_456', 'user_a', 'test_org_456', 'Org Portfolio 456', ARRAY['AAPL'], ARRAY[1.0])
        """)

    # User C (not an org member) CANNOT delete the org portfolio
    deleted = await pg.delete_portfolio("user_c", "port_org_456", org_id="test_org_456")
    assert deleted is False, "User C (non-member) should NOT be able to delete org portfolio"


@pytest.mark.asyncio
async def test_org_portfolio_update_any_member():
    """Organization portfolios can be updated by any org member."""
    pg = await get_postgres_rls_client()

    # Setup org and members
    async with pg.acquire_with_org_context("user_a", None) as conn:
        await conn.execute("""
            INSERT INTO organizations (id, name, slug, creator_id)
            VALUES ('test_org_789', 'Test Org 789', 'test-org-789', 'user_a')
            ON CONFLICT (id) DO NOTHING
        """)

        await conn.execute("""
            INSERT INTO organization_members (id, org_id, user_id, role)
            VALUES
                ('mem_test_org_789_user_a', 'test_org_789', 'user_a', 'org:admin'),
                ('mem_test_org_789_user_b', 'test_org_789', 'user_b', 'org:member')
            ON CONFLICT (org_id, user_id) DO NOTHING
        """)

    # User A creates org portfolio
    async with pg.acquire_with_org_context("user_a", "test_org_789") as conn:
        await conn.execute("""
            INSERT INTO portfolios (id, user_id, org_id, name, tickers, weights)
            VALUES ('port_org_789', 'user_a', 'test_org_789', 'Original Name', ARRAY['AAPL'], ARRAY[1.0])
        """)

    # User B (org member) CAN update User A's org portfolio
    updated = await pg.update_portfolio(
        user_id="user_b",
        portfolio_id="port_org_789",
        name="Updated by User B",
        org_id="test_org_789"
    )
    assert updated is True, "User B (org member) should be able to update org portfolio"

    # Verify the update
    async with pg.acquire_with_org_context("user_b", "test_org_789") as conn:
        result = await conn.fetchrow("""
            SELECT name FROM portfolios WHERE id = 'port_org_789'
        """)
        assert result['name'] == "Updated by User B"


if __name__ == "__main__":
    asyncio.run(test_personal_portfolio_creator_only())
    asyncio.run(test_org_portfolio_any_member_can_delete())
    asyncio.run(test_org_portfolio_non_member_cannot_delete())
    asyncio.run(test_org_portfolio_update_any_member())
    print("✅ All portfolio org permission tests passed!")
