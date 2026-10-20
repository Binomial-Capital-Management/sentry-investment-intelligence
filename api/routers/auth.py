"""
Authentication endpoints for Binomial Risk Analyst.
Handles Clerk webhooks and user management.

Following CODING_RULES.md: KISS, MVP first, no hardcoding.
August 2025 best practices: Svix verification, async PostgreSQL
"""

from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
import json
import base64
import hashlib
import hmac
import time

# Optional Svix import with graceful fallback
try:
    from svix.webhooks import Webhook, WebhookVerificationError  # type: ignore
    SVIX_AVAILABLE = True
except Exception:  # Svix not installed or incompatible
    SVIX_AVAILABLE = False

    class WebhookVerificationError(Exception):
        pass

    Webhook = None  # type: ignore

from core.config import get_config
from core.auth import get_clerk_auth
from core.database import get_postgres_client
from core.database.postgres_client import get_postgres_rls_client
import uuid

logger = logging.getLogger(__name__)
config = get_config()

router = APIRouter(prefix="/auth")


async def _create_organization_for_user(user_id: str, org_data: Dict[str, Any]) -> None:
    """
    Create organization and add user as admin member

    Args:
        user_id: Clerk user ID
        org_data: Organization data from pendingOrgData (name, slug, industry, etc.)
    """
    pg = await get_postgres_rls_client()

    # Generate organization ID
    org_id = f"org_{uuid.uuid4().hex[:24]}"
    org_name = org_data.get("organizationName")
    slug = org_data.get("slug")

    async with pg.pool.acquire() as conn:
        # Create organization
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, creator_id, usage_credits)
            VALUES ($1, $2, $3, $4, $5)
            """,
            org_id, org_name, slug, user_id, 1000
        )

        # Add user as admin member
        member_id = f"mem_{org_id}_{user_id}"
        await conn.execute(
            """
            INSERT INTO organization_members (id, org_id, user_id, role)
            VALUES ($1, $2, $3, $4)
            """,
            member_id, org_id, user_id, "org:admin"
        )


def _verify_clerk_webhook(body: bytes, headers: Dict[str, Any], secret: str) -> Dict[str, Any]:
    """
    Verify Clerk webhook using Svix when available, otherwise perform manual HMAC verification.

    Manual verification implements the Svix scheme:
      signed = base64(hmac_sha256(key=base64_decode(secret_wo_prefix),
                                  msg=f"{id}.{timestamp}.{raw_body}"))
      Compare against values in 'svix-signature' header.
    
    Also validates timestamp to prevent replay attacks (within 5 minutes).
    """
    import time
    
    # Normalize header keys
    norm_headers = {str(k).lower(): v for k, v in (headers or {}).items()}

    msg_id = norm_headers.get("svix-id")
    timestamp = norm_headers.get("svix-timestamp")
    sig_header = norm_headers.get("svix-signature")

    if not msg_id or not timestamp or not sig_header:
        raise WebhookVerificationError("Missing Svix signature headers")

    # Validate timestamp to prevent replay attacks (within 5 minutes)
    try:
        timestamp_int = int(timestamp)
        current_time = int(time.time())
        tolerance_seconds = 300  # 5 minutes
        if abs(current_time - timestamp_int) > tolerance_seconds:
            logger.warning(f"Webhook timestamp outside tolerance: {timestamp_int} vs {current_time}")
            raise WebhookVerificationError("Webhook timestamp too old or in future")
    except ValueError:
        raise WebhookVerificationError("Invalid timestamp format")

    if SVIX_AVAILABLE:
        # Svix verifies and returns the parsed payload as a dict
        wh = Webhook(secret)
        payload_dict = wh.verify(body, norm_headers)
        return payload_dict

    # Manual verification path
    try:
        secret_str = str(secret)
        if secret_str.startswith("whsec_"):
            secret_str = secret_str[len("whsec_") :]
        
        # Decode the base64 secret
        key = base64.b64decode(secret_str)

        # Svix signs: msg_id + "." + timestamp + "." + raw_body
        to_sign = f"{msg_id}.{timestamp}.".encode() + body
        digest = hmac.new(key, to_sign, hashlib.sha256).digest()
        computed_sig = base64.b64encode(digest).decode()
        
        # Parse the signature header (format: "v1,BASE64SIG" or multiple versions separated by spaces)
        provided_sigs = []
        raw = str(sig_header)
        for token in raw.split():
            token = token.strip()
            if "," in token:
                parts = token.split(",", 1)
                if len(parts) == 2:
                    provided_sigs.append(parts[1].strip())
        
        # Compare signatures using constant-time comparison
        match = any(hmac.compare_digest(computed_sig, s) for s in provided_sigs)
        if not match:
            logger.warning(f"Webhook signature mismatch for message {msg_id}")
            raise WebhookVerificationError("Invalid webhook signature")

        return json.loads(body.decode() or "{}")
    except WebhookVerificationError:
        raise
    except Exception as e:
        raise WebhookVerificationError(f"Verification error: {e}")


# Simple in-memory rate limiter for webhook endpoints (per client IP)
class SimpleRateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls: Dict[str, list[float]] = {}

    def check(self, key: str) -> bool:
        now = time.time()
        window_start = now - 60
        bucket = self.calls.setdefault(key, [])
        # drop entries outside window
        self.calls[key] = [t for t in bucket if t > window_start]
        if len(self.calls[key]) >= self.calls_per_minute:
            return False
        self.calls[key].append(now)
        return True


webhook_rate_limiter = SimpleRateLimiter(calls_per_minute=60)

@router.post("/webhook/clerk")
async def clerk_webhook(request: Request):
    """
    Webhook endpoint for Clerk events.
    Syncs user data when users sign up or update their profile.
    Uses Svix for secure webhook verification (2025 best practice).
    """
    if not config.enable_auth:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Authentication not enabled"}
        )

    # Basic rate limit to mitigate DoS even with a valid signature
    client_ip = request.client.host if request.client else "unknown"
    if not webhook_rate_limiter.check(client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Rate limit exceeded"}
        )
    
    # Verify webhook signature (Svix if available, otherwise manual HMAC)
    webhook_secret = config.clerk_webhook_secret
    if not webhook_secret:
        logger.warning("Clerk webhook secret not configured")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Webhook not configured"}
        )
    
    # Get the raw body and headers for verification
    body = await request.body()
    headers = dict(request.headers)
    
    # Verify signature
    try:
        payload = _verify_clerk_webhook(body, headers, webhook_secret)
    except WebhookVerificationError as e:
        logger.warning(f"Webhook verification failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Invalid webhook signature"}
        )
    
    try:
        event_type = payload.get("type")
        data = payload.get("data", {})
        
        # Handle Clerk test webhook
        if event_type == "test" or event_type == "webhook.test":
            logger.info("Clerk test webhook received")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "success", "message": "Test webhook received"}
            )
        
        # Handle different event types
        if event_type == "user.created":
            # New user signed up
            user_id = data.get("id")
            email = data.get("email_addresses", [{}])[0].get("email_address")
            name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()

            logger.info(f"New user created: {user_id}")

            # Sync to PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg_client = await get_postgres_client()
                    await pg_client.upsert_user(user_id, email, name)
                    logger.info(f"User synced to PostgreSQL: {user_id}")
                except Exception as e:
                    logger.error(f"Failed to sync user to PostgreSQL: {e}")

                # Check for pending organization data
                unsafe_metadata = data.get("unsafe_metadata", {})
                pending_org_data = unsafe_metadata.get("pendingOrgData")

                if pending_org_data:
                    logger.info(f"Creating organization for user: {email}")
                    try:
                        await _create_organization_for_user(user_id, pending_org_data)
                        logger.info(f"Organization created successfully")
                    except Exception as e:
                        logger.error(f"Failed to create organization: {e}")
            
        elif event_type == "user.updated":
            # User profile updated
            user_id = data.get("id")
            email = data.get("email_addresses", [{}])[0].get("email_address")
            name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            
            logger.info(f"User updated: {user_id}")
            
            # Update in PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg_client = await get_postgres_client()
                    await pg_client.upsert_user(user_id, email, name)
                    logger.info(f"User updated in PostgreSQL: {user_id}")
                except Exception as e:
                    logger.error(f"Failed to update user in PostgreSQL: {e}")
            
        elif event_type == "session.created":
            # User logged in
            user_id = data.get("user_id")
            logger.info(f"User logged in: {user_id}")
            
        elif event_type == "session.ended":
            # User logged out
            user_id = data.get("user_id")
            logger.info(f"User logged out: {user_id}")

        elif event_type == "organization.created":
            # Organization created in Clerk - sync to PostgreSQL
            org_id = data.get("id")  # Clerk organization ID
            org_name = data.get("name")
            slug = data.get("slug")
            creator_id = data.get("created_by")  # User who created the org
            public_metadata = data.get("public_metadata", {})

            logger.info(f"Organization created: {org_id}")

            # Sync to PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        # Insert organization with metadata
                        await conn.execute(
                            """
                            INSERT INTO organizations (id, name, slug, creator_id, usage_credits, public_metadata)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (id) DO UPDATE SET
                                name = EXCLUDED.name,
                                slug = EXCLUDED.slug,
                                public_metadata = EXCLUDED.public_metadata
                            """,
                            org_id, org_name, slug, creator_id, 1000, public_metadata
                        )

                        # Add creator as admin member
                        member_id = f"mem_{org_id}_{creator_id}"
                        await conn.execute(
                            """
                            INSERT INTO organization_members (id, org_id, user_id, role)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (org_id, user_id) DO UPDATE SET
                                role = EXCLUDED.role
                            """,
                            member_id, org_id, creator_id, "org:admin"
                        )

                    logger.info(f"Organization synced to PostgreSQL: {org_name}")
                except Exception as e:
                    logger.error(f"Failed to sync organization to PostgreSQL: {e}")

        elif event_type == "organization.updated":
            # Organization updated in Clerk - sync changes to PostgreSQL
            org_id = data.get("id")
            org_name = data.get("name")
            slug = data.get("slug")
            public_metadata = data.get("public_metadata", {})

            logger.info(f"Organization updated: {org_id}")

            # Sync to PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE organizations
                            SET name = $2, slug = $3, public_metadata = $4, updated_at = CURRENT_TIMESTAMP
                            WHERE id = $1
                            """,
                            org_id, org_name, slug, public_metadata
                        )
                    logger.info(f"Organization updated in PostgreSQL: {org_name}")
                except Exception as e:
                    logger.error(f"Failed to update organization in PostgreSQL: {e}")

        elif event_type == "organization.deleted":
            # Organization deleted in Clerk - remove from PostgreSQL
            org_id = data.get("id")

            logger.info(f"Organization deleted: {org_id}")

            # Remove from PostgreSQL if enabled (CASCADE will delete members)
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        await conn.execute(
                            """
                            DELETE FROM organizations WHERE id = $1
                            """,
                            org_id
                        )
                    logger.info(f"Organization deleted from PostgreSQL: {org_id}")
                except Exception as e:
                    logger.error(f"Failed to delete organization from PostgreSQL: {e}")

        elif event_type == "organizationMembership.created":
            # User added to organization - sync to PostgreSQL
            membership_id = data.get("id")
            org_id = data.get("organization", {}).get("id")
            user_id = data.get("public_user_data", {}).get("user_id")
            role = data.get("role")  # org:admin or org:member

            logger.info(f"Organization membership created: user {user_id} added to org {org_id} as {role}")

            # Sync to PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO organization_members (id, org_id, user_id, role)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (org_id, user_id) DO UPDATE SET
                                role = EXCLUDED.role
                            """,
                            membership_id, org_id, user_id, role
                        )
                    logger.info(f"Organization membership synced to PostgreSQL")
                except Exception as e:
                    logger.error(f"Failed to sync organization membership to PostgreSQL: {e}")

        elif event_type == "organizationMembership.deleted":
            # User removed from organization - remove from PostgreSQL
            org_id = data.get("organization", {}).get("id")
            user_id = data.get("public_user_data", {}).get("user_id")

            logger.info(f"Organization membership deleted: user {user_id} removed from org {org_id}")

            # Remove from PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        await conn.execute(
                            """
                            DELETE FROM organization_members
                            WHERE org_id = $1 AND user_id = $2
                            """,
                            org_id, user_id
                        )
                    logger.info(f"Organization membership removed from PostgreSQL")
                except Exception as e:
                    logger.error(f"Failed to remove organization membership from PostgreSQL: {e}")

        elif event_type == "organizationMembership.updated":
            # Organization membership updated (role change) - sync to PostgreSQL
            membership_id = data.get("id")
            org_id = data.get("organization", {}).get("id")
            user_id = data.get("public_user_data", {}).get("user_id")
            role = data.get("role")  # org:admin or org:member

            logger.info(f"Organization membership updated: user {user_id} role changed to {role} in org {org_id}")

            # Sync to PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg = await get_postgres_rls_client()
                    async with pg.pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE organization_members
                            SET role = $3, updated_at = CURRENT_TIMESTAMP
                            WHERE org_id = $1 AND user_id = $2
                            """,
                            org_id, user_id, role
                        )
                    logger.info(f"Organization membership role synced to PostgreSQL")
                except Exception as e:
                    logger.error(f"Failed to sync organization membership role to PostgreSQL: {e}")

        elif event_type == "organizationInvitation.created":
            org_id = data.get("organization", {}).get("id")
            invitation_id = data.get("id")
            role = data.get("role")
            logger.info(f"Organization invitation created: {invitation_id} for org {org_id} role {role}")

        elif event_type == "organizationInvitation.accepted":
            org_id = data.get("organization", {}).get("id")
            invitation_id = data.get("id")
            logger.info(f"Organization invitation accepted: {invitation_id} for org {org_id}")

        elif event_type == "organizationInvitation.revoked":
            org_id = data.get("organization", {}).get("id")
            invitation_id = data.get("id")
            logger.info(f"Organization invitation revoked: {invitation_id} for org {org_id}")

        elif event_type == "user.deleted":
            # User deleted from Clerk - delete all user data (GDPR/CCPA compliance)
            user_id = data.get("id")

            logger.info(f"User deleted from Clerk: {user_id}")

            # Delete from PostgreSQL if enabled
            if config.enable_postgres:
                try:
                    pg_client = await get_postgres_client()

                    # Delete user - CASCADE will remove all related data:
                    # - portfolios, chat_sessions, chat_messages, files, risk_analyses
                    # - user_export_settings, organization_members, etc.
                    result = await pg_client.pool.execute(
                        "DELETE FROM users WHERE clerk_user_id = $1",
                        user_id
                    )

                    logger.info(f"User data deleted from PostgreSQL: {user_id} ({result})")
                except Exception as e:
                    logger.error(f"Failed to delete user from PostgreSQL: {e}")
                    # Don't fail webhook - user is already deleted from Clerk

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "success"}
        )
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Processing failed"}
        )

