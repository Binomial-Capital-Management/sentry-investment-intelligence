"""Canvas executor for Portfolio Geodesic Distance tool."""
import logging
from typing import Any, Dict, List, Optional

from core.services.portfolio_service import PortfolioService
from .charts import (
    build_distribution_chart, 
    build_breakdown_chart, 
    build_single_distribution_chart,
    build_geodesic_path_chart,
    build_curvature_chart,
    build_manifold_embedding_chart,
)

logger = logging.getLogger(__name__)


async def execute_geodesic(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute geodesic distance analysis for Canvas."""
    from core.agents.quant_tools.geodesic_distance.tool import analyze_portfolio_geodesic_distance_internal
    
    # Resolve portfolio
    portfolio_id = params.get("portfolio_id")
    compare_to = params.get("compare_to_portfolio_id")
    
    tickers_a = params.get("tickers", [])
    weights_a = params.get("weights")
    name_a = "Portfolio A"
    
    tickers_b = []
    weights_b = None
    name_b = "Portfolio B"
    
    # Resolve primary portfolio
    if portfolio_id:
        tickers_a, weights_a, name_a = await _resolve_portfolio(user_id, portfolio_id)
    
    # Resolve comparison portfolio
    if compare_to:
        tickers_b, weights_b, name_b = await _resolve_portfolio(user_id, compare_to)
    
    if not tickers_a:
        return {"status": "error", "error": "No tickers found - select a portfolio or enter tickers"}
    
    logger.info(f"Geodesic: {name_a} ({len(tickers_a)} tickers) vs {name_b} ({len(tickers_b)} tickers)")
    
    try:
        # Call internal tool WITHOUT charts (we build them ourselves for Canvas)
        # Enable constituent comparison for single portfolio with multiple tickers
        is_single_mode = not tickers_b or len(tickers_b) == 0
        compare_constituents = is_single_mode and len(tickers_a) > 1
        
        result = await analyze_portfolio_geodesic_distance_internal(
            tickers_a=tickers_a,
            weights_a=weights_a,
            name_a=name_a,
            tickers_b=tickers_b if tickers_b else None,
            weights_b=weights_b,
            name_b=name_b,
            lookback_days=params.get("lookback_days", 252),
            generate_charts=False,  # Don't use agent chart handles
            include_geodesic_path=True,  # Enable manifold physics
            include_curvature_analysis=True,
            include_manifold_embedding=True,
            compare_constituents=compare_constituents,  # NxN for single portfolio
        )
        
        if result.get("status") == "error":
            return result
        
        # Build charts directly for Canvas (same pattern as Monte Carlo)
        charts = {}
        mode = result.get("mode", "pairwise")
        logger.info(f"Geodesic mode: {mode}")
        
        if mode == "pairwise":
            # Get data needed for charts - result uses distributions[name] structure
            distributions = result.get("distributions", {})
            logger.info(f"Result keys: {list(result.keys())}")
            logger.info(f"Distribution keys: {list(distributions.keys())}")
            dist1 = distributions.get(name_a, {})
            dist2 = distributions.get(name_b, {})
            logger.info(f"dist1 keys: {list(dist1.keys()) if dist1 else 'EMPTY'}")
            logger.info(f"dist2 keys: {list(dist2.keys()) if dist2 else 'EMPTY'}")
            
            # Build distances dict from distance_analysis for chart functions
            dist_analysis = result.get("distance_analysis", {})
            geo_dist = dist_analysis.get("geodesic_distance", {})
            breakdown = dist_analysis.get("what_drives_the_difference", {})
            
            # Reconstruct distances format expected by chart functions
            distances = {
                "fisher_rao": {
                    "value": geo_dist.get("value", 0),
                    "breakdown": {
                        "mean_contribution": breakdown.get("mean_return_contribution", {}).get("value", 0),
                        "vol_contribution": breakdown.get("volatility_contribution", {}).get("value", 0),
                        "tail_contribution": breakdown.get("tail_behavior_contribution", {}).get("value", 0),
                    }
                }
            }
            
            logger.info(f"Chart conditions: dist1={bool(dist1)}, dist2={bool(dist2)}, geo_dist={bool(geo_dist)}")
            
            # Build distribution overlay chart
            dist_chart = build_distribution_chart(dist1, dist2, name_a, name_b)
            if dist_chart:
                charts["distribution"] = dist_chart
                logger.info("Built distribution chart")
            
            # Build breakdown pie chart
            fr_breakdown = distances.get("fisher_rao", {}).get("breakdown", {})
            breakdown_chart = build_breakdown_chart(fr_breakdown, geo_dist.get("value", 0))
            if breakdown_chart:
                charts["breakdown"] = breakdown_chart
                logger.info("Built breakdown chart")
            
            # Build geodesic path chart (3D manifold)
            manifold_physics = result.get("manifold_physics", {})
            geodesic_path = manifold_physics.get("geodesic_path")
            if geodesic_path:
                path_chart = build_geodesic_path_chart(geodesic_path, name_a, name_b)
                if path_chart:
                    charts["geodesic_path"] = path_chart
                    logger.info("Built geodesic path chart")
            else:
                logger.info(f"No geodesic_path in manifold_physics. Keys: {list(manifold_physics.keys())}")
            
            # Build curvature landscape chart
            curvature_map = manifold_physics.get("curvature_map")
            if curvature_map:
                curv_chart = build_curvature_chart(curvature_map, name_a)
                if curv_chart:
                    charts["curvature"] = curv_chart
                    logger.info("Built curvature chart")
            
            logger.info(f"Built {len(charts)} charts for geodesic pairwise")
        
        elif mode == "single":
            # For single portfolio, build a distribution chart
            dist = result.get("distribution", {})
            if dist:
                chart = build_single_distribution_chart(dist, result.get("portfolio_name", name_a))
                if chart:
                    charts["distribution"] = chart
                    logger.info("Built 1 chart for single mode geodesic")
        
        elif mode == "constituents":
            # For single portfolio with multiple tickers - show manifold embedding
            embedding_data = result.get("manifold_embedding")
            
            logger.info(f"Constituents mode: embedding_data={bool(embedding_data)}")
            
            # Build 3D manifold embedding chart (same as core agent tool)
            if embedding_data:
                embedding_chart = build_manifold_embedding_chart(embedding_data, title="Constituent Manifold Map")
                if embedding_chart:
                    charts["manifold_embedding"] = embedding_chart
                    logger.info("Built manifold embedding chart")
            
            logger.info(f"Built {len(charts)} charts for constituents mode")
        
        # Build metric cards
        metric_cards = []
        
        if mode == "pairwise":
            # Reuse geo_dist already extracted above for charts
            metric_cards = [
                {
                    "id": "distance",
                    "label": "Geodesic Distance",
                    "value": f"{geo_dist.get('value', 0):.3f}",
                    "sentiment": "neutral",
                    "description": f"{geo_dist.get('percentile', 0):.0f}th percentile",
                },
                {
                    "id": "similarity",
                    "label": "Similarity",
                    "value": geo_dist.get("similarity_class", "Unknown").replace("_", " ").title(),
                    "sentiment": "neutral",
                },
                {
                    "id": "correlation",
                    "label": "Correlation",
                    "value": f"{result.get('correlation', 0):.2f}",
                    "sentiment": "neutral",
                },
            ]
        elif mode == "single":
            dist = result.get("distribution", {})
            metrics = dist.get("metrics", {})
            metric_cards = [
                {
                    "id": "dist_type",
                    "label": "Distribution",
                    "value": dist.get("type", "normal").title(),
                    "sentiment": "neutral",
                },
                {
                    "id": "ann_return",
                    "label": "Ann. Return",
                    "value": f"{metrics.get('annualized_return', 0)*100:.1f}%",
                    "sentiment": "positive" if metrics.get('annualized_return', 0) > 0 else "negative",
                },
                {
                    "id": "ann_vol",
                    "label": "Ann. Volatility",
                    "value": f"{metrics.get('annualized_volatility', 0)*100:.1f}%",
                    "sentiment": "neutral",
                },
            ]
        elif mode == "constituents":
            summary = result.get("summary", {})
            most_similar = summary.get("most_similar_pair", {})
            most_different = summary.get("most_different_pair", {})
            metric_cards = [
                {
                    "id": "n_constituents",
                    "label": "Constituents",
                    "value": str(summary.get("n_items", len(tickers_a))),
                    "sentiment": "neutral",
                },
                {
                    "id": "avg_distance",
                    "label": "Avg Distance",
                    "value": f"{summary.get('mean_distance', 0):.3f}",
                    "sentiment": "neutral",
                    "description": "Mean pairwise geodesic",
                },
                {
                    "id": "most_similar",
                    "label": "Most Similar",
                    "value": " & ".join(most_similar.get("items", ["N/A"])[:2]) if most_similar.get("items") else "N/A",
                    "sentiment": "positive",
                    "description": f"d={most_similar.get('distance', 0):.3f}",
                },
            ]
        
        # Build stats table
        stats_table = []
        if mode == "pairwise":
            # Use breakdown already extracted above for charts
            stats_table = [
                {"category": "Distance", "metric": "Fisher-Rao Distance", "value": f"{geo_dist.get('value', 0):.4f}"},
                {"category": "Distance", "metric": "Percentile", "value": f"{geo_dist.get('percentile', 0):.0f}th"},
                {"category": "Breakdown", "metric": "Mean Contribution", "value": breakdown.get("mean_return_contribution", {}).get("percent_of_total", "0%")},
                {"category": "Breakdown", "metric": "Vol Contribution", "value": breakdown.get("volatility_contribution", {}).get("percent_of_total", "0%")},
                {"category": "Breakdown", "metric": "Tail Contribution", "value": breakdown.get("tail_behavior_contribution", {}).get("percent_of_total", "0%")},
            ]
        elif mode == "single":
            dist = result.get("distribution", {})
            metrics = dist.get("metrics", {})
            params = dist.get("params", {})
            stats_table = [
                {"category": "Distribution", "metric": "Type", "value": dist.get("type", "normal").title()},
                {"category": "Distribution", "metric": "Mean (daily)", "value": f"{params.get('mu', params.get('loc', 0))*100:.3f}%"},
                {"category": "Distribution", "metric": "Std Dev (daily)", "value": f"{params.get('sigma', params.get('scale', 0))*100:.3f}%"},
                {"category": "Annualized", "metric": "Return", "value": f"{metrics.get('annualized_return', 0)*100:.1f}%"},
                {"category": "Annualized", "metric": "Volatility", "value": f"{metrics.get('annualized_volatility', 0)*100:.1f}%"},
                {"category": "Risk", "metric": "Sharpe Ratio", "value": f"{metrics.get('sharpe_ratio', 0):.2f}"},
            ]
        elif mode == "constituents":
            summary = result.get("summary", {})
            most_similar = summary.get("most_similar_pair", {})
            most_different = summary.get("most_different_pair", {})
            distributions = result.get("distributions", {})
            
            stats_table = [
                {"category": "Network", "metric": "Constituents", "value": str(summary.get("n_items", 0))},
                {"category": "Network", "metric": "Mean Distance", "value": f"{summary.get('mean_distance', 0):.4f}"},
                {"category": "Network", "metric": "Max Distance", "value": f"{summary.get('max_distance', 0):.4f}"},
                {"category": "Network", "metric": "Min Distance", "value": f"{summary.get('min_nonzero_distance', 0):.4f}"},
                {"category": "Similarity", "metric": "Most Similar Pair", "value": " & ".join(most_similar.get("items", [])[:2]) or "N/A"},
                {"category": "Similarity", "metric": "Similar Pair Distance", "value": f"{most_similar.get('distance', 0):.4f}"},
                {"category": "Diversity", "metric": "Most Different Pair", "value": " & ".join(most_different.get("items", [])[:2]) or "N/A"},
                {"category": "Diversity", "metric": "Different Pair Distance", "value": f"{most_different.get('distance', 0):.4f}"},
            ]
            # Add individual constituent metrics
            for ticker, dist_data in list(distributions.items())[:5]:  # Top 5
                metrics = dist_data.get("metrics", {})
                ann_ret = metrics.get("annualized_return", 0) * 100
                ann_vol = metrics.get("annualized_volatility", 0) * 100
                stats_table.append({"category": "Constituents", "metric": f"{ticker} Return", "value": f"{ann_ret:.1f}%"})
                stats_table.append({"category": "Constituents", "metric": f"{ticker} Vol", "value": f"{ann_vol:.1f}%"})
        
        logger.info(f"Returning: {len(charts)} charts, {len(metric_cards)} metric cards, {len(stats_table)} stats rows")
        
        return {
            "status": "success",
            "tool_id": "geodesic",
            "tickers": tickers_a,
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": result.get("summary", result.get("interpretation", f"Geodesic analysis of {name_a}" + (f" vs {name_b}" if tickers_b else " (select a second portfolio for manifold comparison)"))),
        }
        
    except Exception as e:
        logger.error(f"Geodesic failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


async def _resolve_portfolio(user_id: str, portfolio_id: str):
    """Resolve portfolio to tickers, weights, name."""
    try:
        service = PortfolioService()
        result = await service.get_portfolio(user_id, portfolio_id)
        
        if not result or result.get("status") == "error":
            return [], None, "Unknown"
        
        portfolio = result.get("portfolio", {})
        tickers = portfolio.get("tickers", [])
        weights = portfolio.get("weights", [])
        name = portfolio.get("name", portfolio_id)
        
        if not weights or len(weights) != len(tickers):
            weights = [1.0/len(tickers)] * len(tickers) if tickers else []
        
        return tickers, weights, name
    except Exception as e:
        logger.warning(f"Portfolio resolve failed: {e}")
        return [], None, "Unknown"
