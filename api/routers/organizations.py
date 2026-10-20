"""
Organizations Router
Handles organization-related endpoints including slug validation
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import re
import httpx
from datetime import datetime, timedelta
import time
from collections import defaultdict
from core.database.postgres_client import get_postgres_rls_client
from core.auth.clerk_client import get_clerk_client
from core.cache import cache

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


class InMemoryRateLimiter:
    """Simple sliding-window rate limiter for fallback scenarios."""

    def __init__(self, calls_per_window: int, window_seconds: int = 60):
        self.calls_per_window = calls_per_window
        self.window_seconds = window_seconds
        self.calls = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        bucket = self.calls.setdefault(key, [])
        self.calls[key] = [t for t in bucket if t > window_start]
        if len(self.calls[key]) >= self.calls_per_window:
            return False
        self.calls[key].append(now)
        return True


invite_fallback_limiter = InMemoryRateLimiter(calls_per_window=10, window_seconds=3600)
slug_rate_limiter = InMemoryRateLimiter(calls_per_window=20, window_seconds=60)


class SlugAvailabilityResponse(BaseModel):
    """Response model for slug availability check"""
    available: bool
    slug: str
    message: Optional[str] = None


class OrganizationResponse(BaseModel):
    """Response model for organization data"""
    id: str
    name: str
    slug: str
    usage_credits: int
    created_at: str
    creator_id: Optional[str] = None  # User ID of creator (None if deleted)


class OrganizationCreate(BaseModel):
    """Request model for creating an organization"""
    name: str = Field(..., min_length=1, max_length=100, description="Organization name")
    slug: str = Field(..., min_length=3, max_length=63, description="URL-safe unique identifier")
    industry: Optional[str] = Field(None, max_length=50, description="Industry category")
    id: Optional[str] = Field(None, description="Optional Clerk Organization ID")


class OrganizationUpdate(BaseModel):
    """Request model for updating an organization"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Organization name")
    industry: Optional[str] = Field(None, max_length=50, description="Industry category")


class AddMemberRequest(BaseModel):
    """Request model for adding a member to an organization"""
    user_id: str = Field(..., description="Clerk user ID to add as member")
    role: Literal["org:admin", "org:member"] = Field(..., description="Member role")


class MemberResponse(BaseModel):
    """Response model for organization member"""
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: str
    joined_at: str


class UpdateMemberRoleRequest(BaseModel):
    """Request model for updating member role"""
    role: Literal["org:admin", "org:member"] = Field(..., description="New member role")


class InviteRequest(BaseModel):
    """Request model for inviting a member"""
    email: str = Field(..., description="Email address to invite")
    role: Literal["org:admin", "org:member"] = Field(default="org:member", description="Member role")


class InvitationResponse(BaseModel):
    """Response model for organization invitation"""
    id: str
    email_address: str
    role: str
    status: str
    created_at: str


def validate_slug_format(slug: str) -> tuple[bool, str]:
    """
    Validate slug format
    - 3-63 characters
    - lowercase letters, numbers, hyphens only
    - no leading/trailing hyphens
    - no consecutive hyphens

    Returns: (is_valid, error_message)
    """
    if len(slug) < 3:
        return False, "Slug must be at least 3 characters"

    if len(slug) > 63:
        return False, "Slug must be 63 characters or less"

    if not re.match(r'^[a-z0-9-]+$', slug):
        return False, "Slug can only contain lowercase letters, numbers, and hyphens"

    if slug.startswith('-') or slug.endswith('-'):
        return False, "Slug cannot start or end with a hyphen"

    if '--' in slug:
        return False, "Slug cannot contain consecutive hyphens"

    # Reserved slugs
    reserved = {'api', 'admin', 'app', 'dashboard', 'settings', 'billing', 'auth', 'login', 'signup', 'register'}
    if slug in reserved:
        return False, "This slug is reserved"

    return True, ""


