"""
Implied Correlation Tool - Calculate index implied correlation from constituent option IVs
Status: Production
Created: November 2025

PURPOSE: Calculate implied correlation between index constituents using the Goldman Sachs method.
         Uses index ETF holdings (FMP) and options implied volatility (Polygon) to derive
         the correlation implied by option prices.

FORMULA: ρ = (σ_index² - Σ(w_i² σ_i²)) / (Σ(w_i σ_i)² - Σ(w_i² σ_i²)) × 100

REFERENCE: GS Quant Library - timeseries/measures.py::implied_correlation()
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Union, Optional, Any
import asyncio
from urllib.parse import urlparse, parse_qs

from agents import function_tool
from core.utils.mcp_result_parser import safe_extract_content
from core.agents.risk_tools.shared import register_chart_handle
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# Constants - tenor mapping only
TENOR_DAYS_MAP = {
    "1m": 30,
    "3m": 90,
    "6m": 180
}

VALID_STRIKE_REFS = ["ATM", "DELTA_CALL", "DELTA_PUT"]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_result_text(result: Any) -> str:
    """Extract text from MCP CallToolResult even when isError is set."""
    try:
        content = getattr(result, "content", None)
        if content:
            first_item = content[0]
            if hasattr(first_item, "text"):
                return first_item.text or ""
            if isinstance(first_item, dict):
                return first_item.get("text") or first_item.get("value") or ""
            return str(first_item)
    except Exception:
        pass
    return ""


def _extract_cursor_from_next(next_url: str) -> Optional[str]:
    """Extract cursor query param from Polygon next_url."""
    if not next_url:
        return None
    try:
        parsed = urlparse(next_url)
        qs = parse_qs(parsed.query)
        cursor_values = qs.get("cursor") or qs.get("Cursor") or qs.get("CURSOR")
        if cursor_values:
            return cursor_values[0]
    except Exception:
        return None
    return None


def _select_closest_expiration(contracts: List[Dict[str, Any]], target_expiration: datetime) -> List[Dict[str, Any]]:
    """Pick contracts at the expiration date closest to the target."""
    closest: List[Dict[str, Any]] = []
    smallest_diff: Optional[int] = None

    for contract in contracts:
        exp_str = contract.get("details", {}).get("expiration_date")
        if not exp_str:
            continue
        try:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
        except ValueError:
            continue

        diff = abs((exp_date - target_expiration).days)
        if smallest_diff is None or diff < smallest_diff:
            smallest_diff = diff
            closest = [contract]
        elif diff == smallest_diff:
            closest.append(contract)

    return closest


async def _fetch_etf_holdings(fmp_server, index_ticker: str, top_n: int) -> List[Dict[str, Union[str, float]]]:
    """
    Fetch ETF holdings from FMP TradeFlow server.

    Args:
        fmp_server: FMPTradeFlowServer instance
        index_ticker: ETF ticker (e.g., 'SPY')
        top_n: Number of top holdings to return

    Returns:
        List of dicts with 'ticker' and 'weight' keys
        Example: [{'ticker': 'AAPL', 'weight': 0.0712}, ...]

    Raises:
        ValueError: If no holdings data found
    """
    try:
        import json

        logger.info(f"Fetching ETF holdings for {index_ticker}, top {top_n}")

        # Call FMP get_etf_holdings tool
        result = await fmp_server.call_tool(
            "get_etf_holdings",
            arguments={"symbol": index_ticker, "data_types": ["holdings"]}
        )

        # Extract data from CallToolResult
        if not result or not hasattr(result, 'content') or not result.content:
            raise ValueError(f"No response from ETF holdings API for {index_ticker}")

        text_content = safe_extract_content(result) or _extract_result_text(result)
        if hasattr(result, "isError") and result.isError:
            raise ValueError(f"ETF holdings API error for {index_ticker}: {text_content or 'Unknown error'}")
        if not text_content:
            raise ValueError(f"Empty response from ETF holdings API for {index_ticker}")

        data = json.loads(text_content)

        # Check for errors
        if "error" in data:
            raise ValueError(f"API error for {index_ticker}: {data['error']}")

        # Extract holdings list from nested structure
        if "data" not in data or "holdings" not in data["data"]:
            raise ValueError(f"No holdings data found for {index_ticker}")

        holdings_list = data["data"]["holdings"]
        if not holdings_list or not isinstance(holdings_list, list):
            raise ValueError(f"Invalid holdings data structure for {index_ticker}")

        # Extract ticker and weight from FMP response
        # FMP returns: {'asset': 'AAPL', 'weightPercentage': 7.12, ...}
        holdings = []
        for holding in holdings_list[:top_n]:
            ticker = holding.get('asset')
            weight_pct = holding.get('weightPercentage')

            if ticker and weight_pct is not None:
                # Convert percentage to decimal (7.12 -> 0.0712)
                weight = weight_pct / 100.0
                holdings.append({
                    'ticker': ticker,
                    'weight': weight
                })

        if not holdings:
            raise ValueError(f"No valid holdings extracted from {index_ticker}")

        logger.info(f"Successfully fetched {len(holdings)} holdings for {index_ticker}")
        return holdings

    except Exception as e:
        logger.error(f"Error fetching ETF holdings for {index_ticker}: {e}")
        raise


async def _fetch_index_iv(
    polygon_server,
    index_ticker: str,
    tenor_days: int,
    strike_reference: str,
    expiry_tolerance_days: int,
    atm_strike_tolerance: float,
    delta_call_target: float,
    delta_put_target: float,
    delta_tolerance: float,
    max_pages: int = 6,
    underlying_price: Optional[float] = None
) -> float:
    """
    Fetch implied volatility for the index ETF from Polygon options snapshot.

    Args:
        polygon_server: PolygonOptionsFuturesServer instance
        index_ticker: Index ETF ticker (e.g., 'SPY')
        tenor_days: Target days to expiration (30, 90, 180)
        strike_reference: 'ATM', 'DELTA_CALL', or 'DELTA_PUT'
        expiry_tolerance_days: Days tolerance for expiration matching
        atm_strike_tolerance: Percentage tolerance for ATM strike (e.g., 0.05 = 5%)
        delta_call_target: Target delta for call options (e.g., 0.50)
        delta_put_target: Target delta for put options (e.g., -0.50)
        delta_tolerance: Tolerance for delta matching (e.g., 0.1)

    Returns:
        Implied volatility as decimal (e.g., 0.25 for 25%)

    Raises:
        ValueError: If no suitable options found
    """
    try:
        logger.info(f"Fetching index IV for {index_ticker}, tenor={tenor_days}d, strike_ref={strike_reference}")

        # Calculate target expiration date (3rd Friday of target month for monthly options)
        from datetime import datetime, timedelta
        import json

        target_date = datetime.now() + timedelta(days=tenor_days)
        target_month = target_date.month
        target_year = target_date.year
        first_day = datetime(target_year, target_month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_until_friday)
        third_friday = first_friday + timedelta(days=14)

        target_expiration = third_friday
        min_date = target_expiration - timedelta(days=expiry_tolerance_days)
        max_date = target_expiration + timedelta(days=expiry_tolerance_days)

        logger.info(f"Target tenor {tenor_days}d → expiration range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

        # Step 1: Get underlying price (skip if already provided for batch optimization)
        if underlying_price is None:
            logger.info(f"Step 1: Fetching small sample to extract underlying price for {index_ticker}")
            sample_args = {
                "underlying": index_ticker,
                "limit": 10,
                "expiration_date": target_expiration.strftime("%Y-%m-%d")
            }

            sample_result = await polygon_server.call_tool("get_option_chain", arguments=sample_args)
            if not sample_result or not hasattr(sample_result, 'content') or not sample_result.content:
                raise ValueError(f"No response from options API for {index_ticker} (sample fetch)")

            sample_content = safe_extract_content(sample_result) or _extract_result_text(sample_result)
            if hasattr(sample_result, "isError") and sample_result.isError:
                raise ValueError(f"Options API error for {index_ticker}: {sample_content or 'Unknown error'}")

            if not sample_content or not sample_content.strip():
                raise ValueError(f"Empty response from options API for {index_ticker} (sample fetch)")

            try:
                sample_data = json.loads(sample_content)
            except json.JSONDecodeError as e:
                preview = sample_content[:200].replace("\n", " ")
                raise ValueError(f"Invalid JSON from options API for {index_ticker}: {e.msg}. Preview: {preview}")

            if "error" in sample_data:
                raise ValueError(f"API error for {index_ticker}: {sample_data['error']}")

            if "data" not in sample_data or "results" not in sample_data["data"]:
                raise ValueError(f"No options data found for {index_ticker}")

            sample_contracts = sample_data["data"]["results"] or []
            if not sample_contracts:
                raise ValueError(f"No options contracts found for {index_ticker}")

            # Extract underlying price from first contract
            for contract in sample_contracts:
                if 'underlying_asset' in contract:
                    underlying_price = contract['underlying_asset'].get('price')
                    if underlying_price:
                        break

            if not underlying_price:
                raise ValueError(f"Could not extract underlying price for {index_ticker} from sample")

            logger.info(f"Extracted underlying price for {index_ticker}: ${underlying_price:.2f}")
        else:
            logger.info(f"Step 1: Using pre-fetched underlying price for {index_ticker}: ${underlying_price:.2f}")

        # Calculate ATM strike range (spot ± tolerance)
        strike_lower = underlying_price * (1 - atm_strike_tolerance)
        strike_upper = underlying_price * (1 + atm_strike_tolerance)
        logger.info(f"ATM strike range: ${strike_lower:.2f} to ${strike_upper:.2f} ({atm_strike_tolerance:.1%} tolerance)")

        # Add sanity check for ATM tolerance
        if atm_strike_tolerance > 0.3:
            logger.warning(f"ATM strike tolerance {atm_strike_tolerance:.1%} is unusually large for {index_ticker}")

        # Step 2: Fetch ATM contracts with date + strike filters
        # This ensures we get contracts where greeks/IV are available (not deep ITM/OTM)
        # OPTIMIZATION: Only fetch 10 contracts - we just need a few for IV averaging
        logger.info(f"Step 2: Fetching ATM contracts with strike filters for {index_ticker}")
        chain_limit = 10  # Reduced from 250 - we only need a small sample

        all_contracts = []
        cursor = None
        page = 0
        while page < max_pages:
            page += 1
            args = {
                "underlying": index_ticker,
                "limit": chain_limit,
                "expiration_date": target_expiration.strftime("%Y-%m-%d"),
                "strike_price.gte": strike_lower,
                "strike_price.lte": strike_upper
            }
            if cursor:
                args["cursor"] = cursor

            result = await polygon_server.call_tool("get_option_chain", arguments=args)

            if not result or not hasattr(result, 'content') or not result.content:
                raise ValueError(f"No response from options API for {index_ticker}")

            raw_content = safe_extract_content(result) or _extract_result_text(result)
            if hasattr(result, "isError") and result.isError:
                raise ValueError(f"Options API error for {index_ticker}: {raw_content or 'Unknown error'}")

            if not raw_content or not raw_content.strip():
                raise ValueError(f"Empty response from options API for {index_ticker}")

            try:
                data = json.loads(raw_content)
            except json.JSONDecodeError as e:
                preview = raw_content[:200].replace("\n", " ")
                raise ValueError(
                    f"Invalid JSON from options API for {index_ticker}: {e.msg}. Preview: {preview}"
                )

            if "error" in data:
                raise ValueError(f"API error for {index_ticker}: {data['error']}")

            if "data" not in data or "results" not in data["data"]:
                raise ValueError(f"No options data found for {index_ticker}")

            page_contracts = data["data"]["results"] or []
            all_contracts.extend(page_contracts)
            logger.info(f"Page {page}: received {len(page_contracts)} contracts (running total {len(all_contracts)}) for {index_ticker}")

            next_url = data["data"].get("next_url") or data["data"].get("nextUrl")
            cursor = _extract_cursor_from_next(next_url) if next_url else None
            if not cursor:
                break
            if not page_contracts and page > 1:
                logger.warning(f"Empty page {page} received for {index_ticker}, stopping pagination")
                break

        # Use the fetched contracts directly - they're already filtered server-side
        snapshot_results = all_contracts
        logger.info(f"Received {len(snapshot_results)} ATM contracts from API with server-side filters")

        if not snapshot_results:
            raise ValueError(
                f"No ATM options found for {index_ticker} with tenor={tenor_days}d, "
                f"expiration={target_expiration.strftime('%Y-%m-%d')}, "
                f"strikes ${strike_lower:.2f}-${strike_upper:.2f}"
            )

        # For ATM: Server-side already filtered by strike range, use all contracts
        # For DELTA: Still need client-side filtering since delta changes continuously
        if strike_reference == "ATM":
            # Server-side filtering already applied strike_price.gte/lte
            selected_contracts = snapshot_results
            logger.info(f"Using all {len(selected_contracts)} ATM contracts from server-side filters")
        else:
            # Delta-based selection requires client-side filtering
            selected_contracts = _select_contracts(
                snapshot_results,
                tenor_days,
                strike_reference,
                underlying_price,
                expiry_tolerance_days,
                atm_strike_tolerance,
                delta_call_target,
                delta_put_target,
                delta_tolerance,
                skip_expiry_filter=True  # Skip expiry filter since server-side filter already applied
            )
            logger.info(f"Selected {len(selected_contracts)} contracts after delta filtering")

        if not selected_contracts:
            raise ValueError(
                f"No options found for {index_ticker} with tenor={tenor_days}d, "
                f"strike_ref={strike_reference}. Received {len(snapshot_results)} total contracts."
            )

        # Average IV across selected contracts
        ivs = [c.get('implied_volatility', 0) for c in selected_contracts if c.get('implied_volatility')]

        if not ivs:
            raise ValueError(f"No valid IVs found in selected contracts for {index_ticker}")

        avg_iv = sum(ivs) / len(ivs)
        logger.info(f"Index {index_ticker} IV: {avg_iv:.4f} (avg of {len(ivs)} contracts)")

        return avg_iv

    except Exception as e:
        logger.error(f"Error fetching index IV for {index_ticker}: {e}")
        raise


async def _batch_fetch_underlying_prices(
    polygon_server,
    tickers: List[str],
    target_expiration: datetime
) -> Dict[str, float]:
    """
    Batch fetch underlying prices for multiple tickers in parallel.
    Optimizes by fetching one sample contract per ticker to extract price.

    Args:
        polygon_server: PolygonOptionsFuturesServer instance
        tickers: List of tickers to fetch prices for
        target_expiration: Target expiration date for sampling

    Returns:
        Dict mapping ticker to underlying price
    """
    try:
        logger.info(f"Batch fetching underlying prices for {len(tickers)} tickers in parallel")

        async def fetch_single_price(ticker: str) -> tuple:
            try:
                sample_args = {
                    "underlying": ticker,
                    "limit": 1,
                    "expiration_date": target_expiration.strftime("%Y-%m-%d")
                }

                result = await polygon_server.call_tool("get_option_chain", arguments=sample_args)
                if not result or not hasattr(result, 'content') or not result.content:
                    return (ticker, None, f"No response from API")

                content = safe_extract_content(result) or _extract_result_text(result)
                if hasattr(result, "isError") and result.isError:
                    return (ticker, None, f"API error: {content or 'Unknown'}")

                import json
                data = json.loads(content)
                contracts = data.get("data", {}).get("results", [])

                if contracts and 'underlying_asset' in contracts[0]:
                    price = contracts[0]['underlying_asset'].get('price')
                    if price:
                        return (ticker, price, None)

                return (ticker, None, "No underlying price in response")

            except Exception as e:
                return (ticker, None, str(e))

        # Fetch all prices in parallel
        results = await asyncio.gather(*[fetch_single_price(ticker) for ticker in tickers])

        # Build dict from successful results
        prices = {ticker: price for ticker, price, error in results if price is not None}

        logger.info(f"Successfully fetched prices for {len(prices)}/{len(tickers)} tickers")
        if len(prices) < len(tickers):
            failed = [ticker for ticker, price, error in results if price is None]
            logger.warning(f"Failed to fetch prices for: {', '.join(failed[:10])}{' ...' if len(failed) > 10 else ''}")

        return prices

    except Exception as e:
        logger.error(f"Error batch fetching underlying prices: {e}")
        raise


async def _fetch_constituent_ivs(
    polygon_server,
    tickers: List[str],
    tenor_days: int,
    strike_reference: str,
    expiry_tolerance_days: int,
    atm_strike_tolerance: float,
    delta_call_target: float,
    delta_put_target: float,
    delta_tolerance: float
) -> Dict[str, float]:
    """
    Fetch implied volatilities for multiple constituent tickers.

    Args:
        polygon_server: PolygonOptionsFuturesServer instance
        tickers: List of constituent tickers
        tenor_days: Target days to expiration
        strike_reference: Strike selection method
        expiry_tolerance_days: Days tolerance for expiration matching
        atm_strike_tolerance: Percentage tolerance for ATM strike
        delta_call_target: Target delta for call options
        delta_put_target: Target delta for put options
        delta_tolerance: Tolerance for delta matching

    Returns:
        Dict mapping ticker to IV (e.g., {'AAPL': 0.28, 'MSFT': 0.25})
        Skips tickers with no valid options data
    """
    try:
        logger.info(f"Fetching IVs for {len(tickers)} constituents with batch optimization")

        # Calculate target expiration for price fetching
        target_date = datetime.now() + timedelta(days=tenor_days)
        target_month = target_date.month
        target_year = target_date.year
        first_day = datetime(target_year, target_month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_until_friday)
        target_expiration = first_friday + timedelta(days=14)

        # Step 1: Batch fetch all underlying prices in parallel (50 calls instead of 50*2)
        underlying_prices = await _batch_fetch_underlying_prices(
            polygon_server,
            tickers,
            target_expiration
        )

        # Step 2: Parallelize IV fetching with pre-fetched prices
        async def fetch_single_iv(ticker: str) -> tuple:
            try:
                # Skip if we don't have a price for this ticker
                if ticker not in underlying_prices:
                    return (ticker, None, "No underlying price available")

                iv = await _fetch_index_iv(
                    polygon_server,
                    ticker,
                    tenor_days,
                    strike_reference,
                    expiry_tolerance_days,
                    atm_strike_tolerance,
                    delta_call_target,
                    delta_put_target,
                    delta_tolerance,
                    max_pages=1,
                    underlying_price=underlying_prices[ticker]  # Pass pre-fetched price
                )
                return (ticker, iv, None)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                return (ticker, None, str(e))

        # Fetch all IVs in parallel
        results = await asyncio.gather(*[fetch_single_iv(ticker) for ticker in tickers])

        # Build dict from successful results
        constituent_ivs = {ticker: iv for ticker, iv, error in results if iv is not None}

        logger.info(f"Successfully fetched IVs for {len(constituent_ivs)}/{len(tickers)} constituents")
        return constituent_ivs

    except Exception as e:
        logger.error(f"Error fetching constituent IVs: {e}")
        raise


def _select_contracts(
    snapshot_results: List[Dict],
    tenor_days: int,
    strike_reference: str,
    underlying_price: Optional[float],
    expiry_tolerance_days: int,
    atm_strike_tolerance: float,
    delta_call_target: float,
    delta_put_target: float,
    delta_tolerance: float,
    skip_expiry_filter: bool = False
) -> List[Dict]:
    """
    Filter options contracts by expiration and strike criteria.

    Args:
        snapshot_results: Raw Polygon snapshot results
        tenor_days: Target days to expiration
        strike_reference: Strike selection method
        underlying_price: Current underlying price (for ATM selection)
        expiry_tolerance_days: Days tolerance for expiration matching
        atm_strike_tolerance: Percentage tolerance for ATM strike
        delta_call_target: Target delta for call options
        delta_put_target: Target delta for put options
        delta_tolerance: Tolerance for delta matching

    Returns:
        List of contracts matching criteria
    """
    try:
        # Validate required parameters for strike reference methods
        if strike_reference == "ATM" and not underlying_price:
            raise ValueError("underlying_price is required for ATM strike selection")
        target_date = datetime.now() + timedelta(days=tenor_days)
        min_date = target_date - timedelta(days=expiry_tolerance_days)
        max_date = target_date + timedelta(days=expiry_tolerance_days)

        logger.debug(f"_select_contracts: Filtering {len(snapshot_results)} contracts")
        logger.debug(f"Target date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
        logger.debug(f"Strike reference: {strike_reference}, Underlying price: ${underlying_price}")

        # DEBUG: Log expiration date distribution
        expiration_dates = []
        for contract in snapshot_results:
            details = contract.get('details', {})
            expiration_str = details.get('expiration_date')
            if expiration_str:
                try:
                    exp_date = datetime.strptime(expiration_str, '%Y-%m-%d')
                    expiration_dates.append(exp_date)
                except ValueError:
                    pass

        if expiration_dates:
            expiration_dates.sort()
            logger.info(f"Expiration date range in data: {expiration_dates[0].strftime('%Y-%m-%d')} to {expiration_dates[-1].strftime('%Y-%m-%d')}")
            logger.info(f"First 5 expirations: {[d.strftime('%Y-%m-%d') for d in expiration_dates[:5]]}")
            logger.info(f"Last 5 expirations: {[d.strftime('%Y-%m-%d') for d in expiration_dates[-5:]]}")

        selected = []
        expiry_filtered_count = 0
        strike_filtered_count = 0

        for contract in snapshot_results:
            # Extract contract details
            details = contract.get('details', {})
            expiration_str = details.get('expiration_date')
            strike_price = details.get('strike_price')
            contract_type = details.get('contract_type')

            if not expiration_str:
                continue

            # Parse expiration date
            try:
                expiration_date = datetime.strptime(expiration_str, '%Y-%m-%d')
            except ValueError:
                logger.debug(f"Failed to parse expiration date: {expiration_str}")
                continue

            # Filter by expiration
            if not skip_expiry_filter and not (min_date <= expiration_date <= max_date):
                continue

            expiry_filtered_count += 1

            # Filter by strike reference
            if strike_reference == "ATM":
                if underlying_price and strike_price:
                    strike_diff_pct = abs(strike_price - underlying_price) / underlying_price
                    # Select strikes within tolerance of current price
                    if strike_diff_pct < atm_strike_tolerance:
                        selected.append(contract)
                        strike_filtered_count += 1

            elif strike_reference == "DELTA_CALL":
                if contract_type == "call":
                    greeks = contract.get('greeks', {})
                    delta = greeks.get('delta')
                    if delta and abs(delta - delta_call_target) < delta_tolerance:
                        selected.append(contract)
                        strike_filtered_count += 1

            elif strike_reference == "DELTA_PUT":
                if contract_type == "put":
                    greeks = contract.get('greeks', {})
                    delta = greeks.get('delta')
                    if delta and abs(delta - delta_put_target) < delta_tolerance:
                        selected.append(contract)
                        strike_filtered_count += 1

        logger.info(f"Filtering results: {len(snapshot_results)} total → {expiry_filtered_count} after expiry filter → {strike_filtered_count} after strike filter → {len(selected)} selected")

        return selected

    except Exception as e:
        logger.error(f"Error selecting contracts: {e}")
        return []


# ============================================================================
# CALCULATION FUNCTION
# ============================================================================

def _calculate_gs_correlation(
    index_iv: float,
    constituent_data: List[Dict[str, Union[str, float]]],
    zero_tolerance: float
) -> Dict[str, float]:
    """
    Calculate implied correlation using Goldman Sachs formula.

    Formula:
        ρ = (σ_index² - Σ(w_i² σ_i²)) / (Σ(w_i σ_i)² - Σ(w_i² σ_i²)) × 100

    Args:
        index_iv: Index implied volatility (decimal)
        constituent_data: List of dicts with 'ticker', 'weight', 'iv' keys
        zero_tolerance: Tolerance for denominator zero check

    Returns:
        Dict with calculation breakdown:
        {
            'correlation_pct': float,          # possibly clamped to [-100, 100]
            'index_variance': float,
            'weighted_vol_sum': float,
            'weighted_var_sum': float,
            'numerator': float,
            'denominator': float,
            'raw_correlation': float,          # before clamping
            'clamped': bool                    # True if clamped to [-1,1]
        }

    Raises:
        ValueError: If calculation fails (e.g., division by zero)
    """
    try:
        # Normalize weights in case we only use top-N holdings
        total_weight = sum(d['weight'] for d in constituent_data)
        if total_weight <= 0:
            raise ValueError("Sum of weights is zero or negative - cannot normalize")
        if abs(total_weight - 1.0) > 1e-6:
            scale = 1.0 / total_weight
            for d in constituent_data:
                d['weight'] = d['weight'] * scale
            logger.info(f"Normalized weights by factor {scale:.6f} (raw sum={total_weight:.6f})")

        # Guard against non-positive vols
        for d in constituent_data:
            if d['iv'] <= 0:
                raise ValueError(f"Non-positive IV for {d.get('ticker', 'unknown')}")
        if index_iv <= 0:
            raise ValueError("Non-positive index IV")

        # σ_index²
        index_var = index_iv ** 2

        # Σ(w_i σ_i)
        weighted_vol_sum = sum(d['weight'] * d['iv'] for d in constituent_data)

        # Σ(w_i² σ_i²)
        weighted_var_sum = sum((d['weight'] ** 2) * (d['iv'] ** 2) for d in constituent_data)

        # Numerator: σ_index² - Σ(w_i² σ_i²)
        numerator = index_var - weighted_var_sum

        # Denominator: (Σ(w_i σ_i)² - Σ(w_i² σ_i²))
        denominator = (weighted_vol_sum ** 2) - weighted_var_sum

        if abs(denominator) < zero_tolerance:
            raise ValueError("Denominator too close to zero - calculation unstable")

        # ρ (raw) and clamp to [-1, 1] to avoid >100% correlation from noisy IVs
        raw_corr = numerator / denominator
        clamped = False
        corr = raw_corr
        if raw_corr > 1:
            corr = 1.0
            clamped = True
        elif raw_corr < -1:
            corr = -1.0
            clamped = True

        correlation_pct = corr * 100

        return {
            'correlation_pct': correlation_pct,
            'index_variance': index_var,
            'weighted_vol_sum': weighted_vol_sum,
            'weighted_var_sum': weighted_var_sum,
            'numerator': numerator,
            'denominator': denominator,
            'raw_correlation': raw_corr,
            'clamped': clamped
        }

    except Exception as e:
        logger.error(f"Error calculating GS correlation: {e}")
        raise


# ============================================================================
# CHART FUNCTIONS
# ============================================================================

async def _build_constituent_weights_chart(
    constituent_data: List[Dict[str, Union[str, float]]],
    index_ticker: str
) -> Dict[str, Any]:
    """
    Create horizontal bar chart of constituent weights.

    Args:
        constituent_data: List with 'ticker' and 'weight' keys
        index_ticker: Index ticker for title

    Returns:
        Dict with 'data' and 'layout' for Plotly
    """
    try:
        # Sort by weight descending
        sorted_data = sorted(constituent_data, key=lambda x: x['weight'], reverse=True)

        tickers = [d['ticker'] for d in sorted_data]
        weights = [d['weight'] * 100 for d in sorted_data]  # Convert to %

        fig = go.Figure(data=[
            go.Bar(
                y=tickers,
                x=weights,
                orientation='h',
                marker=dict(color='rgb(55, 83, 109)'),
                text=[f"{w:.2f}%" for w in weights],
                textposition='auto'
            )
        ])

        fig.update_layout(
            title=f"{index_ticker} Constituent Weights",
            xaxis_title="Weight (%)",
            yaxis_title="Ticker",
            height=max(400, len(tickers) * 20),
            template='plotly_white'
        )

        # Return serializable Plotly dict (stored server-side later)
        return fig.to_dict()

    except Exception as e:
        logger.error(f"Error building weights chart: {e}")
        raise


async def _build_volatility_comparison_chart(
    index_ticker: str,
    index_iv: float,
    constituent_data: List[Dict[str, Union[str, float]]]
) -> Dict[str, Any]:
    """
    Create bar chart comparing constituent IVs with index IV line.

    Args:
        index_ticker: Index ticker
        index_iv: Index implied volatility (decimal)
        constituent_data: List with 'ticker' and 'iv' keys

    Returns:
        Dict with 'data' and 'layout' for Plotly
    """
    try:
        # Sort by IV descending
        sorted_data = sorted(constituent_data, key=lambda x: x['iv'], reverse=True)

        tickers = [d['ticker'] for d in sorted_data]
        ivs = [d['iv'] * 100 for d in sorted_data]  # Convert to %

        fig = go.Figure()

        # Constituent IVs as bars
        fig.add_trace(go.Bar(
            x=tickers,
            y=ivs,
            name="Constituent IV",
            marker=dict(color='rgb(55, 83, 109)')
        ))

        # Index IV as horizontal line
        fig.add_trace(go.Scatter(
            x=tickers,
            y=[index_iv * 100] * len(tickers),
            mode='lines',
            name=f"{index_ticker} IV",
            line=dict(color='red', width=2, dash='dash')
        ))

        fig.update_layout(
            title=f"Implied Volatility Comparison: {index_ticker} vs Constituents",
            xaxis_title="Ticker",
            yaxis_title="Implied Volatility (%)",
            height=500,
            template='plotly_white',
            showlegend=True
        )

        # Return serializable Plotly dict (stored server-side later)
        return fig.to_dict()

    except Exception as e:
        logger.error(f"Error building volatility comparison chart: {e}")
        raise


async def _build_correlation_breakdown_chart(
    calculation_details: Dict[str, float]
) -> Dict[str, Any]:
    """
    Create waterfall chart showing GS formula calculation steps.

    Args:
        calculation_details: Dict from _calculate_gs_correlation

    Returns:
        Dict with 'data' and 'layout' for Plotly
    """
    try:
        # Waterfall showing: index_var → -weighted_var_sum → numerator
        #                   weighted_vol_sum² → -weighted_var_sum → denominator
        #                   numerator/denominator → correlation_pct

        index_var = calculation_details['index_variance']
        weighted_var_sum = calculation_details['weighted_var_sum']
        numerator = calculation_details['numerator']
        weighted_vol_sum_sq = calculation_details['weighted_vol_sum'] ** 2
        denominator = calculation_details['denominator']
        correlation_pct = calculation_details['correlation_pct']

        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "total", "absolute", "relative", "total", "relative", "total"],
            x=[
                "σ²_index",
                "-Σ(w²σ²)",
                "Numerator",
                "(Σwσ)²",
                "-Σ(w²σ²)",
                "Denominator",
                "÷",
                "Correlation %"
            ],
            y=[
                index_var,
                -weighted_var_sum,
                numerator,
                weighted_vol_sum_sq,
                -weighted_var_sum,
                denominator,
                numerator / denominator if denominator != 0 else 0,
                correlation_pct
            ],
            text=[
                f"{index_var:.6f}",
                f"-{weighted_var_sum:.6f}",
                f"{numerator:.6f}",
                f"{weighted_vol_sum_sq:.6f}",
                f"-{weighted_var_sum:.6f}",
                f"{denominator:.6f}",
                f"{numerator/denominator:.2f}" if denominator != 0 else "N/A",
                f"{correlation_pct:.2f}%"
            ],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}}
        ))

        fig.update_layout(
            title="GS Implied Correlation Calculation Breakdown",
            yaxis_title="Value",
            height=600,
            template='plotly_white',
            showlegend=False
        )

        # Return serializable Plotly dict (stored server-side later)
        return fig.to_dict()

    except Exception as e:
        logger.error(f"Error building correlation breakdown chart: {e}")
        raise


# ============================================================================
# MAIN TOOL FUNCTION
# ============================================================================

async def calculate_implied_correlation_internal(
    index_ticker: str,
    tenor: str = "3m",
    strike_reference: str = "ATM",
    top_n_constituents: int = 20,
    expiry_tolerance_days: int = 7,
    atm_strike_tolerance: float = 0.05,
    delta_call_target: float = 0.50,
    delta_put_target: float = -0.50,
    delta_tolerance: float = 0.10,
    zero_tolerance: float = 1e-10
) -> dict:
    """
    Calculate implied correlation between index constituents using GS method.

    Uses ETF holdings data (FMP) and options implied volatility (Polygon) to calculate
    the correlation implied by option prices.

    Formula: ρ = (σ_index² - Σ(w_i² σ_i²)) / (Σ(w_i σ_i)² - Σ(w_i² σ_i²)) × 100

    Args:
        index_ticker: Index ETF ticker (e.g., 'SPY', 'QQQ', 'IWM')
        tenor: Time horizon - '1m', '3m', or '6m' (default: '3m')
        strike_reference: Strike selection method:
            - 'ATM': At-the-money (closest to current price)
            - 'DELTA_CALL': Call delta closest to delta_call_target
            - 'DELTA_PUT': Put delta closest to delta_put_target
        top_n_constituents: Number of top holdings to include (default: 20)
        expiry_tolerance_days: Days tolerance for expiration matching (default: 7)
        atm_strike_tolerance: Percentage tolerance for ATM strike selection (default: 0.05 = 5%)
        delta_call_target: Target delta for call options (default: 0.50)
        delta_put_target: Target delta for put options (default: -0.50)
        delta_tolerance: Tolerance for delta matching (default: 0.10)
        zero_tolerance: Tolerance for denominator zero check (default: 1e-10)

    Returns:
        Dict with:
        - status: 'success' or 'error'
        - correlation_pct: Implied correlation percentage
        - index_ticker: Index analyzed
        - tenor: Time horizon used
        - strike_reference: Strike method used
        - n_constituents: Number of constituents analyzed
        - constituent_data: List of constituent details
        - calculation_details: GS formula breakdown
        - charts: List of Plotly JSON charts
        - thresholds_used: Dict of threshold values used in calculation

    Example:
        >>> result = await calculate_implied_correlation("SPY", tenor="3m", strike_reference="ATM")
        >>> print(f"SPY 3-month implied correlation: {result['correlation_pct']:.2f}%")

        >>> # Agent can adjust thresholds for volatile markets
        >>> result = await calculate_implied_correlation(
        ...     "SPY",
        ...     tenor="1m",
        ...     expiry_tolerance_days=14,  # Wider tolerance for illiquid options
        ...     atm_strike_tolerance=0.10  # 10% tolerance for wide bid-ask spreads
        ... )
    """
    fmp_server = None
    polygon_server = None

    try:
        # Validate inputs
        if tenor not in TENOR_DAYS_MAP:
            return {
                "status": "error",
                "error": f"Invalid tenor '{tenor}'. Must be one of: {list(TENOR_DAYS_MAP.keys())}"
            }

        if strike_reference not in VALID_STRIKE_REFS:
            return {
                "status": "error",
                "error": f"Invalid strike_reference '{strike_reference}'. Must be one of: {VALID_STRIKE_REFS}"
            }

        tenor_days = TENOR_DAYS_MAP[tenor]
        logger.info(
            f"Calculating implied correlation for {index_ticker}, "
            f"tenor={tenor} ({tenor_days}d), strike_ref={strike_reference}, top_n={top_n_constituents}"
        )

        # Initialize MCP servers
        from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer
        from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer

        fmp_server = FMPTradeFlowServer()
        polygon_server = PolygonOptionsFuturesServer()

        # Connect to MCP servers
        await fmp_server.connect()
        await polygon_server.connect()

        # Step 1: Fetch ETF holdings
        holdings = await _fetch_etf_holdings(fmp_server, index_ticker, top_n_constituents)

        # Step 2: Fetch index IV
        index_iv = await _fetch_index_iv(
            polygon_server,
            index_ticker,
            tenor_days,
            strike_reference,
            expiry_tolerance_days,
            atm_strike_tolerance,
            delta_call_target,
            delta_put_target,
            delta_tolerance
        )

        # Step 3: Fetch constituent IVs
        constituent_tickers = [h['ticker'] for h in holdings]
        constituent_ivs = await _fetch_constituent_ivs(
            polygon_server,
            constituent_tickers,
            tenor_days,
            strike_reference,
            expiry_tolerance_days,
            atm_strike_tolerance,
            delta_call_target,
            delta_put_target,
            delta_tolerance
        )

        # Step 4: Combine holdings with IVs
        constituent_data = []
        for holding in holdings:
            ticker = holding['ticker']
            if ticker in constituent_ivs:
                constituent_data.append({
                    'ticker': ticker,
                    'weight': holding['weight'],
                    'iv': constituent_ivs[ticker]
                })

        if not constituent_data:
            return {
                "status": "error",
                "error": f"No constituents with valid IV data found for {index_ticker}"
            }

        # Step 5: Calculate correlation
        calculation_details = _calculate_gs_correlation(index_iv, constituent_data, zero_tolerance)

        # Step 6: Generate charts
        charts = []

        weights_chart = await _build_constituent_weights_chart(constituent_data, index_ticker)
        charts.append(
            register_chart_handle(
                weights_chart,
                chart_type="constituent_weights",
                title=f"{index_ticker} Constituent Weights",
                alt_text=f"Top {len(constituent_data)} weights for {index_ticker}"
            )
        )

        volatility_chart = await _build_volatility_comparison_chart(index_ticker, index_iv, constituent_data)
        charts.append(
            register_chart_handle(
                volatility_chart,
                chart_type="volatility_comparison",
                title=f"IV Comparison: {index_ticker} vs Constituents",
                alt_text=f"Implied vol comparison for {index_ticker} and constituents"
            )
        )

        breakdown_chart = await _build_correlation_breakdown_chart(calculation_details)
        charts.append(
            register_chart_handle(
                breakdown_chart,
                chart_type="correlation_breakdown",
                title="GS Implied Correlation Breakdown",
                alt_text="Waterfall of implied correlation calculation"
            )
        )

        # Return results
        return {
            "status": "success",
            "correlation_pct": calculation_details['correlation_pct'],
            "index_ticker": index_ticker,
            "tenor": tenor,
            "strike_reference": strike_reference,
            "n_constituents": len(constituent_data),
            "index_iv": index_iv,
            "constituent_data": constituent_data,
            "calculation_details": calculation_details,
            "charts": charts,
            "thresholds_used": {
                "expiry_tolerance_days": expiry_tolerance_days,
                "atm_strike_tolerance": atm_strike_tolerance,
                "delta_call_target": delta_call_target,
                "delta_put_target": delta_put_target,
                "delta_tolerance": delta_tolerance,
                "zero_tolerance": zero_tolerance
            }
        }

    except Exception as e:
        logger.error(f"Error calculating implied correlation: {e}", exc_info=True)
        # Re-raise so agent sees actual error instead of hallucinating "no data access"
        raise RuntimeError(f"Implied correlation calculation failed: {str(e)}. This is NOT a data access issue - Polygon API errored or rate limit hit.") from e

    finally:
        # Cleanup MCP servers
        if fmp_server:
            try:
                await fmp_server.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up FMP server: {e}")

        if polygon_server:
            try:
                await polygon_server.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up Polygon server: {e}")


@function_tool
async def calculate_implied_correlation(
    index_ticker: str,
    tenor: str = "3m",
    strike_reference: str = "ATM",
    top_n_constituents: int = 20,
    expiry_tolerance_days: int = 7,
    atm_strike_tolerance: float = 0.05,
    delta_call_target: float = 0.50,
    delta_put_target: float = -0.50,
    delta_tolerance: float = 0.10,
    zero_tolerance: float = 1e-10
) -> str:
    """
    Calculate implied correlation between index constituents using GS method.

    Uses ETF holdings data (FMP) and options implied volatility (Polygon) to calculate
    the correlation implied by option prices.

    Formula: ρ = (σ_index² - Σ(w_i² σ_i²)) / (Σ(w_i σ_i)² - Σ(w_i² σ_i²)) × 100

    Args:
        index_ticker: Index ETF ticker (e.g., 'SPY', 'QQQ', 'IWM')
        tenor: Time horizon - '1m', '3m', or '6m' (default: '3m')
        strike_reference: Strike selection method:
            - 'ATM': At-the-money (closest to current price)
            - 'DELTA_CALL': Call delta closest to delta_call_target
            - 'DELTA_PUT': Put delta closest to delta_put_target
        top_n_constituents: Number of top holdings to include (default: 20)
        expiry_tolerance_days: Days tolerance for expiration matching (default: 7)
        atm_strike_tolerance: Percentage tolerance for ATM strike selection (default: 0.05 = 5%)
        delta_call_target: Target delta for call options (default: 0.50)
        delta_put_target: Target delta for put options (default: -0.50)
        delta_tolerance: Tolerance for delta matching (default: 0.10)
        zero_tolerance: Tolerance for denominator zero check (default: 1e-10)

    Returns:
        JSON string with correlation analysis and charts

    Example:
        >>> result = await calculate_implied_correlation("SPY", tenor="3m", strike_reference="ATM")
        >>> print(f"SPY 3-month implied correlation: {result['correlation_pct']:.2f}%")
    """
    from core.utils.result_formatter import jsonify_results
    
    result = await calculate_implied_correlation_internal(
        index_ticker=index_ticker,
        tenor=tenor,
        strike_reference=strike_reference,
        top_n_constituents=top_n_constituents,
        expiry_tolerance_days=expiry_tolerance_days,
        atm_strike_tolerance=atm_strike_tolerance,
        delta_call_target=delta_call_target,
        delta_put_target=delta_put_target,
        delta_tolerance=delta_tolerance,
        zero_tolerance=zero_tolerance
    )
    
    return jsonify_results(result)
