"""
Shared helpers for fetching options chain data with proper pagination.

This module provides a robust, paginated approach to fetching options data
from Polygon, ensuring all contracts are retrieved even for liquid underlyings.

Now supports SERVER-SIDE filtering via the updated MCP server, which is
much more efficient than client-side filtering.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.utils.mcp_result_parser import safe_extract_content, safe_parse_json

logger = logging.getLogger(__name__)


async def fetch_options_chain_paginated(
    polygon_server: Any,
    underlying: str,
    *,
    min_dte: int = 1,
    max_dte: int = 90,
    min_open_interest: int = 0,
    contract_type: Optional[str] = None,  # "call", "put", or None for both
    limit_per_page: int = 250,
    max_pages: int = 10,
    max_contracts: int = 5000,
    require_greeks: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch options chain with full pagination and server-side filtering.
    
    This function uses Polygon's cursor-based pagination and server-side
    expiration date filters to efficiently fetch non-0-DTE options.
    
    Args:
        polygon_server: The Polygon MCP server instance
        underlying: Ticker symbol (e.g., "AAPL", "SPY")
        min_dte: Minimum days to expiration (default 1, excludes 0-DTE)
        max_dte: Maximum days to expiration
        min_open_interest: Minimum OI filter (client-side, 0 = no filter)
        contract_type: "call", "put", or None for both
        limit_per_page: Contracts per API call (max 250)
        max_pages: Maximum number of pagination requests
        max_contracts: Safety cap to prevent runaway pagination
        require_greeks: If True, only return contracts with valid greeks
        
    Returns:
        List of contract dictionaries with full option data
    """
    today = datetime.now().date()
    min_expiry = today + timedelta(days=min_dte)
    max_expiry = today + timedelta(days=max_dte)
    
    all_contracts: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    page_count = 0
    
    logger.info(
        f"[OPTIONS_CHAIN] Fetching {underlying}: DTE {min_dte}-{max_dte}, "
        f"expiry {min_expiry} to {max_expiry}, max_pages={max_pages}"
    )
    
    while page_count < max_pages and len(all_contracts) < max_contracts:
        page_count += 1
        
        try:
            # Build request params with SERVER-SIDE filters
            params: Dict[str, Any] = {
                "underlying": underlying,
                "limit": min(limit_per_page, 250),
                "expiration_date.gte": min_expiry.isoformat(),
                "expiration_date.lte": max_expiry.isoformat(),
            }
            
            if cursor:
                params["cursor"] = cursor
            
            if contract_type:
                params["contract_type"] = contract_type
            
            # Call Polygon MCP server
            result = await polygon_server.call_tool("get_option_chain", params)
            
            # Check for error flag
            if hasattr(result, 'isError') and result.isError:
                error_text = ""
                if hasattr(result, 'content') and result.content:
                    first = result.content[0]
                    if isinstance(first, dict):
                        error_text = first.get('text', '')
                    elif hasattr(first, 'text'):
                        error_text = first.text
                logger.error(f"[OPTIONS_CHAIN] MCP error: {error_text}")
                break
            
            # Parse response - handle various formats
            response_data = _parse_response(result)
            if response_data is None:
                logger.warning(f"[OPTIONS_CHAIN] Page {page_count}: Failed to parse response")
                break
            
            # Check for error in response data
            if "error" in response_data:
                logger.error(f"[OPTIONS_CHAIN] API error: {response_data['error']}")
                break
            
            # Extract contracts and cursor from response.
            # PolygonBaseServer unwraps payload["results"] into response_data["data"],
            # while preserving the original envelope under response_data["raw_response"].
            contracts: List[Dict[str, Any]] = []
            raw_response = response_data.get("raw_response")

            if isinstance(response_data.get("data"), list):
                contracts = response_data["data"]
                if isinstance(raw_response, dict):
                    cursor = raw_response.get("next_cursor") or _extract_cursor_from_next(
                        raw_response.get("next_url")
                    )
                else:
                    cursor = None
            elif isinstance(response_data.get("data"), dict):
                inner_data = response_data["data"]
                contracts = inner_data.get("results", [])
                cursor = inner_data.get("next_cursor") or _extract_cursor_from_next(
                    inner_data.get("next_url")
                )
            else:
                contracts = response_data.get("results", [])
                cursor = response_data.get("next_cursor") or _extract_cursor_from_next(
                    response_data.get("next_url")
                )
            
            if not contracts:
                logger.debug(f"[OPTIONS_CHAIN] Page {page_count}: No contracts, ending")
                break
            
            logger.debug(f"[OPTIONS_CHAIN] Page {page_count}: Got {len(contracts)} contracts")
            
            # Client-side filtering (OI, greeks)
            valid_contracts = []
            for c in contracts:
                filtered = _filter_contract_client_side(
                    c, today, min_dte, max_dte, min_open_interest, require_greeks
                )
                if filtered:
                    valid_contracts.append(filtered)
            
            all_contracts.extend(valid_contracts)
            
            logger.debug(
                f"[OPTIONS_CHAIN] Page {page_count}: {len(valid_contracts)} valid "
                f"(total: {len(all_contracts)})"
            )
            
            # Check if more pages available
            if not cursor:
                logger.debug("[OPTIONS_CHAIN] No cursor, pagination complete")
                break
                
        except Exception as e:
            logger.error(f"[OPTIONS_CHAIN] Page {page_count} error: {e}")
            break
    
    logger.info(
        f"[OPTIONS_CHAIN] Fetched {len(all_contracts)} contracts for {underlying} "
        f"across {page_count} pages"
    )
    
    return all_contracts