def check_invitation_rate_limit(user_id: str, org_id: str) -> bool:
    """
    Check if user has exceeded invitation rate limit using Redis.

    Rate limit: 10 invitations per hour per admin.
    Uses Redis sliding window with automatic expiration.

    Args:
        user_id: User ID performing invitation
        org_id: Organization ID

    Returns:
        True if under limit, False if exceeded
    """
    redis_key = f"invite_ratelimit:{user_id}:{org_id}"

    # Preferred path: Redis
    if cache.enabled:
        try:
            current_count = cache.redis.get(redis_key)

            if current_count is None:
                cache.redis.setex(redis_key, 3600, 1)  # 1 hour TTL
                return True

            count = int(current_count)
            if count >= 10:
                return False

            cache.redis.incr(redis_key)
            return True
        except Exception:
            # Fall through to in-memory limiter on Redis failure
            pass

    # Fallback: in-memory limiter (per-process) to avoid failing open
    return invite_fallback_limiter.allow(f"{user_id}:{org_id}")


@router.get("/check-slug/{slug}", response_model=SlugAvailabilityResponse)
async def check_slug_availability(slug: str, request: Request):
    """
    Check if an organization slug is available.

    Requires authentication to prevent enumeration attacks.

    Args:
        slug: URL-safe organization identifier to check

    Returns:
        SlugAvailabilityResponse with availability status
    """
    # Require authentication to prevent slug enumeration
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Rate limiting per user (not IP) for authenticated requests
    if not slug_rate_limiter.allow(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Validate slug format first
    is_valid, error_msg = validate_slug_format(slug)
    if not is_valid:
        return SlugAvailabilityResponse(
            available=False,
            slug=slug,
            message=error_msg
        )

    try:
        pg = await get_postgres_rls_client()

        # Use SECURITY DEFINER function to bypass RLS for slug checking
        # This avoids infinite recursion in organization_members RLS policies
        async with pg.pool.acquire() as conn:
            is_available = await conn.fetchval(
                "SELECT public.check_organization_slug_available($1)",
                slug
            )

        if not is_available:
            return SlugAvailabilityResponse(
                available=False,
                slug=slug,
                message="This slug is already taken"
            )

        return SlugAvailabilityResponse(
            available=True,
            slug=slug,
            message="Slug is available"
        )

    except Exception as e:
        # Log error but don't expose details to client
        print(f"Error checking slug availability: {e}")
        raise HTTPException(
            status_code=500,
            detail="Unable to check slug availability. Please try again."
        )


@router.get("/my-organizations", response_model=List[OrganizationResponse])
async def get_my_organizations(request: Request):
    """
    Get all organizations the current user is a member of

    Requires authentication via RLS middleware

    Returns:
        List of organizations with basic info
    """
    # Get user_id from request state (set by RLS middleware)
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()
        orgs = await pg.get_user_organizations(user_id)
        return orgs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch organizations: {str(e)}")


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: str, request: Request):
    """
    Get organization details by ID

    Requires authentication and membership in the organization

    Args:
        org_id: Organization ID to fetch

    Returns:
        Organization details
    """
    # Get user_id from request state (set by RLS middleware)
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()
        org = await pg.get_organization_by_id(user_id, org_id)

        if not org:
            raise HTTPException(status_code=404, detail="Organization not found or access denied")

        return org
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch organization: {str(e)}")


# ========== Organization CRUD Endpoints ==========

