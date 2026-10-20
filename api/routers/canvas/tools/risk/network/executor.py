"""Executor for Portfolio Network Risk Canvas tool."""
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


async def _resolve_portfolio_tickers(
    user_id: str,
    org_id: Optional[str],
    portfolio_id: str
) -> Tuple[List[str], Optional[List[float]]]:
    """Fetch tickers and weights from portfolio."""
    try:
        from core.services.portfolio_service import PortfolioService
        service = PortfolioService()
        portfolio = await service.get_portfolio(user_id, portfolio_id)
        
        if not portfolio or portfolio.get("status") == "error":
            return [], None
        
        # Portfolio data is nested under "portfolio" key
        actual_portfolio = portfolio.get("portfolio", {})
        tickers = actual_portfolio.get("tickers", [])
        weights = actual_portfolio.get("weights", [])
        
        if not tickers:
            return [], None
        
        # Default to equal weights if not provided or length mismatch
        if not weights or len(weights) != len(tickers):
            weights = [1.0 / len(tickers)] * len(tickers)
        
        return tickers, weights
    except Exception as e:
        logger.error(f"Failed to resolve portfolio {portfolio_id}: {e}")
        return [], None


async def execute_network_risk(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute portfolio network risk analysis for Canvas."""
    try:
        from core.agents.quant_tools.graph_theory_portfolio_analyzer import (
            _analyze_graph_theory_risk_impl,
            _calculate_cascade_impact,
        )
        from .charts import (
            build_network_chart,
            build_centrality_chart,
            build_community_chart,
            build_risk_gauge,
            build_shock_propagation_chart,
        )
        
        # Extract parameters
        portfolio_id = params.get("portfolio_id")
        tickers = params.get("tickers", [])
        weights = params.get("weights")
        lookback_days = int(params.get("lookback_days", 252))
        correlation_threshold = float(params.get("correlation_threshold", 0.3))
        optimize_hedges = bool(params.get("optimize_hedges", False))
        simulate_shock = bool(params.get("simulate_shock", False))
        shock_ticker = params.get("shock_ticker", "")
        shock_magnitude = float(params.get("shock_magnitude", -10)) / 100  # Convert to decimal
        
        # Resolve portfolio if provided
        if portfolio_id:
            tickers, weights = await _resolve_portfolio_tickers(user_id, org_id, portfolio_id)
            if not tickers:
                return {"status": "error", "error": f"Portfolio {portfolio_id} not found or empty"}
        
        if not tickers or len(tickers) < 2:
            return {"status": "error", "error": "Need at least 2 tickers (provide portfolio_id or tickers)"}
        
        # Normalize tickers
        tickers = [t.upper().strip() for t in tickers if t]
        
        logger.info(f"[NETWORK] Analyzing {len(tickers)} tickers, lookback={lookback_days}")
        
        # Call internal function
        result = await _analyze_graph_theory_risk_impl(
            tickers=tickers,
            weights=weights,
            lookback_days=lookback_days,
            correlation_threshold=correlation_threshold,
            correlation_method="pearson",
            generate_chart=False,  # We build our own charts
            optimize_hedges=optimize_hedges,
        )
        
        if "error" in result:
            return {"status": "error", "error": result.get("error")}
        
        # Extract data
        valid_tickers = result.get("valid_tickers", tickers)
        graph_metrics = result.get("graph_metrics", {})
        mst_edges = result.get("minimum_spanning_tree", [])
        bridges = result.get("bridge_stocks") or []
        communities = result.get("communities", [])
        centrality = result.get("centrality_ranking", [])
        risk_assessment = result.get("risk_assessment", {})
        hedge_optimization = result.get("hedge_optimization", {})
        config = result.get("config", {})
        
        # Build edges list from graph construction
        edges = []
        corr_matrix = result.get("correlation_matrix", {})
        for t1 in valid_tickers:
            for t2 in valid_tickers:
                if t1 < t2:
                    corr = abs(corr_matrix.get(t1, {}).get(t2, 0))
                    if corr >= correlation_threshold:
                        edges.append((t1, t2, corr))
        
        # Build charts
        charts = {}
        
        network_chart = build_network_chart(valid_tickers, edges, communities, centrality, mst_edges)
        if network_chart:
            charts["network"] = network_chart
        
        centrality_chart = build_centrality_chart(centrality)
        if centrality_chart:
            charts["centrality"] = centrality_chart
        
        if len(communities) >= 2:
            community_chart = build_community_chart(communities)
            if community_chart:
                charts["communities"] = community_chart
        
        risk_level = risk_assessment.get("contagion_risk", "LOW")
        composite_z = risk_assessment.get("composite_z_score", 0)
        div_score = risk_assessment.get("diversification_score", 5)
        
        risk_gauge = build_risk_gauge(risk_level, composite_z, div_score)
        if risk_gauge:
            charts["risk_gauge"] = risk_gauge
        
        # Shock propagation simulation
        shock_result = None
        if simulate_shock and valid_tickers:
            import pandas as pd
            
            # Build correlation matrix as DataFrame
            corr_df = pd.DataFrame(index=valid_tickers, columns=valid_tickers, dtype=float)
            for t1 in valid_tickers:
                for t2 in valid_tickers:
                    if t1 == t2:
                        corr_df.loc[t1, t2] = 1.0
                    else:
                        corr_df.loc[t1, t2] = corr_matrix.get(t1, {}).get(t2, 0)
            
            # Determine which ticker to shock
            target_ticker = shock_ticker.upper().strip() if shock_ticker else None
            if not target_ticker or target_ticker not in valid_tickers:
                # Default to most central stock
                if centrality:
                    target_ticker = centrality[0].get("ticker", valid_tickers[0])
                else:
                    target_ticker = valid_tickers[0]
            
            # Build weights dict
            weights_dict = None
            if weights:
                weights_dict = {t: w for t, w in zip(valid_tickers, weights)}
            
            # Build graph structure for cascade calculation
            graph = {"nodes": valid_tickers, "edges": edges}
            
            try:
                shock_result = _calculate_cascade_impact(
                    ticker=target_ticker,
                    shock_pct=shock_magnitude,
                    corr_matrix=corr_df,
                    graph=graph,
                    weights=weights_dict
                )
                
                # Build shock propagation chart
                shock_chart = build_shock_propagation_chart(shock_result, target_ticker, shock_magnitude)
                if shock_chart:
                    charts["shock_propagation"] = shock_chart
                    
            except Exception as e:
                logger.warning(f"Shock simulation failed: {e}")
        
        # Build metric cards
        def safe_fmt(val, fmt=".2f"):
            try:
                if val is None:
                    return "N/A"
                return f"{float(val):{fmt}}"
            except (ValueError, TypeError):
                return "N/A"
        
        metric_cards = [
            {"id": "contagion_risk", "label": "Contagion Risk", "value": risk_level, "description": f"Z-score: {safe_fmt(composite_z)}", "sentiment": "negative" if risk_level == "HIGH" else ("neutral" if risk_level == "MODERATE" else "positive")},
            {"id": "diversification", "label": "Diversification", "value": f"{safe_fmt(div_score, '.1f')}/10", "description": "Structure score", "sentiment": "positive" if div_score >= 7 else ("neutral" if div_score >= 4 else "negative")},
            {"id": "communities", "label": "Communities", "value": str(len(communities)), "description": "Clusters detected", "sentiment": "neutral"},
            {"id": "bridges", "label": "Bridges", "value": str(len(bridges)), "description": "Single points of failure", "sentiment": "negative" if len(bridges) > 2 else "neutral"},
            {"id": "density", "label": "Density", "value": safe_fmt(graph_metrics.get("density", 0)), "description": "Network connectivity", "sentiment": "neutral"},
            {"id": "avg_clustering", "label": "Avg Clustering", "value": safe_fmt(graph_metrics.get("avg_clustering_coefficient", 0)), "description": "Local clustering", "sentiment": "neutral"},
        ]
        
        # Build stats table
        stats_table = [
            {"category": "Network", "metric": "Nodes", "value": str(graph_metrics.get("num_nodes", 0))},
            {"category": "Network", "metric": "Edges", "value": str(graph_metrics.get("num_edges", 0))},
            {"category": "Network", "metric": "Density", "value": safe_fmt(graph_metrics.get("density", 0))},
            {"category": "Network", "metric": "Avg Degree", "value": safe_fmt(graph_metrics.get("avg_degree", 0))},
            {"category": "Network", "metric": "Clustering Coef", "value": safe_fmt(graph_metrics.get("avg_clustering_coefficient", 0))},
            {"category": "Risk", "metric": "Contagion Level", "value": risk_level},
            {"category": "Risk", "metric": "Composite Z-Score", "value": safe_fmt(composite_z)},
            {"category": "Risk", "metric": "Diversification", "value": f"{safe_fmt(div_score, '.1f')}/10"},
            {"category": "Config", "metric": "Lookback Days", "value": str(lookback_days)},
            {"category": "Config", "metric": "Corr Threshold", "value": safe_fmt(correlation_threshold)},
            {"category": "Config", "metric": "Avg Correlation", "value": safe_fmt(config.get("avg_correlation", 0))},
        ]
        
        # Add bridge stocks
        if bridges:
            stats_table.append({"category": "Bridges", "metric": "Critical Nodes", "value": ", ".join(bridges[:5])})
        
        # Add top centrality
        for i, c in enumerate(centrality[:3]):
            stats_table.append({
                "category": "Centrality",
                "metric": f"#{i+1} {c['ticker']}",
                "value": f"Eigen: {safe_fmt(c.get('eigenvector_centrality', 0))}, Between: {safe_fmt(c.get('betweenness_centrality', 0))}",
            })
        
        # Add communities
        for comm in communities[:5]:
            stocks = comm.get("stocks", [])
            stats_table.append({
                "category": "Clusters",
                "metric": f"Cluster {comm.get('id', '?')}",
                "value": f"{len(stocks)} stocks, {safe_fmt(comm.get('avg_internal_correlation', 0), '.0%')} corr",
            })
        
        # Add recommendations
        recommendations = risk_assessment.get("recommendations", [])
        summary_text = risk_assessment.get("summary", "")
        
        # Add hedge info if available
        hedge_summary = {}
        if optimize_hedges and hedge_optimization:
            hedge_priority = hedge_optimization.get("hedge_priority", [])
            if hedge_priority:
                hedge_summary = {
                    "critical_hedges": len([h for h in hedge_priority if h.get("priority") == "CRITICAL"]),
                    "high_hedges": len([h for h in hedge_priority if h.get("priority") == "HIGH"]),
                    "top_hedge": hedge_priority[0] if hedge_priority else None,
                }
                stats_table.append({
                    "category": "Hedges",
                    "metric": "Priority Hedges",
                    "value": f"{hedge_summary['critical_hedges']} critical, {hedge_summary['high_hedges']} high",
                })
        
        # Add shock simulation results
        shock_summary = None
        if shock_result:
            shock_summary = {
                "shocked_ticker": shock_result.get("shocked_ticker"),
                "shock_magnitude": shock_result.get("shock_magnitude"),
                "direct_impact": shock_result.get("direct_portfolio_impact"),
                "propagated_impact": shock_result.get("propagated_impact"),
                "total_impact": shock_result.get("total_portfolio_impact"),
                "cascade_multiplier": shock_result.get("cascade_multiplier"),
                "positions_affected": shock_result.get("positions_impacted"),
            }
            
            stats_table.extend([
                {"category": "Shock Simulation", "metric": "Shocked Ticker", "value": shock_result.get("shocked_ticker", "N/A")},
                {"category": "Shock Simulation", "metric": "Shock Magnitude", "value": shock_result.get("shock_magnitude", "N/A")},
                {"category": "Shock Simulation", "metric": "Direct Impact", "value": shock_result.get("direct_portfolio_impact", "N/A")},
                {"category": "Shock Simulation", "metric": "Propagated Impact", "value": shock_result.get("propagated_impact", "N/A")},
                {"category": "Shock Simulation", "metric": "Total Portfolio Impact", "value": shock_result.get("total_portfolio_impact", "N/A")},
                {"category": "Shock Simulation", "metric": "Cascade Multiplier", "value": f"{shock_result.get('cascade_multiplier', 0):.2f}x"},
                {"category": "Shock Simulation", "metric": "Positions Affected", "value": str(shock_result.get("positions_impacted", 0))},
            ])
            
            # Add metric card for shock
            metric_cards.append({
                "id": "shock_impact",
                "label": "Shock Impact",
                "value": shock_result.get("total_portfolio_impact", "N/A"),
                "description": f"{shock_result.get('cascade_multiplier', 0):.1f}x cascade",
                "sentiment": "negative" if shock_result.get("cascade_multiplier", 0) > 1.5 else "neutral"
            })

        return {
            "status": "success",
            "tool_id": "network_risk",
            "tickers": valid_tickers,
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": {
                "risk_level": risk_level,
                "composite_z_score": composite_z,
                "diversification_score": div_score,
                "n_communities": len(communities),
                "n_bridges": len(bridges),
                "bridges": bridges,
                "summary": summary_text,
                "recommendations": recommendations,
                "hedge_summary": hedge_summary if optimize_hedges else None,
                "shock_summary": shock_summary,
            },
        }
        
    except Exception as e:
        logger.error(f"[NETWORK] Execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
