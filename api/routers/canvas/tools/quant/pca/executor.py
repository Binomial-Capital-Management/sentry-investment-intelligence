"""PCA Analysis Executor for Canvas.

Wraps the PCA analysis tool for Canvas execution.
"""

from typing import Dict, Any, Optional, List
import logging

from .charts import build_scree_chart, build_loadings_heatmap, build_eigen_portfolio_chart

logger = logging.getLogger(__name__)


async def execute_pca_analysis(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute PCA analysis.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including tickers, n_components, period, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.quant_tools.pca_analysis_tool import analyze_pca_internal
    
    try:
        # Get tickers from params
        tickers = params.get('tickers', [])
        
        # Also support portfolio_id resolution
        if params.get('portfolio_id') and not tickers:
            tickers = await _resolve_portfolio_tickers(user_id, org_id, params['portfolio_id'])
        
        if not tickers or len(tickers) < 3:
            return {"status": "error", "error": "PCA requires at least 3 tickers"}
        
        logger.info(f"Canvas PCA analysis: {len(tickers)} tickers for user {user_id}")
        
        # Call the internal function
        result = await analyze_pca_internal(
            tickers=tickers,
            n_components=params.get('n_components'),
            normalize=params.get('normalize', True),
            period=params.get('period', '1Y'),
            n_eigen_portfolios=params.get('n_eigen_portfolios', 4),
        )
        
        if result.get('status') == 'error':
            return {"status": "error", "error": result.get('error')}
        
        # Build Canvas-specific charts from raw data
        explained_variance = result.get('explained_variance', [])
        cumulative_variance = result.get('cumulative_variance', [])
        loadings_matrix = result.get('loadings_matrix', [])
        eigen_portfolios = result.get('eigen_portfolios', {})
        
        scree_chart = build_scree_chart(explained_variance, cumulative_variance)
        loadings_chart = build_loadings_heatmap(tickers, loadings_matrix)
        eigen_chart = build_eigen_portfolio_chart(tickers, eigen_portfolios)
        
        # Build metric cards
        metric_cards = _build_metric_cards(result)
        
        # Build stats table
        stats_table = _build_stats_table(result)
        
        # Build metrics dict
        metrics = _extract_metrics(result)
        
        # Build charts dict
        charts = {"scree_plot": scree_chart, "loadings": loadings_chart}
        if eigen_chart:
            charts["eigen_portfolio"] = eigen_chart
        
        return {
            "status": "success",
            "tool_id": "pca_analysis",
            "tickers": tickers,
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"PCA analysis failed: {e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "..."
        return {"status": "error", "error": error_msg}


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: str
) -> List[str]:
    """Resolve tickers from portfolio ID."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return []
        
        actual_portfolio = portfolio.get("portfolio", {})
        return actual_portfolio.get('tickers', [])
    except Exception as e:
        logger.warning(f"Could not fetch portfolio: {e}")
    return []


def _extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metrics into standardized format."""
    explained = result.get('explained_variance', [])
    cumulative = result.get('cumulative_variance', [])
    
    return {
        "n_components": result.get('n_components'),
        "n_samples": result.get('n_samples'),
        "pc1_variance": explained[0] if explained else None,
        "pc2_variance": explained[1] if len(explained) > 1 else None,
        "cumulative_2pc": cumulative[1] if len(cumulative) > 1 else None,
        "components_for_80pct": result.get('components_for_thresholds', {}).get('80pct'),
    }


def _build_metric_cards(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build displayable metric cards with styling metadata."""
    cards = []
    
    explained = result.get('explained_variance', [])
    cumulative = result.get('cumulative_variance', [])
    thresholds = result.get('components_for_thresholds', {})
    
    # PC1 Variance
    if explained:
        pc1_pct = explained[0] * 100
        cards.append({
            "id": "pc1_variance",
            "label": "PC1 Variance",
            "value": f"{pc1_pct:.1f}%",
            "sentiment": "positive" if pc1_pct > 30 else "neutral",
        })
    
    # Top 2 PCs Combined
    if len(cumulative) >= 2:
        top2_pct = cumulative[1] * 100
        cards.append({
            "id": "top2_variance",
            "label": "Top 2 PCs",
            "value": f"{top2_pct:.1f}%",
            "sentiment": "positive" if top2_pct > 50 else "neutral",
        })
    
    # Components for 80%
    if thresholds.get('80pct'):
        cards.append({
            "id": "components_80",
            "label": "PCs for 80%",
            "value": str(thresholds['80pct']),
            "sentiment": "neutral",
        })
    
    # Sample Size
    n_samples = result.get('n_samples')
    if n_samples:
        cards.append({
            "id": "sample_size",
            "label": "Sample Size",
            "value": f"{n_samples:,} days",
            "sentiment": "neutral",
        })
    
    return cards


def _build_stats_table(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build comprehensive stats table for display."""
    rows = []
    
    # Analysis info
    rows.append({"category": "Analysis", "metric": "Period", "value": result.get('period', '1Y')})
    rows.append({"category": "Analysis", "metric": "Sample Size", "value": f"{result.get('n_samples', 0):,} observations"})
    
    date_range = result.get('date_range', ['', ''])
    rows.append({"category": "Analysis", "metric": "Date Range", "value": f"{date_range[0]} to {date_range[1]}"})
    rows.append({"category": "Analysis", "metric": "Components", "value": str(result.get('n_components', 0))})
    
    # Variance explained
    explained = result.get('explained_variance', [])
    cumulative = result.get('cumulative_variance', [])
    
    for i, (ev, cv) in enumerate(zip(explained[:5], cumulative[:5])):
        rows.append({
            "category": "Variance", 
            "metric": f"PC{i+1}", 
            "value": f"{ev*100:.1f}%",
            "pct": f"Cum: {cv*100:.1f}%"
        })
    
    # Top contributors from PC1
    factor_contributions = result.get('factor_contributions', {})
    pc1_contributors = factor_contributions.get('PC1', [])
    for contrib in pc1_contributors[:3]:
        rows.append({
            "category": "PC1 Drivers",
            "metric": contrib.get('ticker', ''),
            "value": f"{contrib.get('loading', 0):.3f}",
        })
    
    return rows