@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(data: OrganizationCreate, request: Request):
    """
    Create a new organization.

    Clerk is the source of truth - creates in Clerk first, then syncs to local DB.
    The creator will be added as an admin member automatically.

    Args:
        data: Organization creation data (name, slug, industry)

    Returns:
        Created organization data
    """
    import logging
    logger = logging.getLogger(__name__)

    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate slug format
    is_valid, error_msg = validate_slug_format(data.slug)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        clerk = get_clerk_client()
        public_metadata = {"industry": data.industry} if data.industry else None
        clerk_org = None

        # If ID provided, frontend already created in Clerk - skip Clerk creation
        if data.id:
            org_id = data.id
            logger.info(f"Organization {org_id} already exists in Clerk (frontend-created)")
        else:
            # Create in Clerk FIRST (source of truth)
            try:
                clerk_org = await clerk.create_organization(
                    name=data.name,
                    slug=data.slug,
                    created_by=user_id,
                    public_metadata=public_metadata
                )
                org_id = clerk_org["id"]
                logger.info(f"Created organization {org_id} in Clerk")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 422:
                    # Clerk returns 422 for duplicate slug or invalid data
                    raise HTTPException(status_code=409, detail="Organization slug already exists or invalid data")
                raise HTTPException(status_code=500, detail=f"Failed to create organization in Clerk: {e.response.status_code}")

        # Step 2: Sync to local database
        # Note: Webhook will also fire, but we sync immediately for faster response
        try:
            pg = await get_postgres_rls_client()
            org = await pg.create_organization(
                creator_id=user_id,
                name=data.name,
                slug=data.slug,
                industry=data.industry,
                id=org_id  # Use Clerk's org ID
            )
            logger.info(f"Synced organization {org_id} to local database")
            return org
        except Exception as db_error:
            # Log but don't fail - Clerk org exists, webhook will sync
            logger.warning(f"Failed to sync organization to local DB (webhook will retry): {db_error}")
            # Return basic response
            return OrganizationResponse(
                id=org_id,
                name=data.name,
                slug=data.slug,
                usage_credits=1000,
                created_at=clerk_org.get("created_at") if clerk_org else datetime.utcnow().isoformat(),
                creator_id=user_id
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")


@router.put("/{org_id}", response_model=dict)
async def update_organization(org_id: str, data: OrganizationUpdate, request: Request):
    """
    Update organization details (admin only)

    Args:
        org_id: Organization ID
        data: Fields to update

    Returns:
        Success message
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()

        # Build updates dict (only non-None fields)
        updates = {}
        if data.name is not None:
            updates['name'] = data.name
        if data.industry is not None:
            updates['public_metadata'] = {'industry': data.industry}

        if not updates:
            return {"success": True, "message": "No updates provided"}

        success = await pg.update_organization(user_id, org_id, **updates)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to update organization")

        return {"success": True, "message": "Organization updated successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update organization: {str(e)}")


@router.delete("/{org_id}", response_model=dict)
async def delete_organization(org_id: str, request: Request):
    """
    Delete organization (creator or any admin if creator is NULL)

    Clerk is source of truth - delete from Clerk first, then sync local DB.

    Args:
        org_id: Organization ID

    Returns:
        Success message
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()
        
        # Step 1: Verify permission (creator or admin if creator is NULL)
        async with pg.acquire_with_user_context(user_id) as conn:
            org_row = await conn.fetchrow(
                "SELECT creator_id FROM organizations WHERE id = $1",
                org_id
            )
            if not org_row:
                raise HTTPException(status_code=404, detail="Organization not found")
            
            creator_id = org_row['creator_id']
            
            # If creator exists, only creator can delete
            if creator_id and creator_id != user_id:
                raise HTTPException(status_code=403, detail="Only the creator can delete this organization")
            
            # If creator is NULL (orphaned), any admin can delete
            if not creator_id:
                is_admin = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                    )
                """, org_id, user_id)
                if not is_admin:
                    raise HTTPException(status_code=403, detail="Only an admin can delete this organization")

        # Step 2: Delete from Clerk FIRST (source of truth)
        clerk = get_clerk_client()
        try:
            await clerk.delete_organization(org_id)
            logger.info(f"Deleted organization {org_id} from Clerk")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Organization {org_id} not found in Clerk (already deleted?)")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to delete from Clerk: {e.response.status_code}")
        
        # Step 3: Delete from local database (sync)
        try:
            async with pg.acquire_with_user_context(user_id) as conn:
                await conn.execute("DELETE FROM organizations WHERE id = $1", org_id)
            logger.info(f"Deleted organization {org_id} from local database")
        except Exception as db_error:
            # Log but don't fail - Clerk deletion succeeded
            logger.error(f"Failed to sync organization deletion to local DB: {db_error}")

        return {"success": True, "message": "Organization deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete organization: {str(e)}")


@router.post("/{org_id}/leave", response_model=dict)
async def leave_organization(org_id: str, request: Request):
    """
    Leave an organization (self-removal)

    Members can remove themselves from an organization.
    Note: The last admin cannot leave without first promoting another member.
    
    Clerk is the source of truth - we remove from Clerk first, then sync local DB.

    Args:
        org_id: Organization ID

    Returns:
        Success message
    """
    import logging
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Step 1: Remove from Clerk FIRST (source of truth)
        # This is the authoritative action - if Clerk fails, we fail
        clerk = get_clerk_client()
        try:
            await clerk.remove_organization_member(org_id, user_id)
            logging.info(f"Successfully removed {user_id} from org {org_id} in Clerk")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # User not in org in Clerk - maybe already left
                logging.warning(f"User {user_id} not found in org {org_id} in Clerk (already left?)")
            elif e.response.status_code == 403:
                # Clerk's last-admin protection kicked in
                raise HTTPException(
                    status_code=403, 
                    detail="Cannot leave: you are the last admin. Promote another member first."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to leave organization: Clerk error {e.response.status_code}"
                )

        # Step 2: Clean up local database (best effort - may not exist there)
        try:
            pg = await get_postgres_rls_client()
            await pg.leave_organization(org_id=org_id, user_id=user_id)
        except ValueError:
            # User wasn't in local DB - that's fine, Clerk was source of truth
            logging.info(f"User {user_id} not in local DB for org {org_id} (Clerk-only membership)")
        except Exception as db_error:
            # Log but don't fail - Clerk removal was successful
            logging.warning(f"Failed to clean up local DB after leaving org: {db_error}")

        return {"success": True, "message": "You have left the organization successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to leave organization: {str(e)}")


# ========== Member Management Endpoints ==========

@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def get_organization_members(org_id: str, request: Request):
    """
    Get all members of an organization from Clerk (source of truth).

    Requires membership in the organization.

    Args:
        org_id: Organization ID

    Returns:
        List of members with user details
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # First verify user is a member (check local DB for RLS)
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            is_member = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                )
            """, org_id, user_id)
            
            if not is_member:
                raise HTTPException(status_code=403, detail="Not a member of this organization")
        
        # Fetch members from Clerk (source of truth)
        clerk = get_clerk_client()
        clerk_members = await clerk.get_organization_members(org_id)
        
        # Transform Clerk response to our MemberResponse format
        members = []
        for membership in clerk_members:
            # Clerk membership structure: {id, role, created_at, public_user_data: {user_id, ...}}
            public_user_data = membership.get('public_user_data', {})
            member_user_id = public_user_data.get('user_id')
            
            # Get email and name from public_user_data or identifier
            email = public_user_data.get('identifier')  # Usually the email
            first_name = public_user_data.get('first_name', '')
            last_name = public_user_data.get('last_name', '')
            name = f"{first_name} {last_name}".strip() or None
            
            members.append(MemberResponse(
                user_id=member_user_id or membership.get('id', ''),
                email=email,
                name=name,
                role=membership.get('role', 'org:member'),
                joined_at=membership.get('created_at', '')
            ))
        
        logger.info(f"Fetched {len(members)} members from Clerk for org {org_id}")
        return members
        
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Organization not found")
        logger.error(f"Clerk API error fetching members: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch members from Clerk: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to fetch members: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch members: {str(e)}")


@router.post("/{org_id}/members", response_model=dict, status_code=201)
async def add_organization_member(org_id: str, data: AddMemberRequest, request: Request):
    """
    Add a member to an organization (admin only)

    Args:
        org_id: Organization ID
        data: Member data (user_id and role)

    Returns:
        Success message
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()
        success = await pg.add_organization_member(
            org_id=org_id,
            user_id=data.user_id,
            role=data.role,
            requesting_user_id=user_id
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to add member")

        return {"success": True, "message": "Member added successfully"}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add member: {str(e)}")


@router.put("/{org_id}/members/{member_user_id}/role", response_model=MemberResponse)
async def update_member_role(org_id: str, member_user_id: str, data: UpdateMemberRoleRequest, request: Request):
    """
    Update a member's role in an organization (admin only)
    
    Clerk is source of truth - update Clerk first, then sync local DB.

    Args:
        org_id: Organization ID
        member_user_id: User ID whose role to update
        data: New role data

    Returns:
        Updated member information
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        pg = await get_postgres_rls_client()
        
        # Step 1: Verify requesting user is admin
        async with pg.acquire_with_user_context(user_id) as conn:
            is_admin = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                )
            """, org_id, user_id)
            
            if not is_admin:
                raise HTTPException(status_code=403, detail="Only admins can update member roles")

        # Step 2: Update in Clerk FIRST (source of truth)
        clerk = get_clerk_client()
        try:
            await clerk.update_organization_member_role(org_id, member_user_id, data.role)
            logger.info(f"Updated role for {member_user_id} to {data.role} in Clerk")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Member not found in Clerk")
            elif e.response.status_code == 422:
                # Clerk's last-admin protection
                raise HTTPException(status_code=400, detail="Cannot demote the last admin")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to update role in Clerk: {e.response.status_code}")

        # Step 3: Sync to local database
        try:
            async with pg.acquire_with_user_context(user_id) as conn:
                await conn.execute("""
                    UPDATE organization_members
                    SET role = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, member_user_id, data.role)
        except Exception as db_error:
            logger.error(f"Failed to sync role update to local DB: {db_error}")

        # Fetch updated member info from Clerk
        clerk_members = await clerk.get_organization_members(org_id)
        updated_member = None
        for m in clerk_members:
            if m.get('public_user_data', {}).get('user_id') == member_user_id:
                public_data = m.get('public_user_data', {})
                first_name = public_data.get('first_name', '')
                last_name = public_data.get('last_name', '')
                updated_member = MemberResponse(
                    user_id=member_user_id,
                    email=public_data.get('identifier'),
                    name=f"{first_name} {last_name}".strip() or None,
                    role=m.get('role', data.role),
                    joined_at=m.get('created_at', '')
                )
                break

        if not updated_member:
            raise HTTPException(status_code=404, detail="Member not found after update")

        return updated_member
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update member role: {str(e)}")


@router.delete("/{org_id}/members/{member_user_id}", response_model=dict)
async def remove_organization_member(org_id: str, member_user_id: str, request: Request):
    """
    Remove a member from an organization (admin only)
    
    Clerk is source of truth - remove from Clerk first, then sync local DB.

    Args:
        org_id: Organization ID
        member_user_id: User ID to remove

    Returns:
        Success message
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Prevent removing self (use leave endpoint instead)
    if member_user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself. Use the leave endpoint instead.")

    try:
        pg = await get_postgres_rls_client()
        
        # Step 1: Verify requesting user is admin
        async with pg.acquire_with_user_context(user_id) as conn:
            is_admin = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                )
            """, org_id, user_id)
            
            if not is_admin:
                raise HTTPException(status_code=403, detail="Only admins can remove members")

        # Step 2: Remove from Clerk FIRST (source of truth)
        clerk = get_clerk_client()
        try:
            await clerk.remove_organization_member(org_id, member_user_id)
            logger.info(f"Removed member {member_user_id} from org {org_id} in Clerk")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Member {member_user_id} not found in org {org_id} in Clerk")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to remove from Clerk: {e.response.status_code}")

        # Step 3: Sync to local database
        try:
            async with pg.acquire_with_user_context(user_id) as conn:
                await conn.execute("""
                    DELETE FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, member_user_id)
        except Exception as db_error:
            logger.error(f"Failed to sync member removal to local DB: {db_error}")

        return {"success": True, "message": "Member removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove member: {str(e)}")


