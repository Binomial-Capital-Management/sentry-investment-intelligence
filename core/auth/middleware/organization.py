"""
Organization middleware - ONLY handles organization context.
Single responsibility: Extract and verify organization membership.
"""

import logging
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_config

logger = logging.getLogger(__name__)


class OrganizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle organization context.
    
    Responsibilities:
    - Extract X-Organization-ID header (or query param for SSE)
    - Verify user membership in organization
    - Sync organization data to local database
    - Set request.state.org_id
    
    Does NOT handle: Token verification, RLS context setting
    
    Requires: AuthMiddleware to run first (sets request.state.user)
    """
    
    async def dispatch(self, request: Request, call_next):
        # Initialize org state
        request.state.org_id = None
        
        # Extract org ID from header or query param (for SSE)
        org_id = request.headers.get('X-Organization-ID') or request.query_params.get('org_id')
        
        if not org_id:
            return await call_next(request)
        
        # Need authenticated user to verify membership
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            logger.debug(f"Organization header provided but no authenticated user")
            return await call_next(request)
        
        logger.debug(f"Organization context: {org_id} for user: {user_id}")
        
        # Check dev mode source - skip Clerk verification for dev users
        user = getattr(request.state, 'user', {})
        is_dev_auth = user.get('source') in ('headers', 'query', 'fallback')
        
        if is_dev_auth:
            # Dev mode: trust the org ID, auto-sync to DB
            request.state.org_id = org_id
            await self._sync_dev_org(org_id, user_id)
            return await call_next(request)
        
        # Production: verify membership with Clerk
        membership_verified = await self._verify_membership(org_id, user_id)
        
        if membership_verified:
            request.state.org_id = org_id
            logger.debug(f"✅ Verified org context: {org_id} for user: {user_id}")
            await self._sync_org_to_db(org_id, user_id)
        else:
            logger.warning(f"⚠️ User {user_id} not verified as member of org {org_id}")
        
        return await call_next(request)
    
    async def _verify_membership(self, org_id: str, user_id: str) -> bool:
        """Verify user membership in organization via Clerk."""
        try:
            from core.auth.clerk_client import get_clerk_client
            clerk = get_clerk_client()
            members = await clerk.get_organization_members(org_id)
            
            for member in members:
                member_user_id = member.get('public_user_data', {}).get('user_id')
                if member_user_id == user_id:
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Clerk membership check failed: {e}")
            # Fallback to local DB check
            return await self._check_local_membership(org_id, user_id)
    
    async def _check_local_membership(self, org_id: str, user_id: str) -> bool:
        """Check membership in local database as fallback."""
        try:
            from core.database.postgres_client import get_postgres_rls_client
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                return await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM organization_members WHERE org_id = $1 AND user_id = $2)",
                    org_id, user_id
                )
        except Exception as e:
            logger.debug(f"Local membership check failed: {e}")
            return False
    
    async def _sync_org_to_db(self, org_id: str, user_id: str):
        """Sync organization to local database."""
        config = get_config()
        if not config.enable_postgres:
            return
        
        try:
            from core.auth.clerk_client import get_clerk_client
            from core.database.postgres_client import get_postgres_rls_client
            
            clerk = get_clerk_client()
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                # Check if org exists
                org_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM organizations WHERE id = $1)",
                    org_id
                )
                
                if not org_exists:
                    # Fetch org details from Clerk
                    org_name = "Organization"
                    org_slug = f"org-{org_id[-12:]}"
                    try:
                        clerk_org = await clerk.get_organization(org_id)
                        if clerk_org:
                            org_name = clerk_org.get('name', org_name)
                            org_slug = clerk_org.get('slug', org_slug)
                    except Exception:
                        pass
                    
                    await conn.execute(
                        """
                        INSERT INTO organizations (id, name, slug, usage_credits, created_at)
                        VALUES ($1, $2, $3, 0, NOW())
                        ON CONFLICT (id) DO NOTHING
                        """,
                        org_id, org_name, org_slug
                    )
                
                # Ensure membership with correct role
                member_id = f"mem_{uuid.uuid4().hex[:24]}"
                clerk_role = 'org:member'
                
                try:
                    members = await clerk.get_organization_members(org_id)
                    for member in members:
                        if member.get('public_user_data', {}).get('user_id') == user_id:
                            clerk_role = member.get('role', 'org:member')
                            break
                except Exception:
                    pass
                
                await conn.execute(
                    """
                    INSERT INTO organization_members (id, org_id, user_id, role, joined_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (org_id, user_id) DO UPDATE SET role = EXCLUDED.role
                    """,
                    member_id, org_id, user_id, clerk_role
                )
                
        except Exception as e:
            logger.warning(f"Failed to sync org to DB: {e}")
    
    async def _sync_dev_org(self, org_id: str, user_id: str):
        """Sync dev organization to database (best effort)."""
        config = get_config()
        if not config.enable_postgres:
            return
        
        try:
            from core.database.postgres_client import get_postgres_rls_client
            
            pg = await get_postgres_rls_client()
            async with pg.acquire_with_user_context(user_id) as conn:
                # Ensure org exists
                await conn.execute(
                    """
                    INSERT INTO organizations (id, name, slug, usage_credits, created_at)
                    VALUES ($1, $2, $3, 0, NOW())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    org_id, "Dev Organization", f"dev-org-{org_id[-8:]}"
                )
                
                # Ensure membership as admin
                member_id = f"mem_{uuid.uuid4().hex[:24]}"
                await conn.execute(
                    """
                    INSERT INTO organization_members (id, org_id, user_id, role, joined_at)
                    VALUES ($1, $2, $3, 'org:admin', NOW())
                    ON CONFLICT (org_id, user_id) DO NOTHING
                    """,
                    member_id, org_id, user_id
                )
                
            logger.debug(f"✅ DEV: Synced org {org_id} for user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ DEV: Failed to sync org: {e}")
