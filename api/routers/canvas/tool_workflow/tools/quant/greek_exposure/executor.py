"""Canvas executor for unified Greek Exposure (Delta/Gamma/Vega/Theta)."""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List

from core.agents.quant_tools.delta_exposure_tool import _calculate_delta_impl
from core.agents.quant_tools.gamma_exposure_tool import _calculate_gamma_impl
from core.agents.quant_tools.vega_exposure_tool import _calculate_vega_impl
from core.agents.quant_tools.theta_decay_tool import _calculate_theta_impl
from core.services.portfolio_service import PortfolioService
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json

from .charts import (
    build_greek_by_underlying_chart,
    build_position_breakdown_chart,
    build_greek_summary_chart
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
    # Move to next Friday
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
        # OTM: calls above spot, puts below spot
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
        # ITM: calls below spot, puts above spot
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
    
    # Round to nearest $5 (or $1 for cheap stocks)
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
        
        # Normalize weights
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


async def execute_greek_exposure(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute unified Greek Exposure analysis for Canvas.
    
    Args:
        user_id: User ID for RLS context
        org_id: Organization ID for RLS context
        params: Tool parameters including greek_type and positions
    
    Returns:
        Canvas-formatted result
    """
    try:
        # 1. EXTRACT PARAMETERS
        greek_type = params.get("greek_type", "delta")
        tickers = params.get("tickers", [])
        portfolio_id = params.get("portfolio_id")
        option_type = params.get("option_type", "call")
        moneyness = params.get("moneyness", "atm")
        expiry_months = params.get("expiry_months", 3)
        days_forward = params.get("days_forward", 1)  # Only for theta
        
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
                "tool_id": "greek_exposure",
                "tickers": [],
                "weights": []
            }
        
        # 2. PARSE POSITIONS
        portfolio_positions = []
        for pos in positions_raw:
            position = {
                "underlying": pos.get("underlying", "").upper().strip(),
                "expiry": pos.get("expiry", "").strip(),
                "option_type": pos.get("option_type", "call").lower(),
                "strike": float(pos.get("strike", 0)),
                "quantity": int(pos.get("quantity", 0))
            }
            if "implied_volatility" in pos and pos["implied_volatility"]:
                position["implied_volatility"] = float(pos["implied_volatility"])
            portfolio_positions.append(position)
        
        # 3. CALL APPROPRIATE INTERNAL FUNCTION
        greek_config = {
            "delta": {
                "func": _calculate_delta_impl,
                "total_key": "total_delta",
                "by_underlying_key": None,  # Not returned by delta
                "position_key": "position_delta",
                "unit_key": "delta",
                "name": "Delta",
                "symbol": "Δ",
                "description": "Measures price sensitivity to underlying movement",
                "unit": "shares equivalent"
            },
            "gamma": {
                "func": _calculate_gamma_impl,
                "total_key": "total_gamma",
                "by_underlying_key": "gamma_by_underlying",
                "position_key": "position_gamma",
                "unit_key": "gamma",
                "name": "Gamma",
                "symbol": "Γ",
                "description": "Measures delta sensitivity to underlying movement",
                "unit": "delta change per $1"
            },
            "vega": {
                "func": _calculate_vega_impl,
                "total_key": "total_vega",
                "by_underlying_key": "vega_by_underlying",
                "position_key": "position_vega",
                "unit_key": "vega",
                "name": "Vega",
                "symbol": "ν",
                "description": "Measures price sensitivity to volatility change",
                "unit": "$ per 1% vol change"
            },
            "theta": {
                "func": _calculate_theta_impl,
                "total_key": "total_theta",
                "by_underlying_key": "theta_by_underlying",
                "position_key": "position_theta",
                "unit_key": "theta",
                "name": "Theta",
                "symbol": "Θ",
                "description": "Measures daily time decay",
                "unit": "$/day"
            }
        }
        
        config = greek_config.get(greek_type)
        if not config:
            return {
                "status": "error",
                "error": f"Unknown greek_type: {greek_type}. Choose from: delta, gamma, vega, theta",
                "tool_id": "greek_exposure",
                "tickers": [],
                "weights": []
            }
        
        # Call the function
        if greek_type == "theta":
            result = await config["func"](portfolio_positions, None, days_forward)
        else:
            result = await config["func"](portfolio_positions, None, True)
        
        # 4. CHECK FOR ERRORS
        if result.get("error"):
            return {
                "status": "error",
                "error": f"{config['name']} calculation failed: {result['error']}",
                "tool_id": "greek_exposure",
                "tickers": [],
                "weights": []
            }
        
        # 5. EXTRACT DATA
        total_value = _safe_float(result.get(config["total_key"], 0))
        by_underlying = result.get(config["by_underlying_key"], {}) or {}
        position_details = result.get("position_details", [])
        successful = result.get("successful_positions", 0)
        failed = result.get("failed_positions", 0)
        total_positions = result.get("total_positions", len(portfolio_positions))
        
        # Build by_underlying from position_details if not available
        if not by_underlying and position_details:
            by_underlying = {}
            for pos in position_details:
                underlying = pos.get("underlying", "Unknown")
                pos_greek = _safe_float(pos.get(config["position_key"], 0))
                if underlying not in by_underlying:
                    by_underlying[underlying] = 0.0
                by_underlying[underlying] += pos_greek
        
        underlyings = sorted(by_underlying.keys()) if by_underlying else []
        
        # 6. BUILD METRIC CARDS
        metric_cards = [
            {
                "label": f"Total {config['name']}",
                "value": f"{total_value:+,.2f}",
                "subtext": config["unit"]
            },
            {
                "label": "Positions Analyzed",
                "value": f"{successful}/{total_positions}",
                "subtext": f"{failed} failed" if failed > 0 else "all successful"
            }
        ]
        
        # Add theta-specific card
        if greek_type == "theta":
            projected_pnl = _safe_float(result.get("total_projected_pnl", total_value * days_forward))
            metric_cards.append({
                "label": f"{days_forward}-Day Projected P&L",
                "value": f"${projected_pnl:+,.2f}",
                "subtext": "from time decay"
            })
        
        # Add gamma-specific card (gamma notional)
        if greek_type == "gamma":
            gamma_notional = _safe_float(result.get("total_gamma_notional", 0))
            if gamma_notional != 0:
                metric_cards.append({
                    "label": "Gamma Notional",
                    "value": f"${gamma_notional:+,.0f}",
                    "subtext": "P&L from 1% spot move"
                })
        
        # 7. BUILD STATS TABLE
        stats_table = []
        
        stats_table.append({
            "category": "Summary",
            "metric": f"Total {config['name']} ({config['symbol']})",
            "value": f"{total_value:+,.4f}"
        })
        stats_table.append({
            "category": "Summary",
            "metric": "Successful Positions",
            "value": f"{successful}"
        })
        stats_table.append({
            "category": "Summary",
            "metric": "Failed Positions",
            "value": f"{failed}"
        })
        
        # By underlying breakdown
        for underlying, greek_val in by_underlying.items():
            stats_table.append({
                "category": underlying,
                "metric": config['name'],
                "value": f"{greek_val:+,.4f}"
            })
        
        # 8. BUILD CHARTS
        charts = {}
        
        # Chart 1: Greek by underlying
        if by_underlying:
            chart1 = build_greek_by_underlying_chart(
                by_underlying=by_underlying,
                greek_name=config["name"],
                greek_symbol=config["symbol"]
            )
            if chart1:
                charts["greek_by_underlying"] = chart1
        
        # Chart 2: Position breakdown
        if position_details:
            chart2 = build_position_breakdown_chart(
                position_details=position_details,
                position_key=config["position_key"],
                greek_name=config["name"]
            )
            if chart2:
                charts["position_breakdown"] = chart2
        
        # 9. BUILD SUMMARY
        summary = (
            f"**{config['name']} Exposure Analysis**\n\n"
            f"**What is {config['name']}?**\n"
            f"{config['description']}\n\n"
            f"**Portfolio {config['name']}:** {total_value:+,.4f} {config['unit']}\n\n"
        )
        
        if greek_type == "delta":
            summary += (
                f"**Interpretation:**\n"
                f"- Delta of {total_value:+,.0f} means the portfolio behaves like holding {abs(total_value):,.0f} shares\n"
                f"- Positive delta = bullish exposure (profits when underlying rises)\n"
                f"- Negative delta = bearish exposure (profits when underlying falls)\n"
            )
        elif greek_type == "gamma":
            summary += (
                f"**Interpretation:**\n"
                f"- Gamma of {total_value:+,.4f} means delta changes by this amount per $1 move\n"
                f"- High positive gamma = delta becomes more bullish on rallies\n"
                f"- High negative gamma = short gamma risk (delta moves against you)\n"
            )
        elif greek_type == "vega":
            summary += (
                f"**Interpretation:**\n"
                f"- Vega of {total_value:+,.2f} means portfolio gains/loses this much per 1% vol change\n"
                f"- Positive vega = long volatility (profits from vol expansion)\n"
                f"- Negative vega = short volatility (profits from vol contraction)\n"
            )
        elif greek_type == "theta":
            projected = total_value * days_forward
            summary += (
                f"**Interpretation:**\n"
                f"- Theta of {total_value:+,.2f}/day means portfolio loses ${abs(total_value):.2f} daily to time decay\n"
                f"- {days_forward}-day projected P&L: ${projected:+,.2f}\n"
                f"- Negative theta is normal for long options (you pay for time)\n"
                f"- Positive theta means you collect time decay (short options)\n"
            )
        
        if by_underlying:
            summary += f"\n**Breakdown by Underlying:**\n"
            for underlying, val in sorted(by_underlying.items(), key=lambda x: abs(x[1]), reverse=True):
                summary += f"- **{underlying}**: {val:+,.4f}\n"
        
        # 10. RETURN CANVAS FORMAT
        return {
            "status": "success",
            "tool_id": "greek_exposure",
            "tickers": underlyings,
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                f"total_{greek_type}": total_value,
                "successful_positions": successful,
                "failed_positions": failed,
                "total_positions": total_positions,
                "greek_type": greek_type
            },
            "summary": summary
        }
    
    except Exception as e:
        logger.error(f"Greek exposure execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Execution failed: {str(e)}",
            "tool_id": "greek_exposure",
            "tickers": [],
            "weights": []
        }