# ========== Invitation Management Endpoints ==========

@router.post("/{org_id}/invite", response_model=InvitationResponse, status_code=201)
async def invite_member(org_id: str, data: InviteRequest, request: Request):
    """
    Invite a new member to an organization by email (admin only).

    Creates a Clerk invitation that the recipient can accept to join.
    Rate limited to 10 invitations per hour per admin.

    Args:
        org_id: Organization ID
        data: Invitation data (email and role)

    Returns:
        Invitation details from Clerk
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Verify user is admin
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            is_admin = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                )
            """, org_id, user_id)

            if not is_admin:
                raise HTTPException(status_code=403, detail="Only admins can invite members")

        # Check rate limit
        if not check_invitation_rate_limit(user_id, org_id):
            raise HTTPException(
                status_code=429,
                detail="Invitation rate limit exceeded. Maximum 10 invitations per hour."
            )

        # Create invitation via Clerk API
        clerk = get_clerk_client()
        invitation = await clerk.create_organization_invitation(
            org_id=org_id,
            email=data.email,
            role=data.role,
            inviter_user_id=user_id
        )

        return InvitationResponse(
            id=invitation["id"],
            email_address=invitation["email_address"],
            role=invitation["role"],
            status=invitation["status"],
            created_at=invitation["created_at"]
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 422:
            raise HTTPException(status_code=400, detail="Invalid email address or user already invited")
        elif e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Clerk API rate limit exceeded. Please try again later.")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to create invitation: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invite member: {str(e)}")