def _extract_cursor_from_next(next_url: Optional[str]) -> Optional[str]:
    """Extract cursor parameter from Polygon's next_url."""
    if not next_url:
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(next_url)
        params = parse_qs(parsed.query)
        cursor_values = params.get("cursor", [])
        return cursor_values[0] if cursor_values else None
    except Exception:
        return None


def _parse_response(result: Any) -> Optional[Dict[str, Any]]:
    """Parse MCP server response into a dictionary."""
    logger.debug(f"[PARSE] Result type: {type(result)}")

    # Direct dict response
    if isinstance(result, dict):
        logger.debug(f"[PARSE] Direct dict with keys: {list(result.keys())[:5]}")
        return result

    parsed = safe_parse_json(result, default={})
    if parsed:
        logger.debug(f"[PARSE] Parsed payload keys: {list(parsed.keys())[:5]}")
        return parsed

    raw_text = safe_extract_content(result)
    if raw_text:
        preview = raw_text[:200] if len(raw_text) > 200 else raw_text
        logger.error(f"[PARSE] Failed to parse MCP content: {preview}")
    else:
        logger.warning(f"[PARSE] Unhandled result type: {type(result)}, repr: {repr(result)[:200]}")
    return None


def _filter_contract_client_side(
    contract: Dict[str, Any],
    today,
    min_dte: int,
    max_dte: int,
    min_oi: int,
    require_greeks: bool
) -> Optional[Dict[str, Any]]:
    """
    Apply client-side filters that can't be done server-side.
    
    Server-side filters handle: expiration_date, contract_type, strike_price
    Client-side filters: open_interest threshold, greeks requirement, DTE validation
    """
    details = contract.get('details', {})
    greeks = contract.get('greeks', {})
    
    # Get expiration and validate DTE (double-check server-side filter)
    exp_str = details.get('expiration_date') or contract.get('expiration_date')
    if exp_str:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dte = (exp_date - today).days
            if dte < min_dte or dte > max_dte:
                return None
            contract['_dte'] = dte
        except ValueError:
            return None
    
    # Check OI filter
    oi = contract.get('open_interest', 0) or 0
    if oi < min_oi:
        return None
    
    # Check greeks if required
    if require_greeks:
        if not greeks or greeks.get('delta') is None:
            return None
    
    return contract


async def fetch_options_chain_simple(
    polygon_server: Any,
    underlying: str,
    *,
    min_dte: int = 1,
    max_dte: int = 45,
    limit: int = 250,
) -> List[Dict[str, Any]]:
    """
    Simplified single-page fetch for quick lookups.
    
    Use this when you need a quick sample of options and don't need
    exhaustive coverage. For full chain analysis, use fetch_options_chain_paginated.
    
    Args:
        polygon_server: The Polygon MCP server instance
        underlying: Ticker symbol
        min_dte: Minimum days to expiration
        max_dte: Maximum days to expiration  
        limit: Max contracts to fetch (single request)
        
    Returns:
        List of contract dictionaries
    """
    return await fetch_options_chain_paginated(
        polygon_server,
        underlying,
        min_dte=min_dte,
        max_dte=max_dte,
        limit_per_page=min(limit, 250),
        max_pages=1,
    )


def extract_contract_details(contract: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract commonly needed fields from a contract in a normalized format.
    
    Args:
        contract: Raw contract dict from Polygon
        
    Returns:
        Normalized dict with key fields
    """
    details = contract.get("details", {})
    greeks = contract.get("greeks", {})
    day = contract.get("day", {})
    
    return {
        "ticker": contract.get("ticker") or details.get("ticker"),
        "underlying": details.get("underlying_ticker"),
        "strike": details.get("strike_price"),
        "expiration": details.get("expiration_date"),
        "contract_type": details.get("contract_type"),
        "dte": contract.get("_dte"),
        
        # Greeks
        "delta": greeks.get("delta"),
        "gamma": greeks.get("gamma"),
        "theta": greeks.get("theta"),
        "vega": greeks.get("vega"),
        
        # Pricing
        "iv": contract.get("implied_volatility"),
        "open_interest": contract.get("open_interest"),
        "volume": day.get("volume"),
        "last_price": day.get("close") or day.get("last"),
        "bid": contract.get("bid"),
        "ask": contract.get("ask"),
    }
