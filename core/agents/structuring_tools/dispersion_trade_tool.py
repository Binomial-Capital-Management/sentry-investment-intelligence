"""
Dispersion Trade Pricing Tool

Prices and analyzes dispersion trades: long index vol, short constituent vols.
Profits when correlation decreases (constituents move independently).

NO HARDCODING: Uses Polygon for options data, FMP for correlation.
"""

from agents import function_tool
from typing import Dict, Any, Optional, List
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import math
import json
import asyncio

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer
from core.mcp_servers.polygon.PolygonOptionsFuturesServer import PolygonOptionsFuturesServer
from core.utils.risk_adapter import jsonify_results
from core.utils.mcp_result_parser import safe_extract_content

# Import from existing tools
from core.agents.quant_tools.correlation_matrix_tool import (
    _fetch_price_data,
    _calculate_correlation_matrix
)

logger = logging.getLogger(__name__)


async def _get_risk_free_rate() -> float:
    """Fetch current risk-free rate from FRED (3M Treasury)."""
    try:
        from core.mcp_servers.EconomicDataServer import EconomicDataServer
        fred_server = EconomicDataServer()
        await fred_server.connect()

        try:
            fred_result = await fred_server.get_series_data(series_id="DGS3MO")

            if fred_result and fred_result.get("data") and len(fred_result["data"]) > 0:
                rfr = fred_result["data"][-1]["value"] / 100.0
                logger.info(f"Fetched risk-free rate from FRED: {rfr:.4f}")
                return rfr
            else:
                logger.warning("FRED returned no data, using fallback 4%")
                return 0.04
        finally:
            await fred_server.cleanup()

    except Exception as e:
        logger.warning(f"Failed to fetch risk-free rate from FRED: {e}")
        return 0.04


def _extract_result_text(result) -> str:
    """Extract text content from MCP result."""
    if hasattr(result, 'content'):
        if isinstance(result.content, list):
            text_parts = [item.text for item in result.content if hasattr(item, 'text')]
            return ''.join(text_parts)
        elif hasattr(result.content, 'text'):
            return result.content.text
        return str(result.content)
    return str(result)


def _black_scholes_vega(spot, strike, time_to_exp, vol, rate):
    """Calculate Black-Scholes vega (same for calls and puts)."""
    if time_to_exp <= 0:
        return 0.0

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))

    # N'(d1) = normal PDF at d1
    norm_pdf = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 ** 2)

    # vega = S × N'(d1) × √T
    # Divide by 100 to get vega per 1% vol change
    vega = (spot * norm_pdf * math.sqrt(time_to_exp)) / 100.0

    return vega


def _black_scholes_delta(spot, strike, time_to_exp, vol, rate, option_type):
    """Calculate Black-Scholes delta."""
    if time_to_exp <= 0:
        return 1.0 if (option_type == 'call' and spot > strike) else 0.0

    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))

    if option_type == 'call':
        return norm_cdf(d1)
    else:
        return norm_cdf(d1) - 1.0


def _black_scholes_price(spot, strike, time_to_exp, vol, rate, option_type):
    """Calculate Black-Scholes option price."""
    if time_to_exp <= 0:
        if option_type == 'call':
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)

    def norm_cdf(x):
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    d1 = (math.log(spot / strike) + (rate + 0.5 * vol ** 2) * time_to_exp) / (vol * math.sqrt(time_to_exp))
    d2 = d1 - vol * math.sqrt(time_to_exp)

    if option_type == 'call':
        price = spot * norm_cdf(d1) - strike * math.exp(-rate * time_to_exp) * norm_cdf(d2)
    else:
        price = strike * math.exp(-rate * time_to_exp) * norm_cdf(-d2) - spot * norm_cdf(-d1)

    return max(0, price)