@router.get("/{org_id}/invitations", response_model=List[InvitationResponse])
async def list_invitations(org_id: str, request: Request, status: Optional[str] = None):
    """
    List all invitations for an organization.

    Requires membership in the organization.

    Args:
        org_id: Organization ID
        status: Optional filter by status (pending, accepted, revoked, expired)

    Returns:
        List of invitations
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Verify user is member
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            is_member = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                )
            """, org_id, user_id)

            if not is_member:
                raise HTTPException(status_code=403, detail="You must be a member to view invitations")

        # Get invitations from Clerk
        clerk = get_clerk_client()
        status_filter = [status] if status else None
        invitations = await clerk.list_organization_invitations(org_id, status=status_filter)

        return [
            InvitationResponse(
                id=inv["id"],
                email_address=inv["email_address"],
                role=inv["role"],
                status=inv["status"],
                created_at=inv["created_at"]
            )
            for inv in invitations
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list invitations: {str(e)}")


@router.delete("/{org_id}/invitations/{invitation_id}", response_model=dict)
async def revoke_invitation(org_id: str, invitation_id: str, request: Request):
    """
    Revoke (cancel) a pending invitation (admin only).

    Args:
        org_id: Organization ID
        invitation_id: Invitation ID to revoke

    Returns:
        Success message
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Verify user is admin
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            is_admin = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                )
            """, org_id, user_id)

            if not is_admin:
                raise HTTPException(status_code=403, detail="Only admins can revoke invitations")

        # Revoke via Clerk API
        clerk = get_clerk_client()
        await clerk.revoke_organization_invitation(org_id, invitation_id, user_id)

        return {"success": True, "message": "Invitation revoked successfully"}

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Invitation not found")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to revoke invitation: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke invitation: {str(e)}")


