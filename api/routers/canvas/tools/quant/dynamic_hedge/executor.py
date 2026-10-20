"""
Dynamic Hedge Canvas Executor

Multi-Greek monitoring and rebalancing optimization with historical backtesting.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def execute_dynamic_hedge(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Dynamic Hedge for Canvas."""
    from .charts import (
        build_greeks_evolution_chart,
        build_drift_score_chart,
        build_pnl_comparison_chart,
        build_scenario_heatmap
    )
    from core.agents.quant_tools.dynamic_hedge_tool import construct_dynamic_hedge_internal
    from core.services.portfolio_service import PortfolioService
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.utils.mcp_result_parser import safe_parse_json
    
    # Extract parameters
    input_type = params.get('input_type', 'portfolio')
    portfolio_id = params.get('portfolio_id')
    tickers = params.get('tickers', [])  # Additional tickers for manual positions
    
    hedge_tickers_str = params.get('hedge_tickers', 'SPY')
    hedge_tickers = [t.strip().upper() for t in hedge_tickers_str.split(',') if t.strip()]
    
    target_delta = params.get('target_delta', 0.0)
    target_vega = params.get('target_vega')  # None = neutral
    
    threshold = params.get('threshold', 0.1)
    frequency = params.get('frequency', 'daily')
    lookback = params.get('lookback', '30D')
    
    # Options settings for auto-generation
    moneyness = params.get('moneyness', 'atm')
    days_to_expiry = params.get('days_to_expiry', 30)
    option_type = params.get('option_type', 'call')
    
    try:
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
            
            # Generate synthetic option positions from holdings
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
                
                # Create position (weight-proportional contracts)
                contracts = max(1, int(weight * 10))  # Scale weight to contracts
                
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
        
        if not positions:
            return {"status": "error", "error": "No positions to analyze. Select a portfolio or enter tickers."}
        
        if not hedge_tickers:
            return {"status": "error", "error": "No hedge tickers specified. Enter tickers like 'SPY' or 'SPY,QQQ'."}
        
        logger.info(f"Dynamic Hedge: {len(positions)} positions, hedge with {hedge_tickers}, lookback={lookback}")
        
        # Build rebalance params
        rebalance_params = {
            'threshold': threshold,
            'frequency_check': frequency,
            'cost_threshold': 0.02,
            'min_trade_size': 1.0
        }
        
        # Call internal function
        result = await construct_dynamic_hedge_internal(
            portfolio_positions=positions,
            hedge_tickers=hedge_tickers,
            underlying_prices=None,
            hedge_target=target_delta,
            vega_target=target_vega if target_vega and target_vega != 0 else None,
            rebalance_params=rebalance_params,
            lookback_period=lookback
        )
        
        if result.get('status') == 'error':
            return result
        
        # Extract results
        results = result.get('results', {})
        portfolio_greeks = results.get('current_portfolio_greeks', {})
        residual_greeks = results.get('current_residual_greeks', {})
        initial_hedge = results.get('initial_hedge', {})
        rebalancing_rules = results.get('rebalancing_rules', {})
        drift_analysis = results.get('drift_analysis', {})
        scenarios = results.get('scenarios', [])
        backtest = results.get('backtest_results', {})
        summary = results.get('summary', {})
        
        # Build metric cards
        metric_cards = [
            {
                "label": "Portfolio Delta",
                "value": f"{portfolio_greeks.get('delta', 0):.2f}",
                "description": "Net delta exposure"
            },
            {
                "label": "Residual Delta",
                "value": f"{residual_greeks.get('delta', 0):.2f}",
                "description": "After hedge"
            },
            {
                "label": "Drift Score",
                "value": f"{drift_analysis.get('drift_score', 0):.4f}",
                "description": "Multi-Greek drift"
            },
            {
                "label": "Rebalance",
                "value": "YES" if drift_analysis.get('rebalance_recommended') else "NO",
                "description": "Recommended action"
            }
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Greeks", "metric": "Portfolio Delta", "value": f"{portfolio_greeks.get('delta', 0):.2f}", "percent": ""},
            {"category": "Greeks", "metric": "Portfolio Gamma", "value": f"{portfolio_greeks.get('gamma', 0):.4f}", "percent": ""},
            {"category": "Greeks", "metric": "Portfolio Vega", "value": f"{portfolio_greeks.get('vega', 0):.2f}", "percent": ""},
            {"category": "Greeks", "metric": "Portfolio Theta", "value": f"{portfolio_greeks.get('theta', 0):.2f}", "percent": ""},
            {"category": "Residual", "metric": "Residual Delta", "value": f"{residual_greeks.get('delta', 0):.2f}", "percent": ""},
            {"category": "Residual", "metric": "Residual Gamma", "value": f"{residual_greeks.get('gamma', 0):.4f}", "percent": ""},
            {"category": "Residual", "metric": "Residual Vega", "value": f"{residual_greeks.get('vega', 0):.2f}", "percent": ""},
            {"category": "Residual", "metric": "Residual Theta", "value": f"{residual_greeks.get('theta', 0):.2f}", "percent": ""},
            {"category": "Drift", "metric": "Drift Score", "value": f"{drift_analysis.get('drift_score', 0):.4f}", "percent": ""},
            {"category": "Drift", "metric": "Delta Drift", "value": f"{drift_analysis.get('component_drifts', {}).get('delta_drift', 0):.2f}", "percent": ""},
            {"category": "Drift", "metric": "Vega Drift", "value": f"{drift_analysis.get('component_drifts', {}).get('vega_drift', 0):.2f}", "percent": ""},
            {"category": "Drift", "metric": "Rebalance Recommended", "value": "Yes" if drift_analysis.get('rebalance_recommended') else "No", "percent": ""},
            {"category": "Hedge", "metric": "Optimal Frequency", "value": rebalancing_rules.get('optimal_rebalance_frequency', 'daily').title(), "percent": ""},
            {"category": "Hedge", "metric": "Total Notional", "value": f"${initial_hedge.get('total_notional', 0):,.0f}", "percent": ""},
            {"category": "Hedge", "metric": "Transaction Cost", "value": f"${initial_hedge.get('total_transaction_cost', 0):,.2f}", "percent": ""},
        ]
        
        # Add hedge quantities
        hedge_quantities = initial_hedge.get('hedge_quantities', {})
        for ticker, qty in hedge_quantities.items():
            stats_table.append({
                "category": "Positions",
                "metric": f"{ticker} Quantity",
                "value": f"{qty:,.2f} shares",
                "percent": ""
            })
        
        # Add backtest stats if available
        if backtest and not backtest.get('error'):
            stats_table.extend([
                {"category": "Backtest", "metric": "Period", "value": lookback, "percent": ""},
                {"category": "Backtest", "metric": "Total Trades", "value": str(backtest.get('total_trades', 0)), "percent": ""},
                {"category": "Backtest", "metric": "Hedged P&L", "value": f"${backtest.get('hedged_pnl', 0):,.2f}", "percent": ""},
                {"category": "Backtest", "metric": "Unhedged P&L", "value": f"${backtest.get('unhedged_pnl', 0):,.2f}", "percent": ""},
                {"category": "Backtest", "metric": "P&L Improvement", "value": f"${backtest.get('pnl_improvement', 0):,.2f}", "percent": f"{backtest.get('pnl_improvement_pct', 0):.1f}%"},
                {"category": "Backtest", "metric": "Transaction Costs", "value": f"${backtest.get('total_transaction_costs', 0):,.2f}", "percent": ""},
                {"category": "Backtest", "metric": "Theta Income", "value": f"${backtest.get('total_theta_income', 0):,.2f}", "percent": ""},
            ])
        
        # Build charts
        charts = {}
        
        # Greeks evolution chart (from backtest if available)
        if backtest and backtest.get('daily_results'):
            greeks_chart = build_greeks_evolution_chart(backtest['daily_results'])
            if greeks_chart:
                charts['greeks'] = greeks_chart
            
            drift_chart = build_drift_score_chart(backtest['daily_results'], threshold)
            if drift_chart:
                charts['drift'] = drift_chart
            
            pnl_chart = build_pnl_comparison_chart(backtest['daily_results'])
            if pnl_chart:
                charts['pnl'] = pnl_chart
        
        # Scenario heatmap
        if scenarios:
            scenario_chart = build_scenario_heatmap(scenarios)
            if scenario_chart:
                charts['scenarios'] = scenario_chart
        
        # Generate summary
        rebalance_str = "**REBALANCE RECOMMENDED**" if drift_analysis.get('rebalance_recommended') else "No rebalancing needed"
        
        summary_text = (
            f"**Dynamic Hedge Analysis**\n\n"
            f"Positions: {len(positions)} options | Hedge: {', '.join(hedge_tickers)}\n\n"
            f"**Portfolio Greeks:** Δ={portfolio_greeks.get('delta', 0):.2f}, Γ={portfolio_greeks.get('gamma', 0):.4f}, "
            f"V={portfolio_greeks.get('vega', 0):.2f}, Θ={portfolio_greeks.get('theta', 0):.2f}\n\n"
            f"**Residual (after hedge):** Δ={residual_greeks.get('delta', 0):.2f}\n\n"
            f"**Drift Score:** {drift_analysis.get('drift_score', 0):.4f} → {rebalance_str}\n\n"
            f"**Optimal Frequency:** {rebalancing_rules.get('optimal_rebalance_frequency', 'daily').title()}"
        )
        
        if backtest and not backtest.get('error'):
            summary_text += (
                f"\n\n**Backtest ({lookback}):** "
                f"Hedged P&L ${backtest.get('hedged_pnl', 0):,.0f} vs "
                f"Unhedged ${backtest.get('unhedged_pnl', 0):,.0f} "
                f"(+${backtest.get('pnl_improvement', 0):,.0f})"
            )
        
        return {
            "status": "success",
            "tool_id": "dynamic_hedge",
            "tickers": position_tickers + hedge_tickers,
            "weights": [],
            "metrics": {
                "portfolio_delta": portfolio_greeks.get('delta', 0),
                "residual_delta": residual_greeks.get('delta', 0),
                "drift_score": drift_analysis.get('drift_score', 0),
                "rebalance_recommended": drift_analysis.get('rebalance_recommended', False),
            },
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
            "summary": summary_text,
        }
    
    except Exception as e:
        logger.error(f"Dynamic hedge failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}
