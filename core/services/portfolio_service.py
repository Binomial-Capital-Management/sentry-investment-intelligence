"""
Portfolio Service Layer
Handles all portfolio database operations with proper RLS and type normalization.
Following CODING_RULES.md: KISS, DRY, single responsibility.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PortfolioService:
    """Service layer for portfolio operations with RLS enforcement."""
    
    def __init__(self):
        """Initialize service. DB client obtained per-request for proper RLS."""
        pass
    
    async def list_user_portfolios(self, user_id: str) -> Dict[str, Any]:
        """
        List all portfolios for a user with RLS enforcement.
        
        Args:
            user_id: User ID for RLS context
            
        Returns:
            Dict with portfolios list and metadata
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        if not user_id:
            return {
                "status": "error",
                "message": "User ID required for portfolio access"
            }
        
        if not config.enable_postgres:
            return {
                "status": "success",
                "portfolios": [],
                "message": "Database not enabled",
                "count": 0
            }
        
        try:
            pg = await get_postgres_rls_client()
            
            # Use RLS-enforced query with proper transaction scope
            async with pg.acquire_with_user_context(user_id) as conn:
                rows = await conn.fetch("""
                    SELECT id, name, is_default, created_at, updated_at
                    FROM portfolios 
                    ORDER BY is_default DESC, created_at DESC
                """)
            
            if not rows:
                return {
                    "status": "success",
                    "portfolios": [],
                    "message": "No portfolios found",
                    "count": 0
                }
            
            # Convert to DTOs with proper type handling
            from core.utils.dto_utils import record_to_dict
            
            portfolios = []
            default_id = None
            
            for row in rows:
                # Convert once to dict with proper type conversions
                portfolio_dto = record_to_dict(row)
                
                if portfolio_dto.get("is_default"):
                    default_id = portfolio_dto["id"]
                
                portfolios.append(portfolio_dto)
            
            return {
                "status": "success",
                "portfolios": portfolios,
                "default_portfolio_id": default_id,
                "count": len(portfolios),
                "message": f"Found {len(portfolios)} portfolio(s)"
            }
            
        except Exception as e:
            logger.error(f"Failed to list portfolios for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to list portfolios: {str(e)}"
            }
    
    async def get_portfolio(self, user_id: str, portfolio_id_or_name: str) -> Dict[str, Any]:
        """
        Get portfolio details with holdings.
        
        Args:
            user_id: User ID for RLS context
            portfolio_id_or_name: Portfolio UUID or name (case-insensitive)
            
        Returns:
            Portfolio details including tickers and weights
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        if not user_id:
            return {
                "status": "error",
                "message": "User ID required for portfolio access"
            }
        
        if not config.enable_postgres:
            return {
                "status": "error",
                "message": "Database not enabled"
            }
        
        try:
            pg = await get_postgres_rls_client()
            
            async with pg.acquire_with_user_context(user_id) as conn:
                # Try UUID match first
                row = None
                try:
                    import uuid
                    portfolio_uuid = uuid.UUID(portfolio_id_or_name)
                    # Explicitly filter by user_id in addition to RLS
                    row = await conn.fetchrow("""
                        SELECT id, name, tickers, weights, is_default, 
                               created_at, updated_at, metadata, value
                        FROM portfolios 
                        WHERE id = $1 AND user_id = $2
                    """, portfolio_uuid, user_id)
                except (ValueError, TypeError):
                    # Not a UUID, try name match (case-insensitive)
                    rows = await conn.fetch("""
                        SELECT id, name, tickers, weights, is_default, 
                               created_at, updated_at, metadata, value
                        FROM portfolios 
                        WHERE LOWER(name) = LOWER($1) AND user_id = $2
                    """, portfolio_id_or_name, user_id)
                    
                    if len(rows) > 1:
                        # Multiple portfolios with same name - disambiguation needed
                        from core.utils.dto_utils import record_to_dict
                        
                        # Sort by creation date for deterministic selection
                        sorted_rows = sorted(rows, key=lambda r: r["created_at"])
                        candidates = [record_to_dict(r) for r in sorted_rows]
                        
                        return {
                            "status": "error",
                            "error_code": "DISAMBIGUATION_REQUIRED",
                            "message": f"Multiple portfolios named '{portfolio_id_or_name}'. Please use ID.",
                            "candidates": candidates
                        }
                    elif rows:
                        row = rows[0]
            
            if not row:
                return {
                    "status": "error",
                    "message": f"Portfolio '{portfolio_id_or_name}' not found"
                }
            
            # Convert to dict once with proper type conversions
            from core.utils.dto_utils import record_to_dict
            row_dict = record_to_dict(row)
            
            # Normalize metadata to dict
            metadata = self._normalize_metadata(row_dict.get("metadata"))
            # Value is stored directly in the value column, fallback to metadata, then default
            # Convert Decimal to float if needed
            raw_value = row_dict.get("value")
            if raw_value is not None:
                portfolio_value = float(raw_value)
            elif metadata.get("value") is not None:
                portfolio_value = float(metadata.get("value"))
            else:
                portfolio_value = 1000000
            
            # Handle missing weights
            tickers = row_dict.get("tickers", [])
            weights = row_dict.get("weights", [])
            if tickers and not weights:
                weights = [1.0 / len(tickers)] * len(tickers)
            
            # Build DTO (row_dict already has proper types from record_to_dict)
            portfolio_dto = {
                "id": row_dict["id"],  # Already string from record_to_dict
                "name": row_dict["name"],
                "tickers": tickers,
                "weights": weights,
                "value": portfolio_value,
                "is_default": row_dict.get("is_default", False),
                "created_at": row_dict.get("created_at"),  # Already ISO string
                "updated_at": row_dict.get("updated_at")   # Already ISO string
            }
            
            return {
                "status": "success",
                "portfolio": portfolio_dto,
                "message": f"Loaded portfolio: {row_dict['name']}"
            }
            
        except Exception as e:
            logger.error(f"Failed to get portfolio {portfolio_id_or_name} for user {user_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to get portfolio: {str(e)}"
            }
    
    async def get_active_portfolio(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get the active portfolio for a session, falling back to default.
        
        Args:
            session_id: Session ID to check for active portfolio
            user_id: User ID for RLS context
            
        Returns:
            Active or default portfolio details
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        if not config.enable_postgres:
            return {
                "status": "error",
                "message": "Database not enabled"
            }
        
        try:
            pg = await get_postgres_rls_client()
            
            # Check for active portfolio in session
            async with pg.acquire_with_user_context(user_id) as conn:
                # Try to get active portfolio from session
                if session_id:
                    try:
                        import uuid
                        session_uuid = uuid.UUID(session_id)
                        row = await conn.fetchrow("""
                            SELECT active_portfolio_id 
                            FROM chat_sessions 
                            WHERE id = $1 AND user_id = $2
                        """, session_uuid, user_id)
                        
                        if row and row["active_portfolio_id"]:
                            result = await self.get_portfolio(user_id, str(row["active_portfolio_id"]))
                            if result["status"] == "success":
                                result["message"] = f"Using active portfolio: {result['portfolio']['name']}"
                                result["is_active"] = True
                                return result
                    except (ValueError, TypeError):
                        # Invalid session ID format
                        pass
            
            # Fall back to default portfolio
            portfolios = await self.list_user_portfolios(user_id)
            
            if portfolios["status"] != "success":
                return portfolios
            
            default_id = portfolios.get("default_portfolio_id")
            if default_id:
                result = await self.get_portfolio(user_id, default_id)
                if result["status"] == "success":
                    result["message"] = f"Using default portfolio: {result['portfolio']['name']}"
                    result["is_default"] = True
                return result
            
            if portfolios["count"] > 0:
                return {
                    "status": "error",
                    "message": "No active or default portfolio set",
                    "available_portfolios": portfolios["portfolios"]
                }
            
            return {
                "status": "error",
                "message": "No portfolios found"
            }
            
        except Exception as e:
            logger.error(f"Failed to get active portfolio: {e}")
            return {
                "status": "error",
                "message": f"Failed to get active portfolio: {str(e)}"
            }
    
    async def set_active_portfolio(self, session_id: str, user_id: str, portfolio_id: str) -> Dict[str, Any]:
        """
        Set the active portfolio for a session.
        
        Args:
            session_id: Session to update
            user_id: User ID for RLS context
            portfolio_id: Portfolio to set as active
            
        Returns:
            Confirmation of active portfolio setting
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        
        config = get_config()
        
        # Verify portfolio exists and user has access
        portfolio_result = await self.get_portfolio(user_id, portfolio_id)
        
        if portfolio_result["status"] != "success":
            return portfolio_result
        
        portfolio = portfolio_result["portfolio"]
        
        if not config.enable_postgres:
            logger.info(f"Set active portfolio for session {session_id}: {portfolio['name']} (DB disabled)")
            return {
                "status": "success",
                "message": f"Now using portfolio: {portfolio['name']} (session-only)",
                "active_portfolio_id": portfolio["id"],
                "portfolio_name": portfolio["name"],
                "tickers": portfolio["tickers"],
                "weights": portfolio["weights"],
                "value": portfolio["value"]
            }
        
        try:
            pg = await get_postgres_rls_client()
            
            # Persist to database
            async with pg.acquire_with_user_context(user_id) as conn:
                import uuid
                session_uuid = uuid.UUID(session_id)
                portfolio_uuid = uuid.UUID(portfolio["id"])
                
                # Update or create session with active portfolio
                await conn.execute("""
                    UPDATE chat_sessions 
                    SET active_portfolio_id = $1, updated_at = NOW()
                    WHERE id = $2 AND user_id = $3
                """, portfolio_uuid, session_uuid, user_id)
                
            logger.info(f"Set active portfolio for session {session_id}: {portfolio['name']} ({portfolio['id']})")
            
            return {
                "status": "success",
                "message": f"Now using portfolio: {portfolio['name']}",
                "active_portfolio_id": portfolio["id"],
                "portfolio_name": portfolio["name"],
                "tickers": portfolio["tickers"],
                "weights": portfolio["weights"],
                "value": portfolio["value"]
            }
            
        except Exception as e:
            logger.error(f"Failed to set active portfolio: {e}")
            # Still return success with portfolio data, just log the persistence failure
            return {
                "status": "success",
                "message": f"Now using portfolio: {portfolio['name']} (persistence failed)",
                "active_portfolio_id": portfolio["id"],
                "portfolio_name": portfolio["name"],
                "tickers": portfolio["tickers"],
                "weights": portfolio["weights"],
                "value": portfolio["value"],
                "warning": f"Failed to persist selection: {str(e)}"
            }
    
    def _normalize_metadata(self, metadata_raw: Any) -> Dict[str, Any]:
        """
        Normalize metadata to dict, handling JSON strings and None.
        
        Args:
            metadata_raw: Raw metadata from database (str, dict, or None)
            
        Returns:
            Normalized dict (empty dict if invalid)
        """
        if metadata_raw is None:
            return {}
        
        if isinstance(metadata_raw, dict):
            return metadata_raw
        
        if isinstance(metadata_raw, str):
            try:
                return json.loads(metadata_raw)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse metadata JSON: {e}")
                return {}
        
        logger.warning(f"Unexpected metadata type: {type(metadata_raw)}")
        return {}


# Singleton instance
_portfolio_service = None

def get_portfolio_service() -> PortfolioService:
    """Get singleton portfolio service instance."""
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service