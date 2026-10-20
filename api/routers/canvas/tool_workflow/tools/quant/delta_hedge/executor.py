"""Executor for Delta Hedge Canvas tool."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def execute_delta_hedge(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute delta hedge construction for Canvas."""
    try:
        from core.agents.quant_tools.delta_hedge_tool import construct_delta_hedge_internal
        from core.services.portfolio_service import PortfolioService
        from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
        from core.utils.mcp_result_parser import safe_parse_json
        from .charts import build_hedge_comparison_chart, build_delta_breakdown_chart, build_hedge_instruments_chart
        
        # Extract parameters
        input_type = params.get("input_type", "portfolio")
        portfolio_id = params.get("portfolio_id")
        tickers = params.get("tickers", "")
        hedge_tickers = params.get("hedge_tickers", "SPY")
        target_delta = float(params.get("target_delta", 0.0))
        rebalance_threshold = float(params.get("rebalance_threshold", 0.1))
        option_type = params.get("option_type", "call")
        moneyness = params.get("moneyness", "atm")
        days_to_expiry = int(params.get("days_to_expiry", 30))
        
        # Parse hedge tickers
        if isinstance(hedge_tickers, str):
            hedge_tickers = [t.strip().upper() for t in hedge_tickers.split(',') if t.strip()]
        
        if not hedge_tickers:
            hedge_tickers = ["SPY"]
        
        # Build positions from portfolio or tickers
        positions = []
        position_tickers = []
        
        if input_type == 'portfolio' and portfolio_id:
            # Fetch portfolio holdings
            portfolio_service = PortfolioService()
            result = await portfolio_service.get_portfolio(user_id, portfolio_id)
            
            if result.get("status") != "success":
                return {"status": "error", "error": f"Portfolio not found: {result.get('message', 'Unknown error')}"}
            
            portfolio = result.get("portfolio", {})
            tickers_list = portfolio.get("tickers", [])
            weights_list = portfolio.get("weights", [])
            
            if not tickers_list:
                return {"status": "error", "error": "Portfolio has no tickers"}
            
            # Normalize weights
            if not weights_list or len(weights_list) != len(tickers_list):
                weights_list = [1.0 / len(tickers_list)] * len(tickers_list)
            else:
                total_weight = sum(weights_list)
                if total_weight > 0:
                    weights_list = [w / total_weight for w in weights_list]
            
            # Generate synthetic options from holdings
            fmp_server = FMPMarketDataServer()
            await fmp_server.connect()
            
            expiry_date = (datetime.now() + timedelta(days=days_to_expiry)).strftime('%Y-%m-%d')
            
            for ticker, weight in zip(tickers_list, weights_list):
                if not ticker or weight <= 0:
                    continue
                
                position_tickers.append(ticker)
                
                # Fetch current price
                try:
                    result = await fmp_server.call_tool("get_historical_data", {
                        "symbol": ticker,
                        "start": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                        "end": datetime.now().strftime("%Y-%m-%d")
                    })
                    data = safe_parse_json(result)
                    prices = data.get("prices", []) or data.get("closes", [])
                    current_price = float(prices[-1]) if prices else 100.0
                except Exception:
                    current_price = 100.0
                
                # Calculate strike based on moneyness
                if moneyness == 'atm':
                    strike = round(current_price, 0)
                elif moneyness == 'otm_5':
                    strike = round(current_price * (1.05 if option_type == 'call' else 0.95), 0)
                elif moneyness == 'itm_5':
                    strike = round(current_price * (0.95 if option_type == 'call' else 1.05), 0)
                else:
                    strike = round(current_price, 0)
                
                # Create position
                contracts = max(1, int(weight * 10))
                
                positions.append({
                    'underlying': ticker,
                    'option_type': option_type,
                    'strike': strike,
                    'expiry': expiry_date,
                    'quantity': contracts,
                    'position_type': 'long'
                })
            
            await fmp_server.cleanup()
            
        elif input_type == 'ticker' and tickers:
            # Use provided tickers
            if isinstance(tickers, str):
                tickers = [t.strip().upper() for t in tickers.split(',') if t.strip()]
            
            fmp_server = FMPMarketDataServer()
            await fmp_server.connect()
            
            expiry_date = (datetime.now() + timedelta(days=days_to_expiry)).strftime('%Y-%m-%d')
            
            for ticker in tickers:
                position_tickers.append(ticker)
                
                try:
                    result = await fmp_server.call_tool("get_historical_data", {
                        "symbol": ticker,
                        "start": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
                        "end": datetime.now().strftime("%Y-%m-%d")
                    })
                    data = safe_parse_json(result)
                    prices = data.get("prices", []) or data.get("closes", [])
                    current_price = float(prices[-1]) if prices else 100.0
                except Exception:
                    current_price = 100.0
                
                if moneyness == 'atm':
                    strike = round(current_price, 0)
                elif moneyness == 'otm_5':
                    strike = round(current_price * (1.05 if option_type == 'call' else 0.95), 0)
                elif moneyness == 'itm_5':
                    strike = round(current_price * (0.95 if option_type == 'call' else 1.05), 0)
                else:
                    strike = round(current_price, 0)
                
                positions.append({
                    'underlying': ticker,
                    'option_type': option_type,
                    'strike': strike,
                    'expiry': expiry_date,
                    'quantity': 1,
                    'position_type': 'long'
                })
            
            await fmp_server.cleanup()
        else:
            return {"status": "error", "error": "Provide portfolio_id or tickers"}
        
        if not positions:
            return {"status": "error", "error": "No valid positions to hedge"}
        
        logger.info(f"Delta Hedge: {len(positions)} positions, hedge with {hedge_tickers}")
        
        # Call internal function
        result = await construct_delta_hedge_internal(
            portfolio_positions=positions,
            hedge_tickers=hedge_tickers,
            underlying_prices=None,
            hedge_target=target_delta,
            rebalance_threshold=rebalance_threshold,
            use_polygon=True
        )
        
        if result.get('error'):
            return {"status": "error", "error": result['error']}
        
        # Extract results
        current_delta = result.get('current_portfolio_delta', 0)
        target = result.get('target_delta', 0)
        delta_to_hedge = result.get('delta_to_hedge', 0)
        hedge_strategies = result.get('hedge_strategies', [])
        residual_delta = result.get('residual_delta', 0)
        hedge_ratio = result.get('hedge_ratio', 0)
        rebalance_info = result.get('rebalance_monitoring', {})
        total_tx_cost = result.get('total_transaction_cost', 0)
        
        # Build metric cards
        metric_cards = [
            {
                "label": "Current Delta",
                "value": f"{current_delta:.2f}",
                "description": "Before hedge"
            },
            {
                "label": "Residual Delta",
                "value": f"{residual_delta:.4f}",
                "description": "After hedge",
                "sentiment": "positive" if abs(residual_delta) < abs(target_delta) + rebalance_threshold else "negative"
            },
            {
                "label": "Delta to Hedge",
                "value": f"{delta_to_hedge:.2f}",
                "description": "Required adjustment"
            },
            {
                "label": "Hedge Ratio",
                "value": f"{hedge_ratio:.2%}",
                "description": "Hedge/Portfolio notional"
            },
            {
                "label": "Transaction Cost",
                "value": f"${total_tx_cost:,.2f}",
                "description": "Estimated cost"
            },
            {
                "label": "Rebalance Needed",
                "value": "Yes" if rebalance_info.get('requires_rebalance') else "No",
                "description": f"Threshold: {rebalance_threshold}",
                "sentiment": "negative" if rebalance_info.get('requires_rebalance') else "positive"
            },
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Portfolio", "metric": "Current Delta", "value": f"{current_delta:.4f}"},
            {"category": "Portfolio", "metric": "Target Delta", "value": f"{target:.4f}"},
            {"category": "Portfolio", "metric": "Delta to Hedge", "value": f"{delta_to_hedge:.4f}"},
            {"category": "Hedge", "metric": "Residual Delta", "value": f"{residual_delta:.4f}"},
            {"category": "Hedge", "metric": "Hedge Ratio", "value": f"{hedge_ratio:.2%}"},
            {"category": "Hedge", "metric": "Transaction Cost", "value": f"${total_tx_cost:,.2f}"},
            {"category": "Rebalance", "metric": "Threshold", "value": f"{rebalance_threshold}"},
            {"category": "Rebalance", "metric": "Current Buffer", "value": f"{rebalance_info.get('current_buffer', 0):.4f}"},
            {"category": "Rebalance", "metric": "Requires Action", "value": "Yes" if rebalance_info.get('requires_rebalance') else "No"},
        ]
        
        # Add hedge strategies to stats
        for i, strategy in enumerate(hedge_strategies[:5]):
            if strategy.get('strategy_type') == 'single_instrument':
                stats_table.append({
                    "category": "Strategy",
                    "metric": f"{strategy['ticker']}",
                    "value": f"{strategy['quantity']:.2f} shares @ ${strategy['current_price']:.2f} (β={strategy['beta']:.2f})"
                })
        
        # Build charts
        charts = {}
        
        hedge_chart = build_hedge_comparison_chart(current_delta, residual_delta, target, hedge_strategies)
        if hedge_chart:
            charts["hedge_comparison"] = hedge_chart
        
        breakdown = result.get('portfolio_delta_breakdown', [])
        if breakdown:
            breakdown_chart = build_delta_breakdown_chart(breakdown)
            if breakdown_chart:
                charts["delta_breakdown"] = breakdown_chart
        
        if hedge_strategies:
            instruments_chart = build_hedge_instruments_chart(hedge_strategies)
            if instruments_chart:
                charts["hedge_instruments"] = instruments_chart
        
        return {
            "status": "success",
            "tool_id": "delta_hedge",
            "tickers": position_tickers,
            "metrics": {
                "current_delta": current_delta,
                "residual_delta": residual_delta,
                "target_delta": target,
                "hedge_ratio": hedge_ratio,
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": f"Delta hedge constructed: {current_delta:.2f} → {residual_delta:.4f} using {', '.join(hedge_tickers)}. "
                      f"{'Rebalancing required.' if rebalance_info.get('requires_rebalance') else 'Within threshold.'}",
        }
        
    except Exception as e:
        logger.error(f"Delta hedge execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