async def _fetch_atm_straddle(
    polygon_server: PolygonOptionsFuturesServer,
    ticker: str,
    target_expiration: datetime,
    atm_tolerance: float = 0.05,
    risk_free_rate: float = 0.04
) -> Dict[str, Any]:
    """
    Fetch ATM straddle data from Polygon options chain.
    Copies pattern from implied_correlation_tool.

    Args:
        polygon_server: Connected Polygon server
        ticker: Stock or index ticker
        target_expiration: Target expiration date
        atm_tolerance: ATM strike tolerance (5% default)

    Returns:
        Dict with spot, strike, call_iv, put_iv, avg_iv, vega, delta, time_to_expiry

    Raises:
        ValueError: If unable to fetch options data
    """
    try:
        # Step 1: Fetch small sample to extract underlying price
        logger.info(f"Fetching sample to extract underlying price for {ticker}")
        sample_args = {
            "underlying": ticker,
            "limit": 10,
            "expiration_date": target_expiration.strftime("%Y-%m-%d")
        }

        sample_result = await polygon_server.call_tool("get_option_chain", arguments=sample_args)
        if not sample_result or not hasattr(sample_result, 'content') or not sample_result.content:
            raise ValueError(f"No response from options API for {ticker}")

        sample_content = _extract_result_text(sample_result)
        if hasattr(sample_result, "isError") and sample_result.isError:
            raise ValueError(f"Options API error for {ticker}: {sample_content or 'Unknown error'}")

        if not sample_content or not sample_content.strip():
            raise ValueError(f"Empty response from options API for {ticker}")

        try:
            sample_data = json.loads(sample_content)
        except json.JSONDecodeError as e:
            preview = sample_content[:200].replace("\n", " ")
            raise ValueError(f"Invalid JSON from options API for {ticker}: {e.msg}. Preview: {preview}")

        if "error" in sample_data:
            raise ValueError(f"API error for {ticker}: {sample_data['error']}")

        if "data" not in sample_data or "results" not in sample_data["data"]:
            raise ValueError(f"No options data found for {ticker}")

        sample_contracts = sample_data["data"]["results"] or []
        if not sample_contracts:
            raise ValueError(f"No options contracts found for {ticker}")

        # Extract underlying price from first contract
        underlying_price = None
        for contract in sample_contracts:
            if 'underlying_asset' in contract:
                underlying_price = contract['underlying_asset'].get('price')
                if underlying_price:
                    break

        if not underlying_price:
            raise ValueError(f"Could not extract underlying price for {ticker} from sample")

        logger.info(f"Extracted underlying price for {ticker}: ${underlying_price:.2f}")

        # Step 2: Calculate ATM strike range
        strike_lower = underlying_price * (1 - atm_tolerance)
        strike_upper = underlying_price * (1 + atm_tolerance)
        logger.info(f"ATM strike range for {ticker}: ${strike_lower:.2f} to ${strike_upper:.2f}")

        # Step 3: Fetch ATM contracts with strike filters
        logger.info(f"Fetching ATM contracts for {ticker}")
        args = {
            "underlying": ticker,
            "limit": 50,
            "expiration_date": target_expiration.strftime("%Y-%m-%d"),
            "strike_price.gte": strike_lower,
            "strike_price.lte": strike_upper
        }

        result = await polygon_server.call_tool("get_option_chain", arguments=args)

        if not result or not hasattr(result, 'content') or not result.content:
            raise ValueError(f"No response from options API for {ticker}")

        raw_content = _extract_result_text(result)
        if hasattr(result, "isError") and result.isError:
            raise ValueError(f"Options API error for {ticker}: {raw_content or 'Unknown error'}")

        if not raw_content or not raw_content.strip():
            raise ValueError(f"Empty response from options API for {ticker}")

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            preview = raw_content[:200].replace("\n", " ")
            raise ValueError(f"Invalid JSON from options API for {ticker}: {e.msg}. Preview: {preview}")

        if "error" in data:
            raise ValueError(f"API error for {ticker}: {data['error']}")

        if "data" not in data or "results" not in data["data"]:
            raise ValueError(f"No options data found for {ticker}")

        contracts = data["data"]["results"] or []
        if not contracts:
            raise ValueError(f"No ATM contracts found for {ticker}")

        logger.info(f"Received {len(contracts)} ATM contracts for {ticker}")

        # Step 4: Separate calls and puts, extract IVs
        call_ivs = []
        put_ivs = []
        strikes = {}

        for contract in contracts:
            details = contract.get("details", {})
            strike = details.get("strike_price")
            contract_type = details.get("contract_type", "").lower()
            iv = contract.get("implied_volatility")

            if not strike or not contract_type or not iv:
                continue

            strike = float(strike)
            iv = float(iv)

            if strike not in strikes:
                strikes[strike] = {}

            strikes[strike][contract_type] = iv

            if contract_type == "call":
                call_ivs.append(iv)
            elif contract_type == "put":
                put_ivs.append(iv)

        if not call_ivs and not put_ivs:
            raise ValueError(f"No valid IVs found in ATM contracts for {ticker}")

        # Find ATM strike (closest to spot)
        atm_strike = min(strikes.keys(), key=lambda x: abs(x - underlying_price))

        # Get call and put IVs at ATM strike
        call_iv = strikes[atm_strike].get('call')
        put_iv = strikes[atm_strike].get('put')

        if not call_iv or not put_iv:
            # Fallback: average across all strikes
            call_iv = sum(call_ivs) / len(call_ivs) if call_ivs else None
            put_iv = sum(put_ivs) / len(put_ivs) if put_ivs else None

        if not call_iv and not put_iv:
            raise ValueError(f"No call or put IVs found for {ticker}")

        # Average IV for straddle
        avg_iv = (call_iv + put_iv) / 2.0 if call_iv and put_iv else (call_iv or put_iv)

        # Calculate time to expiry
        time_to_exp = (target_expiration - datetime.now()).days / 365.0

        if time_to_exp <= 0:
            raise ValueError(f"Options expired for {ticker}")

        # Calculate vega
        vega = _black_scholes_vega(underlying_price, atm_strike, time_to_exp, avg_iv, risk_free_rate)

        # Calculate straddle price
        call_price = _black_scholes_price(underlying_price, atm_strike, time_to_exp, avg_iv, risk_free_rate, 'call')
        put_price = _black_scholes_price(underlying_price, atm_strike, time_to_exp, avg_iv, risk_free_rate, 'put')
        straddle_price = call_price + put_price

        # Calculate net delta (should be ~0 for ATM straddle)
        call_delta = _black_scholes_delta(underlying_price, atm_strike, time_to_exp, avg_iv, risk_free_rate, 'call')
        put_delta = _black_scholes_delta(underlying_price, atm_strike, time_to_exp, avg_iv, risk_free_rate, 'put')
        net_delta = call_delta + put_delta

        logger.info(f"ATM straddle for {ticker}: spot=${underlying_price:.2f}, strike=${atm_strike:.2f}, "
                   f"IV={avg_iv:.2%}, vega={vega:.4f}, price=${straddle_price:.2f}")

        return {
            "ticker": ticker,
            "spot": float(underlying_price),
            "strike": float(atm_strike),
            "call_iv": float(call_iv) if call_iv else None,
            "put_iv": float(put_iv) if put_iv else None,
            "avg_iv": float(avg_iv),
            "vega": float(vega),
            "delta": float(net_delta),
            "straddle_price": float(straddle_price),
            "call_price": float(call_price),
            "put_price": float(put_price),
            "time_to_expiry": float(time_to_exp),
            "expiration_date": target_expiration.strftime("%Y-%m-%d"),
            "days_to_expiry": (target_expiration - datetime.now()).days
        }

    except Exception as e:
        logger.error(f"ATM straddle fetch failed for {ticker}: {e}")
        raise


