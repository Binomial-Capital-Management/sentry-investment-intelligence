"""
FastAPI middleware for PostgreSQL RLS user context.
Sets user context for each request based on authentication.

Following CODING_RULES.md: KISS, simple middleware pattern.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.auth import get_clerk_auth
from fastapi.security import HTTPAuthorizationCredentials
from core.config import get_config
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)


class RLSContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject PostgreSQL RLS context based on authenticated user.
    This ensures all database operations in a request are properly isolated.
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request with proper RLS context.
        Note: This is a simplified version - in production you'd want
        to handle this at the connection level for each DB operation.
        """
        
        # Store user info in request state for downstream use
        request.state.user_id = None
        request.state.clerk_user_id = None
        request.state.org_id = None  # Organization context for workspace switching
        
        # Skip auth for health checks, public endpoints, and WebSocket connections
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json", "/v6/health"] or request.url.path.startswith("/ws/"):
            return await call_next(request)
        
        # Initialize config early to avoid UnboundLocalError if exceptions occur before assignment
        config = get_config()
        try:
            # Get current user from Clerk auth if enabled

            # SECURE DEV OVERRIDE: Requires both secret key and user ID
            # Works regardless of ENABLE_AUTH setting for dev mode
            import os

            # Check if we're in production
            is_production = os.getenv('ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production'

            # Get dev secret key from environment
            dev_secret_key = os.getenv('DEV_SECRET')

            # Check for dev bypass attempt (works regardless of enable_auth)
            if not is_production and dev_secret_key:
                # Check headers for dev authentication
                provided_secret = request.headers.get('X-Dev-Secret')
                provided_user_id = request.headers.get('X-Dev-User-Id')

                # Validate both secret key AND user ID are provided and correct
                if provided_secret == dev_secret_key and provided_user_id:
                    request.state.user_id = provided_user_id
                    request.state.clerk_user_id = f"dev_{provided_user_id}"
                    request.state.auth_checked = True
                    logger.warning(f"⚠️ DEV MODE: Authenticated with secure dev key for user: {provided_user_id}")

                    # Extract org context (header or query param for SSE)
                    # In dev mode, skip Clerk verification (dev users don't exist in Clerk)
                    org_id_header = request.headers.get('X-Organization-ID') or request.query_params.get('org_id')
                    if org_id_header:
                        request.state.org_id = org_id_header
                        logger.debug(f"✅ DEV AUTH PATH - Set organization context: {org_id_header}")
                        
                        # Auto-sync to local DB for dev mode (best effort)
                        try:
                            import uuid
                            pg = await get_postgres_rls_client()
                            async with pg.acquire_with_user_context(provided_user_id) as conn:
                                # Ensure org exists
                                await conn.execute(
                                    """
                                    INSERT INTO organizations (id, name, slug, usage_credits, created_at)
                                    VALUES ($1, $2, $3, 0, NOW())
                                    ON CONFLICT (id) DO NOTHING
                                    """,
                                    org_id_header, "Dev Organization", f"dev-org-{org_id_header[-8:]}"
                                )
                                # Ensure membership as admin for dev
                                member_id = f"mem_{uuid.uuid4().hex[:24]}"
                                await conn.execute(
                                    """
                                    INSERT INTO organization_members (id, org_id, user_id, role, joined_at)
                                    VALUES ($1, $2, $3, 'org:admin', NOW())
                                    ON CONFLICT (org_id, user_id) DO NOTHING
                                    """,
                                    member_id, org_id_header, provided_user_id
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ DEV AUTH PATH - Failed to sync: {e}")

                    response = await call_next(request)
                    return response
                elif provided_secret or provided_user_id:
                    # Someone tried to use dev bypass but failed authentication
                    logger.error(f"Failed dev authentication attempt from {request.client.host}")
                    raise HTTPException(status_code=403, detail="Invalid dev credentials")

            if config.enable_auth:
                auth = get_clerk_auth()
                
                # Try to get authenticated user
                try:
                    # For protected endpoints, use required_auth
                    if request.url.path.startswith("/api/v6/user/"):
                        current_user = await auth.required_auth(request)
                    else:
                        # For other endpoints, use optional auth from request
                        current_user = await auth.optional_auth_from_request(request)
                        
                        # SSE/EventSource cannot set headers; try ticket first, then token
                        if not current_user:
                            # First try SSE ticket (preferred - doesn't expose JWT in URL)
                            ticket_from_qs = request.query_params.get('ticket')
                            if ticket_from_qs:
                                try:
                                    from api.routers.sse_tickets import validate_and_consume_ticket
                                    ticket_user = await validate_and_consume_ticket(ticket_from_qs)
                                    if ticket_user:
                                        current_user = ticket_user
                                        logger.debug(f"SSE ticket validated for user: {ticket_user.get('user_id')}")
                                except Exception as e:
                                    logger.debug(f"SSE ticket validation failed: {e}")
                            
                            # Fallback: allow token via query param (legacy, less secure)
                            if not current_user:
                                token_from_qs = request.query_params.get('token')
                                if token_from_qs:
                                    try:
                                        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_from_qs)
                                        current_user = await auth.verify_token(credentials)
                                    except Exception as e:
                                        logger.debug(f"Query token verification failed: {e}")
                    
                    if current_user:
                        clerk_user_id = current_user.get('user_id')

                        # Simply use Clerk ID for both fields - no UUID lookup
                        if clerk_user_id:
                            request.state.user_id = clerk_user_id
                            request.state.clerk_user_id = clerk_user_id
                            logger.debug(f"Set RLS context for Clerk user: {clerk_user_id}")
                    else:
                        # Dev-friendly SSE: support dev credentials via query params when headers unavailable
                        try:
                            if not is_production and dev_secret_key:
                                qs_dev_secret = request.query_params.get('x_dev_secret')
                                qs_dev_user = request.query_params.get('x_dev_user_id')
                                if qs_dev_secret == dev_secret_key and qs_dev_user:
                                    request.state.user_id = qs_dev_user
                                    request.state.clerk_user_id = f"dev_{qs_dev_user}"
                                    request.state.auth_checked = True
                                    logger.warning(f"⚠️ DEV MODE (QS): Authenticated with secure dev key for user: {qs_dev_user}")
                        except Exception as e:
                            logger.debug(f"Dev QS auth check failed: {e}")
                
                except HTTPException:
                    # Auth failed for required endpoints
                    raise
                except Exception as e:
                    logger.error(f"Error in auth middleware: {e}")

            # Dev mode fallback when auth is disabled
            if not request.state.user_id and not config.enable_auth:
                import os
                dev_user_id = os.getenv('DEV_INTERNAL_USER_ID', 'dev-local-user')
                request.state.user_id = dev_user_id
                request.state.clerk_user_id = f"dev_{dev_user_id}"
                logger.warning(f"⚠️ DEV MODE: Using fixed internal user ID: {dev_user_id} - NOT FOR PRODUCTION")

            # Extract organization context from header OR query params (for SSE/EventSource)
            # SSE doesn't support custom headers, so we also check query params
            org_id_header = request.headers.get('X-Organization-ID') or request.query_params.get('org_id')
            logger.debug(f"🔍 MIDDLEWARE - Organization context: {org_id_header}")
            
            if org_id_header and request.state.user_id:
                # Verify membership with Clerk before setting org context (security)
                from core.auth.clerk_client import get_clerk_client
                import uuid
                
                membership_verified = False
                clerk_role = 'org:member'  # Default role if verification succeeds
                
                try:
                    clerk = get_clerk_client()
                    members = await clerk.get_organization_members(org_id_header)
                    # Check if user is actually a member in Clerk
                    for member in members:
                        member_user_id = member.get('public_user_data', {}).get('user_id')
                        if member_user_id == request.state.user_id:
                            membership_verified = True
                            clerk_role = member.get('role', 'org:member')
                            break
                except Exception as clerk_err:
                    # If Clerk is unreachable, fall back to local DB check
                    logger.warning(f"⚠️ MIDDLEWARE - Clerk membership check failed: {clerk_err}")
                    try:
                        pg = await get_postgres_rls_client()
                        async with pg.acquire_with_user_context(request.state.user_id) as conn:
                            membership_verified = await conn.fetchval(
                                "SELECT EXISTS(SELECT 1 FROM organization_members WHERE org_id = $1 AND user_id = $2)",
                                org_id_header, request.state.user_id
                            )
                    except Exception:
                        pass
                
                if not membership_verified:
                    logger.warning(f"⚠️ MIDDLEWARE - User {request.state.user_id} not verified as member of org {org_id_header}")
                    # Don't set org context - user will operate in personal workspace
                else:
                    # Set verified org context
                    request.state.org_id = org_id_header
                    logger.debug(f"✅ MIDDLEWARE - Verified org context: {org_id_header} for user: {request.state.user_id}")
                    
                    # Sync to local DB for RLS (best effort, already verified with Clerk)
                    try:
                        pg = await get_postgres_rls_client()
                        async with pg.acquire_with_user_context(request.state.user_id) as conn:
                            # Ensure organization exists
                            org_exists = await conn.fetchval(
                                "SELECT EXISTS(SELECT 1 FROM organizations WHERE id = $1)",
                                org_id_header
                            )
                            
                            if not org_exists:
                                # Fetch org details from Clerk
                                org_name = "Organization"
                                org_slug = f"org-{org_id_header[-12:]}"
                                try:
                                    clerk_org = await clerk.get_organization(org_id_header)
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
                                    org_id_header, org_name, org_slug
                                )
                            
                            # Ensure membership exists with correct role
                            member_id = f"mem_{uuid.uuid4().hex[:24]}"
                            await conn.execute(
                                """
                                INSERT INTO organization_members (id, org_id, user_id, role, joined_at)
                                VALUES ($1, $2, $3, $4, NOW())
                                ON CONFLICT (org_id, user_id) DO UPDATE SET role = EXCLUDED.role
                                """,
                                member_id, org_id_header, request.state.user_id, clerk_role
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ MIDDLEWARE - Failed to sync to local DB: {e}")

            # Process the request
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Pass through HTTP exceptions (like 401 Unauthorized)
            raise
        except Exception as e:
            logger.error(f"Unexpected error in RLS middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )


def get_user_context(request: Request) -> Optional[Dict[str, Any]]:
    """
    Helper function to get user context from request state.
    Use this in route handlers to access user and organization information.
    """
    if hasattr(request.state, 'user_id') and request.state.user_id:
        return {
            'user_id': request.state.user_id,
            'clerk_user_id': getattr(request.state, 'clerk_user_id', None),
            'org_id': getattr(request.state, 'org_id', None)
        }
    return None
