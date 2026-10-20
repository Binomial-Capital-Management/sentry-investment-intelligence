"""
IBKR Flex Query integration service.
Fetches portfolio positions from Interactive Brokers using Flex Query API.

Key Features:
- Explicit field parsing with validation (19 fields vs 50+)
- Redis caching with 6-hour TTL
- Fernet encryption for credentials
- Used by both API endpoints and background scheduler

Following CODING_RULES.md: KISS, DRY, YAGNI, explicit over dynamic.
"""

import os
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

try:
    import ibflex
    IBFLEX_AVAILABLE = True
except ImportError:
    IBFLEX_AVAILABLE = False
    logging.warning("ibflex not installed - IBKR integration unavailable")

from cryptography.fernet import Fernet

from core.cache import cache
from core.database.postgres_client import get_postgres_rls_client

logger = logging.getLogger(__name__)


# IBKR Flex Query field mapping
# Based on ibflex library OpenPosition attributes and Sentry requirements
REQUIRED_FIELDS = [
    'accountId',          # Account identifier
    'currency',           # Position currency
    'assetCategory',      # Asset class (STK, OPT, FUT, etc.)
    'symbol',             # Ticker symbol
    'description',        # Security description
    'position',           # Number of shares/contracts
    'markPrice',          # Current market price
    'positionValue',      # Current position value
    'costBasisPrice',     # Average cost per share
    'costBasisMoney',     # Total cost basis
    'fifoPnlUnrealized'   # Unrealized profit/loss
]

RECOMMENDED_FIELDS = [
    'fxRateToBase',       # Exchange rate to base currency
    'subCategory',        # Asset subcategory
    'conid',              # Contract identifier (unique ID)
    'multiplier',         # Contract multiplier (options/futures)
    'reportDate',         # Date of report
    'openPrice',          # Opening price
    'percentOfNAV',       # Position as % of portfolio
    'side'                # Long/Short
]

# Fallback mappings for alternative field names
FIELD_ALIASES = {
    'position': ['position', 'quantity'],  # Try position first, fallback to quantity
    'fifoPnlUnrealized': ['fifoPnlUnrealized', 'unrealizedCapitalGainsPnl'],
}

# Fields requiring float conversion from XML strings
NUMERIC_FIELDS = {
    'position', 'markPrice', 'positionValue', 'costBasisPrice',
    'costBasisMoney', 'fifoPnlUnrealized', 'fxRateToBase',
    'multiplier', 'strike', 'percentOfNAV', 'openPrice',
    'fineness', 'weight', 'accruedInt'
}

TRADE_NUMERIC_FIELDS = {
    'quantity',
    'tradePrice',
    'tradeMoney',
    'proceeds',
    'cost',
    'ibCommission',
    'otherCommission',
    'brokerExecutionCommission',
    'tradeFee',
    'taxes',
    'fxRateToBase',
    'multiplier',
    'strike',
    'fifoPnlRealized',  # Realized P&L for closed positions
    'mtmPnl'            # Mark-to-market P&L
}