@router.get("/me")
async def get_current_user(
    user: Optional[Dict[str, Any]] = Depends(get_clerk_auth().optional_auth)
):
    """
    Get current authenticated user info.
    Returns None if not authenticated.
    """
    if not config.enable_auth:
        return {"authenticated": False, "auth_enabled": False}
    
    if user:
        return {
            "authenticated": True,
            "user": user
        }
    else:
        return {
            "authenticated": False,
            "auth_enabled": True
        }

@router.post("/logout")
async def logout_user(
    user: Optional[Dict[str, Any]] = Depends(get_clerk_auth().optional_auth)
):
    """
    Server-side logout endpoint for cleanup operations.
    Clerk handles the actual session termination on the client side.
    """
    if not config.enable_auth:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Authentication not enabled"}
        )

    if user:
        user_id = user.get('user_id')
        session_id = user.get('session_id')

        logger.info(f"User logout cleanup: {user_id}")

        # Optional: Perform server-side cleanup here
        # e.g., clear cached user data, invalidate tokens, etc.

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "logout_complete", "user_id": user_id}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "no_session"}
        )

@router.get("/status")
async def auth_status():
    """
    Check authentication system status.
    """
    clerk_auth = get_clerk_auth()

    return {
        "auth_enabled": config.enable_auth,
        "postgres_enabled": config.enable_postgres,
        "clerk_configured": bool(config.clerk_secret_key),
        "jwks_url": clerk_auth.jwks_url if config.enable_auth else None
    }
