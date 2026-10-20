"""
Database module for Binomial Risk Analyst V6.
Provides unified PostgreSQL client for user management, portfolios, and chats.
"""

from .postgres_client import get_postgres_client, get_postgres_rls_client, PostgresClient

__all__ = ['get_postgres_client', 'get_postgres_rls_client', 'PostgresClient']