class IBKRService:
    """
    IBKR position fetcher with Redis caching and dynamic parsing.
    Shared by both API endpoints and background scheduler.
    """

    def __init__(self):
        # Encryption key for storing credentials
        encryption_key = os.getenv('BROKER_CREDENTIAL_ENCRYPTION_KEY')
        if not encryption_key:
            logger.warning("BROKER_CREDENTIAL_ENCRYPTION_KEY not set - IBKR integration disabled")
            self.enabled = False
            return

        try:
            self.fernet = Fernet(encryption_key.encode())
            self.enabled = IBFLEX_AVAILABLE
        except Exception as e:
            logger.error(f"Failed to initialize Fernet encryption: {e}")
            self.enabled = False

        # Cache TTL: 6 hours (aligned with twice-daily sync schedule)
        self.cache_ttl = int(os.getenv('IBKR_CACHE_TTL_SECONDS', '21600'))

        logger.info(f"IBKRService initialized (enabled={self.enabled}, cache_ttl={self.cache_ttl}s)")

    def encrypt_token(self, token: str) -> str:
        """Encrypt IBKR Flex Token before database storage."""
        if not self.enabled:
            raise RuntimeError("IBKRService not enabled")
        return self.fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt IBKR Flex Token for API calls."""
        if not self.enabled:
            raise RuntimeError("IBKRService not enabled")
        return self.fernet.decrypt(encrypted_token.encode()).decode()

    async def validate_credentials(
        self,
        flex_token: str,
        flex_query_id: str
    ) -> bool:
        """
        Test IBKR credentials by making a test API call.
        Used during initial connection setup.
        """
        if not self.enabled:
            return False

        try:
            # ibflex.client.download is synchronous - run in thread pool
            response = await asyncio.to_thread(
                ibflex.client.download,
                flex_token,
                flex_query_id
            )
            return response is not None
        except Exception as e:
            logger.error(f"IBKR credential validation failed: {e}")
            return False

    async def get_user_positions(
        self,
        user_id: str,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get user's IBKR positions with caching.

        This is the CORE FUNCTION used by:
        1. API endpoint (when user views portfolio)
        2. Background scheduler (refreshes all users twice daily)
        3. Connection endpoint (immediate first sync)

        Flow:
        1. Check Redis cache (if enabled)
        2. If cache hit: return cached data (50ms response)
        3. If cache miss: fetch from IBKR (3-5s), cache, return

        Args:
            user_id: User ID for RLS context
            use_cache: Whether to check cache first (default True)

        Returns:
            Dict with structure:
            {
                'positions': List[Dict] - Position data with dynamic fields,
                'cash_balance': float - Total cash in USD (from BASE_SUMMARY or USD)
            }
        """
        if not self.enabled:
            raise RuntimeError("IBKRService not enabled - check BROKER_CREDENTIAL_ENCRYPTION_KEY")

        cache_key = f"ibkr_positions:{user_id}"

        # Step 1: Check cache (if enabled)
        if use_cache:
            try:
                cached = cache.get(cache_key)
                if cached:
                    logger.info(f"Cache HIT for user {user_id}")
                    return cached
            except Exception as e:
                logger.warning(f"Redis cache error (non-fatal): {e}")

        # Step 2: Cache miss - fetch from IBKR
        logger.info(f"Cache MISS for user {user_id} - fetching from IBKR")

        try:
            # Get encrypted credentials from database
            connection = await self._get_connection(user_id)
            if not connection:
                raise ValueError(f"No active IBKR connection for user {user_id}")

            # Decrypt token
            decrypted_token = self.decrypt_token(connection['flex_token_encrypted'])

            # Call IBKR API (synchronous library, run in thread pool)
            logger.info(f"Calling IBKR Flex Query API for user {user_id}...")
            response = await asyncio.to_thread(
                ibflex.client.download,
                decrypted_token,
                connection['flex_query_id']
            )

            # Parse XML response using custom ElementTree parser
            logger.info(f"Parsing IBKR XML response with custom ElementTree parser...")
            result = self._parse_flex_query_response(response)

            # Extract positions and cash from result dict
            positions_list = result.get('positions', [])
            cash_balance = result.get('cash_balance', 0.0)
            logger.info(f"Fetched {len(positions_list)} positions, ${cash_balance:,.2f} cash for user {user_id}")

            # Step 3: Cache result (full dict with positions and cash)
            try:
                cache.set(cache_key, result, ttl=self.cache_ttl)
                logger.info(f"Cached {len(positions_list)} positions + cash for user {user_id} (expires in {self.cache_ttl}s)")
            except Exception as e:
                logger.warning(f"Failed to cache positions (non-fatal): {e}")

            # Update last_sync_at timestamp (skip for temp validation connections)
            connection_id = connection.get('id')
            if connection_id and connection_id != 'temp-validation':
                await self._update_last_sync(connection_id)

            return result

        except Exception as e:
            logger.error(f"Failed to fetch positions for user {user_id}: {e}")

            # Try to return stale cache if available (graceful degradation)
            try:
                cached = cache.get(cache_key)
                if cached:
                    logger.warning(f"Returning stale cache for user {user_id} after error")
                    return cached
            except:
                pass

            # No cache available - re-raise error
            raise

    def _parse_flex_query_response(self, xml_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Parse IBKR Flex Query XML response using ElementTree.

        Replaces ibflex.parser.parse() which fails on newer IBKR fields like 'subCategory'.
        Extracts ALL 50+ fields dynamically with proper type conversion.

        Args:
            xml_bytes: Raw XML response from ibflex.client.download()

        Returns:
            List of position dicts with structure:
            {
                'symbol': 'AAPL',
                'position': 100.0,          # float for calculations
                'markPrice': 150.25,        # float for calculations
                'subCategory': 'COMMON',    # NEW: now accessible
                '_source': 'ibkr',
                '_fetched_at': '2025-11-10T15:00:00',
                # ... ALL other IBKR fields
            }

        Raises:
            ValueError: If XML is malformed, too large, or invalid structure
        """
        import xml.etree.ElementTree as ET

        positions = []

        # Security: Check XML size before parsing (prevent DoS)
        MAX_XML_SIZE = 10 * 1024 * 1024  # 10MB - sufficient for any portfolio
        if len(xml_bytes) > MAX_XML_SIZE:
            logger.error(
                f"IBKR returned abnormally large XML: {len(xml_bytes)/1024/1024:.1f}MB. "
                f"Expected <10MB for normal portfolios."
            )
            raise ValueError(
                f"IBKR response too large ({len(xml_bytes)/1024/1024:.1f}MB). "
                f"Maximum allowed: {MAX_XML_SIZE/1024/1024:.0f}MB. "
                f"Contact support if you have >1000 positions."
            )

        # Step 1: Parse XML bytes with security protections
        try:
            # Parse XML without explicit parser (matches test script behavior)
            # Note: Python 3.8+ ElementTree has built-in XXE protection by default
            root = ET.fromstring(xml_bytes)
            logger.info(f"XML parsed successfully into ElementTree ({len(xml_bytes)/1024:.1f}KB)")
        except ET.ParseError as e:
            logger.error(f"IBKR returned invalid XML: {e}")
            raise ValueError(f"IBKR API returned malformed XML response: {e}")

        # Step 2: Find all OpenPosition elements using XPath
        position_elements = root.findall('.//OpenPosition')

        if not position_elements:
            logger.info("No positions found in IBKR Flex Query response (empty portfolio)")
            # Continue to parse cash even if no positions exist
            # Don't return early - cash parsing happens below

        logger.info(f"Found {len(position_elements)} position elements in XML")

        # Step 3: Extract attributes from each position element
        for idx, position_elem in enumerate(position_elements):
            position = {}
            parsing_errors = []

            # Extract ALL attributes dynamically
            for attr_name, attr_value in position_elem.attrib.items():

                # Handle IBKR's NULL convention: empty string = null/not applicable
                # This is explicit - IBKR uses "" to mean "field not applicable"
                if attr_value == "":
                    position[attr_name] = None
                    continue

                # Convert numeric fields for calculations
                if attr_name in NUMERIC_FIELDS:
                    try:
                        # Note: Crypto positions have fractional quantities (e.g., 0.09865661 BTC)
                        # Python float provides sufficient precision (15-17 digits)
                        numeric_value = float(attr_value)
                        position[attr_name] = numeric_value
                    except (ValueError, TypeError) as e:
                        # CRITICAL: Store None instead of string to prevent type errors in calculations
                        logger.error(
                            f"Position {idx} ({position_elem.attrib.get('symbol', 'UNKNOWN')}): "
                            f"CRITICAL - Failed to convert numeric field {attr_name}='{attr_value}' to float. "
                            f"Setting to None. Error: {e}"
                        )
                        position[attr_name] = None
                        parsing_errors.append(f"Invalid {attr_name}: {attr_value}")
                else:
                    # String field - store as-is
                    position[attr_name] = attr_value

            # Track parsing errors for debugging
            if parsing_errors:
                position['_parsing_errors'] = parsing_errors
                logger.warning(
                    f"Position {position.get('symbol', 'UNKNOWN')} has {len(parsing_errors)} "
                    f"parsing errors: {', '.join(parsing_errors)}"
                )

            # Add metadata (required by API router)
            position['_source'] = 'ibkr'
            position['_fetched_at'] = datetime.utcnow().isoformat()

            # Validate required fields (warn only, don't block)
            missing_required = [
                field for field in REQUIRED_FIELDS
                if position.get(field) is None
            ]
            if missing_required:
                logger.warning(
                    f"Position {position.get('symbol', 'UNKNOWN')} is missing "
                    f"required fields: {', '.join(missing_required)}"
                )

            positions.append(position)

        logger.info(
            f"Parsed {len(positions)} positions with dynamic field discovery "
            f"(~{len(position_elements[0].attrib) if position_elements else 0} fields per position)"
        )

        # Step 4: Parse trades/transactions if present (Activity Flex Query trades section)
        trades = []
        trade_elements = root.findall('.//Trade')
        logger.info(f"Found {len(trade_elements)} Trade elements in XML")

        for idx, trade_elem in enumerate(trade_elements):
            trade: Dict[str, Any] = {}
            parsing_errors: List[str] = []

            for attr_name, attr_value in trade_elem.attrib.items():
                if attr_value == "":
                    trade[attr_name] = None
                    continue

                if attr_name in TRADE_NUMERIC_FIELDS:
                    try:
                        trade[attr_name] = float(attr_value)
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Trade {idx} ({trade_elem.attrib.get('symbol', 'UNKNOWN')}): "
                            f"failed to convert numeric field {attr_name}='{attr_value}' to float. "
                            f"Setting to None. Error: {e}"
                        )
                        trade[attr_name] = None
                        parsing_errors.append(f"Invalid {attr_name}: {attr_value}")
                else:
                    trade[attr_name] = attr_value

            if parsing_errors:
                trade['_parsing_errors'] = parsing_errors

            # Enrich with metadata
            trade['_source'] = 'ibkr'
            trade['_fetched_at'] = datetime.utcnow().isoformat()

            # Stable external identifier (helps dedupe on resync)
            external_id = trade.get('tradeID') or trade.get('orderID') or trade.get('relatedTradeID')
            if external_id:
                trade['_external_id'] = str(external_id)

            trades.append(trade)

        # Step 4: Parse cash balances if present (requires Cash Report section in Flex Query)
        # Note: Cash data is in <CashReportCurrency> child elements, not <CashReport> parent
        cash_elements = root.findall('.//CashReportCurrency')
        logger.info(f"Found {len(cash_elements)} CashReportCurrency elements in XML")

        # Debug: If no elements found, try alternative methods to diagnose issue
        if not cash_elements:
            logger.warning("XPath .//CashReportCurrency returned 0 elements - trying alternative methods")
            # Try iter() which is more reliable than findall() in some edge cases
            iter_elements = list(root.iter('CashReportCurrency'))
            logger.warning(f"root.iter() found {len(iter_elements)} elements")
            if iter_elements:
                logger.error("CRITICAL: iter() found elements but findall() did not - using iter() results")
                cash_elements = iter_elements

            # Check if CashReport parent exists
            cash_report_parents = root.findall('.//CashReport')
            logger.warning(f"Found {len(cash_report_parents)} CashReport parent elements")
            if cash_report_parents and not cash_elements:
                logger.error("CRITICAL: CashReport exists but has no CashReportCurrency children")

        cash_balances = {}

        for cash_elem in cash_elements:
            currency = cash_elem.attrib.get('currency')
            ending_cash = cash_elem.attrib.get('endingCash')

            if not currency or not ending_cash:
                continue

            # BASE_SUMMARY is the total across all currencies (use this for portfolio cash)
            if currency == 'BASE_SUMMARY':
                try:
                    cash_balances['BASE'] = float(ending_cash)
                except ValueError:
                    logger.warning(f"Invalid BASE_SUMMARY cash value: {ending_cash}")
                continue

            # Store individual currency balances
            if ending_cash:
                try:
                    cash_balances[currency] = float(ending_cash)
                except ValueError:
                    logger.warning(f"Invalid cash value for {currency}: {ending_cash}")

        # Use BASE_SUMMARY (total across all currencies) or fallback to USD
        total_cash_usd = cash_balances.get('BASE', cash_balances.get('USD', 0.0))

        if cash_balances:
            logger.info(f"Parsed cash balances: {cash_balances} (using USD: ${total_cash_usd:,.2f})")
        else:
            logger.info("No cash balances found (Cash Report section may not be enabled in Flex Query)")

        # Return positions, trades (if any), and cash balance
        return {
            'positions': positions,
            'trades': trades,
            'cash_balance': total_cash_usd
        }

    async def _get_connection(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's active IBKR connection from database with RLS."""
        pg = await get_postgres_rls_client()

        async with pg.acquire_with_user_context(user_id) as conn:
            row = await conn.fetchrow("""
                SELECT
                    id,
                    flex_token_encrypted,
                    flex_query_id,
                    token_expires_at,
                    created_at
                FROM broker_connections
                WHERE user_id = $1
                  AND broker_type = 'ibkr'
                  AND status = 'active'
                LIMIT 1
            """, user_id)

            if not row:
                return None

            # Check token expiration (warn if near expiry)
            if row['token_expires_at']:
                hours_until_expiry = (row['token_expires_at'] - datetime.utcnow()).total_seconds() / 3600
                if hours_until_expiry < 24:
                    logger.warning(
                        f"IBKR token for user {user_id} expires in {hours_until_expiry:.1f} hours"
                    )

            return dict(row)

    async def clear_cache(self, user_id: str) -> bool:
        """
        Clear cached IBKR positions for a user.

        Useful when:
        - User reports stale data
        - After Flex Query configuration changes
        - Troubleshooting cache-related issues

        Args:
            user_id: User ID for cache key

        Returns:
            bool: True if cache was cleared, False if no cache existed
        """
        cache_key = f"ibkr_positions:{user_id}"
        try:
            from core.cache.redis_cache import cache
            deleted = cache.delete(cache_key)
            if deleted:
                logger.info(f"Cleared IBKR cache for user {user_id}")
            else:
                logger.info(f"No IBKR cache found for user {user_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to clear IBKR cache for user {user_id}: {e}")
            return False

    async def _update_last_sync(self, connection_id: str) -> None:
        """Update last_sync_at timestamp after successful fetch."""
        pg = await get_postgres_rls_client()

        # Use acquire without user context since we're updating by ID
        async with pg.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    UPDATE broker_connections
                    SET
                        last_sync_at = NOW(),
                        error_message = NULL,
                        status = 'active'
                    WHERE id = $1
                """, connection_id)


# Singleton instance
_ibkr_service: Optional[IBKRService] = None


def get_ibkr_service() -> IBKRService:
    """Get singleton IBKRService instance."""
    global _ibkr_service
    if _ibkr_service is None:
        _ibkr_service = IBKRService()
    return _ibkr_service
