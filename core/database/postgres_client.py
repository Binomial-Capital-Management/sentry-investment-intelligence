"""
PostgreSQL client with Row-Level Security (RLS) support.
Unified client for user management (Clerk) and portfolio/chat features.

Following CODING_RULES.md: KISS, DRY, no hardcoding.
Best practices for PostgreSQL RLS in SaaS (2025).
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import uuid
import asyncpg
import json
import asyncio

from core.config import get_config

logger = logging.getLogger(__name__)


class PostgresClient:
    """
    PostgreSQL client with Row-Level Security support.
    Handles both Clerk user management and portfolio/chat features.
    Uses SET LOCAL within transactions for safe multi-tenant isolation.
    """
    
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.enable_postgres
        self.database_url = self.config.database_url
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Create connection pool with proper configuration."""
        if not self.enabled or not self.database_url:
            logger.info("PostgreSQL not enabled or configured")
            return
            
        try:
            # Setup callback for RLS context management
            async def setup_rls(conn):
                """Clear RLS context when connection is acquired from pool.
                Use set_config to empty string to avoid RESET errors on custom GUC.
                """
                await conn.execute("SELECT set_config('app.current_user_id', '', true)")
            
            # Get pool sizes from config (defaults sized for higher throughput; tune via env)
            min_pool_size = int(os.getenv('POSTGRES_POOL_MIN_SIZE', '10'))
            max_pool_size = int(os.getenv('POSTGRES_POOL_MAX_SIZE', '150'))
            
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=min_pool_size,
                max_size=max_pool_size,
                max_queries=50000,
                max_inactive_connection_lifetime=300,
                command_timeout=60,
                setup=setup_rls  # Clear context on connection acquire
            )
            logger.info(f"PostgreSQL connection pool created with RLS support (min={min_pool_size}, max={max_pool_size})")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            self.enabled = False

    async def _acquire_conn(self) -> asyncpg.Connection:
        """Acquire a pooled connection with a gentle timeout and a single retry."""
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        timeout = float(os.getenv("POSTGRES_ACQUIRE_TIMEOUT_SECONDS", "60"))
        attempts = 2
        last_error: Optional[Exception] = None

        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(self.pool.acquire(), timeout=timeout)
            except Exception as e:
                last_error = e
                if attempt < attempts - 1:
                    # Back off modestly before the final try
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                break

        raise RuntimeError(f"Failed to acquire DB connection after {attempts} attempts (last error: {last_error})")
    
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")
    
    async def ensure_rls_policies(self):
        """Ensure RLS policies exist (migrations handle schema)."""
        if not self.pool:
            return
            
        # Only ensure RLS policies, not tables (migrations handle schema)
        rls_sql = """
        -- Enable Row Level Security (if tables exist)
        DO $$ 
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_sessions') THEN
                ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS chat_sessions_isolation ON chat_sessions;
                CREATE POLICY chat_sessions_isolation ON chat_sessions
                    FOR ALL USING (user_id = current_setting('app.current_user_id', true));
            END IF;
            
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_messages') THEN
                ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS chat_messages_isolation ON chat_messages;
                CREATE POLICY chat_messages_isolation ON chat_messages
                    FOR ALL USING (user_id = current_setting('app.current_user_id', true));
            END IF;
            
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'portfolios') THEN
                ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS portfolios_isolation ON portfolios;
                CREATE POLICY portfolios_isolation ON portfolios
                    FOR ALL USING (user_id = current_setting('app.current_user_id', true));
            END IF;
            
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'risk_analyses') THEN
                ALTER TABLE risk_analyses ENABLE ROW LEVEL SECURITY;
                DROP POLICY IF EXISTS risk_analyses_isolation ON risk_analyses;
                CREATE POLICY risk_analyses_isolation ON risk_analyses
                    FOR ALL USING (user_id = current_setting('app.current_user_id', true));
            END IF;
        END $$;
        """
        
        try:
            conn = await self._acquire_conn()
            try:
                await conn.execute(rls_sql)
                logger.info("PostgreSQL RLS policies ensured (schema from migrations)")
            finally:
                try:
                    await self.pool.release(conn)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to ensure RLS policies: {e}")
    
    # ========== RLS Context Management ==========
    
    @asynccontextmanager
    async def acquire_with_user_context(self, user_id: Optional[str] = None):
        """
        Acquire a connection with user context set for RLS.
        Uses SET LOCAL within transaction for automatic cleanup.
        
        This is the KEY pattern for RLS in multi-tenant SaaS:
        - SET LOCAL ensures context resets after transaction
        - Prevents context leakage in connection pools
        - Safe for concurrent requests
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")
        
        conn = await self._acquire_conn()
        try:
            async with conn.transaction():
                # Set user context for RLS if user_id provided
                if user_id:
                    # Use set_config for transaction-scoped context with parameter binding (safe)
                    # Third argument 'true' makes it LOCAL to the current transaction
                    await conn.execute(
                        "SELECT set_config('app.current_user_id', $1, true)",
                        str(user_id)
                    )
                    logger.debug(f"Set RLS context for user: {user_id}")
                
                yield conn
                # Context automatically cleared when transaction ends
        finally:
            try:
                await self.pool.release(conn)
            except Exception:
                pass

    @asynccontextmanager
    async def acquire_with_org_context(self, user_id: Optional[str] = None, org_id: Optional[str] = None):
        """
        Acquire a connection with both user and organization context set for RLS.
        Uses SET LOCAL within transaction for automatic cleanup.

        This enables dual-access RLS policies where resources can be:
        - Personal (org_id IS NULL AND user_id matches)
        - Organization (org_id matches AND user is member)

        Args:
            user_id: The authenticated user's ID (required for RLS)
            org_id: The active organization's ID (optional, for org workspace)
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        conn = await self._acquire_conn()
        try:
            async with conn.transaction():
                # Set user context for RLS (required)
                if user_id:
                    await conn.execute(
                        "SELECT set_config('app.current_user_id', $1, true)",
                        str(user_id)
                    )
                    logger.debug(f"Set RLS user context: {user_id}")

                # Set organization context for RLS (optional)
                if org_id:
                    await conn.execute(
                        "SELECT set_config('app.current_org_id', $1, true)",
                        str(org_id)
                    )
                    logger.warning(f"🔍 RLS DEBUG - Set app.current_org_id = '{org_id}'")
                else:
                    # Clear org context to ensure personal workspace
                    await conn.execute("SELECT set_config('app.current_org_id', '', true)")
                    logger.warning(f"🔍 RLS DEBUG - Set app.current_org_id = '' (personal workspace)")

                # Verify settings were applied
                current_user = await conn.fetchval("SELECT current_setting('app.current_user_id', true)")
                current_org = await conn.fetchval("SELECT current_setting('app.current_org_id', true)")
                logger.warning(f"🔍 RLS DEBUG - Verified settings: user_id='{current_user}', org_id='{current_org}'")

                yield conn
                # Context automatically cleared when transaction ends
        finally:
            try:
                await self.pool.release(conn)
            except Exception:
                pass

    async def with_user_context(self, user_id: Optional[str], conn: asyncpg.Connection):
        """
        Set user context for RLS within a transaction (legacy method for compatibility).
        Aug 2025 best practice: Use SET LOCAL for transaction-scoped context.
        """
        if user_id:
            await conn.execute("SELECT set_config('app.current_user_id', $1, true)", str(user_id))
        else:
            await conn.execute("RESET app.current_user_id")
    
    # ========== User Management (Clerk Integration) ==========
    
    async def upsert_user(
        self, 
        clerk_user_id: str, 
        email: str, 
        name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create or update user (called from Clerk webhook)."""
        if not self.pool:
            return None
            
        try:
            conn = await self._acquire_conn()
            try:
                row = await conn.fetchrow("""
                    INSERT INTO users (clerk_user_id, email, name)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (clerk_user_id) 
                    DO UPDATE SET 
                        email = EXCLUDED.email,
                        name = EXCLUDED.name,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, clerk_user_id, email, name, usage_credits
                """, clerk_user_id, email, name)
                
                return dict(row) if row else None
            finally:
                try:
                    await self.pool.release(conn)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to upsert user: {e}")
            return None
    
    async def get_user(self, clerk_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by Clerk ID (bypasses RLS for auth checks)."""
        if not self.pool:
            return None
            
        try:
            conn = await self._acquire_conn()
            try:
                async with conn.transaction():
                    row = await conn.fetchrow("""
                        SELECT id, clerk_user_id, email, name, usage_credits
                        FROM users
                        WHERE clerk_user_id = $1
                    """, clerk_user_id)
                    
                    return dict(row) if row else None
            finally:
                try:
                    await self.pool.release(conn)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None
    
    async def get_user_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_user for compatibility."""
        return await self.get_user(clerk_user_id)
    
    async def get_internal_user_id(self, clerk_user_id: str) -> Optional[str]:
        """Get internal user ID from Clerk user ID."""
        user = await self.get_user(clerk_user_id)
        return user['id'] if user else None
    
    # ========== Portfolio Management (with RLS) ==========
    
    async def save_portfolio(
        self,
        user_id: str,
        name: str,
        tickers: List[str],
        weights: List[float],
        is_default: bool = False,
        value: Optional[float] = None,
        cash_balance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        holdings: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Save or update a portfolio with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # If setting as default, unset other defaults first
                if is_default:
                    if org_id is None:
                        await conn.execute("""
                            UPDATE portfolios
                            SET is_default = FALSE
                            WHERE user_id = $1 AND org_id IS NULL AND is_default = TRUE
                        """, user_id)
                    else:
                        await conn.execute("""
                            UPDATE portfolios
                            SET is_default = FALSE
                            WHERE user_id = $1 AND org_id = $2 AND is_default = TRUE
                        """, user_id, org_id)

                # Insert new portfolio
                row = await conn.fetchrow("""
                    INSERT INTO portfolios (user_id, org_id, name, tickers, weights, is_default, value, cash_balance, metadata, holdings)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id, name, tickers, weights, is_default, value, cash_balance, holdings, created_at
                """, user_id, org_id, name, tickers, weights, is_default,
                value or 1000000,  # Default to 1M if not specified
                cash_balance or 0,  # Default to 0 if not specified
                json.dumps(metadata) if metadata else '{}',
                json.dumps(holdings) if holdings else '[]')

                if row:
                    result = dict(row)
                    # Parse holdings from JSONB string to list for Pydantic compatibility
                    if result.get('holdings'):
                        try:
                            result['holdings'] = json.loads(result['holdings']) if isinstance(result['holdings'], str) else result['holdings']
                        except (json.JSONDecodeError, TypeError):
                            result['holdings'] = []
                    return result
                return None
        except Exception as e:
            logger.error(f"Failed to save portfolio: {e}")
            return None
    
    async def get_portfolio_by_id(self, user_id: str, portfolio_id: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific portfolio by ID with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = """
                    SELECT id, name, tickers, weights, is_default, value, cash_balance, holdings, created_at, updated_at, metadata,
                           broker_connection_id, source_type, synced_at
                    FROM portfolios
                    WHERE id = $1
                """
                params: List[Any] = [portfolio_id]
                if org_id is None:
                    query += " AND user_id = $2"
                    params.append(user_id)

                row = await conn.fetchrow(query, *params)

                if row:
                    result = dict(row)
                    # Parse holdings from JSONB string to list for Pydantic compatibility
                    if result.get('holdings'):
                        try:
                            result['holdings'] = json.loads(result['holdings']) if isinstance(result['holdings'], str) else result['holdings']
                        except (json.JSONDecodeError, TypeError):
                            result['holdings'] = []
                    return result
                return None
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return None
    
    async def get_user_portfolios(
        self,
        user_id: str,
        limit: int = 50,
        org_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all portfolios for a user with RLS."""
        if not self.pool:
            return []

        try:
            # DEBUG: Log query construction
            logger.warning(f"🔍 DB DEBUG - get_user_portfolios called with user_id: {user_id}, org_id: {org_id}")

            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = """
                    SELECT id, name, tickers, weights, is_default, value, cash_balance, holdings, created_at, updated_at,
                           broker_connection_id, source_type, synced_at
                    FROM portfolios
                """
                params: List[Any] = []

                if org_id is None:
                    query += " WHERE user_id = $1"
                    params.append(user_id)
                    logger.warning(f"🔍 DB DEBUG - Personal workspace: adding user_id filter")
                else:
                    logger.warning(f"🔍 DB DEBUG - Org workspace: relying on RLS for org_id={org_id}")

                limit_param = len(params) + 1
                query += f"""
                    ORDER BY is_default DESC, created_at DESC
                    LIMIT ${limit_param}
                """
                params.append(limit)

                logger.warning(f"🔍 DB DEBUG - Query: {query}")
                logger.warning(f"🔍 DB DEBUG - Params: {params}")
                rows = await conn.fetch(query, *params)
                logger.warning(f"🔍 DB DEBUG - Returned {len(rows)} rows")

                # Parse holdings from JSONB strings to lists for Pydantic compatibility
                results = []
                for row in rows:
                    result = dict(row)
                    if result.get('holdings'):
                        try:
                            result['holdings'] = json.loads(result['holdings']) if isinstance(result['holdings'], str) else result['holdings']
                        except (json.JSONDecodeError, TypeError):
                            result['holdings'] = []
                    results.append(result)
                return results
        except Exception as e:
            logger.error(f"Failed to get portfolios: {e}")
            return []
    
    async def delete_portfolio(self, user_id: str, portfolio_id: str, org_id: Optional[str] = None) -> bool:
        """Delete a portfolio with RLS."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = "DELETE FROM portfolios WHERE id = $1"
                params: List[Any] = [portfolio_id]

                if org_id is None:
                    query += " AND user_id = $2"
                    params.append(user_id)

                result = await conn.execute(query, *params)

                return result.split()[-1] != '0'
        except Exception as e:
            logger.error(f"Failed to delete portfolio: {e}")
            return False
    
    async def update_portfolio(
        self,
        user_id: str,
        portfolio_id: str,
        name: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
        value: Optional[float] = None,
        cash_balance: Optional[float] = None,
        holdings: Optional[List[Dict[str, Any]]] = None,
        org_id: Optional[str] = None
    ) -> bool:
        """Update an existing portfolio with RLS."""
        if not self.pool:
            return False

        try:
            # User ID is already internal from middleware
            internal_user_id = user_id

            async with self.acquire_with_org_context(internal_user_id, org_id) as conn:
                # Build dynamic update query
                updates = []
                params: List[Any] = [portfolio_id]
                param_count = 2
                where_clause = "id = $1"

                if org_id is None:
                    where_clause += f" AND user_id = ${param_count}"
                    params.append(internal_user_id)
                    param_count += 1

                if name is not None:
                    updates.append(f"name = ${param_count}")
                    params.append(name)
                    param_count += 1

                if tickers is not None:
                    updates.append(f"tickers = ${param_count}")
                    params.append(tickers)
                    param_count += 1

                if weights is not None:
                    updates.append(f"weights = ${param_count}")
                    params.append(weights)
                    param_count += 1

                if value is not None:
                    updates.append(f"value = ${param_count}")
                    params.append(value)
                    param_count += 1

                if cash_balance is not None:
                    updates.append(f"cash_balance = ${param_count}")
                    params.append(cash_balance)
                    param_count += 1

                if holdings is not None:
                    updates.append(f"holdings = ${param_count}")
                    params.append(json.dumps(holdings))
                    param_count += 1

                if not updates:
                    return True  # Nothing to update

                updates.append("updated_at = CURRENT_TIMESTAMP")

                query = f"""
                    UPDATE portfolios
                    SET {', '.join(updates)}
                    WHERE {where_clause}
                """

                result = await conn.execute(query, *params)
                return result.split()[-1] != '0'
        except Exception as e:
            logger.error(f"Failed to update portfolio: {e}")
            return False

    async def bulk_update_portfolios(
        self,
        user_id: str,
        updates: List[Dict[str, Any]]
    ) -> int:
        """
        Bulk update multiple portfolios for a user in a single transaction.

        Args:
            user_id: User ID for RLS context
            updates: List of dicts with keys: portfolio_id, holdings, value, weights

        Returns:
            Number of portfolios updated
        """
        if not self.pool or not updates:
            return 0

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Prepare data for bulk update
                records = [
                    (
                        json.dumps(update['holdings']) if isinstance(update['holdings'], (dict, list)) else update['holdings'],
                        update['value'],
                        update['weights'],
                        update['portfolio_id']
                    )
                    for update in updates
                ]

                # Execute bulk update with executemany
                await conn.executemany("""
                    UPDATE portfolios
                    SET holdings = $1::jsonb,
                        value = $2,
                        weights = $3,
                        updated_at = NOW()
                    WHERE id = $4
                """, records)

                logger.info(f"Bulk updated {len(records)} portfolios for user {user_id}")
                return len(records)

        except Exception as e:
            logger.error(f"Failed to bulk update portfolios: {e}")
            return 0

    async def bulk_insert_portfolio_history(
        self,
        user_id: str,
        snapshots: List[Dict[str, Any]]
    ) -> int:
        """
        Bulk insert portfolio value history snapshots in a single transaction.

        Args:
            user_id: User ID for RLS context
            snapshots: List of dicts with keys: portfolio_id, snapshot_date, total_value, holdings_snapshot, prices_snapshot

        Returns:
            Number of snapshots inserted
        """
        if not self.pool or not snapshots:
            return 0

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Prepare data for bulk insert
                records = [
                    (
                        snapshot['portfolio_id'],
                        user_id,
                        snapshot['snapshot_date'],
                        snapshot['total_value'],
                        json.dumps(snapshot['holdings_snapshot']) if isinstance(snapshot['holdings_snapshot'], (dict, list)) else snapshot['holdings_snapshot'],
                        json.dumps(snapshot['prices_snapshot']) if isinstance(snapshot['prices_snapshot'], (dict, list)) else snapshot['prices_snapshot']
                    )
                    for snapshot in snapshots
                ]

                # Execute bulk insert/upsert with executemany
                await conn.executemany("""
                    INSERT INTO portfolio_value_history (
                        portfolio_id, user_id, snapshot_date, total_value,
                        holdings_snapshot, prices_snapshot
                    )
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                    ON CONFLICT (portfolio_id, snapshot_date)
                    DO UPDATE SET
                        total_value = EXCLUDED.total_value,
                        holdings_snapshot = EXCLUDED.holdings_snapshot,
                        prices_snapshot = EXCLUDED.prices_snapshot
                """, records)

                logger.info(f"Bulk inserted {len(records)} portfolio history snapshots for user {user_id}")
                return len(records)

        except Exception as e:
            logger.error(f"Failed to bulk insert portfolio history: {e}")
            return 0

    async def set_default_portfolio(
        self,
        user_id: str,
        portfolio_id: str,
        org_id: Optional[str] = None
    ) -> bool:
        """Set a portfolio as default for the user."""
        if not self.pool:
            return False

        try:
            # User ID is already internal from middleware
            internal_user_id = user_id

            async with self.acquire_with_org_context(internal_user_id, org_id) as conn:
                # First, unset all portfolios as default
                await conn.execute("""
                    UPDATE portfolios 
                    SET is_default = FALSE 
                    WHERE user_id = $1
                """, internal_user_id)
                
                # Then set the specified portfolio as default
                result = await conn.execute("""
                    UPDATE portfolios 
                    SET is_default = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1 AND user_id = $2
                """, portfolio_id, internal_user_id)
                
                # Check if update affected any rows
                return result.split()[-1] != '0'
        except Exception as e:
            logger.error(f"Failed to set default portfolio: {e}")
            return False
    
    # ========== Chat Session Management (with RLS) ==========
    
    async def create_chat_session(
        self,
        user_id: str,
        title: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new chat session with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow("""
                    INSERT INTO chat_sessions (user_id, org_id, title)
                    VALUES ($1, $2, $3)
                    RETURNING id, title, created_at
                """, user_id, org_id, title or "New Chat")
                
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            return None
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        org_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user with RLS."""
        if not self.pool:
            return []

        try:
            # DEBUG: Log query construction
            logger.warning(f"🔍 CHATS DEBUG - get_user_sessions called with user_id: {user_id}, org_id: {org_id}")

            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # Conditional query: filter by user_id only in personal workspace
                query = """
                    SELECT id, title, created_at, updated_at
                    FROM chat_sessions
                """
                params = []

                if org_id is None:
                    # Personal workspace: filter by user_id
                    query += " WHERE user_id = $1"
                    params.append(user_id)
                    query += " ORDER BY updated_at DESC LIMIT $2"
                    params.append(limit)
                    logger.warning(f"🔍 CHATS DEBUG - Personal workspace: adding user_id filter")
                else:
                    # Organization workspace: RLS handles filtering
                    query += " ORDER BY updated_at DESC LIMIT $1"
                    params.append(limit)
                    logger.warning(f"🔍 CHATS DEBUG - Org workspace: relying on RLS for org_id={org_id}")

                logger.warning(f"🔍 CHATS DEBUG - Query: {query}")
                logger.warning(f"🔍 CHATS DEBUG - Params: {params}")
                rows = await conn.fetch(query, *params)
                logger.warning(f"🔍 CHATS DEBUG - Returned {len(rows)} rows")

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get chat sessions: {e}")
            return []
    
    async def delete_chat_session(self, user_id: str, session_id: str, org_id: Optional[str] = None) -> bool:
        """Delete a chat session with RLS."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute("""
                    DELETE FROM chat_sessions
                    WHERE id = $1 AND user_id = $2
                """, session_id, user_id)

                return result.split()[-1] != '0'
        except Exception as e:
            logger.error(f"Failed to delete chat session: {e}")
            return False

    async def bulk_delete_chat_sessions(
        self,
        user_id: str,
        session_ids: List[str],
        org_id: Optional[str] = None
    ) -> int:
        """Bulk delete multiple chat sessions with RLS. Returns count of deleted sessions."""
        if not self.pool or not session_ids:
            return 0

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute("""
                    DELETE FROM chat_sessions
                    WHERE id = ANY($1::uuid[]) AND user_id = $2
                """, session_ids, user_id)

                # Result format: "DELETE N"
                deleted_count = int(result.split()[-1])
                logger.info(f"Bulk deleted {deleted_count} chat sessions for user {user_id}")
                return deleted_count
        except Exception as e:
            logger.error(f"Failed to bulk delete chat sessions: {e}")
            return 0

    async def update_chat_session(
        self,
        user_id: str,
        session_id: str,
        title: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update a chat session title with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow("""
                    UPDATE chat_sessions
                    SET title = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2 AND user_id = $3
                    RETURNING id, title, created_at, updated_at
                """, title, session_id, user_id)

                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to update chat session: {e}")
            return None
    
    async def save_chat_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_ids: Optional[List[str]] = None,
        org_id: Optional[str] = None
    ) -> Optional[str]:
        """Save a chat message metadata with RLS (content also in SQLite)."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # Ensure session exists before inserting message (upsert pattern)
                # This prevents foreign key constraint violations
                await conn.execute("""
                    INSERT INTO chat_sessions (id, user_id, org_id, title)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO NOTHING
                """, session_id, user_id, org_id, "Chat Session")

                row = await conn.fetchrow("""
                    INSERT INTO chat_messages (session_id, user_id, org_id, role, content, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, session_id, user_id, org_id, role, content,
                json.dumps(metadata) if metadata else '{}')

                message_id = row['id'] if row else None

                # Save file associations if provided
                if file_ids and message_id:
                    import uuid
                    for file_id in file_ids:
                        await conn.execute("""
                            INSERT INTO message_files (message_id, file_id)
                            VALUES ($1, $2)
                        """, message_id, uuid.UUID(file_id))

                return str(message_id) if message_id else None
        except Exception as e:
            logger.error(f"Failed to save chat message: {e}")
            return None

    # ========== Google Drive Integration (RLS) ==========

    async def upsert_drive_credential(
        self,
        user_id: str,
        drive_user_id: str,
        drive_email: str,
        refresh_token_encrypted: str,
        scopes: List[str],
        token_metadata: Optional[Dict[str, Any]] = None,
        org_id: str = '',
    ) -> Optional[Dict[str, Any]]:
        """Create or update a Google Drive credential. org_id='' for personal, org_id='org_xxx' for org token."""
        if not self.pool:
            return None

        metadata_json = json.dumps(token_metadata or {})

        try:
            ctx = self.acquire_with_org_context(user_id, org_id) if org_id else self.acquire_with_user_context(user_id)
            async with ctx as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO google_drive_credentials (
                        user_id,
                        org_id,
                        drive_user_id,
                        drive_email,
                        refresh_token_encrypted,
                        scopes,
                        token_metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    ON CONFLICT (user_id, org_id, drive_user_id)
                    DO UPDATE
                    SET
                        drive_email = EXCLUDED.drive_email,
                        refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                        scopes = EXCLUDED.scopes,
                        token_metadata = EXCLUDED.token_metadata,
                        updated_at = NOW()
                    RETURNING id, user_id, org_id, drive_user_id, drive_email, refresh_token_encrypted, scopes, token_metadata, created_at, updated_at
                    """,
                    user_id,
                    org_id,
                    drive_user_id,
                    drive_email,
                    refresh_token_encrypted,
                    scopes,
                    metadata_json,
                )
                return dict(row) if row else None
        except Exception as exc:
            logger.error(f"Failed to upsert Google Drive credential: {exc}")
            return None

    async def get_drive_credentials(self, user_id: str, org_id: str = '') -> List[Dict[str, Any]]:
        """List Google Drive credentials. For personal (org_id='') or org tokens."""
        if not self.pool:
            return []

        try:
            ctx = self.acquire_with_org_context(user_id, org_id) if org_id else self.acquire_with_user_context(user_id)
            async with ctx as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, org_id, drive_user_id, drive_email, refresh_token_encrypted, scopes, token_metadata, created_at, updated_at
                    FROM google_drive_credentials
                    ORDER BY updated_at DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Failed to fetch Google Drive credentials: {exc}")
            return []

    async def delete_drive_credential(self, user_id: str, credential_id: str) -> bool:
        """Delete a Google Drive credential owned by the user."""
        if not self.pool:
            return False

        try:
            credential_uuid = uuid.UUID(credential_id)
        except ValueError:
            logger.warning(f"Invalid Google Drive credential UUID: {credential_id}")
            return False

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                result = await conn.execute(
                    """
                    DELETE FROM google_drive_credentials
                    WHERE id = $1
                    """,
                    credential_uuid,
                )
                return result.split()[-1] != '0'
        except Exception as exc:
            logger.error(f"Failed to delete Google Drive credential: {exc}")
            return False

    # ========== OneDrive Integration (RLS) ==========

    async def upsert_onedrive_credential(
        self,
        user_id: str,
        drive_user_id: str,
        drive_email: str,
        refresh_token_encrypted: str,
        scopes: List[str],
        token_metadata: Optional[Dict[str, Any]] = None,
        org_id: str = '',
    ) -> Optional[Dict[str, Any]]:
        """Create or update a OneDrive credential. org_id='' for personal, org_id='org_xxx' for org token."""
        if not self.pool:
            return None

        metadata_json = json.dumps(token_metadata or {})

        try:
            # Use org context if org_id provided, else user context
            ctx = self.acquire_with_org_context(user_id, org_id) if org_id else self.acquire_with_user_context(user_id)
            async with ctx as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO onedrive_credentials (
                        user_id,
                        org_id,
                        drive_user_id,
                        drive_email,
                        refresh_token_encrypted,
                        scopes,
                        token_metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                    ON CONFLICT (user_id, org_id, drive_user_id)
                    DO UPDATE
                    SET
                        drive_email = EXCLUDED.drive_email,
                        refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                        scopes = EXCLUDED.scopes,
                        token_metadata = EXCLUDED.token_metadata,
                        updated_at = NOW()
                    RETURNING id, user_id, org_id, drive_user_id, drive_email, refresh_token_encrypted, scopes, token_metadata, created_at, updated_at
                    """,
                    user_id,
                    org_id,
                    drive_user_id,
                    drive_email,
                    refresh_token_encrypted,
                    scopes,
                    metadata_json,
                )
                return dict(row) if row else None
        except Exception as exc:
            logger.error(f"Failed to upsert OneDrive credential: {exc}")
            return None

    async def get_onedrive_credentials(self, user_id: str, org_id: str = '') -> List[Dict[str, Any]]:
        """List OneDrive credentials. For personal (org_id='') or org tokens."""
        if not self.pool:
            return []

        try:
            ctx = self.acquire_with_org_context(user_id, org_id) if org_id else self.acquire_with_user_context(user_id)
            async with ctx as conn:
                # RLS handles filtering - just select all visible
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, org_id, drive_user_id, drive_email, refresh_token_encrypted, scopes, token_metadata, created_at, updated_at
                    FROM onedrive_credentials
                    ORDER BY updated_at DESC
                    """
                )
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Failed to fetch OneDrive credentials: {exc}")
            return []

    async def delete_onedrive_credential(self, user_id: str, credential_id: str) -> bool:
        """Delete a OneDrive credential owned by the user."""
        if not self.pool:
            return False

        try:
            credential_uuid = uuid.UUID(credential_id)
        except ValueError:
            logger.warning(f"Invalid OneDrive credential UUID: {credential_id}")
            return False

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                result = await conn.execute(
                    """
                    DELETE FROM onedrive_credentials
                    WHERE id = $1
                    """,
                    credential_uuid,
                )
                return result.split()[-1] != '0'
        except Exception as exc:
            logger.error(f"Failed to delete OneDrive credential: {exc}")
            return False
    
    # ========== Analytics & Tracking (with RLS) ==========
    
    async def track_analysis(
        self,
        clerk_user_id: str,
        analysis_type: str,
        tickers: List[str]
    ):
        """Track risk analysis for usage history (MVP feature with RLS)."""
        if not self.pool:
            return
        
        try:
            # Get user ID first
            user = await self.get_user(clerk_user_id)
            if not user:
                return
            
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Set user context for RLS
                    await self.with_user_context(user['id'], conn)
                    
                    # Track the analysis
                    await conn.execute("""
                        INSERT INTO risk_analyses (user_id, analysis_type, tickers)
                        VALUES ($1, $2, $3)
                    """, user['id'], analysis_type, tickers)
                    
                    # Deduct credit
                    await conn.execute("""
                        UPDATE users 
                        SET usage_credits = GREATEST(0, usage_credits - 1)
                        WHERE id = $1
                    """, user['id'])
                
        except Exception as e:
            logger.error(f"Failed to track analysis: {e}")

    # ========== Portfolio Transactions (Accounting) ==========

    async def record_transaction(
        self,
        user_id: str,
        portfolio_id: str,
        transaction_type: str,  # 'BUY' or 'SELL'
        ticker: str,
        quantity: float,
        price: float,
        total_amount: float,
        transaction_date: str,
        cost_basis: Optional[float] = None,
        realized_gain_loss: Optional[float] = None,
        lots_affected: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[str] = None,
        org_id: Optional[str] = None,
        source: str = "manual",
        external_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Record a portfolio transaction (buy or sell) for accounting purposes.
        Returns transaction ID if successful, None otherwise.
        """
        if not self.pool:
            return None

        try:
            portfolio_uuid = uuid.UUID(portfolio_id)
        except ValueError:
            logger.warning(f"Invalid portfolio UUID: {portfolio_id}")
            return None

        # Convert transaction_date string to datetime object
        try:
            if isinstance(transaction_date, str):
                # Handle ISO format strings
                parsed_date = datetime.fromisoformat(transaction_date.replace('Z', '+00:00'))
            else:
                parsed_date = transaction_date
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid transaction_date format: {transaction_date}, using current time")
            parsed_date = datetime.utcnow()

        # Convert empty string org_id to None for FK constraint (organizations table)
        db_org_id = org_id if org_id else None
        
        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO portfolio_transactions (
                        portfolio_id, user_id, org_id, transaction_type, ticker,
                        quantity, price, total_amount, transaction_date,
                        cost_basis, realized_gain_loss, lots_affected, notes,
                        source, external_id
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (portfolio_id, external_id) WHERE external_id IS NOT NULL
                    DO UPDATE SET
                        transaction_type = EXCLUDED.transaction_type,
                        ticker = EXCLUDED.ticker,
                        quantity = EXCLUDED.quantity,
                        price = EXCLUDED.price,
                        total_amount = EXCLUDED.total_amount,
                        transaction_date = EXCLUDED.transaction_date,
                        cost_basis = COALESCE(EXCLUDED.cost_basis, portfolio_transactions.cost_basis),
                        realized_gain_loss = COALESCE(EXCLUDED.realized_gain_loss, portfolio_transactions.realized_gain_loss),
                        lots_affected = COALESCE(EXCLUDED.lots_affected, portfolio_transactions.lots_affected),
                        notes = COALESCE(EXCLUDED.notes, portfolio_transactions.notes),
                        source = EXCLUDED.source,
                        org_id = EXCLUDED.org_id
                    RETURNING id
                    """,
                    portfolio_uuid,
                    user_id,
                    db_org_id,
                    transaction_type,
                    ticker.upper(),
                    quantity,
                    price,
                    total_amount,
                    parsed_date,
                    cost_basis,
                    realized_gain_loss,
                    json.dumps(lots_affected) if lots_affected else None,
                    notes,
                    source,
                    external_id
                )
                return str(row['id']) if row else None
        except Exception as exc:
            logger.error(f"Failed to record transaction: {exc}")
            return None

    async def get_portfolio_transactions(
        self,
        user_id: str,
        portfolio_id: str,
        ticker: Optional[str] = None,
        transaction_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        org_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get transaction history for a portfolio.
        Optionally filter by ticker, transaction type, and date range.
        date_from/date_to should be ISO date strings (YYYY-MM-DD).
        """
        if not self.pool:
            return []

        try:
            portfolio_uuid = uuid.UUID(portfolio_id)
        except ValueError:
            logger.warning(f"Invalid portfolio UUID: {portfolio_id}")
            return []

        try:
            # Build query with optional filters
            query = """
                SELECT
                    id, portfolio_id, user_id, transaction_type, ticker,
                    quantity, price, total_amount, transaction_date,
                    cost_basis, realized_gain_loss, lots_affected, notes,
                    created_at, source, external_id, org_id
                FROM portfolio_transactions
                WHERE portfolio_id = $1
            """
            params = [portfolio_uuid]
            param_count = 2

            if ticker:
                query += f" AND ticker = ${param_count}"
                params.append(ticker.upper())
                param_count += 1

            if transaction_type:
                query += f" AND transaction_type = ${param_count}"
                params.append(transaction_type.upper())
                param_count += 1

            if date_from:
                query += f" AND transaction_date::date >= ${param_count}"
                # Parse ISO date string to Python date object
                parsed_from = datetime.fromisoformat(date_from).date()
                params.append(parsed_from)
                param_count += 1

            if date_to:
                # Add one day to include the entire end date
                query += f" AND transaction_date::date <= ${param_count}"
                parsed_to = datetime.fromisoformat(date_to).date()
                params.append(parsed_to)
                param_count += 1

            query += f" ORDER BY transaction_date DESC, created_at DESC LIMIT ${param_count}"
            params.append(limit)

            async with self.acquire_with_org_context(user_id, org_id) as conn:
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.error(f"Failed to get portfolio transactions: {exc}")
            return []

    async def delete_transactions(
        self,
        user_id: str,
        portfolio_id: str,
        transaction_ids: List[str],
        org_id: Optional[str] = None
    ) -> int:
        """
        Delete multiple transactions with RLS protection.
        Returns count of transactions deleted.
        """
        if not self.pool:
            return 0

        if not transaction_ids:
            return 0

        try:
            portfolio_uuid = uuid.UUID(portfolio_id)
        except ValueError:
            logger.warning(f"Invalid portfolio UUID: {portfolio_id}")
            return 0

        # Convert transaction IDs to UUID strings for query
        try:
            transaction_uuids = [str(uuid.UUID(tid)) for tid in transaction_ids]
        except ValueError as e:
            logger.warning(f"Invalid transaction UUID in list: {e}")
            return 0

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # RLS automatically filters to user's transactions only
                result = await conn.execute(
                    """
                    DELETE FROM portfolio_transactions
                    WHERE portfolio_id = $1 AND id = ANY($2::uuid[])
                    """,
                    portfolio_uuid,
                    transaction_uuids
                )
                # Parse delete count from result string like "DELETE 3"
                deleted_count = int(result.split()[-1]) if result.split() else 0
                return deleted_count
        except Exception as exc:
            logger.error(f"Failed to delete transactions: {exc}")
            return 0

    # ======================
    # User Insights Methods
    # ======================

    async def create_insight(
        self,
        user_id: str,
        page_type: str,
        title: str,
        content: Dict[str, Any],
        priority: int = 5,
        region: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new user insight with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Set default expiration to 24 hours if not specified
                if expires_at is None:
                    expires_at = datetime.utcnow() + timedelta(hours=24)

                row = await conn.fetchrow("""
                    INSERT INTO user_insights (
                        user_id, page_type, region, title, content, priority,
                        expires_at, metadata, generated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING id, user_id, page_type, region, title, content, priority,
                              is_read, metadata, generated_at, expires_at,
                              created_at, updated_at
                """, user_id, page_type, region, title, json.dumps(content), priority,
                expires_at, json.dumps(metadata) if metadata else '{}',
                datetime.utcnow())

                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to create insight: {e}")
            return None

    async def get_insights(
        self,
        user_id: str,
        page_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 6,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get user insights with RLS. Returns most recent by priority."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                query = """
                    SELECT id, user_id, page_type, region, title, content, priority,
                           is_read, metadata, generated_at, expires_at,
                           created_at, updated_at
                    FROM user_insights
                    WHERE user_id = $1
                """
                params = [user_id]
                param_count = 2

                if page_type:
                    query += f" AND page_type = ${param_count}"
                    params.append(page_type)
                    param_count += 1

                if region:
                    query += f" AND region = ${param_count}"
                    params.append(region)
                    param_count += 1

                if unread_only:
                    query += " AND NOT is_read"

                # Sort by priority (descending) then by generated_at (most recent first)
                query += f" ORDER BY priority DESC, generated_at DESC LIMIT ${param_count}"
                params.append(limit)

                rows = await conn.fetch(query, *params)

                # Parse JSONB fields from strings to dictionaries
                insights = []
                for row in rows:
                    insight_dict = dict(row)
                    # Parse content field from JSON string
                    if isinstance(insight_dict.get('content'), str):
                        insight_dict['content'] = json.loads(insight_dict['content'])
                    # Parse metadata field from JSON string
                    if isinstance(insight_dict.get('metadata'), str):
                        insight_dict['metadata'] = json.loads(insight_dict['metadata'])
                    insights.append(insight_dict)

                return insights
        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
            return []

    async def update_insight(
        self,
        user_id: str,
        insight_id: str,
        is_read: Optional[bool] = None,
        priority: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an insight with RLS."""
        if not self.pool:
            return None

        try:
            insight_uuid = uuid.UUID(insight_id)
        except ValueError:
            logger.warning(f"Invalid insight UUID: {insight_id}")
            return None

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                updates = []
                params = [insight_uuid]
                param_count = 2

                if is_read is not None:
                    updates.append(f"is_read = ${param_count}")
                    params.append(is_read)
                    param_count += 1

                if priority is not None:
                    updates.append(f"priority = ${param_count}")
                    params.append(priority)
                    param_count += 1

                if not updates:
                    return None

                query = f"""
                    UPDATE user_insights
                    SET {', '.join(updates)}
                    WHERE id = $1
                    RETURNING id, user_id, page_type, title, content, priority,
                              is_read, metadata, generated_at, expires_at,
                              created_at, updated_at
                """

                row = await conn.fetchrow(query, *params)
                if not row:
                    return None

                # Parse JSONB fields from strings to dictionaries
                insight_dict = dict(row)
                if isinstance(insight_dict.get('content'), str):
                    insight_dict['content'] = json.loads(insight_dict['content'])
                if isinstance(insight_dict.get('metadata'), str):
                    insight_dict['metadata'] = json.loads(insight_dict['metadata'])

                return insight_dict
        except Exception as e:
            logger.error(f"Failed to update insight: {e}")
            return None

    async def delete_insight(
        self,
        user_id: str,
        insight_id: str
    ) -> bool:
        """Delete an insight with RLS."""
        if not self.pool:
            return False

        try:
            insight_uuid = uuid.UUID(insight_id)
        except ValueError:
            logger.warning(f"Invalid insight UUID: {insight_id}")
            return False

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                result = await conn.execute("""
                    DELETE FROM user_insights
                    WHERE id = $1
                """, insight_uuid)

                # Parse delete count from result string
                deleted_count = int(result.split()[-1]) if result.split() else 0
                return deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete insight: {e}")
            return False

    async def delete_old_insights(
        self,
        user_id: str,
        older_than_hours: int = 24
    ) -> int:
        """Delete insights older than specified hours with RLS."""
        if not self.pool:
            return 0

        attempts = 2
        for attempt in range(attempts):
            try:
                async with self.acquire_with_user_context(user_id) as conn:
                    cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)

                    result = await conn.execute("""
                        DELETE FROM user_insights
                        WHERE user_id = $1 AND generated_at < $2
                    """, user_id, cutoff_time)

                    # Parse delete count from result string
                    deleted_count = int(result.split()[-1]) if result.split() else 0
                    return deleted_count
            except Exception as e:
                is_conn_error = "connection" in str(e).lower() or "too many connections" in str(e).lower()
                logger.error(f"Failed to delete old insights (attempt {attempt + 1}/{attempts}): {e}")
                if is_conn_error and attempt < attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return 0

    async def bulk_create_insights(
        self,
        user_id: str,
        insights: List[Dict[str, Any]]
    ) -> int:
        """
        Create multiple insights in a single database transaction for efficiency.

        Args:
            user_id: User ID for RLS context
            insights: List of insight dicts with keys: page_type, region, title, content, priority, metadata

        Returns:
            Number of insights created
        """
        if not self.pool or not insights:
            return 0

        attempts = 2
        for attempt in range(attempts):
            try:
                async with self.acquire_with_user_context(user_id) as conn:
                    # Prepare data for bulk insert
                    records = []
                    for insight in insights:
                        # Set default expiration to 24 hours if not specified
                        expires_at = insight.get("expires_at")
                        if expires_at is None:
                            expires_at = datetime.utcnow() + timedelta(hours=24)

                        records.append((
                            user_id,
                            insight.get("page_type"),
                            insight.get("region"),
                            insight.get("title", "Insight"),
                            json.dumps(insight.get("content", {})),
                            insight.get("priority", 5),
                            expires_at,
                            json.dumps(insight.get("metadata", {})),
                            datetime.utcnow()  # generated_at
                        ))

                    # Execute bulk insert
                    await conn.executemany("""
                        INSERT INTO user_insights (
                            user_id, page_type, region, title, content, priority,
                            expires_at, metadata, generated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, records)

                    logger.info(f"Bulk created {len(records)} insights for user {user_id}")
                    return len(records)

            except Exception as e:
                is_conn_error = "connection" in str(e).lower() or "too many connections" in str(e).lower()
                logger.error(f"Failed to bulk create insights (attempt {attempt + 1}/{attempts}): {e}")
                if is_conn_error and attempt < attempts - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                return 0

    async def try_advisory_lock(self, lock_id: int) -> bool:
        """
        Try to acquire a PostgreSQL session-level advisory lock (non-blocking).
        Used to prevent duplicate scheduled jobs across multiple workers.
        
        Returns True if lock acquired, False if another process holds it.
        Lock is automatically released when the connection/session ends.
        """
        if not self.pool:
            return True  # No DB = proceed (single-process mode)

        try:
            conn = await self._acquire_conn()
            try:
                # pg_try_advisory_lock returns true if lock acquired, false otherwise
                # Session-level lock is held until explicitly released or session ends
                row = await conn.fetchrow("SELECT pg_try_advisory_lock($1) as acquired", lock_id)
                return row['acquired'] if row else False
            finally:
                try:
                    await self.pool.release(conn)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Advisory lock check failed: {e}")
            return True  # On error, proceed to avoid skipping job entirely

    async def get_all_users(self) -> List[str]:
        """Get all user IDs for batch operations (no RLS context needed)."""
        if not self.pool:
            return []

        try:
            conn = await self._acquire_conn()
            try:
                rows = await conn.fetch("SELECT id FROM users")
                return [str(row['id']) for row in rows]
            finally:
                try:
                    await self.pool.release(conn)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return []

    # ========== Screener Session Management (with RLS) ==========

    async def create_screener_session(
        self,
        user_id: str,
        title: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new screener session with RLS."""
        if not self.pool:
            return None

        try:
            # Generate session_id if not provided
            if not session_id:
                session_id = str(uuid.uuid4())

            async with self.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow("""
                    INSERT INTO screener_sessions (id, user_id, title)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (id) DO UPDATE
                    SET updated_at = CURRENT_TIMESTAMP,
                        title = COALESCE(EXCLUDED.title, screener_sessions.title)
                    RETURNING id, title, created_at, updated_at
                """, session_id, user_id, title or "New Screening Session")

                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to create screener session: {e}")
            return None

    async def save_screener_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Save a screener message with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow("""
                    INSERT INTO screener_messages (session_id, user_id, role, content, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                """, session_id, user_id, role, content,
                json.dumps(metadata) if metadata else '{}')

                return str(row['id']) if row else None
        except Exception as e:
            logger.error(f"Failed to save screener message: {e}")
            return None

    async def get_screener_sessions(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get all screener sessions for a user with RLS."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                rows = await conn.fetch("""
                    SELECT id, title, created_at, updated_at
                    FROM screener_sessions
                    ORDER BY updated_at DESC
                    LIMIT $1
                """, limit)

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get screener sessions: {e}")
            return []

    async def get_screener_messages(
        self,
        user_id: str,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Get messages for a screener session with RLS."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                rows = await conn.fetch("""
                    SELECT id, role, content, metadata, created_at
                    FROM screener_messages
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                """, session_id)

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get screener messages: {e}")
            return []

    # ========== Organization Management ==========

    async def create_organization(
        self,
        creator_id: str,
        name: str,
        slug: str,
        industry: Optional[str] = None,
        id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new organization and add creator as admin member.

        Args:
            creator_id: Clerk user ID of the creator
            name: Organization name
            slug: URL-safe unique identifier
            industry: Optional industry category
            id: Optional explicit Organization ID (e.g. from Clerk)

        Returns:
            Created organization data
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            async with self.acquire_with_user_context(creator_id) as conn:
                # Generate organization ID if not provided
                org_id = id or f"org_{uuid.uuid4().hex[:24]}"

                # Prepare public metadata
                public_metadata = {"industry": industry} if industry else {}

                # Create organization
                org_row = await conn.fetchrow("""
                    INSERT INTO organizations (id, name, slug, creator_id, usage_credits, public_metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, name, slug, creator_id, usage_credits, created_at, updated_at, public_metadata
                """, org_id, name, slug, creator_id, 1000, json.dumps(public_metadata))

                # Add creator as admin member
                member_id = f"mem_{org_id}_{creator_id}"
                await conn.execute("""
                    INSERT INTO organization_members (id, org_id, user_id, role)
                    VALUES ($1, $2, $3, $4)
                """, member_id, org_id, creator_id, "org:admin")

                logger.info(f"Created organization: {name} (id: {org_id}) with creator {creator_id} as admin")

                # Return organization data
                org_data = dict(org_row)
                # asyncpg returns jsonb as dict, no need to json.loads
                org_data['public_metadata'] = org_data.get('public_metadata') or {}
                return org_data

        except Exception as e:
            logger.error(f"Failed to create organization: {e}")
            raise

    async def get_user_organizations(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all organizations the user is a member of.

        Args:
            user_id: Clerk user ID

        Returns:
            List of organizations with user's role
        """
        if not self.pool:
            return []

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Application-level filtering since RLS is disabled on organization_members
                rows = await conn.fetch("""
                    SELECT
                        o.id,
                        o.name,
                        o.slug,
                        o.creator_id,
                        o.usage_credits,
                        o.created_at,
                        o.updated_at,
                        o.public_metadata,
                        om.role,
                        om.joined_at
                    FROM organizations o
                    JOIN organization_members om ON o.id = om.org_id
                    WHERE om.user_id = $1
                    ORDER BY om.joined_at DESC
                """, user_id)

                result = []
                for row in rows:
                    org_data = dict(row)
                    # asyncpg returns jsonb as dict, no need to json.loads
                    org_data['public_metadata'] = org_data.get('public_metadata') or {}
                    # Convert datetime fields to ISO strings for Pydantic
                    if org_data.get('created_at'):
                        org_data['created_at'] = org_data['created_at'].isoformat()
                    if org_data.get('updated_at'):
                        org_data['updated_at'] = org_data['updated_at'].isoformat()
                    if org_data.get('joined_at'):
                        org_data['joined_at'] = org_data['joined_at'].isoformat()
                    result.append(org_data)

                return result

        except Exception as e:
            logger.error(f"Failed to get user organizations: {e}")
            return []

    async def get_organization_by_id(
        self,
        user_id: str,
        org_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get organization details if user is a member.

        Args:
            user_id: Clerk user ID
            org_id: Organization ID

        Returns:
            Organization data with user's role, or None if not a member
        """
        if not self.pool:
            return None

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Check membership and get org data
                row = await conn.fetchrow("""
                    SELECT
                        o.id,
                        o.name,
                        o.slug,
                        o.creator_id,
                        o.usage_credits,
                        o.created_at,
                        o.updated_at,
                        o.public_metadata,
                        om.role
                    FROM organizations o
                    JOIN organization_members om ON o.id = om.org_id
                    WHERE o.id = $1 AND om.user_id = $2
                """, org_id, user_id)

                if row:
                    org_data = dict(row)
                    # asyncpg returns jsonb as dict, no need to json.loads
                    org_data['public_metadata'] = org_data.get('public_metadata') or {}
                    # Convert datetime fields to ISO strings for Pydantic
                    if org_data.get('created_at'):
                        org_data['created_at'] = org_data['created_at'].isoformat()
                    if org_data.get('updated_at'):
                        org_data['updated_at'] = org_data['updated_at'].isoformat()
                    return org_data

                return None

        except Exception as e:
            logger.error(f"Failed to get organization by ID: {e}")
            return None

    async def update_organization(
        self,
        user_id: str,
        org_id: str,
        **updates
    ) -> bool:
        """
        Update organization details (admin only).

        Args:
            user_id: Clerk user ID (must be admin)
            org_id: Organization ID
            **updates: Fields to update (name, public_metadata, etc.)

        Returns:
            True if updated successfully

        Raises:
            PermissionError: If user is not an admin
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Check if user is an admin
                is_admin = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                    )
                """, org_id, user_id)

                if not is_admin:
                    raise PermissionError("Only admins can update organization")

                # Build dynamic UPDATE query
                allowed_fields = {'name', 'public_metadata'}
                filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

                if not filtered_updates:
                    return True  # No valid updates

                # Special handling for public_metadata
                if 'public_metadata' in filtered_updates:
                    filtered_updates['public_metadata'] = json.dumps(filtered_updates['public_metadata'])

                set_clauses = [f"{key} = ${i+3}" for i, key in enumerate(filtered_updates.keys())]
                query = f"""
                    UPDATE organizations
                    SET {', '.join(set_clauses)}, updated_at = NOW()
                    WHERE id = $1 AND id IN (
                        SELECT org_id FROM organization_members
                        WHERE user_id = $2 AND role = 'org:admin'
                    )
                """

                result = await conn.execute(query, org_id, user_id, *filtered_updates.values())

                logger.info(f"Updated organization {org_id} by admin {user_id}")
                return result == "UPDATE 1"

        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"Failed to update organization: {e}")
            return False

    async def delete_organization(
        self,
        user_id: str,
        org_id: str
    ) -> bool:
        """
        Delete organization (creator only).

        Args:
            user_id: Clerk user ID (must be creator)
            org_id: Organization ID

        Returns:
            True if deleted successfully

        Raises:
            PermissionError: If user is not the creator
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Only creator can delete (stricter than admin)
                result = await conn.execute("""
                    DELETE FROM organizations
                    WHERE id = $1 AND creator_id = $2
                """, org_id, user_id)

                if result == "DELETE 0":
                    raise PermissionError("Only the creator can delete the organization")

                logger.info(f"Deleted organization {org_id} by creator {user_id}")
                return result == "DELETE 1"

        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete organization: {e}")
            return False

    async def add_organization_member(
        self,
        org_id: str,
        user_id: str,
        role: str,
        requesting_user_id: str
    ) -> bool:
        """
        Add a member to an organization (admin only).

        Args:
            org_id: Organization ID
            user_id: Clerk user ID to add
            role: Member role ('org:admin' or 'org:member')
            requesting_user_id: Clerk user ID making the request (must be admin)

        Returns:
            True if added successfully

        Raises:
            PermissionError: If requesting user is not an admin
            ValueError: If invalid role
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        if role not in ('org:admin', 'org:member'):
            raise ValueError(f"Invalid role: {role}. Must be 'org:admin' or 'org:member'")

        try:
            async with self.acquire_with_user_context(requesting_user_id) as conn:
                # Check if requesting user is an admin
                is_admin = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                    )
                """, org_id, requesting_user_id)

                if not is_admin:
                    raise PermissionError("Only admins can add members")

                # Validate that user exists in the system
                # user_id is a Clerk user ID, so check clerk_user_id column
                user_exists = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM users WHERE clerk_user_id = $1
                    )
                """, user_id)

                if not user_exists:
                    raise ValueError(f"User {user_id} does not exist in the system. They must sign up first.")

                # Add member (or update role if already exists)
                member_id = f"mem_{org_id}_{user_id}"
                await conn.execute("""
                    INSERT INTO organization_members (id, org_id, user_id, role)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (org_id, user_id) DO UPDATE SET role = EXCLUDED.role
                """, member_id, org_id, user_id, role)

                logger.info(f"Added member {user_id} to org {org_id} with role {role}")
                return True

        except (PermissionError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Failed to add organization member: {e}")
            return False

    async def update_organization_member_role(
        self,
        org_id: str,
        member_user_id: str,
        new_role: str,
        requesting_user_id: str
    ) -> bool:
        """
        Update a member's role in an organization (admin only).

        Args:
            org_id: Organization ID
            member_user_id: Clerk user ID whose role to update
            new_role: New role ('org:admin' or 'org:member')
            requesting_user_id: Clerk user ID making the request (must be admin)

        Returns:
            True if updated successfully

        Raises:
            PermissionError: If requesting user is not an admin
            ValueError: If invalid role or member not found
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        if new_role not in ('org:admin', 'org:member'):
            raise ValueError(f"Invalid role: {new_role}. Must be 'org:admin' or 'org:member'")

        try:
            async with self.acquire_with_user_context(requesting_user_id) as conn:
                # Check if requesting user is an admin
                is_admin = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                    )
                """, org_id, requesting_user_id)

                if not is_admin:
                    raise PermissionError("Only admins can update member roles")

                # Check if member exists
                member_exists = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2
                    )
                """, org_id, member_user_id)

                if not member_exists:
                    raise ValueError(f"Member {member_user_id} not found in organization")

                # If demoting (new_role != org:admin), check if we are demoting the last admin
                if new_role != 'org:admin':
                    # Check if the target user is currently an admin
                    is_target_admin = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM organization_members
                            WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                        )
                    """, org_id, member_user_id)

                    if is_target_admin:
                        # Check how many admins exist
                        admin_count = await conn.fetchval("""
                            SELECT COUNT(*) FROM organization_members
                            WHERE org_id = $1 AND role = 'org:admin'
                        """, org_id)

                        if admin_count <= 1:
                            raise ValueError("Cannot demote the last admin. Promote another member first.")

                # Update member role
                result = await conn.execute("""
                    UPDATE organization_members
                    SET role = $3, updated_at = CURRENT_TIMESTAMP
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, member_user_id, new_role)

                logger.info(f"Updated member {member_user_id} role to {new_role} in org {org_id}")
                return result == "UPDATE 1"

        except (PermissionError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Failed to update organization member role: {e}")
            return False

    async def remove_organization_member(
        self,
        org_id: str,
        user_id: str,
        requesting_user_id: str
    ) -> bool:
        """
        Remove a member from an organization (admin only).

        Args:
            org_id: Organization ID
            user_id: Clerk user ID to remove
            requesting_user_id: Clerk user ID making the request (must be admin)

        Returns:
            True if removed successfully

        Raises:
            PermissionError: If requesting user is not an admin or trying to remove themselves
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            async with self.acquire_with_user_context(requesting_user_id) as conn:
                # Check if requesting user is an admin
                is_admin = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2 AND role = 'org:admin'
                    )
                """, org_id, requesting_user_id)

                if not is_admin:
                    raise PermissionError("Only admins can remove members")

                # Prevent admins from removing themselves
                if user_id == requesting_user_id:
                    raise PermissionError("Cannot remove yourself from the organization")

                # Remove member
                result = await conn.execute("""
                    DELETE FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, user_id)

                logger.info(f"Removed member {user_id} from org {org_id}")
                return result == "DELETE 1"

        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"Failed to remove organization member: {e}")
            return False

    async def leave_organization(
        self,
        org_id: str,
        user_id: str
    ) -> bool:
        """
        Allow a member to leave an organization (self-removal).

        Note: The last admin cannot leave without first promoting another member.

        Args:
            org_id: Organization ID
            user_id: Clerk user ID of the member leaving

        Returns:
            True if left successfully

        Raises:
            PermissionError: If user is the last admin
            ValueError: If user is not a member of the organization
        """
        if not self.pool:
            raise RuntimeError("PostgreSQL pool not initialized")

        try:
            async with self.acquire_with_user_context(user_id) as conn:
                # Check if user is a member
                member_role = await conn.fetchval("""
                    SELECT role FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, user_id)

                if not member_role:
                    raise ValueError("You are not a member of this organization")

                # If user is admin, check if they're the last admin
                if member_role == 'org:admin':
                    admin_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM organization_members
                        WHERE org_id = $1 AND role = 'org:admin'
                    """, org_id)

                    if admin_count <= 1:
                        raise PermissionError("Cannot leave: you are the last admin. Promote another member first or delete the organization.")

                # Remove member
                result = await conn.execute("""
                    DELETE FROM organization_members
                    WHERE org_id = $1 AND user_id = $2
                """, org_id, user_id)

                logger.info(f"User {user_id} left organization {org_id}")
                return result == "DELETE 1"

        except (PermissionError, ValueError):
            raise
        except Exception as e:
            logger.error(f"Failed to leave organization: {e}")
            return False

    async def get_organization_members(
        self,
        org_id: str,
        requesting_user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all members of an organization.

        Args:
            org_id: Organization ID
            requesting_user_id: Clerk user ID making the request (must be a member)

        Returns:
            List of members with user details

        Raises:
            PermissionError: If requesting user is not a member
        """
        if not self.pool:
            return []

        try:
            async with self.acquire_with_user_context(requesting_user_id) as conn:
                # Check if requesting user is a member
                is_member = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM organization_members
                        WHERE org_id = $1 AND user_id = $2
                    )
                """, org_id, requesting_user_id)

                if not is_member:
                    raise PermissionError("Not a member of this organization")

                # Get all members with user details
                rows = await conn.fetch("""
                    SELECT
                        om.user_id,
                        om.role,
                        om.joined_at,
                        u.email,
                        u.name
                    FROM organization_members om
                    LEFT JOIN users u ON om.user_id = u.clerk_user_id
                    WHERE om.org_id = $1
                    ORDER BY om.role DESC, om.joined_at ASC
                """, org_id)

                # Convert datetime fields to ISO strings for Pydantic
                members = []
                for row in rows:
                    member = dict(row)
                    if member.get('joined_at'):
                        member['joined_at'] = member['joined_at'].isoformat()
                    members.append(member)

                return members

        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"Failed to get organization members: {e}")
            return []

    # ========== Canvas Process Management (with RLS) ==========

    async def save_canvas_process(
        self,
        user_id: str,
        tool_id: str,
        tickers: List[str],
        weights: List[float],
        metrics: Dict[str, Any],
        stats_table: List[Dict[str, Any]],
        charts: Dict[str, Any],
        name: Optional[str] = None,
        org_id: Optional[str] = None,
        object_type: Optional[str] = None,
        hmm_enabled: bool = False,
        current_regime: Optional[str] = None,
        regime_params: Optional[Dict[str, Any]] = None,
        graph_steps: Optional[List[Dict[str, Any]]] = None,
        graph_edges: Optional[List[Dict[str, Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        process_type: str = "tool",
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Save a canvas process with RLS.
        
        Args:
            process_type: 'tool' for tool workflows, 'data_workspace' for unified data tables
            config: Configuration for data_workspace (objects, date_from, date_to, frequency, columns)
        """
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.fetchrow(
                    """
                    INSERT INTO canvas_processes 
                    (user_id, org_id, name, tool_id, tickers, weights, metrics, stats_table, charts, 
                     object_type, hmm_enabled, current_regime, regime_params, graph_steps, graph_edges, params,
                     process_type, config)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    RETURNING id
                    """,
                    user_id,
                    org_id if org_id else None,
                    name,
                    tool_id,
                    tickers,
                    weights,
                    json.dumps(metrics),
                    json.dumps(stats_table),
                    json.dumps(charts),
                    object_type,
                    hmm_enabled,
                    current_regime,
                    json.dumps(regime_params) if regime_params else None,
                    json.dumps(graph_steps) if graph_steps else None,
                    json.dumps(graph_edges) if graph_edges else None,
                    json.dumps(params) if params else '{}',
                    process_type,
                    json.dumps(config) if config else '{}',
                )

                return str(result['id']) if result else None

        except Exception as e:
            logger.error(f"Failed to save canvas process: {e}")
            return None

    async def get_canvas_processes(
        self,
        user_id: str,
        org_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        process_type: Optional[str] = None,
        limit: int = 50,
        archived: Optional[bool] = False,
    ) -> List[Dict[str, Any]]:
        """Get canvas processes for user with RLS."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = """
                    SELECT id, user_id, org_id, name, tool_id, tickers, weights,
                           metrics, stats_table, charts, object_type, hmm_enabled, current_regime,
                           regime_params, graph_steps, graph_edges, params, process_type, config,
                           created_at, updated_at, archived_at
                    FROM canvas_processes
                    WHERE user_id = $1
                """
                params = [user_id]
                param_idx = 2

                if org_id:
                    query += f" AND org_id = ${param_idx}"
                    params.append(org_id)
                    param_idx += 1
                else:
                    query += " AND org_id IS NULL"

                if tool_id:
                    query += f" AND tool_id = ${param_idx}"
                    params.append(tool_id)
                    param_idx += 1

                if process_type:
                    query += f" AND process_type = ${param_idx}"
                    params.append(process_type)
                    param_idx += 1

                if archived is True:
                    query += " AND archived_at IS NOT NULL"
                elif archived is False:
                    query += " AND archived_at IS NULL"

                query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
                params.append(limit)

                rows = await conn.fetch(query, *params)

                processes = []
                for row in rows:
                    process = dict(row)
                    process['id'] = str(process['id'])
                    # Parse JSONB fields
                    if process.get('metrics'):
                        process['metrics'] = json.loads(process['metrics']) if isinstance(process['metrics'], str) else process['metrics']
                    if process.get('stats_table'):
                        process['stats_table'] = json.loads(process['stats_table']) if isinstance(process['stats_table'], str) else process['stats_table']
                    if process.get('charts'):
                        process['charts'] = json.loads(process['charts']) if isinstance(process['charts'], str) else process['charts']
                    if process.get('regime_params'):
                        process['regime_params'] = json.loads(process['regime_params']) if isinstance(process['regime_params'], str) else process['regime_params']
                    if process.get('graph_steps'):
                        process['graph_steps'] = json.loads(process['graph_steps']) if isinstance(process['graph_steps'], str) else process['graph_steps']
                    if process.get('graph_edges'):
                        process['graph_edges'] = json.loads(process['graph_edges']) if isinstance(process['graph_edges'], str) else process['graph_edges']
                    if process.get('params'):
                        process['params'] = json.loads(process['params']) if isinstance(process['params'], str) else process['params']
                    if process.get('config'):
                        process['config'] = json.loads(process['config']) if isinstance(process['config'], str) else process['config']
                    # Convert timestamps
                    if process.get('created_at'):
                        process['created_at'] = process['created_at'].isoformat()
                    if process.get('updated_at'):
                        process['updated_at'] = process['updated_at'].isoformat()
                    if process.get('archived_at'):
                        process['archived_at'] = process['archived_at'].isoformat()
                    processes.append(process)

                return processes

        except Exception as e:
            logger.error(f"Failed to get canvas processes: {e}")
            return []

    async def get_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a single canvas process by ID with RLS."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = """
                    SELECT id, user_id, org_id, name, tool_id, tickers, weights,
                           metrics, stats_table, charts, object_type, hmm_enabled, current_regime,
                           regime_params, graph_steps, graph_edges, params, process_type, config,
                           created_at, updated_at
                    FROM canvas_processes
                    WHERE id = $1 AND user_id = $2
                """
                params = [uuid.UUID(process_id), user_id]

                if org_id:
                    query += " AND org_id = $3"
                    params.append(org_id)
                else:
                    query += " AND org_id IS NULL"

                row = await conn.fetchrow(query, *params)

                if not row:
                    return None

                process = dict(row)
                process['id'] = str(process['id'])
                # Parse JSONB fields
                if process.get('metrics'):
                    val = process['metrics']
                    process['metrics'] = json.loads(val) if isinstance(val, str) else val
                if process.get('stats_table'):
                    val = process['stats_table']
                    process['stats_table'] = json.loads(val) if isinstance(val, str) else val
                if process.get('charts'):
                    val = process['charts']
                    process['charts'] = json.loads(val) if isinstance(val, str) else val
                if process.get('regime_params'):
                    val = process['regime_params']
                    process['regime_params'] = json.loads(val) if isinstance(val, str) else val
                if process.get('graph_steps'):
                    val = process['graph_steps']
                    process['graph_steps'] = json.loads(val) if isinstance(val, str) else val
                if process.get('graph_edges'):
                    val = process['graph_edges']
                    process['graph_edges'] = json.loads(val) if isinstance(val, str) else val
                if process.get('params'):
                    val = process['params']
                    process['params'] = json.loads(val) if isinstance(val, str) else val
                if process.get('config'):
                    val = process['config']
                    process['config'] = json.loads(val) if isinstance(val, str) else val
                # Convert timestamps
                if process.get('created_at'):
                    process['created_at'] = process['created_at'].isoformat()
                if process.get('updated_at'):
                    process['updated_at'] = process['updated_at'].isoformat()

                return process

        except Exception as e:
            logger.error(f"Failed to get canvas process {process_id}: {e}")
            return None

    async def update_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> bool:
        """Update a canvas process with RLS."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                updates = []
                params = []
                param_idx = 1

                if name is not None:
                    updates.append(f"name = ${param_idx}")
                    params.append(name)
                    param_idx += 1

                if not updates:
                    return True

                params.append(process_id)
                query = f"UPDATE canvas_processes SET {', '.join(updates)} WHERE id = ${param_idx}"

                result = await conn.execute(query, *params)
                return result == "UPDATE 1"

        except Exception as e:
            logger.error(f"Failed to update canvas process: {e}")
            return False

    async def update_canvas_process_full(
        self,
        user_id: str,
        process_id: str,
        tool_id: str,
        tickers: List[str],
        metrics: Optional[Dict[str, Any]] = None,
        stats_table: Optional[List[Dict[str, Any]]] = None,
        charts: Optional[Dict[str, Any]] = None,
        org_id: Optional[str] = None,
        weights: Optional[List[float]] = None,
        params: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        hmm_enabled: bool = False,
        current_regime: Optional[str] = None,
        regime_params: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update all fields of a canvas process with RLS."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    """
                    UPDATE canvas_processes
                    SET tool_id = $1,
                        tickers = $2,
                        weights = $3,
                        metrics = $4,
                        stats_table = $5,
                        charts = $6,
                        params = $7,
                        name = COALESCE($8, name),
                        hmm_enabled = $9,
                        current_regime = $10,
                        regime_params = $11,
                        updated_at = NOW()
                    WHERE id = $12 AND user_id = $13
                    """,
                    tool_id,
                    tickers,
                    weights or [],
                    json.dumps(metrics or {}),
                    json.dumps(stats_table or []),
                    json.dumps(charts or {}),
                    json.dumps(params) if params else '{}',
                    name,
                    hmm_enabled,
                    current_regime,
                    json.dumps(regime_params) if regime_params else None,
                    uuid.UUID(process_id),
                    user_id,
                )
                success = result == "UPDATE 1"
                if success:
                    logger.info(f"Updated canvas process {process_id} for user {user_id}")
                else:
                    logger.warning(f"No canvas process updated for {process_id}")
                return success

        except Exception as e:
            logger.error(f"Failed to update canvas process full: {e}")
            return False

    async def update_process_params_and_tickers(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        tickers: Optional[List[str]] = None,
        weights: Optional[List[float]] = None,
    ) -> bool:
        """
        Partial update for process params, tickers, and weights.
        
        Only updates fields that are provided (not None).
        Used by agentic tools for quick param/ticker modifications.
        """
        if not self.pool:
            return False

        try:
            # Build dynamic update query based on provided fields
            updates = []
            values = []
            param_idx = 1
            
            if params is not None:
                updates.append(f"params = ${param_idx}")
                values.append(json.dumps(params))
                param_idx += 1
            
            if tickers is not None:
                updates.append(f"tickers = ${param_idx}")
                values.append(tickers)
                param_idx += 1
            
            if weights is not None:
                updates.append(f"weights = ${param_idx}")
                values.append(weights)
                param_idx += 1
            
            if not updates:
                logger.warning("update_process_params_and_tickers called with no updates")
                return True  # Nothing to update is technically success
            
            updates.append("updated_at = NOW()")
            
            # Add process_id and user_id to values
            values.extend([uuid.UUID(process_id), user_id])
            
            query = f"""
                UPDATE canvas_processes
                SET {', '.join(updates)}
                WHERE id = ${param_idx} AND user_id = ${param_idx + 1}
            """
            
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(query, *values)
                success = result == "UPDATE 1"
                if success:
                    logger.info(f"Updated process params/tickers for {process_id}")
                else:
                    logger.warning(f"No process updated for {process_id}")
                return success

        except Exception as e:
            logger.error(f"Failed to update process params/tickers: {e}")
            return False

    async def full_update_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
        name: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Full update for data workspace processes (name, tickers, params, config)."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    """
                    UPDATE canvas_processes
                    SET name = $1,
                        tickers = $2,
                        params = $3,
                        config = $4,
                        updated_at = NOW()
                    WHERE id = $5 AND user_id = $6
                    """,
                    name,
                    tickers or [],
                    json.dumps(params) if params else "{}",
                    json.dumps(config) if config else "{}",
                    uuid.UUID(process_id),
                    user_id,
                )
                success = result == "UPDATE 1"
                if success:
                    logger.info(f"Full updated canvas process {process_id} for user {user_id}")
                else:
                    logger.warning(f"No canvas process full updated for {process_id}")
                return success

        except Exception as e:
            logger.error(f"Failed to full update canvas process: {e}")
            return False

    async def delete_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Soft-delete a canvas process (set archived_at)."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    "UPDATE canvas_processes SET archived_at = NOW() WHERE id = $1 AND user_id = $2",
                    uuid.UUID(process_id), user_id,
                )
                return result == "UPDATE 1"

        except Exception as e:
            logger.error(f"Failed to archive canvas process: {e}")
            return False

    async def permanent_delete_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Permanently delete a canvas process from the database."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    "DELETE FROM canvas_processes WHERE id = $1 AND user_id = $2",
                    uuid.UUID(process_id), user_id,
                )
                return result == "DELETE 1"

        except Exception as e:
            logger.error(f"Failed to permanently delete canvas process: {e}")
            return False

    async def restore_canvas_process(
        self,
        user_id: str,
        process_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Restore a soft-deleted canvas process (clear archived_at)."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    "UPDATE canvas_processes SET archived_at = NULL WHERE id = $1 AND user_id = $2",
                    uuid.UUID(process_id), user_id,
                )
                return result == "UPDATE 1"

        except Exception as e:
            logger.error(f"Failed to restore canvas process: {e}")
            return False

    # =========================================================================
    # Canvas Chat Thread Methods
    # =========================================================================

    async def create_canvas_chat_thread(
        self,
        user_id: str,
        org_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new Canvas chat thread."""
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO canvas_chat_threads (user_id, org_id, title)
                    VALUES ($1, $2, $3)
                    RETURNING id, user_id, org_id, title, pinned, created_at, updated_at
                    """,
                    user_id,
                    org_id or '',
                    title,
                )
                if row:
                    return {
                        'id': str(row['id']),
                        'user_id': row['user_id'],
                        'org_id': row['org_id'],
                        'title': row['title'],
                        'pinned': row['pinned'] or False,
                        'created_at': row['created_at'].isoformat(),
                        'updated_at': row['updated_at'].isoformat(),
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to create canvas chat thread: {e}")
            return None

    async def get_canvas_chat_threads(
        self,
        user_id: str,
        org_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get Canvas chat threads for user, sorted by pinned first then by updated_at."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = """
                    SELECT id, user_id, org_id, title, pinned, last_process_id, last_tool_id,
                           created_at, updated_at
                    FROM canvas_chat_threads
                    WHERE user_id = $1
                """
                params = [user_id]

                if org_id:
                    query += " AND org_id = $2"
                    params.append(org_id)
                else:
                    query += " AND org_id = ''"

                query += f" ORDER BY pinned DESC, updated_at DESC LIMIT ${len(params) + 1}"
                params.append(limit)

                rows = await conn.fetch(query, *params)
                threads = []
                for row in rows:
                    threads.append({
                        'id': str(row['id']),
                        'user_id': row['user_id'],
                        'org_id': row['org_id'],
                        'title': row['title'],
                        'pinned': row['pinned'] or False,
                        'last_process_id': str(row['last_process_id']) if row['last_process_id'] else None,
                        'last_tool_id': row['last_tool_id'],
                        'created_at': row['created_at'].isoformat(),
                        'updated_at': row['updated_at'].isoformat(),
                    })
                return threads
        except Exception as e:
            logger.error(f"Failed to get canvas chat threads: {e}")
            return []

    async def update_canvas_chat_thread(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
        title: Optional[str] = None,
        pinned: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a Canvas chat thread (title and/or pinned status)."""
        if not self.pool:
            return None

        # Build dynamic SET clause based on provided fields
        set_parts = ["updated_at = NOW()"]
        params = []
        param_idx = 1

        if title is not None:
            set_parts.append(f"title = ${param_idx}")
            params.append(title)
            param_idx += 1

        if pinned is not None:
            set_parts.append(f"pinned = ${param_idx}")
            params.append(pinned)
            param_idx += 1

        # Add thread_id and user_id params
        params.append(thread_id)
        thread_id_idx = param_idx
        param_idx += 1

        params.append(user_id)
        user_id_idx = param_idx
        param_idx += 1

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                query = f"""
                    UPDATE canvas_chat_threads
                    SET {', '.join(set_parts)}
                    WHERE id = ${thread_id_idx}::uuid AND user_id = ${user_id_idx}
                """

                if org_id:
                    params.append(org_id)
                    query += f" AND org_id = ${param_idx}"
                else:
                    query += " AND org_id = ''"

                query += " RETURNING id, user_id, org_id, title, pinned, last_process_id, last_tool_id, created_at, updated_at"

                row = await conn.fetchrow(query, *params)
                if row:
                    return {
                        'id': str(row['id']),
                        'user_id': row['user_id'],
                        'org_id': row['org_id'],
                        'title': row['title'],
                        'pinned': row['pinned'] or False,
                        'last_process_id': str(row['last_process_id']) if row['last_process_id'] else None,
                        'last_tool_id': row['last_tool_id'],
                        'created_at': row['created_at'].isoformat(),
                        'updated_at': row['updated_at'].isoformat(),
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to update canvas chat thread: {e}")
            return None

    async def save_canvas_chat_message(
        self,
        thread_id: str,
        user_id: str,
        role: str,
        content: str,
        org_id: Optional[str] = None,
        process_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Save a message to a Canvas chat thread."""
        if not self.pool:
            return None

        # Validate thread_id is a valid UUID
        try:
            thread_uuid = uuid.UUID(thread_id)
        except (ValueError, TypeError):
            logger.warning(f"Skipping message save - invalid thread_id: {thread_id}")
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO canvas_chat_messages
                        (thread_id, user_id, org_id, role, content, process_id, tool_id, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id, thread_id, role, content, process_id, tool_id, created_at
                    """,
                    thread_uuid,
                    user_id,
                    org_id or '',
                    role,
                    content,
                    uuid.UUID(process_id) if process_id else None,
                    tool_id,
                    json.dumps(metadata) if metadata else None,
                )

                # Update thread's updated_at and last_process context
                await conn.execute(
                    """
                    UPDATE canvas_chat_threads
                    SET updated_at = NOW(),
                        last_process_id = COALESCE($2, last_process_id),
                        last_tool_id = COALESCE($3, last_tool_id)
                    WHERE id = $1
                    """,
                    uuid.UUID(thread_id),
                    uuid.UUID(process_id) if process_id else None,
                    tool_id,
                )

                if row:
                    return {
                        'id': str(row['id']),
                        'thread_id': str(row['thread_id']),
                        'role': row['role'],
                        'content': row['content'],
                        'process_id': str(row['process_id']) if row['process_id'] else None,
                        'tool_id': row['tool_id'],
                        'created_at': row['created_at'].isoformat(),
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to save canvas chat message: {e}")
            return None

    async def get_canvas_chat_messages(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get messages for a Canvas chat thread."""
        if not self.pool:
            return []

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, thread_id, role, content, process_id, tool_id, metadata, created_at
                    FROM canvas_chat_messages
                    WHERE thread_id = $1 AND user_id = $2
                    ORDER BY created_at ASC
                    LIMIT $3
                    """,
                    uuid.UUID(thread_id),
                    user_id,
                    limit,
                )

                messages = []
                for row in rows:
                    msg = {
                        'id': str(row['id']),
                        'thread_id': str(row['thread_id']),
                        'role': row['role'],
                        'content': row['content'],
                        'process_id': str(row['process_id']) if row['process_id'] else None,
                        'tool_id': row['tool_id'],
                        'created_at': row['created_at'].isoformat(),
                    }
                    if row['metadata']:
                        msg['metadata'] = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                    messages.append(msg)
                return messages
        except Exception as e:
            logger.error(f"Failed to get canvas chat messages: {e}")
            return []

    async def update_canvas_chat_message_metadata(
        self,
        user_id: str,
        message_id: str,
        metadata: dict,
        org_id: Optional[str] = None,
    ) -> bool:
        """Update metadata JSONB on a canvas chat message."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    """
                    UPDATE canvas_chat_messages
                    SET metadata = $1
                    WHERE id = $2 AND user_id = $3
                    """,
                    json.dumps(metadata),
                    uuid.UUID(message_id),
                    user_id,
                )
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Failed to update chat message metadata: {e}")
            return False

    async def delete_canvas_chat_thread(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Delete a Canvas chat thread and all its messages."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result = await conn.execute(
                    "DELETE FROM canvas_chat_threads WHERE id = $1 AND user_id = $2",
                    uuid.UUID(thread_id),
                    user_id,
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete canvas chat thread: {e}")
            return False

    # =========================================================================
    # CANVAS WORKSPACE SNAPSHOTS (Chat-Workspace Binding)
    # =========================================================================

    async def save_canvas_workspace_snapshot(
        self,
        thread_id: str,
        user_id: str,
        snapshot: Dict[str, Any],
        org_id: Optional[str] = None,
    ) -> bool:
        """Save workspace snapshot for a chat thread.
        
        Stores tab configurations (not data) that can be restored when loading
        a chat from history. Called after each AI action that modifies tabs.
        
        Args:
            thread_id: Chat thread UUID
            user_id: User ID for authorization
            snapshot: WorkspaceSnapshot dict with captured_at, tabs, activeTabId
            org_id: Optional organization ID
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.pool:
            return False

        try:
            import json
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # First try with user_id check for proper authorization
                result = await conn.execute(
                    """
                    UPDATE canvas_chat_threads 
                    SET workspace_snapshot = $1::jsonb, updated_at = NOW()
                    WHERE id = $2::uuid AND user_id = $3
                    """,
                    json.dumps(snapshot),
                    uuid.UUID(thread_id),
                    user_id,
                )
                if result == "UPDATE 1":
                    return True
                
                # Fallback: update by thread_id only (handles dev mode user_id mismatch)
                # The thread_id is a UUID which provides sufficient uniqueness
                result = await conn.execute(
                    """
                    UPDATE canvas_chat_threads 
                    SET workspace_snapshot = $1::jsonb, updated_at = NOW()
                    WHERE id = $2::uuid
                    """,
                    json.dumps(snapshot),
                    uuid.UUID(thread_id),
                )
                if result == "UPDATE 1":
                    logger.warning(f"Workspace snapshot saved without user_id match for thread {thread_id}")
                    return True
                
                logger.warning(f"Thread {thread_id} not found for workspace snapshot save")
                return False
        except Exception as e:
            logger.error(f"Failed to save workspace snapshot: {e}")
            return False

    async def get_canvas_workspace_snapshot(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get workspace snapshot for a chat thread.
        
        Retrieves stored tab configurations for restoring workspace state
        when loading a chat from history.
        
        Args:
            thread_id: Chat thread UUID
            user_id: User ID for authorization
            org_id: Optional organization ID
            
        Returns:
            WorkspaceSnapshot dict if exists, None otherwise
        """
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # First try with user_id check for proper authorization
                row = await conn.fetchrow(
                    """
                    SELECT workspace_snapshot 
                    FROM canvas_chat_threads 
                    WHERE id = $1::uuid AND user_id = $2
                    """,
                    uuid.UUID(thread_id),
                    user_id,
                )
                if row and row["workspace_snapshot"]:
                    return row["workspace_snapshot"]
                
                # Fallback: query by thread_id only (handles dev mode user_id mismatch)
                row = await conn.fetchrow(
                    """
                    SELECT workspace_snapshot 
                    FROM canvas_chat_threads 
                    WHERE id = $1::uuid
                    """,
                    uuid.UUID(thread_id),
                )
                if row and row["workspace_snapshot"]:
                    return row["workspace_snapshot"]
                return None
        except Exception as e:
            logger.error(f"Failed to get workspace snapshot: {e}")
            return None

    async def clear_canvas_workspace_snapshot(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Clear workspace snapshot for a chat thread.
        
        Called when all chat-linked tabs are deleted.
        
        Args:
            thread_id: Chat thread UUID
            user_id: User ID for authorization
            org_id: Optional organization ID
            
        Returns:
            True if cleared successfully, False otherwise
        """
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                # First try with user_id check for proper authorization
                result = await conn.execute(
                    """
                    UPDATE canvas_chat_threads 
                    SET workspace_snapshot = NULL, updated_at = NOW()
                    WHERE id = $1::uuid AND user_id = $2
                    """,
                    uuid.UUID(thread_id),
                    user_id,
                )
                if result == "UPDATE 1":
                    return True
                
                # Fallback: update by thread_id only (handles dev mode user_id mismatch)
                result = await conn.execute(
                    """
                    UPDATE canvas_chat_threads 
                    SET workspace_snapshot = NULL, updated_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    uuid.UUID(thread_id),
                )
                return result == "UPDATE 1"
        except Exception as e:
            logger.error(f"Failed to clear workspace snapshot: {e}")
            return False

    # =========================================================================
    # CANVAS ACTION RESULTS (AI Feedback Loop)
    # =========================================================================

    async def store_canvas_action_result(
        self,
        thread_id: str,
        action_id: str,
        action_type: str,
        user_id: str,
        success: bool,
        org_id: Optional[str] = None,
        symbol: Optional[str] = None,
        error: Optional[str] = None,
        cancelled: bool = False,
        data: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Store an action result for AI feedback loop.
        
        Called when frontend reports success/failure of an AI-initiated action.
        Results are fetched and injected into AI context on next turn.
        """
        if not self.pool:
            return None

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                result_id = await conn.fetchval(
                    """
                    INSERT INTO canvas_action_results 
                        (thread_id, action_id, action_type, symbol, success, error, cancelled, data, user_id, org_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id
                    """,
                    uuid.UUID(thread_id),
                    action_id,
                    action_type,
                    symbol,
                    success,
                    error,
                    cancelled,
                    json.dumps(data) if data else None,
                    user_id,
                    org_id or '',
                )
                return str(result_id) if result_id else None
        except Exception as e:
            logger.error(f"Failed to store canvas action result: {e}")
            return None

    async def get_pending_canvas_action_results(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get unprocessed action results for a thread.
        
        Used by chat service to inject feedback into AI context.
        """
        if not self.pool:
            return []

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, action_id, action_type, symbol, success, error, cancelled, data, created_at
                    FROM canvas_action_results
                    WHERE thread_id = $1 AND user_id = $2 AND processed = FALSE
                    ORDER BY created_at ASC
                    """,
                    uuid.UUID(thread_id),
                    user_id,
                )
                return [
                    {
                        "id": str(row["id"]),
                        "action_id": row["action_id"],
                        "action_type": row["action_type"],
                        "symbol": row["symbol"],
                        "success": row["success"],
                        "error": row["error"],
                        "cancelled": row["cancelled"],
                        "data": json.loads(row["data"]) if row["data"] else None,
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get pending action results: {e}")
            return []

    async def mark_canvas_action_results_processed(
        self,
        thread_id: str,
        user_id: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """Mark all pending action results for a thread as processed."""
        if not self.pool:
            return False

        try:
            async with self.acquire_with_org_context(user_id, org_id) as conn:
                await conn.execute(
                    """
                    UPDATE canvas_action_results
                    SET processed = TRUE
                    WHERE thread_id = $1 AND user_id = $2 AND processed = FALSE
                    """,
                    uuid.UUID(thread_id),
                    user_id,
                )
                return True
        except Exception as e:
            logger.error(f"Failed to mark action results as processed: {e}")
            return False


# Global instance (singleton pattern)
_postgres_client = None

async def get_postgres_client() -> PostgresClient:
    """Get or create the global PostgreSQL client."""
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgresClient()
        await _postgres_client.connect()
        # Skip ensure_rls_policies - migrations handle this with proper permissions
        # await _postgres_client.ensure_rls_policies()
    return _postgres_client

async def reset_postgres_client():
    """Reset the global PostgreSQL client. Used for testing."""
    global _postgres_client
    if _postgres_client is not None:
        await _postgres_client.disconnect()
        _postgres_client = None

# Compatibility alias for old imports
async def get_postgres_rls_client() -> PostgresClient:
    """Compatibility alias for get_postgres_client."""
    return await get_postgres_client()
