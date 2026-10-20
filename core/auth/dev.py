"""
Centralized dev mode bypass logic.
All dev authentication bypass functionality in one place.

SECURITY NOTE: Dev bypass is ONLY enabled when:
1. ENV != 'production' and ENVIRONMENT != 'production'
2. DEV_SECRET environment variable is set
3. Correct secret is provided via header or query param
"""

import os
import logging
from typing import Optional, Tuple
from fastapi import Request

logger = logging.getLogger(__name__)


def is_production() -> bool:
    """Check if we're running in production environment."""
    return (
        os.getenv('ENV') == 'production' or 
        os.getenv('ENVIRONMENT') == 'production'
    )


def get_dev_secret() -> Optional[str]:
    """Get the dev secret from environment."""
    if is_production():
        return None
    return os.getenv('DEV_SECRET')


def is_dev_mode_available() -> bool:
    """Check if dev mode bypass is available."""
    return not is_production() and get_dev_secret() is not None


def extract_dev_credentials_from_headers(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract dev credentials from request headers.
    Returns: (provided_secret, provided_user_id)
    """
    provided_secret = request.headers.get('X-Dev-Secret')
    provided_user_id = request.headers.get('X-Dev-User-Id')
    return provided_secret, provided_user_id


def extract_dev_credentials_from_query(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract dev credentials from query params (for SSE/EventSource).
    Returns: (provided_secret, provided_user_id)
    """
    provided_secret = request.query_params.get('x_dev_secret')
    provided_user_id = request.query_params.get('x_dev_user_id')
    return provided_secret, provided_user_id


def validate_dev_credentials(provided_secret: Optional[str], provided_user_id: Optional[str]) -> bool:
    """
    Validate dev credentials against environment secret.
    Returns True if credentials are valid.
    """
    if not is_dev_mode_available():
        return False
    
    dev_secret = get_dev_secret()
    
    # Both secret and user ID must be provided and correct
    return (
        provided_secret is not None and
        provided_user_id is not None and
        provided_secret == dev_secret
    )


def attempt_dev_auth(request: Request) -> Optional[dict]:
    """
    Attempt to authenticate using dev credentials.
    
    Checks headers first, then query params (for SSE).
    
    Returns:
        dict with user_id and clerk_user_id if successful, None otherwise
    """
    if not is_dev_mode_available():
        return None
    
    # Try headers first
    provided_secret, provided_user_id = extract_dev_credentials_from_headers(request)
    
    if validate_dev_credentials(provided_secret, provided_user_id):
        logger.info(f"DEV MODE: Authenticated via headers for user: {provided_user_id}")
        return {
            'user_id': provided_user_id,
            'clerk_user_id': f"dev_{provided_user_id}",
            'source': 'headers'
        }
    
    # Partial credentials in headers is an auth failure attempt
    if provided_secret or provided_user_id:
        logger.error(f"Failed dev authentication attempt from {request.client.host}")
        return None  # Indicates failed attempt
    
    # Try query params (for SSE)
    qs_secret, qs_user = extract_dev_credentials_from_query(request)
    
    if validate_dev_credentials(qs_secret, qs_user):
        logger.info(f"DEV MODE: Authenticated via query params for user: {qs_user}")
        return {
            'user_id': qs_user,
            'clerk_user_id': f"dev_{qs_user}",
            'source': 'query'
        }
    
    return None


def get_fallback_dev_user() -> Optional[dict]:
    """
    Get fallback dev user when auth is completely disabled.
    Only used when enable_auth is False.
    """
    if is_production():
        return None
    
    dev_user_id = os.getenv('DEV_INTERNAL_USER_ID', 'dev-local-user')
    logger.info(f"DEV MODE: Using fallback user ID: {dev_user_id}")
    
    return {
        'user_id': dev_user_id,
        'clerk_user_id': f"dev_{dev_user_id}",
        'source': 'fallback'
    }
