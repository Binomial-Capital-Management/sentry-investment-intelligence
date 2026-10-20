"""Canvas executor for Cross-Asset Greeks (second-order Greeks)."""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.agents.quant_tools import calculate_cross_greeks_internal
from core.services.portfolio_service import PortfolioService
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from .charts import (
    build_greeks_by_underlying_chart,
    build_position_details_chart,
    build_greeks_comparison_chart
)

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


def _get_expiry(months: int = 3) -> str:
    """Get expiry date (N months from now, next Friday)."""
    date = datetime.now() + timedelta(days=months * 30)
    days_until_friday = (4 - date.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    date = date + timedelta(days=days_until_friday)
    return date.strftime("%Y-%m-%d")


def _calculate_strike(price: float, moneyness: str, option_type: str) -> float:
    """Calculate strike based on moneyness."""
    if moneyness == "atm":
        strike = price
    elif moneyness == "otm_5":
        if option_type == "call":
            strike = price * 1.05
        else:
            strike = price * 0.95
    elif moneyness == "otm_10":
        if option_type == "call":
            strike = price * 1.10
        else:
            strike = price * 0.90
    elif moneyness == "itm_5":
        if option_type == "call":
            strike = price * 0.95
        else:
            strike = price * 1.05
    elif moneyness == "itm_10":
        if option_type == "call":
            strike = price * 0.90
        else:
            strike = price * 1.10
    else:
        strike = price
    
    if strike >= 50:
        strike = round(strike / 5) * 5
    else:
        strike = round(strike)
    
    return max(strike, 1.0)


async def _fetch_price(fmp_server, ticker: str) -> float:
    """Fetch current price for a ticker."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)
        result = await fmp_server.call_tool("get_historical_data", {
            "symbol": ticker,
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        if result and hasattr(result, 'content'):
            data = safe_parse_json(result)
            prices = data.get("prices") or data.get("closes") or data.get("close") or []
            if prices:
                return float(prices[-1])
    except Exception as e:
        logger.warning(f"Failed to fetch price for {ticker}: {e}")
    return 0.0


async def _generate_positions_from_tickers(
    tickers: List[str],
    option_type: str = "call",
    moneyness: str = "atm",
    expiry_months: int = 3
) -> List[Dict[str, Any]]:
    """Generate options from a list of tickers with specified parameters."""
    positions = []
    
    if not tickers:
        return positions
    
    try:
        fmp_server = FMPMarketDataServer()
        try:
            await fmp_server.connect()
            
            expiry = _get_expiry(expiry_months)
            
            for ticker in tickers:
                ticker = ticker.upper().strip()
                if not ticker:
                    continue
                
                price = await _fetch_price(fmp_server, ticker)
                if price <= 0:
                    continue
                
                strike = _calculate_strike(price, moneyness, option_type)
                
                positions.append({
                    "underlying": ticker,
                    "strike": strike,
                    "option_type": option_type,
                    "quantity": 10,
                    "expiry": expiry
                })
                logger.info(f"Generated: {ticker} ${strike} {option_type[0].upper()} exp {expiry}")
        finally:
            await fmp_server.cleanup()
    
    except Exception as e:
        logger.error(f"Failed to generate positions from tickers: {e}")
    
    return positions


async def _generate_positions_from_portfolio(
    user_id: str,
    portfolio_id: str,
    option_type: str = "call",
    moneyness: str = "atm",
    expiry_months: int = 3
) -> List[Dict[str, Any]]:
    """Generate options from portfolio holdings with specified parameters."""
    positions = []
    
    try:
        portfolio_service = PortfolioService()
        result = await portfolio_service.get_portfolio(user_id, portfolio_id)
        
        if result.get("status") != "success":
            logger.warning(f"Portfolio {portfolio_id} not found: {result.get('message', 'Unknown error')}")
            return positions
        
        portfolio = result.get("portfolio", {})
        tickers = portfolio.get("tickers", [])
        weights = portfolio.get("weights", [])
        
        if not tickers:
            logger.warning(f"Portfolio {portfolio_id} has no tickers")
            return positions
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers)
        else:
            total_weight = sum(weights)
            if total_weight > 0:
                weights = [w / total_weight for w in weights]
        
        fmp_server = FMPMarketDataServer()
        try:
            await fmp_server.connect()
            
            expiry = _get_expiry(expiry_months)
            
            for ticker, weight in zip(tickers, weights):
                price = await _fetch_price(fmp_server, ticker)
                if price <= 0:
                    logger.warning(f"Could not fetch price for {ticker}")
                    continue
                
                strike = _calculate_strike(price, moneyness, option_type)
                quantity = max(1, int(weight * 100))
                
                positions.append({
                    "underlying": ticker.upper(),
                    "strike": strike,
                    "option_type": option_type,
                    "quantity": quantity,
                    "expiry": expiry
                })
                logger.info(f"Generated: {ticker} ${strike} {option_type[0].upper()} x{quantity} exp {expiry}")
        finally:
            await fmp_server.cleanup()
    
    except Exception as e:
        logger.error(f"Failed to generate positions from portfolio: {e}", exc_info=True)
    
    return positions


async def execute_cross_greeks(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Cross-Asset Greeks calculation for Canvas.
    
    Args:
        user_id: User ID for RLS context
        org_id: Organization ID for RLS context
        params: Tool parameters from frontend
    
    Returns:
        Canvas-formatted result with metrics, charts, summary
    """
    try:
        # 1. EXTRACT AND VALIDATE PARAMETERS
        tickers = params.get("tickers", [])
        portfolio_id = params.get("portfolio_id")
        option_type = params.get("option_type", "call")
        moneyness = params.get("moneyness", "atm")
        expiry_months = params.get("expiry_months", 3)
        use_polygon = params.get("use_polygon", True)
        greeks = params.get("greeks", ["vanna", "volga", "charm", "veta"])
        
        # 2. GENERATE POSITIONS FROM TICKERS OR PORTFOLIO
        positions_raw = []
        
        # Priority: tickers first, then portfolio
        if tickers and len(tickers) > 0:
            positions_raw = await _generate_positions_from_tickers(
                tickers, option_type, moneyness, expiry_months
            )
        elif portfolio_id:
            positions_raw = await _generate_positions_from_portfolio(
                user_id, portfolio_id, option_type, moneyness, expiry_months
            )
        
        if not positions_raw:
            return {
                "status": "error",
                "error": "No positions provided. Please add at least one option position.",
                "tool_id": "cross_greeks",
                "tickers": [],
                "weights": []
            }
        
        # 2. PARSE POSITIONS
        # Frontend sends positions as list of dicts with:
        # {underlying, expiry, option_type, strike, quantity, implied_volatility (optional)}
        portfolio_positions = []
        for pos in positions_raw:
            position = {
                "underlying": pos.get("underlying", "").upper().strip(),
                "expiry": pos.get("expiry", "").strip(),
                "option_type": pos.get("option_type", "call").lower(),
                "strike": float(pos.get("strike", 0)),
                "quantity": int(pos.get("quantity", 0))
            }
            
            # Optional IV
            if "implied_volatility" in pos and pos["implied_volatility"]:
                position["implied_volatility"] = float(pos["implied_volatility"])
            
            portfolio_positions.append(position)
        
        # 3. CALL INTERNAL FUNCTION
        result = await calculate_cross_greeks_internal(
            portfolio_positions=portfolio_positions,
            underlying_prices=None,  # Let tool fetch prices
            use_polygon=use_polygon,
            scenarios=greeks
        )
        
        # 4. CHECK FOR ERRORS
        if result.get("error"):
            return {
                "status": "error",
                "error": f"Cross-Greeks calculation failed: {result['error']}",
                "tool_id": "cross_greeks",
                "tickers": [],
                "weights": []
            }
        
        # 5. EXTRACT DATA
        successful = result.get("successful_positions", 0)
        failed = result.get("failed_positions", 0)
        total = result.get("total_positions", len(portfolio_positions))
        
        # Extract Greek totals
        vanna_total = _safe_float(result.get("vanna", {}).get("total", 0)) if "vanna" in greeks else 0
        volga_total = _safe_float(result.get("volga", {}).get("total", 0)) if "volga" in greeks else 0
        charm_total = _safe_float(result.get("charm", {}).get("total", 0)) if "charm" in greeks else 0
        veta_total = _safe_float(result.get("veta", {}).get("total", 0)) if "veta" in greeks else 0
        
        # Extract by-underlying breakdowns
        vanna_by_underlying = result.get("vanna", {}).get("by_underlying", {}) if "vanna" in greeks else {}
        volga_by_underlying = result.get("volga", {}).get("by_underlying", {}) if "volga" in greeks else {}
        charm_by_underlying = result.get("charm", {}).get("by_underlying", {}) if "charm" in greeks else {}
        veta_by_underlying = result.get("veta", {}).get("by_underlying", {}) if "veta" in greeks else {}
        
        # Get unique underlyings
        all_underlyings = set()
        for greek_data in [vanna_by_underlying, volga_by_underlying, charm_by_underlying, veta_by_underlying]:
            all_underlyings.update(greek_data.keys())
        underlyings = sorted(all_underlyings)
        
        # 6. BUILD METRIC CARDS
        metric_cards = []
        
        if "vanna" in greeks:
            metric_cards.append({
                "label": "Total Vanna",
                "value": f"{vanna_total:,.2f}",
                "subtext": "∂²V/∂S∂σ (spot × vol)"
            })
        
        if "volga" in greeks:
            metric_cards.append({
                "label": "Total Volga",
                "value": f"{volga_total:,.2f}",
                "subtext": "∂²V/∂σ² (vol × vol)"
            })
        
        if "charm" in greeks:
            metric_cards.append({
                "label": "Total Charm",
                "value": f"{charm_total:,.2f}",
                "subtext": "∂²V/∂S∂t (spot × time)"
            })
        
        if "veta" in greeks:
            metric_cards.append({
                "label": "Total Veta",
                "value": f"{veta_total:,.2f}",
                "subtext": "∂²V/∂σ∂t (vol × time)"
            })
        
        # 7. BUILD STATS TABLE
        stats_table = []
        
        # Portfolio summary
        stats_table.append({
            "category": "Portfolio",
            "metric": "Total Positions",
            "value": f"{total}"
        })
        stats_table.append({
            "category": "Portfolio",
            "metric": "Successful",
            "value": f"{successful}"
        })
        stats_table.append({
            "category": "Portfolio",
            "metric": "Failed",
            "value": f"{failed}"
        })
        stats_table.append({
            "category": "Portfolio",
            "metric": "Unique Underlyings",
            "value": f"{len(underlyings)}"
        })
        
        # Greek totals
        if "vanna" in greeks:
            stats_table.append({
                "category": "Total Greeks",
                "metric": "Vanna",
                "value": f"{vanna_total:,.4f}"
            })
        if "volga" in greeks:
            stats_table.append({
                "category": "Total Greeks",
                "metric": "Volga",
                "value": f"{volga_total:,.4f}"
            })
        if "charm" in greeks:
            stats_table.append({
                "category": "Total Greeks",
                "metric": "Charm (daily)",
                "value": f"{charm_total:,.4f}"
            })
        if "veta" in greeks:
            stats_table.append({
                "category": "Total Greeks",
                "metric": "Veta (daily)",
                "value": f"{veta_total:,.4f}"
            })
        
        # By-underlying breakdown
        for underlying in underlyings:
            if "vanna" in greeks and underlying in vanna_by_underlying:
                stats_table.append({
                    "category": underlying,
                    "metric": "Vanna",
                    "value": f"{vanna_by_underlying[underlying]:,.4f}"
                })
            if "volga" in greeks and underlying in volga_by_underlying:
                stats_table.append({
                    "category": underlying,
                    "metric": "Volga",
                    "value": f"{volga_by_underlying[underlying]:,.4f}"
                })
            if "charm" in greeks and underlying in charm_by_underlying:
                stats_table.append({
                    "category": underlying,
                    "metric": "Charm",
                    "value": f"{charm_by_underlying[underlying]:,.4f}"
                })
            if "veta" in greeks and underlying in veta_by_underlying:
                stats_table.append({
                    "category": underlying,
                    "metric": "Veta",
                    "value": f"{veta_by_underlying[underlying]:,.4f}"
                })
        
        # 8. BUILD CHARTS
        charts = {}
        
        # Chart 1: Greeks by underlying (bar chart)
        chart1 = build_greeks_by_underlying_chart(
            underlyings=underlyings,
            vanna_by_underlying=vanna_by_underlying if "vanna" in greeks else {},
            volga_by_underlying=volga_by_underlying if "volga" in greeks else {},
            charm_by_underlying=charm_by_underlying if "charm" in greeks else {},
            veta_by_underlying=veta_by_underlying if "veta" in greeks else {},
            greeks=greeks
        )
        if chart1:
            charts["greeks_by_underlying"] = chart1
        
        # Chart 2: Position details (scatter/bubble)
        position_details = result.get(greeks[0], {}).get("position_details", []) if greeks else []
        chart2 = build_position_details_chart(
            position_details=position_details,
            greek_type=greeks[0] if greeks else "vanna"
        )
        if chart2:
            charts["position_details"] = chart2
        
        # Chart 3: Greeks comparison (bar chart comparing totals)
        chart3 = build_greeks_comparison_chart(
            vanna_total=vanna_total if "vanna" in greeks else 0,
            volga_total=volga_total if "volga" in greeks else 0,
            charm_total=charm_total if "charm" in greeks else 0,
            veta_total=veta_total if "veta" in greeks else 0,
            greeks=greeks
        )
        if chart3:
            charts["greeks_comparison"] = chart3
        
        # 9. BUILD SUMMARY
        greek_names = {
            "vanna": "Vanna (∂²V/∂S∂σ)",
            "volga": "Volga (∂²V/∂σ²)",
            "charm": "Charm (∂²V/∂S∂t)",
            "veta": "Veta (∂²V/∂σ∂t)"
        }
        
        greeks_list = ", ".join([greek_names.get(g, g) for g in greeks])
        
        summary = (
            f"**Cross-Asset Greeks Analysis**\n\n"
            f"**Portfolio Overview:**\n"
            f"- **Total Positions**: {total}\n"
            f"- **Successful**: {successful}\n"
            f"- **Failed**: {failed}\n"
            f"- **Unique Underlyings**: {len(underlyings)} ({', '.join(underlyings) if underlyings else 'None'})\n\n"
            f"**Calculated Greeks:** {greeks_list}\n\n"
        )
        
        if "vanna" in greeks:
            summary += (
                f"**Vanna** (∂²V/∂S∂σ): {vanna_total:,.4f}\n"
                f"- Measures how delta changes with volatility\n"
                f"- Positive vanna → delta increases when vol rises\n"
                f"- Key for managing delta-vega interactions\n\n"
            )
        
        if "volga" in greeks:
            summary += (
                f"**Volga** (∂²V/∂σ²): {volga_total:,.4f}\n"
                f"- Measures how vega changes with volatility (vol of vol)\n"
                f"- Positive volga → vega increases when vol rises\n"
                f"- Important for volatility trading strategies\n\n"
            )
        
        if "charm" in greeks:
            summary += (
                f"**Charm** (∂²V/∂S∂t): {charm_total:,.4f} daily\n"
                f"- Measures how delta decays over time\n"
                f"- Positive charm → delta increases as expiry approaches\n"
                f"- Critical for understanding delta drift\n\n"
            )
        
        if "veta" in greeks:
            summary += (
                f"**Veta** (∂²V/∂σ∂t): {veta_total:,.4f} daily\n"
                f"- Measures how vega decays over time\n"
                f"- Usually negative (vega decreases as time passes)\n"
                f"- Key for time-based vol exposure management\n\n"
            )
        
        summary += (
            f"**Interpretation:**\n"
            f"Second-order Greeks capture complex, non-linear sensitivities that first-order Greeks (delta, vega, theta) miss. "
            f"These are essential for:\n"
            f"- **Multi-leg strategies**: Understanding how Greeks evolve\n"
            f"- **Vol trading**: Managing convexity in volatility exposure\n"
            f"- **Dynamic hedging**: Anticipating delta/vega changes\n"
            f"- **Risk management**: Identifying hidden tail risks\n\n"
            f"**Units:**\n"
            f"- Vanna: Change in delta per 1% vol change\n"
            f"- Volga: Change in vega per 1% vol change\n"
            f"- Charm: Change in delta per day\n"
            f"- Veta: Change in vega per day per 1% vol change"
        )
        
        # 10. RETURN CANVAS FORMAT
        return {
            "status": "success",
            "tool_id": "cross_greeks",
            "tickers": underlyings,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "vanna_total": vanna_total,
                "volga_total": volga_total,
                "charm_total": charm_total,
                "veta_total": veta_total,
                "successful_positions": successful,
                "failed_positions": failed,
                "total_positions": total,
                "unique_underlyings": len(underlyings)
            },
            "summary": summary
        }
    
    except ValueError as e:
        logger.error(f"Parameter validation error: {e}")
        return {
            "status": "error",
            "error": f"Invalid parameters: {str(e)}",
            "tool_id": "cross_greeks",
            "tickers": [],
            "weights": []
        }
    except Exception as e:
        logger.error(f"Cross-Greeks execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Execution failed: {str(e)}",
            "tool_id": "cross_greeks",
            "tickers": [],
            "weights": []
        }
