"""
Clerk authentication middleware for FastAPI.
Verifies JWT tokens from Clerk and protects endpoints.

Following CODING_RULES.md: KISS, no hardcoding, MVP first.
"""

import os
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import jwt
from jwt import PyJWKClient

from core.config import get_config

logger = logging.getLogger(__name__)

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)

class ClerkAuth:
    """
    Clerk authentication handler.
    Verifies JWT tokens issued by Clerk.
    """
    
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.enable_auth
        self.secret_key = self.config.clerk_secret_key
        
        # Clerk JWKS URL for token verification
        # Using Clerk's public key endpoint (no hardcoding)
        if self.enabled and self.secret_key:
            # Extract Clerk instance from secret key (format: sk_live_xxx or sk_test_xxx)
            # The publishable key determines the Clerk instance URL
            self.jwks_url = self._get_jwks_url()
            logger.info(f"Clerk JWKS URL: {self.jwks_url}")
            # Enable JWKS key caching to avoid HTTP request on every token verification
            # Keys cached for 1 hour, handles key rotation with up to 16 cached keys
            self.jwks_client = PyJWKClient(
                self.jwks_url,
                cache_keys=True,
                lifespan=3600,  # 1 hour cache
                max_cached_keys=16
            ) if self.jwks_url else None
        else:
            self.jwks_url = None
            self.jwks_client = None
            
    def _get_jwks_url(self) -> Optional[str]:
        """
        Construct JWKS URL from Clerk configuration.
        Aug 2025: Clerk now requires instance-specific JWKS URLs.
        Format: https://<clerk-instance>.clerk.accounts.dev/.well-known/jwks.json
        """
        # Extract Clerk instance ID from secret key
        # The secret key format helps determine if test or prod
        if self.secret_key.startswith('sk_test_'):
            # For test keys, need to get instance from env or derive
            # Best practice: Store CLERK_INSTANCE_URL in env
            instance_url = os.getenv('CLERK_INSTANCE_URL')
            if instance_url:
                return f"{instance_url}/.well-known/jwks.json"
            else:
                # Fallback to standard test endpoint
                # Note: This requires the publishable key to derive instance
                logger.info("Using default Clerk test JWKS endpoint")
                return "https://api.clerk.com/v1/jwks"
        elif self.secret_key.startswith('sk_live_'):
            # Production instance
            instance_url = os.getenv('CLERK_INSTANCE_URL')
            if instance_url:
                return f"{instance_url}/.well-known/jwks.json"
            else:
                # Production fallback
                return "https://api.clerk.com/v1/jwks"
        else:
            logger.warning("Unknown Clerk secret key format, auth may not work")
            return None
    
    async def verify_token(self, credentials: Optional[HTTPAuthorizationCredentials]) -> Dict[str, Any]:
        """
        Verify a Clerk JWT token.
        Returns the decoded token payload if valid.
        """
        if not self.enabled:
            # Auth disabled, return mock user
            # Use a fixed UUID for anonymous users in dev mode
            # This is the nil/zero UUID - commonly used for "no user" scenarios
            return {"user_id": "00000000-0000-0000-0000-000000000000", "email": "anonymous@local"}

        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not self.jwks_client:
            logger.error("Clerk JWKS client not initialized")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service not configured",
            )

        try:
            # Extract token string - handle both HTTPAuthorizationCredentials and raw string
            token = credentials.credentials if hasattr(credentials, 'credentials') else str(credentials)

            # Get the signing key from Clerk's JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Verify and decode the token
            # Verify audience ONLY when explicitly configured via env AND running in production
            is_prod = os.getenv('ENV') == 'production' or os.getenv('ENVIRONMENT') == 'production'
            audience_value = os.getenv('CLERK_JWT_AUDIENCE')

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": bool(audience_value) and is_prod},
                audience=audience_value if audience_value else None,
            )
            
            # Extract user info from Clerk token
            user_info = {
                "user_id": payload.get("sub"),  # Clerk user ID
                "email": payload.get("email"),
                "name": payload.get("name"),
                "session_id": payload.get("sid"),  # Clerk session ID
            }
            
            return user_info
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )
    
    async def get_current_user(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
    ) -> Dict[str, Any]:
        """
        FastAPI dependency to get the current authenticated user.
        Can be used in route handlers like:
        
        @app.get("/protected")
        async def protected_route(user = Depends(clerk_auth.get_current_user)):
            return {"user": user}
        """
        return await self.verify_token(credentials)
    
    async def optional_auth(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
    ) -> Optional[Dict[str, Any]]:
        """
        Optional authentication - doesn't fail if no token provided.
        Returns None if no valid token, user info if authenticated.
        """
        if not self.enabled:
            return None

        if not credentials:
            return None

        try:
            return await self.verify_token(credentials)
        except Exception as e:
            logger.debug(f"Optional auth failed: {e}")
            return None

    async def required_auth(
        self,
        request
    ) -> Dict[str, Any]:
        """
        Required authentication from request object for middleware.
        Extracts Bearer token from request headers.
        """
        # Extract authorization header from request
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create credentials object from header
        token = auth_header.split(" ")[1] if " " in auth_header else ""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        return await self.verify_token(credentials)

    async def optional_auth_from_request(
        self,
        request
    ) -> Optional[Dict[str, Any]]:
        """
        Optional authentication from request object for middleware.
        Extracts Bearer token from request headers if present.
        """
        if not self.enabled:
            return None

        # Extract authorization header from request
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        try:
            # Create credentials object from header
            token = auth_header.split(" ")[1] if " " in auth_header else ""
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            return await self.verify_token(credentials)
        except Exception as e:
            logger.debug(f"Optional auth from request failed: {e}")
            return None


# Global instance (singleton pattern)
_clerk_auth = None

def get_clerk_auth() -> ClerkAuth:
    """Get or create the global Clerk auth instance."""
    global _clerk_auth
    if _clerk_auth is None:
        _clerk_auth = ClerkAuth()
    return _clerk_auth