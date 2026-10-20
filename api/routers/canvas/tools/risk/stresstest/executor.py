"""
Correlation Stress Test Canvas Executor

Tests portfolio risk under correlation shock scenarios.
"""
from typing import Dict, List, Any, Optional
import logging
import numpy as np
import pandas as pd

from .charts import build_risk_escalation_chart, build_distribution_chart, build_correlation_heatmap

logger = logging.getLogger(__name__)


async def execute_stress_test(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute correlation stress test for Canvas.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
    from core.utils.mcp_result_parser import safe_parse_json
    
    tickers = params.get('tickers')
    weights = params.get('weights')
    
    # Resolve portfolio if provided
    if params.get('portfolio_id'):
        tickers, weights = await _resolve_portfolio(user_id, org_id, params['portfolio_id'])
    
    if not tickers or len(tickers) < 2:
        return {"status": "error", "error": "Need at least 2 tickers for stress test"}
    
    n_assets = len(tickers)
    
    # Default to equal weights if not provided
    if not weights:
        weights = [1.0 / n_assets] * n_assets
    weights = np.array(weights)
    weights = weights / weights.sum()  # Normalize
    
    try:
        # Fetch market data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        period = params.get('period', '1y')
        price_data = {}
        valid_tickers = []
        
        for ticker in tickers:
            try:
                result = await market_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })
                if result and hasattr(result, 'content'):
                    data = safe_parse_json(result)
                    if data and "dates" in data:
                        dates = data.get("dates", [])
                        prices = data.get("prices", []) or data.get("closes", [])
                        if dates and prices and len(dates) >= 50:
                            price_data[ticker] = pd.Series(prices, index=pd.to_datetime(dates))
                            valid_tickers.append(ticker)
            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
        
        await market_server.cleanup()
        
        if len(valid_tickers) < 2:
            return {"status": "error", "error": f"Insufficient data. Only got: {valid_tickers}"}
        
        # Adjust weights if some tickers failed
        if len(valid_tickers) != n_assets:
            ticker_to_weight = dict(zip(tickers, weights))
            weights = np.array([ticker_to_weight.get(t, 0) for t in valid_tickers])
            weights = weights / weights.sum()
        
        # Build returns DataFrame
        prices_df = pd.DataFrame(price_data).sort_index().dropna()
        returns = np.log(prices_df / prices_df.shift(1)).dropna()
        
        # Calculate baseline statistics
        baseline_corr = returns.corr().values
        baseline_cov = returns.cov().values
        mean_returns = returns.mean().values
        individual_vols = returns.std().values
        
        # Average correlation (off-diagonal)
        n = len(valid_tickers)
        mask = ~np.eye(n, dtype=bool)
        baseline_avg_corr = baseline_corr[mask].mean()
        
        # Simulation parameters
        n_simulations = params.get('n_simulations', 1000)
        time_horizon = params.get('time_horizon', 63)  # ~3 months
        portfolio_value = params.get('portfolio_value', 1_000_000)
        confidence_level = params.get('confidence_level', 0.95)
        correlation_scenarios = params.get('correlation_scenarios', [0.50, 0.75, 0.90, 0.95])
        
        # Ensure correlation_scenarios are floats
        if correlation_scenarios:
            correlation_scenarios = [float(c) for c in correlation_scenarios]
        
        # Baseline simulation
        baseline_paths = _simulate_paths(
            mean_returns, baseline_cov, weights,
            n_simulations, time_horizon, portfolio_value
        )
        baseline_metrics = _calculate_risk_metrics(baseline_paths, confidence_level, portfolio_value)
        baseline_div_benefit = _calculate_diversification_benefit(
            baseline_metrics['volatility'], individual_vols, weights
        )
        
        # Stressed scenarios
        stressed_results = {}
        stressed_paths_all = []
        stressed_corr_all = []
        
        for target_corr in correlation_scenarios:
            # Shock correlation matrix
            shocked_corr = _shock_correlation_matrix(baseline_corr, target_corr)
            shocked_cov = shocked_corr * np.outer(individual_vols, individual_vols)
            
            # Stressed mean returns (crash scenario)
            crash_return = -0.10 - (target_corr - 0.5) * 0.6  # -10% to -40%
            stressed_means = np.full_like(mean_returns, crash_return / 252)
            
            # Simulate
            stressed_paths = _simulate_paths(
                stressed_means, shocked_cov, weights,
                n_simulations, time_horizon, portfolio_value
            )
            stressed_metrics = _calculate_risk_metrics(stressed_paths, confidence_level, portfolio_value)
            stressed_div = _calculate_diversification_benefit(
                stressed_metrics['volatility'], individual_vols, weights
            )
            
            # Calculate changes
            var_increase = ((stressed_metrics['var'] - baseline_metrics['var']) / 
                           baseline_metrics['var'] * 100) if baseline_metrics['var'] > 0 else 0
            
            stressed_results[target_corr] = {
                'var_95': float(stressed_metrics['var']),
                'var_95_pct': float((stressed_metrics['var'] / portfolio_value) * 100),
                'cvar_95': float(stressed_metrics['cvar']),
                'cvar_95_pct': float((stressed_metrics['cvar'] / portfolio_value) * 100),
                'expected_value': float(stressed_metrics['expected_value']),
                'volatility': float(stressed_metrics['volatility']),
                'diversification_benefit': float(stressed_div),
                'var_increase_pct': float(var_increase),
                'var_increase_dollars': float(stressed_metrics['var'] - baseline_metrics['var']),
                'diversification_loss': float(baseline_div_benefit - stressed_div),
            }
            
            stressed_paths_all.append(stressed_paths)
            stressed_corr_all.append(shocked_corr)
        
        # Build charts
        charts = {}
        
        # Risk escalation chart
        escalation_chart = build_risk_escalation_chart(
            baseline_metrics, stressed_results, correlation_scenarios, portfolio_value
        )
        if escalation_chart:
            charts["risk_escalation"] = escalation_chart
        
        # Distribution comparison (baseline vs worst case)
        worst_corr = max(correlation_scenarios)
        worst_idx = correlation_scenarios.index(worst_corr)
        dist_chart = build_distribution_chart(
            baseline_paths, stressed_paths_all[worst_idx], portfolio_value
        )
        if dist_chart:
            charts["distribution_comparison"] = dist_chart
        
        # Correlation heatmap
        heatmap_chart = build_correlation_heatmap(
            baseline_corr, stressed_corr_all[worst_idx], valid_tickers
        )
        if heatmap_chart:
            charts["correlation_heatmap"] = heatmap_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(baseline_metrics, stressed_results, portfolio_value, confidence_level)
        
        # Build stats table
        stats_table = _build_stats_table(
            baseline_metrics, baseline_avg_corr, baseline_div_benefit,
            stressed_results, correlation_scenarios, portfolio_value, confidence_level
        )
        
        # Build metrics dict
        metrics = {
            "baseline_var_95": baseline_metrics['var'],
            "baseline_cvar_95": baseline_metrics['cvar'],
            "baseline_avg_correlation": float(baseline_avg_corr),
            "baseline_diversification_benefit": float(baseline_div_benefit),
            "stressed_scenarios": stressed_results,
            "n_simulations": n_simulations,
            "time_horizon_days": time_horizon,
        }
        
        return {
            "status": "success",
            "tool_id": "stress_test",
            "tickers": valid_tickers,
            "weights": weights.tolist(),
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Stress test execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio(user_id: str, org_id: Optional[str], portfolio_id: str):
    """Resolve portfolio to tickers and weights."""
    from core.services.portfolio_service import PortfolioService
    
    service = PortfolioService()
    # Note: get_portfolio takes (user_id, portfolio_id_or_name) - org_id is not used
    portfolio = await service.get_portfolio(user_id, portfolio_id)
    
    if not portfolio or portfolio.get("status") == "error":
        return None, None
    
    # Unwrap API response: {"status": "success", "portfolio": {...}, "message": "..."}
    # Portfolio contains: tickers (list), weights (list), value, etc.
    actual_portfolio = portfolio.get("portfolio", {})
    
    # Get tickers and weights directly (not from positions!)
    tickers = actual_portfolio.get("tickers", [])
    weights = actual_portfolio.get("weights", [])
    
    if not tickers:
        return None, None
    
    # If weights missing, distribute equally
    if not weights or len(weights) != len(tickers):
        weights = [1.0 / len(tickers)] * len(tickers)
    
    # Normalize weights
    total = sum(weights)
    if total > 0:
        weights = [w / total for w in weights]
    
    return tickers, weights


def _shock_correlation_matrix(corr_matrix: np.ndarray, target_corr: float) -> np.ndarray:
    """Shock correlation matrix to target level."""
    n = corr_matrix.shape[0]
    shocked = np.full((n, n), target_corr)
    np.fill_diagonal(shocked, 1.0)
    
    # Ensure positive semi-definite
    eigenvalues, eigenvectors = np.linalg.eigh(shocked)
    eigenvalues = np.maximum(eigenvalues, 1e-8)
    shocked = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    
    # Re-normalize
    d = np.sqrt(np.diag(shocked))
    shocked = shocked / np.outer(d, d)
    np.fill_diagonal(shocked, 1.0)
    
    return shocked


def _simulate_paths(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    weights: np.ndarray,
    n_simulations: int,
    time_horizon: int,
    initial_value: float
) -> np.ndarray:
    """Generate portfolio value paths using multivariate simulation."""
    try:
        L = np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        L = eigenvectors @ np.diag(np.sqrt(eigenvalues))
    
    n_assets = len(mean_returns)
    Z = np.random.standard_normal((n_simulations, time_horizon, n_assets))
    
    correlated_returns = mean_returns[np.newaxis, np.newaxis, :] + np.einsum('ij,klj->kli', L, Z)
    portfolio_returns = np.einsum('ijk,k->ij', correlated_returns, weights)
    
    cumulative_returns = np.cumprod(1 + portfolio_returns, axis=1)
    portfolio_values = cumulative_returns * initial_value
    
    initial_values = np.full((n_simulations, 1), initial_value)
    return np.concatenate([initial_values, portfolio_values], axis=1)


def _calculate_risk_metrics(
    portfolio_paths: np.ndarray,
    confidence_level: float,
    initial_value: float
) -> Dict[str, float]:
    """Calculate VaR, CVaR, and other risk metrics."""
    terminal_values = portfolio_paths[:, -1]
    losses = initial_value - terminal_values
    
    var_percentile = (1 - confidence_level) * 100
    var = np.percentile(losses, 100 - var_percentile)
    
    var_threshold = np.percentile(terminal_values, var_percentile)
    tail_losses = losses[terminal_values <= var_threshold]
    cvar = tail_losses.mean() if len(tail_losses) > 0 else var
    
    returns = (terminal_values - initial_value) / initial_value
    
    return {
        'var': float(var),
        'cvar': float(cvar),
        'expected_value': float(terminal_values.mean()),
        'volatility': float(returns.std()),
        'percentile_5': float(np.percentile(terminal_values, 5)),
        'percentile_50': float(np.percentile(terminal_values, 50)),
        'percentile_95': float(np.percentile(terminal_values, 95))
    }


def _calculate_diversification_benefit(
    portfolio_vol: float,
    individual_vols: np.ndarray,
    weights: np.ndarray
) -> float:
    """Calculate diversification benefit."""
    weighted_avg_vol = np.sum(individual_vols * weights)
    if weighted_avg_vol > 0:
        return max(0.0, 1.0 - (portfolio_vol / weighted_avg_vol))
    return 0.0


def _build_metric_cards(
    baseline_metrics: Dict[str, float],
    stressed_results: Dict[float, Dict[str, float]],
    portfolio_value: float,
    confidence_level: float
) -> List[Dict[str, Any]]:
    """Build metric cards from stress test results."""
    cards = []
    conf_pct = int(confidence_level * 100)
    
    # Baseline VaR
    baseline_var = baseline_metrics['var']
    baseline_var_pct = (baseline_var / portfolio_value) * 100
    cards.append({
        "id": "baseline_var",
        "label": f"Baseline {conf_pct}% VaR",
        "value": f"${baseline_var:,.0f} ({baseline_var_pct:.1f}%)",
        "sentiment": "neutral",
    })
    
    # Worst case VaR
    worst_corr = max(stressed_results.keys())
    worst_result = stressed_results[worst_corr]
    cards.append({
        "id": "worst_var",
        "label": f"Crash {conf_pct}% VaR",
        "value": f"${worst_result['var_95']:,.0f} ({worst_result['var_95_pct']:.1f}%)",
        "sentiment": "negative",
    })
    
    # VaR increase
    cards.append({
        "id": "var_increase",
        "label": "VaR Increase (Crash)",
        "value": f"+{worst_result['var_increase_pct']:.0f}%",
        "sentiment": "negative",
    })
    
    # Diversification loss
    cards.append({
        "id": "div_loss",
        "label": "Diversification Lost",
        "value": f"{worst_result['diversification_loss']:.1%}",
        "sentiment": "negative" if worst_result['diversification_loss'] > 0.1 else "neutral",
    })
    
    return cards


def _build_stats_table(
    baseline_metrics: Dict[str, float],
    baseline_avg_corr: float,
    baseline_div_benefit: float,
    stressed_results: Dict[float, Dict[str, float]],
    correlation_scenarios: List[float],
    portfolio_value: float,
    confidence_level: float
) -> List[Dict[str, str]]:
    """Build stats table from stress test results."""
    rows = []
    conf_pct = int(confidence_level * 100)
    
    # Baseline summary
    baseline_var_pct = (baseline_metrics['var'] / portfolio_value) * 100
    baseline_cvar_pct = (baseline_metrics['cvar'] / portfolio_value) * 100
    
    rows.append({"category": "Baseline", "metric": "Average Correlation", "value": f"{baseline_avg_corr:.3f}"})
    rows.append({"category": "Baseline", "metric": f"{conf_pct}% VaR", "value": f"${baseline_metrics['var']:,.0f} ({baseline_var_pct:.1f}%)"})
    rows.append({"category": "Baseline", "metric": f"{conf_pct}% CVaR", "value": f"${baseline_metrics['cvar']:,.0f} ({baseline_cvar_pct:.1f}%)"})
    rows.append({"category": "Baseline", "metric": "Diversification Benefit", "value": f"{baseline_div_benefit:.1%}"})
    rows.append({"category": "Baseline", "metric": "Expected Terminal Value", "value": f"${baseline_metrics['expected_value']:,.0f}"})
    
    # Stressed scenarios
    rows.append({"category": "Scenarios", "metric": "─" * 20, "value": "─" * 15})
    
    for target_corr in sorted(correlation_scenarios):
        s = stressed_results[target_corr]
        crash_label = f"ρ → {target_corr:.0%}"
        
        rows.append({
            "category": crash_label,
            "metric": f"{conf_pct}% VaR",
            "value": f"${s['var_95']:,.0f} ({s['var_95_pct']:.1f}%)",
            "pct": f"+{s['var_increase_pct']:.0f}% vs baseline",
        })
        rows.append({
            "category": crash_label,
            "metric": f"{conf_pct}% CVaR",
            "value": f"${s['cvar_95']:,.0f} ({s['cvar_95_pct']:.1f}%)",
        })
        rows.append({
            "category": crash_label,
            "metric": "Diversification Benefit",
            "value": f"{s['diversification_benefit']:.1%}",
            "pct": f"−{s['diversification_loss']:.1%} lost",
        })
    
    # Risk interpretation
    worst = stressed_results[max(correlation_scenarios)]
    if worst['var_increase_pct'] > 100:
        risk_level = "Very High"
    elif worst['var_increase_pct'] > 50:
        risk_level = "High"
    else:
        risk_level = "Moderate"
    
    rows.append({"category": "Summary", "metric": "Crash Sensitivity", "value": risk_level})
    
    return rows