def _calculate_index_implied_vol(
    constituent_vols: List[float],
    weights: List[float],
    avg_correlation: float
) -> float:
    """
    Calculate implied index volatility from constituent vols and correlation.

    Formula: σ_index² = Σ(w_i² σ_i²) + ΣΣ(w_i w_j ρ σ_i σ_j) for i≠j

    Args:
        constituent_vols: List of constituent implied vols
        weights: List of index weights (must sum to 1)
        avg_correlation: Average pairwise correlation

    Returns:
        Index implied volatility
    """
    n = len(constituent_vols)
    variance = 0.0

    # Variance from weighted sum
    for i in range(n):
        # Self-correlation term
        variance += (weights[i] ** 2) * (constituent_vols[i] ** 2)

        # Cross-correlation terms
        for j in range(i + 1, n):
            variance += 2 * weights[i] * weights[j] * avg_correlation * constituent_vols[i] * constituent_vols[j]

    return math.sqrt(max(0, variance))


async def price_dispersion_trade_internal(
    index_ticker: str,
    notional: float,
    constituent_tickers: Optional[List[str]] = None,
    num_constituents: int = 10,
    weights_json: Optional[str] = None,
    tenor: str = "3M",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Internal implementation for dispersion trade pricing.
    
    Call this directly from Canvas executors. For agent usage, use price_dispersion_trade.

    Dispersion Trade Structure:
    1. BUY index ATM straddle (long index volatility)
    2. SELL weighted basket of constituent ATM straddles (short single-stock vols)

    Trade Thesis:
    - Profits when correlation decreases (constituents move independently)
    - σ_index² = Σ(w_i² σ_i²) + ΣΣ(w_i w_j ρ_ij σ_i σ_j)
    - If ρ decreases → index vol drops more than constituent vols → profit

    Vega Neutrality:
    - Positions sized so net vega ≈ 0 at initiation
    - Constituent contracts = (Index_Vega × weight_i) / Constituent_Vega_i

    Data Sources:
    - Polygon: ATM straddle IVs for index and constituents (same expiration)
    - FMP: Historical prices for correlation calculation

    Args:
        index_ticker: Index ticker (e.g., "SPY", "QQQ")
        constituent_tickers: List of constituent stock tickers
        weights_json: JSON string mapping ticker to index weight (must sum to 1.0)
            Example: '{"AAPL": 0.25, "MSFT": 0.20, "NVDA": 0.15}'
        notional: Trade notional amount ($)
        tenor: Option tenor ("1M", "3M", "6M", "1Y")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with:
        {
            "status": "success",
            "net_cost": float - Initial cost of dispersion trade ($)
            "index_straddle_cost": float - Cost of index straddle ($)
            "constituent_straddles_cost": float - Total cost of constituent straddles ($)
            "net_vega": float - Net vega exposure (should be ~0)
            "net_delta": float - Net delta exposure (should be ~0)
            "correlation_beta": float - P&L sensitivity to 1% correlation change
            "current_avg_correlation": float - Current realized correlation
            "implied_correlation": float - Correlation implied by option prices
            "index_data": Dict - Index straddle details
            "constituent_data": List[Dict] - Constituent straddle details
            "position_sizes": Dict[str, int] - Number of contracts per ticker
            "inputs": Dict - Echo of inputs
            "data_sources": List[str] - Data sources used
            "summary": str - Human-readable summary
        }

        On error:
        {
            "status": "error",
            "error": str - Error message
            "calculation_type": "dispersion_trade"
        }

    Examples:
        # SPY dispersion with top 5 constituents
        result = await price_dispersion_trade(
            index_ticker="SPY",
            constituent_tickers=["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"],
            weights={
                "AAPL": 0.25,
                "MSFT": 0.20,
                "NVDA": 0.18,
                "GOOGL": 0.12,
                "AMZN": 0.25
            },
            notional=1_000_000,
            tenor="3M"
        )
        print(f"Net Cost: ${result['net_cost']:,.2f}")
        print(f"Correlation Beta: ${result['correlation_beta']:,.0f} per 1% move")
    """
    try:
        data_sources = []
        
        # Auto-fetch ETF holdings if constituents not provided
        if not constituent_tickers:
            logger.info(f"No constituents provided, fetching top {num_constituents} holdings for {index_ticker}")
            tradeflow_server = FMPTradeFlowServer()
            await tradeflow_server.connect()
            
            result = await tradeflow_server.call_tool(
                "get_etf_holdings",
                arguments={"symbol": index_ticker, "data_types": ["holdings"]}
            )
            
            text_content = safe_extract_content(result) or _extract_result_text(result)
            if not text_content:
                raise ValueError(f"No ETF holdings found for {index_ticker}")
            
            holdings_data = json.loads(text_content)
            
            # FMP returns nested structure: data["data"]["holdings"]
            if "data" not in holdings_data or "holdings" not in holdings_data["data"]:
                raise ValueError(f"No holdings data found for {index_ticker}")
            
            holdings_list = holdings_data["data"]["holdings"]
            if not holdings_list or not isinstance(holdings_list, list):
                raise ValueError(f"No holdings in response for {index_ticker}")
            
            # Sort by weight and take top N
            sorted_holdings = sorted(holdings_list, key=lambda x: float(x.get("weightPercentage", 0) or 0), reverse=True)
            top_holdings = sorted_holdings[:num_constituents]
            
            # Extract tickers and weights
            constituent_tickers = []
            weights = {}
            for h in top_holdings:
                ticker = (h.get("asset") or h.get("symbol") or h.get("ticker", "")).upper()
                weight = float(h.get("weightPercentage", 0) or 0) / 100.0
                if ticker and ticker != index_ticker:
                    constituent_tickers.append(ticker)
                    weights[ticker] = weight
            
            # Normalize weights
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}
            
            logger.info(f"Fetched {len(constituent_tickers)} constituents: {constituent_tickers}")
            data_sources.append(f"etf_holdings: FMP {index_ticker} top {len(constituent_tickers)}")
        
        # Parse weights from JSON string or use equal weights (if constituents were provided manually)
        if weights_json:
            try:
                weights = json.loads(weights_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid weights JSON: {e}")
        elif not constituent_tickers:
            raise ValueError("No constituent tickers provided and could not fetch ETF holdings")
        elif 'weights' not in dir() or not weights:
            # Default to equal weights if we have manual constituents but no weights
            n = len(constituent_tickers)
            weights = {ticker: 1.0/n for ticker in constituent_tickers}
            logger.info(f"Using equal weights for {n} constituents")

        # Set pricing date
        if pricing_date is None:
            pricing_date = datetime.now().strftime("%Y-%m-%d")

        pricing_dt = datetime.strptime(pricing_date, "%Y-%m-%d")

        # Parse tenor to get target expiration
        tenor = tenor.upper()
        if tenor.endswith('M'):
            tenor_months = int(tenor[:-1])
            # Target 3rd Friday of month (standard monthly expiration)
            target_month = pricing_dt + timedelta(days=tenor_months * 30)
            # Find 3rd Friday
            first_day = target_month.replace(day=1)
            # First Friday
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            # Third Friday
            target_expiration = first_friday + timedelta(days=14)
        elif tenor.endswith('Y'):
            tenor_years = int(tenor[:-1])
            target_month = pricing_dt + timedelta(days=tenor_years * 365)
            first_day = target_month.replace(day=1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            target_expiration = first_friday + timedelta(days=14)
        else:
            raise ValueError(f"Invalid tenor format: {tenor}. Use '1M', '3M', '6M', '1Y'")

        logger.info(f"Target expiration: {target_expiration.strftime('%Y-%m-%d')} (3rd Friday)")

        # Fetch risk-free rate from FRED
        risk_free_rate = await _get_risk_free_rate()
        data_sources = [f"risk_free_rate: FRED 3M Treasury ({risk_free_rate:.4f})"]

        # Validate inputs
        if notional <= 0:
            raise ValueError(f"Notional must be positive: {notional}")

        if not constituent_tickers:
            raise ValueError("Must provide at least one constituent ticker")

        # Validate weights
        total_weight = sum(weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0 (got {total_weight:.2f})")

        for ticker in constituent_tickers:
            if ticker not in weights:
                raise ValueError(f"Missing weight for constituent {ticker}")

        # Connect to servers
        polygon_server = PolygonOptionsFuturesServer()
        fmp_server = FMPMarketDataServer()

        try:
            await polygon_server.connect()
            await fmp_server.connect()

            # Step 1: Fetch index ATM straddle
            logger.info(f"Fetching ATM straddle for index {index_ticker}")
            index_data = await _fetch_atm_straddle(polygon_server, index_ticker, target_expiration, risk_free_rate=risk_free_rate)
            data_sources.append(f"index_straddle: Polygon {index_ticker} ATM (expiry={target_expiration.strftime('%Y-%m-%d')})")

            # Step 2: Fetch constituent ATM straddles in parallel
            logger.info(f"Fetching ATM straddles for {len(constituent_tickers)} constituents in parallel")

            async def fetch_single_constituent(ticker: str):
                try:
                    return await _fetch_atm_straddle(polygon_server, ticker, target_expiration, risk_free_rate=risk_free_rate)
                except Exception as e:
                    logger.warning(f"Failed to fetch straddle for {ticker}: {e}")
                    return None

            results = await asyncio.gather(*[fetch_single_constituent(ticker) for ticker in constituent_tickers])

            constituent_data = [r for r in results if r is not None]
            failed_tickers = [constituent_tickers[i] for i, r in enumerate(results) if r is None]

            if not constituent_data:
                raise ValueError("No constituent straddles could be fetched")

            if failed_tickers:
                logger.warning(f"Failed to fetch {len(failed_tickers)} constituents: {', '.join(failed_tickers)}")
                data_sources.append(f"failed_tickers: {', '.join(failed_tickers)}")

            data_sources.append(f"constituent_straddles: Polygon {len(constituent_data)}/{len(constituent_tickers)} tickers")

            # Step 3: Calculate historical correlation
            logger.info("Calculating historical correlation matrix")
            all_tickers = [c["ticker"] for c in constituent_data]
            lookback_days = 252  # 1 year

            # Fetch price data - rename columns to ticker names for proper merge
            price_dfs = {}
            for ticker in all_tickers:
                try:
                    df = await _fetch_price_data(fmp_server, ticker, lookback_days)
                    # Set date as index and rename price column to ticker
                    df = df.set_index('date')
                    df = df.rename(columns={'price': ticker})
                    price_dfs[ticker] = df
                except Exception as e:
                    logger.warning(f"Failed to fetch price data for {ticker}: {e}")

            if len(price_dfs) < 2:
                # Fallback: use default correlation
                avg_correlation = 0.5
                logger.warning("Using default correlation (0.5) - insufficient price data")
            else:
                # Merge all price data on date index
                merged_df = pd.concat(price_dfs.values(), axis=1, join='inner')

                if len(merged_df) < 30:
                    avg_correlation = 0.5
                    logger.warning("Using default correlation (0.5) - insufficient overlapping data")
                else:
                    # Calculate correlation matrix
                    returns_df = merged_df.pct_change().dropna()
                    corr_matrix = returns_df.corr(method='pearson')

                    # Average pairwise correlation
                    constituent_cols = [c["ticker"] for c in constituent_data if c["ticker"] in corr_matrix.columns]
                    if len(constituent_cols) >= 2:
                        corr_values = []
                        for i, ticker_i in enumerate(constituent_cols):
                            for ticker_j in constituent_cols[i+1:]:
                                corr_values.append(corr_matrix.loc[ticker_i, ticker_j])
                        avg_correlation = float(np.mean(corr_values))
                    else:
                        avg_correlation = 0.5

            data_sources.append(f"correlation: FMP historical ({lookback_days} days, avg={avg_correlation:.2%})")

        finally:
            await polygon_server.cleanup()
            await fmp_server.cleanup()

        # Step 4: Calculate index position first (needed for constituent sizing)
        index_vega = index_data["vega"]
        index_contracts = int(notional / (index_data["straddle_price"] * 100))
        index_cost = index_data["straddle_price"] * index_contracts * 100
        total_index_vega = index_vega * index_contracts

        # Step 5: Calculate constituent position sizes (vega-neutral)
        position_sizes = {}
        constituent_positions = []

        for straddle in constituent_data:
            ticker = straddle["ticker"]
            weight = weights.get(ticker, 0)

            # Vega-neutral sizing: match weighted portion of index vega
            # contracts = (total_index_vega × weight) / constituent_vega
            target_vega = total_index_vega * weight
            contracts = int(round(target_vega / straddle["vega"])) if straddle["vega"] > 0 else 0

            position_sizes[ticker] = contracts

            constituent_positions.append({
                **straddle,
                "weight": weight,
                "contracts": contracts,
                "total_cost": straddle["straddle_price"] * contracts * 100  # 100 shares per contract
            })

        # Step 6: Calculate net cost
        constituent_total_cost = sum(p["total_cost"] for p in constituent_positions)
        net_cost = index_cost - constituent_total_cost

        # Step 7: Calculate net Greeks
        constituent_vega_total = sum(p["vega"] * p["contracts"] for p in constituent_positions)
        constituent_delta_total = sum(p["delta"] * p["contracts"] for p in constituent_positions)
        net_vega = total_index_vega - constituent_vega_total
        net_delta = index_data["delta"] * index_contracts - constituent_delta_total

        # Step 8: Calculate implied correlation from option prices
        # Solve for ρ where σ_index(ρ) = index_IV
        constituent_vols = [p["avg_iv"] for p in constituent_positions]
        raw_weights = [p["weight"] for p in constituent_positions]
        
        # Normalize weights to sum to 1 (since we only have top N constituents)
        weight_sum = sum(raw_weights)
        constituent_weights = [w / weight_sum for w in raw_weights] if weight_sum > 0 else raw_weights

        # Solve for implied correlation
        implied_correlation = avg_correlation  # Default fallback
        try:
            from scipy.optimize import brentq
            
            def implied_vol_diff(rho):
                return _calculate_index_implied_vol(constituent_vols, constituent_weights, rho) - index_data["avg_iv"]
            
            # Check if solution exists in range
            vol_at_neg = implied_vol_diff(-0.5)
            vol_at_pos = implied_vol_diff(0.99)
            
            if vol_at_neg * vol_at_pos < 0:  # Root exists
                implied_correlation = brentq(implied_vol_diff, -0.5, 0.99, xtol=0.001)
            else:
                # No root - use grid search for closest match
                best_rho = avg_correlation
                best_diff = abs(implied_vol_diff(avg_correlation))
                for rho in [i/100 for i in range(-50, 100, 5)]:
                    diff = abs(implied_vol_diff(rho))
                    if diff < best_diff:
                        best_diff = diff
                        best_rho = rho
                implied_correlation = best_rho
                logger.info(f"Grid search implied correlation: {best_rho:.2%}")
        except Exception as e:
            logger.warning(f"Could not solve for implied correlation: {e}, using realized")

        # Step 9: Calculate correlation beta (P&L sensitivity to 1% correlation change)
        rho_up = avg_correlation + 0.01
        index_vol_up = _calculate_index_implied_vol(constituent_vols, constituent_weights, rho_up)
        index_vol_current = _calculate_index_implied_vol(constituent_vols, constituent_weights, avg_correlation)

        # Higher correlation → higher index vol → loss for long index position
        correlation_beta = -(index_vol_up - index_vol_current) * index_vega * index_contracts * 100

        # Build summary
        summary = (
            f"Dispersion trade: {index_ticker} index ({index_contracts} contracts) vs "
            f"{len(constituent_data)} constituents, ${notional:,.0f} notional. "
            f"Net cost: ${net_cost:,.2f}. "
            f"Realized correlation: {avg_correlation:.2%}, "
            f"Implied correlation: {implied_correlation:.2%}. "
            f"Correlation beta: ${correlation_beta:,.0f} per 1% move."
        )

        return jsonify_results({
            "status": "success",
            "net_cost": float(net_cost),
            "index_straddle_cost": float(index_cost),
            "constituent_straddles_cost": float(constituent_total_cost),
            "net_vega": float(net_vega),
            "net_delta": float(net_delta),
            "correlation_beta": float(correlation_beta),
            "current_avg_correlation": float(avg_correlation),
            "implied_correlation": float(implied_correlation),
            "index_data": index_data,
            "constituent_data": constituent_positions,
            "position_sizes": position_sizes,
            "index_contracts": index_contracts,
            "inputs": {
                "index_ticker": index_ticker,
                "constituent_tickers": constituent_tickers,
                "weights": weights,
                "notional": notional,
                "tenor": tenor,
                "pricing_date": pricing_date
            },
            "data_sources": data_sources,
            "summary": summary
        })

    except Exception as e:
        logger.error(f"Dispersion trade pricing failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "calculation_type": "dispersion_trade"
        }


@function_tool
async def price_dispersion_trade(
    index_ticker: str,
    notional: float,
    constituent_tickers: Optional[List[str]] = None,
    num_constituents: int = 10,
    weights_json: Optional[str] = None,
    tenor: str = "3M",
    pricing_date: Optional[str] = None
) -> dict:
    """
    Price and analyze dispersion trades (long index vol, short constituent vols).
    
    Auto-fetches ETF holdings if constituent_tickers not provided.

    Dispersion Trade Structure:
    1. BUY index ATM straddle (long index volatility)
    2. SELL weighted basket of constituent ATM straddles (short single-stock vols)

    Trade Thesis:
    - Profits when correlation decreases (constituents move independently)
    - σ_index² = Σ(w_i² σ_i²) + ΣΣ(w_i w_j ρ_ij σ_i σ_j)
    - If ρ decreases → index vol drops more than constituent vols → profit

    Args:
        index_ticker: Index ticker (e.g., "SPY", "QQQ")
        notional: Trade notional amount ($)
        constituent_tickers: Optional list of constituents (auto-fetched if not provided)
        num_constituents: Number of top holdings to use if auto-fetching (default 10)
        weights_json: JSON string mapping ticker to index weight
        tenor: Option tenor ("1M", "3M", "6M", "1Y")
        pricing_date: Valuation date (YYYY-MM-DD, default: today)

    Returns:
        Dict with net_cost, correlation_beta, implied_correlation, etc.
    """
    return await price_dispersion_trade_internal(
        index_ticker=index_ticker,
        notional=notional,
        constituent_tickers=constituent_tickers,
        num_constituents=num_constituents,
        weights_json=weights_json,
        tenor=tenor,
        pricing_date=pricing_date,
    )
