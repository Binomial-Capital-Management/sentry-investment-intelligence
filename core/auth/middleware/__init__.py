"""
Auth middleware components - each with single responsibility.

Usage in app_fastapi.py:
    # IMPORTANT: Middleware executes in REVERSE order of registration
    # Last added = first to execute
    
    from core.auth.middleware import AuthMiddleware, RLSMiddleware, OrganizationMiddleware
    
    # 3. Organization context (runs LAST - needs user from auth)
    app.add_middleware(OrganizationMiddleware)
    
    # 2. RLS context (runs SECOND - needs user from auth)
    app.add_middleware(RLSMiddleware)
    
    # 1. Auth/JWT verification (runs FIRST)
    app.add_middleware(AuthMiddleware)
    
    # Request flow: AuthMiddleware → RLSMiddleware → OrganizationMiddleware → Route
"""

from .auth import AuthMiddleware
from .rls import RLSMiddleware
from .organization import OrganizationMiddleware

__all__ = ['AuthMiddleware', 'RLSMiddleware', 'OrganizationMiddleware']
