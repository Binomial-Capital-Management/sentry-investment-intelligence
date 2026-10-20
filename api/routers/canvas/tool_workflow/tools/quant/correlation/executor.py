"""Correlation Matrix Executor for Canvas.

Wraps the correlation matrix analysis tool for Canvas execution.
Graph building is done generically by the Canvas router - NOT here.
"""

from typing import Dict, Any, Optional, List
import logging

from .charts import build_correlation_heatmap, build_eigenvalue_chart, build_cluster_chart

logger = logging.getLogger(__name__)


async def execute_correlation_matrix(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute correlation matrix analysis.
    
    Args:
        user_id: Authenticated user ID
        org_id: Organization ID for RLS
        params: Tool parameters including tickers, method, lookback_period, etc.
        
    Returns:
        Standardized result dict with metrics, charts, and stats_table
    """
    from core.agents.quant_tools.correlation_matrix_tool import analyze_correlation_matrix_internal
    
    try:
        # Get tickers from params
        tickers = params.get('tickers', [])
        
        # Also support portfolio_id resolution
        if params.get('portfolio_id') and not tickers:
            tickers = await _resolve_portfolio_tickers(user_id, org_id, params['portfolio_id'])
        
        if not tickers or len(tickers) < 2:
            return {"status": "error", "error": "Need at least 2 tickers for correlation analysis"}
        
        logger.info(f"Canvas correlation matrix: {len(tickers)} tickers for user {user_id}")
        
        # Call the internal function
        result = await analyze_correlation_matrix_internal(
            tickers=tickers,
            method=params.get('method', 'pearson'),
            window=params.get('window'),
            lookback_period=params.get('lookback_period', 252),
            hierarchical_clustering=params.get('hierarchical_clustering', True),
            copula_analysis=params.get('copula_analysis', False),
            tail_dependence=params.get('tail_dependence', False),
            cluster_count=params.get('cluster_count'),
            tail_threshold=params.get('tail_threshold', 0.95),
        )
        
        if result.get('error'):
            return {"status": "error", "error": result.get('error'), "details": result.get('details')}
        
        # Use valid tickers from result (some may have been skipped)
        valid_tickers = result.get('tickers', tickers)
        skipped_tickers = result.get('skipped_tickers', [])
        
        if skipped_tickers:
            logger.info(f"Skipped {len(skipped_tickers)} tickers with invalid data: {skipped_tickers}")
        
        # Build Canvas-specific charts from raw data
        # Convert correlation_matrix dict to 2D array format for chart builder
        corr_matrix_dict = result.get('correlation_matrix', {})
        if corr_matrix_dict and valid_tickers:
            corr_matrix_array = [
                [corr_matrix_dict.get(t1, {}).get(t2, 0.0) for t2 in valid_tickers]
                for t1 in valid_tickers
            ]
        else:
            corr_matrix_array = []
        
        eigenvalues = result.get('eigenvalues', [])
        clustering = result.get('hierarchical_clustering')
        
        heatmap_chart = build_correlation_heatmap(valid_tickers, corr_matrix_array, result.get('method', 'pearson'))
        eigenvalue_chart = build_eigenvalue_chart(eigenvalues, valid_tickers)
        cluster_chart = build_cluster_chart(valid_tickers, clustering) if clustering else None
        
        # Build metric cards
        metric_cards = _build_metric_cards(result)
        
        # Add skipped tickers warning card if any
        if skipped_tickers:
            metric_cards.append({
                "id": "skipped",
                "label": "Skipped Tickers",
                "value": ", ".join(skipped_tickers),
                "sentiment": "negative",
            })
        
        # Build stats table
        stats_table = _build_stats_table(result)
        
        # Build metrics dict
        metrics = _extract_metrics(result)
        metrics["skipped_tickers"] = skipped_tickers
        
        # Build charts dict
        charts = {"correlation_heatmap": heatmap_chart, "eigenvalues": eigenvalue_chart}
        if cluster_chart:
            charts["clusters"] = cluster_chart
        
        final_result = {
            "status": "success",
            "tool_id": "correlation_matrix",
            "tickers": valid_tickers,
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
        return final_result
        
    except Exception as e:
        logger.error(f"Correlation matrix failed: {e}", exc_info=True)
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
    return {
        "avg_correlation": result.get('avg_correlation'),
        "condition_number": result.get('condition_number'),
        "determinant": result.get('determinant'),
        "sample_size": result.get('sample_size'),
        "method": result.get('method'),
        "top_eigenvalue": result.get('eigenvalues', [None])[0],
    }


def _build_metric_cards(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build displayable metric cards with styling metadata."""
    cards = []
    
    # Average Correlation
    avg_corr = result.get('avg_correlation')
    if avg_corr is not None:
        sentiment = "positive" if avg_corr > 0.5 else "negative" if avg_corr < 0 else "neutral"
        cards.append({
            "id": "avg_correlation",
            "label": "Avg Correlation",
            "value": f"{avg_corr:.3f}",
            "sentiment": sentiment,
        })
    
    # Condition Number (matrix stability)
    cond = result.get('condition_number')
    if cond is not None:
        sentiment = "negative" if cond > 30 else "positive" if cond < 10 else "neutral"
        cards.append({
            "id": "condition_number",
            "label": "Condition Number",
            "value": f"{cond:.1f}",
            "sentiment": sentiment,
        })
    
    # Sample Size
    sample = result.get('sample_size')
    if sample is not None:
        cards.append({
            "id": "sample_size",
            "label": "Sample Size",
            "value": f"{sample:,} days",
            "sentiment": "neutral",
        })
    
    # Top Eigenvalue (dominant factor)
    eigenvalues = result.get('eigenvalues', [])
    if eigenvalues:
        total = sum(eigenvalues)
        top_pct = (eigenvalues[0] / total * 100) if total > 0 else 0
        cards.append({
            "id": "dominant_factor",
            "label": "Dominant Factor",
            "value": f"{top_pct:.1f}%",
            "sentiment": "neutral",
        })
    
    # Cluster Count (if available)
    clustering = result.get('hierarchical_clustering', {})
    if clustering and clustering.get('cluster_count'):
        cards.append({
            "id": "clusters",
            "label": "Asset Clusters",
            "value": str(clustering['cluster_count']),
            "sentiment": "neutral",
        })
    
    return cards


def _build_stats_table(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build comprehensive stats table for display."""
    rows = []
    
    # Analysis info
    rows.append({"category": "Analysis", "metric": "Method", "value": result.get('method', 'pearson').capitalize()})
    rows.append({"category": "Analysis", "metric": "Lookback Period", "value": f"{result.get('lookback_days', 252)} days"})
    rows.append({"category": "Analysis", "metric": "Sample Size", "value": f"{result.get('sample_size', 0):,} observations"})
    rows.append({"category": "Analysis", "metric": "Date Range", "value": f"{result.get('start_date', '')} to {result.get('end_date', '')}"})
    
    # Matrix diagnostics
    rows.append({"category": "Matrix", "metric": "Avg Correlation", "value": f"{result.get('avg_correlation', 0):.4f}"})
    rows.append({"category": "Matrix", "metric": "Condition Number", "value": f"{result.get('condition_number', 0):.2f}"})
    rows.append({"category": "Matrix", "metric": "Determinant", "value": f"{result.get('determinant', 0):.6f}"})
    
    # Eigenvalue analysis
    eigenvalues = result.get('eigenvalues', [])
    if eigenvalues:
        total = sum(eigenvalues)
        for i, ev in enumerate(eigenvalues[:5]):  # Top 5 components
            pct = (ev / total * 100) if total > 0 else 0
            rows.append({"category": "Eigenvalues", "metric": f"PC{i+1}", "value": f"{pct:.1f}% variance"})
    
    # Clustering (if available)
    clustering = result.get('hierarchical_clustering', {})
    if clustering:
        rows.append({"category": "Clustering", "metric": "Cluster Count", "value": str(clustering.get('cluster_count', 0))})
        rows.append({"category": "Clustering", "metric": "Linkage Method", "value": clustering.get('linkage_method', 'ward')})
    
    return rows

