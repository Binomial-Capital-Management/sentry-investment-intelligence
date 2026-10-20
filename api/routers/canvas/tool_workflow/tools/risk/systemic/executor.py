"""
Systemic Risk Canvas Executor
"""
from typing import Dict, List, Any, Optional
import logging

from core.agents.quant_tools.systemic_risk_score_tool import analyze_systemic_risk_internal
from .charts import build_risk_contribution_chart, build_score_gauge, build_network_density_chart

logger = logging.getLogger(__name__)


async def execute_systemic_risk(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute systemic risk analysis for Canvas."""
    try:
        # Resolve tickers
        portfolio_id = params.get("portfolio_id")
        tickers = params.get("tickers", [])
        weights = params.get("weights")
        
        if portfolio_id:
            tickers, weights = await _resolve_portfolio_tickers(user_id, org_id, portfolio_id)
            if not tickers:
                return {"status": "error", "error": f"Portfolio {portfolio_id} not found or empty"}
        
        if not tickers or len(tickers) < 2:
            return {"status": "error", "error": "Need at least 2 tickers for systemic risk analysis"}
        
        # Call internal systemic risk function
        result = await analyze_systemic_risk_internal(
            tickers=tickers,
            weights=weights,
            lookback_days=params.get("lookback_days", 252),
            correlation_threshold=params.get("correlation_threshold", 0.3),
        )
        
        if result.get("error"):
            return {"status": "error", "error": result.get("error"), "details": result.get("details")}
        
        valid_tickers = result.get("tickers", tickers)
        skipped_positions = result.get("skipped_positions", [])
        risk_contributions = result.get("position_risk_contributions", [])
        portfolio_score = result.get("portfolio_systemic_risk_score", 0)
        
        # Build charts
        contribution_chart = build_risk_contribution_chart(risk_contributions, portfolio_score)
        gauge_chart = build_score_gauge(portfolio_score)
        network_chart = build_network_density_chart(
            valid_tickers,
            result.get("avg_correlation", 0),
            result.get("network_density", 0)
        )
        
        charts = {}
        if contribution_chart:
            charts["risk_contributions"] = contribution_chart
        if gauge_chart:
            charts["score_gauge"] = gauge_chart
        if network_chart:
            charts["network_metrics"] = network_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(result)
        
        if skipped_positions:
            skipped_names = [s.get('ticker', str(s)) for s in skipped_positions]
            metric_cards.append({
                "id": "skipped",
                "label": "Excluded",
                "value": ", ".join(skipped_names[:3]),
                "sentiment": "neutral",
            })
        
        # Build stats table
        stats_table = _build_stats_table(result, risk_contributions)
        
        # Build metrics dict
        metrics = _extract_metrics(result)
        
        return {
            "status": "success",
            "tool_id": "systemic_risk",
            "tickers": valid_tickers,
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Systemic risk execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: str
) -> tuple:
    """Fetch tickers and weights from portfolio."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return [], None
        
        actual_portfolio = portfolio.get("portfolio", {})
        tickers = actual_portfolio.get('tickers', [])
        weights = actual_portfolio.get('weights', [])
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers) if tickers else None
        return tickers, weights
    except Exception as e:
        logger.warning(f"Could not fetch portfolio: {e}")
    return [], None


def _build_metric_cards(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build metric cards from systemic risk results."""
    cards = []
    
    portfolio_score = result.get("portfolio_systemic_risk_score", 0)
    
    # Score interpretation
    if portfolio_score <= 3:
        score_label = "Low Risk"
        sentiment = "positive"
    elif portfolio_score <= 5:
        score_label = "Moderate"
        sentiment = "neutral"
    elif portfolio_score <= 7:
        score_label = "Elevated"
        sentiment = "negative"
    else:
        score_label = "High Risk"
        sentiment = "negative"
    
    cards.append({
        "id": "score",
        "label": "Systemic Risk Score",
        "value": f"{portfolio_score:.1f}/10",
        "sentiment": sentiment,
    })
    
    cards.append({
        "id": "interpretation",
        "label": "Risk Level",
        "value": score_label,
        "sentiment": sentiment,
    })
    
    cards.append({
        "id": "avg_corr",
        "label": "Avg Correlation",
        "value": f"{result.get('avg_correlation', 0):.1%}",
        "sentiment": "neutral",
    })
    
    cards.append({
        "id": "density",
        "label": "Network Density",
        "value": f"{result.get('network_density', 0):.1%}",
        "sentiment": "neutral",
    })
    
    # Warning card
    warning = result.get("concentration_warning")
    if warning:
        cards.append({
            "id": "warning",
            "label": "Warning",
            "value": warning,
            "sentiment": "negative",
        })
    
    return cards


def _build_stats_table(result: Dict[str, Any], risk_contributions: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Build stats table from systemic risk results."""
    rows = []
    
    # Portfolio-level systemic metrics
    portfolio_score = result.get("portfolio_systemic_risk_score", 0)
    rows.append({
        "category": "Portfolio Score",
        "metric": "Systemic Risk Score",
        "value": f"{portfolio_score:.1f}/100",
        "pct": "Higher = more systemic risk",
    })
    
    # Risk level interpretation
    if portfolio_score >= 70:
        risk_level = "High"
    elif portfolio_score >= 40:
        risk_level = "Moderate"
    else:
        risk_level = "Low"
    rows.append({"category": "Portfolio Score", "metric": "Risk Level", "value": risk_level})
    
    # Network metrics
    avg_corr = result.get("avg_correlation", 0)
    network_density = result.get("network_density", 0)
    rows.append({"category": "Network", "metric": "Average Correlation", "value": f"{avg_corr:.3f}"})
    rows.append({"category": "Network", "metric": "Network Density", "value": f"{network_density:.3f}"})
    
    # Clustering coefficient if available
    clustering_coef = result.get("clustering_coefficient")
    if clustering_coef is not None:
        rows.append({"category": "Network", "metric": "Clustering Coefficient", "value": f"{clustering_coef:.3f}"})
    
    # Concentration warning
    concentration_warning = result.get("concentration_warning")
    if concentration_warning:
        rows.append({"category": "Warnings", "metric": "Concentration", "value": concentration_warning})
    
    # Individual position risk contributions
    rows.append({"category": "Positions", "metric": "─" * 20, "value": "─" * 15})  # Divider
    
    for i, contrib in enumerate(risk_contributions[:10], 1):  # Top 10
        ticker = contrib.get("ticker", "Unknown")
        risk_pct = contrib.get("risk_contribution", 0)
        pagerank = contrib.get("pagerank", 0)
        betweenness = contrib.get("betweenness", 0)
        degree = contrib.get("degree_centrality", 0)
        
        rows.append({
            "category": f"#{i} Position",
            "metric": ticker,
            "value": f"{risk_pct:.1%} risk",
            "pct": f"PR:{pagerank:.3f} BW:{betweenness:.3f}" + (f" D:{degree:.3f}" if degree else ""),
        })
    
    # Recommendation
    recommendation = result.get("recommendation")
    if recommendation:
        rows.append({"category": "Recommendation", "metric": "Action", "value": recommendation[:80]})
    
    return rows


def _extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metrics for persistence."""
    return {
        "portfolio_systemic_risk_score": result.get("portfolio_systemic_risk_score"),
        "avg_correlation": result.get("avg_correlation"),
        "network_density": result.get("network_density"),
        "concentration_warning": result.get("concentration_warning"),
        "recommendation": result.get("recommendation"),
        "position_risk_contributions": result.get("position_risk_contributions", [])[:5],  # Top 5
    }