@router.post("/{org_id}/invitations/{invitation_id}/resend", response_model=InvitationResponse, status_code=201)
async def resend_invitation(org_id: str, invitation_id: str, request: Request):
    """
    Resend an invitation by revoking and creating a new one (admin only).

    Clerk doesn't have native resend, so we implement it as revoke + recreate.

    Args:
        org_id: Organization ID
        invitation_id: Original invitation ID to resend

    Returns:
        New invitation details
    """
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # Verify user is admin
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_user_context(user_id) as conn:
            is_admin = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM organization_members
                    WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                )
            """, org_id, user_id)

            if not is_admin:
                raise HTTPException(status_code=403, detail="Only admins can resend invitations")

        clerk = get_clerk_client()

        # Get original invitation details
        invitations = await clerk.list_organization_invitations(org_id)
        original = next((inv for inv in invitations if inv["id"] == invitation_id), None)

        if not original:
            raise HTTPException(status_code=404, detail="Invitation not found")

        if original["status"] == "accepted":
            raise HTTPException(status_code=400, detail="Cannot resend an accepted invitation")

        email = original["email_address"]
        role = original["role"]

        # Revoke old invitation (if pending)
        if original["status"] == "pending":
            try:
                await clerk.revoke_organization_invitation(org_id, invitation_id, user_id)
            except:
                pass  # Ignore errors if already revoked

        # Check rate limit
        if not check_invitation_rate_limit(user_id, org_id):
            raise HTTPException(
                status_code=429,
                detail="Invitation rate limit exceeded. Maximum 10 invitations per hour."
            )

        # Create new invitation
        new_invitation = await clerk.create_organization_invitation(
            org_id=org_id,
            email=email,
            role=role,
            inviter_user_id=user_id
        )

        return InvitationResponse(
            id=new_invitation["id"],
            email_address=new_invitation["email_address"],
            role=new_invitation["role"],
            status=new_invitation["status"],
            created_at=new_invitation["created_at"]
        )

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 422:
            raise HTTPException(status_code=400, detail="Invalid email or invitation data")
        elif e.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Clerk API rate limit exceeded. Please try again later.")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to resend invitation: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend invitation: {str(e)}")
