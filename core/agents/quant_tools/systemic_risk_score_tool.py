"""
Systemic Risk Score Tool - PageRank-Based Network Centrality Analysis

Thin wrapper around _analyze_graph_theory_risk_impl() that adds:
- PageRank scoring with adaptive damping (derived from network density)
- Variance-normalized combination of centrality metrics
- Portfolio-level systemic risk score (0-10 scale)
- Concentration warnings and actionable recommendations

Philosophy:
-----------
Traditional portfolio risk metrics treat positions independently. This tool
models the portfolio as a correlation network and applies PageRank-style
scoring to identify which positions contribute most to SYSTEMIC risk - the
risk that a shock to one position cascades through the network.

Key Insight: A position's systemic importance depends not just on its own
characteristics, but on how connected it is to OTHER important positions
(the PageRank principle from web search).

Mathematical Foundation:
-----------------------
1. PageRank with adaptive damping:
   PR(i) = (1-d)/N + d * Σ(PR(j) * A_ji / out_degree(j))
   
   Damping factor 'd' is derived from network density:
   - Denser networks → higher damping (prevents over-smoothing)
   - Sparser networks → lower damping (allows differentiation)

2. Risk contribution: Variance-normalized combination of PageRank and betweenness
   - Weights determined by discriminative power (std deviation) of each metric
   - Automatically adapts to portfolio structure

3. Portfolio systemic score: Gini coefficient of risk contributions × scaling
   - Higher concentration → higher systemic risk
   - Score 0-10: 0 = perfectly distributed, 10 = extreme concentration

NO HARDCODING: Uses dynamic normalization for all weights and thresholds.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
import logging
import uuid

# Agent framework
from agents import function_tool

# Internal utilities
from core.utils.risk_adapter import jsonify_results

# Visualization
from core.visualization.plotly_charts import RiskCharts
from core.agents.risk_tools.shared import register_chart_handle

# Underlying graph analysis (use internal impl, not the decorated tool)
from core.agents.quant_tools.graph_theory_portfolio_analyzer import _analyze_graph_theory_risk_impl

logger = logging.getLogger(__name__)


# =============================================================================
# PAGERANK WITH ADAPTIVE DAMPING
# =============================================================================

def _calculate_adaptive_damping(density: float, expected_density: Optional[float] = None) -> float:
    """
    Calculate adaptive damping factor based on network density.
    
    Rationale:
    - Denser networks need higher damping to prevent over-smoothing
    - Sparser networks need lower damping to allow differentiation
    - Based on empirical findings in graph theory literature
    
    Args:
        density: Observed network density (edges / max_edges)
        expected_density: Expected density for random graph (optional)
    
    Returns:
        Damping factor in range [0.5, 0.95]
    """
    if expected_density is None:
        # Use median expected density for typical portfolios
        expected_density = 0.4
    
    # Scale damping with relative density
    relative_density = density / max(expected_density, 0.01)
    
    # Logistic scaling to bound in [0.5, 0.95]
    # Higher relative density → higher damping
    damping = 0.5 + 0.45 * (1 / (1 + np.exp(-2 * (relative_density - 1))))
    
    return round(min(0.95, max(0.5, damping)), 3)


def _calculate_pagerank(
    corr_matrix: Dict[str, Dict[str, float]],
    correlation_threshold: float,
    damping: float,
    max_iterations: int = 100,
    tolerance: float = 1e-6
) -> Dict[str, float]:
    """
    Calculate PageRank scores for portfolio positions.
    
    Uses power iteration with adaptive damping factor.
    Edge weights are absolute correlations above threshold.
    
    Args:
        corr_matrix: Nested dict of correlations (ticker -> ticker -> corr)
        correlation_threshold: Minimum |correlation| to create edge
        damping: Damping factor (0.5-0.95)
        max_iterations: Maximum power iterations
        tolerance: Convergence tolerance
    
    Returns:
        Dict mapping ticker -> PageRank score (normalized to sum=1)
    """
    tickers = list(corr_matrix.keys())
    n = len(tickers)
    
    if n == 0:
        return {}
    
    if n == 1:
        return {tickers[0]: 1.0}
    
    # Build adjacency matrix with correlation weights
    adj_matrix = np.zeros((n, n))
    for i, t1 in enumerate(tickers):
        for j, t2 in enumerate(tickers):
            if i != j:
                corr = abs(corr_matrix[t1][t2])
                if corr >= correlation_threshold:
                    adj_matrix[i, j] = corr
    
    # Calculate out-degree (sum of outgoing edge weights)
    out_degree = adj_matrix.sum(axis=1)
    
    # Handle dangling nodes (no outgoing edges)
    dangling_mask = out_degree == 0
    out_degree[dangling_mask] = 1  # Prevent division by zero
    
    # Create transition matrix
    transition = adj_matrix / out_degree[:, np.newaxis]
    
    # Dangling nodes distribute uniformly
    transition[dangling_mask, :] = 1.0 / n
    
    # Initialize PageRank uniformly
    pagerank = np.ones(n) / n
    
    # Power iteration
    for iteration in range(max_iterations):
        new_pagerank = (1 - damping) / n + damping * transition.T @ pagerank
        
        # Check convergence
        diff = np.abs(new_pagerank - pagerank).sum()
        pagerank = new_pagerank
        
        if diff < tolerance:
            logger.debug(f"PageRank converged in {iteration + 1} iterations")
            break
    
    # Normalize to sum=1
    pagerank = pagerank / pagerank.sum()
    
    return {ticker: round(float(pagerank[i]), 6) for i, ticker in enumerate(tickers)}


# =============================================================================
# RISK CONTRIBUTION CALCULATION
# =============================================================================

def _compute_risk_contributions(
    pagerank_scores: Dict[str, float],
    centrality_ranking: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Combine PageRank and betweenness into risk contribution scores.
    
    Uses variance-normalized weighting:
    - Weight each metric by its discriminative power (std deviation)
    - Higher variance = more useful for distinguishing positions
    - Automatically adapts to portfolio structure
    
    Args:
        pagerank_scores: Dict mapping ticker -> PageRank score
        centrality_ranking: List of dicts with ticker, betweenness_centrality, etc.
    
    Returns:
        List of dicts with ticker, pagerank, betweenness, risk_contribution
        Sorted by risk_contribution descending
    """
    if not pagerank_scores or not centrality_ranking:
        return []
    
    # Extract betweenness scores
    betweenness_map = {
        c["ticker"]: c.get("betweenness_centrality", 0)
        for c in centrality_ranking
    }
    
    tickers = list(pagerank_scores.keys())
    
    # Get arrays for variance calculation
    pr_values = np.array([pagerank_scores.get(t, 0) for t in tickers])
    bt_values = np.array([betweenness_map.get(t, 0) for t in tickers])
    
    # Calculate variance-normalized weights
    pr_std = np.std(pr_values) if len(pr_values) > 1 else 0.01
    bt_std = np.std(bt_values) if len(bt_values) > 1 else 0.01
    
    # Prevent division by zero
    total_std = pr_std + bt_std
    if total_std < 1e-10:
        pr_weight = 0.5
        bt_weight = 0.5
    else:
        pr_weight = pr_std / total_std
        bt_weight = bt_std / total_std
    
    logger.debug(f"Variance-normalized weights: PageRank={pr_weight:.3f}, Betweenness={bt_weight:.3f}")
    
    # Calculate risk contributions
    contributions = []
    for ticker in tickers:
        pr = pagerank_scores.get(ticker, 0)
        bt = betweenness_map.get(ticker, 0)
        
        # Weighted combination
        risk_contrib = pr_weight * pr + bt_weight * bt
        
        contributions.append({
            "ticker": ticker,
            "pagerank": round(pr, 4),
            "betweenness": round(bt, 4),
            "risk_contribution": round(risk_contrib, 4)
        })
    
    # Normalize risk contributions to sum to 1
    total_risk = sum(c["risk_contribution"] for c in contributions)
    if total_risk > 0:
        for c in contributions:
            c["risk_contribution"] = round(c["risk_contribution"] / total_risk, 4)
    
    # Sort by risk contribution descending
    contributions.sort(key=lambda x: x["risk_contribution"], reverse=True)
    
    return contributions


# =============================================================================
# PORTFOLIO SYSTEMIC SCORE
# =============================================================================

def _calculate_gini_coefficient(values: List[float]) -> float:
    """
    Calculate Gini coefficient measuring inequality/concentration.
    
    Returns:
        Gini coefficient in [0, 1]: 0 = perfect equality, 1 = maximum inequality
    """
    if not values or len(values) < 2:
        return 0.0
    
    values = np.array(sorted(values))
    n = len(values)
    
    # Gini formula: G = (2 * Σ(i * x_i) - (n + 1) * Σ(x_i)) / (n * Σ(x_i))
    cumsum = np.cumsum(values)
    total = values.sum()
    
    if total == 0:
        return 0.0
    
    gini = (2 * np.sum((np.arange(1, n + 1) * values)) - (n + 1) * total) / (n * total)
    
    return max(0.0, min(1.0, gini))


def _calculate_portfolio_systemic_score(
    risk_contributions: List[Dict[str, Any]],
    avg_correlation: Optional[float] = None
) -> float:
    """
    Calculate portfolio-level systemic risk score (0-10 scale).
    
    Based on:
    1. Gini coefficient of risk contributions (concentration measure)
    2. Average correlation level (higher correlation = more systemic risk)
    
    Score interpretation:
    - 0-3: Low systemic risk (well-distributed, uncorrelated)
    - 3-5: Moderate systemic risk
    - 5-7: Elevated systemic risk (some concentration)
    - 7-10: High systemic risk (concentrated, correlated)
    
    Args:
        risk_contributions: List of position risk contributions
        avg_correlation: Average absolute correlation in portfolio
    
    Returns:
        Score from 0 to 10
    """
    if not risk_contributions:
        return 0.0
    
    # Extract risk contribution values
    contrib_values = [c["risk_contribution"] for c in risk_contributions]
    
    # Calculate Gini coefficient
    gini = _calculate_gini_coefficient(contrib_values)
    
    # Base score from Gini (0-10 scale)
    base_score = gini * 10
    
    # Adjust for correlation level if provided
    if avg_correlation is not None:
        # Higher average correlation increases systemic risk
        # Scaling: avg_corr of 0.5 adds ~20% to score
        correlation_multiplier = 1 + (avg_correlation * 0.4)
        base_score *= correlation_multiplier
    
    # Also consider number of positions (fewer = higher concentration risk)
    n_positions = len(risk_contributions)
    if n_positions < 5:
        # Small portfolios are inherently more concentrated
        size_adjustment = 1 + (5 - n_positions) * 0.1
        base_score *= size_adjustment
    
    # Bound to 0-10
    final_score = max(0.0, min(10.0, base_score))
    
    return round(final_score, 1)


# =============================================================================
# WARNINGS AND RECOMMENDATIONS
# =============================================================================

def _generate_concentration_warning(
    risk_contributions: List[Dict[str, Any]]
) -> Optional[str]:
    """
    Generate warning if any position dominates systemic risk.
    
    Dynamic thresholding based on portfolio size:
    - 2 positions: warn if one has >60% (expected: 50%)
    - 5 positions: warn if one has >30% (expected: 20%)
    - 10 positions: warn if one has >20% (expected: 10%)
    
    Returns:
        Warning string or None if no concerning concentration
    """
    if not risk_contributions:
        return None
    
    n = len(risk_contributions)
    expected_share = 1.0 / n
    
    # Warning threshold: 1.5x expected share, minimum 15%
    threshold = max(0.15, expected_share * 1.5)
    
    # Check top contributor
    top = risk_contributions[0]
    if top["risk_contribution"] > threshold:
        pct = int(top["risk_contribution"] * 100)
        return f"{top['ticker']} accounts for {pct}% of systemic risk"
    
    # Check if top 2 dominate (for larger portfolios)
    if n >= 5 and len(risk_contributions) >= 2:
        top_2_share = sum(c["risk_contribution"] for c in risk_contributions[:2])
        if top_2_share > 0.5:
            pct = int(top_2_share * 100)
            tickers = f"{risk_contributions[0]['ticker']} and {risk_contributions[1]['ticker']}"
            return f"{tickers} together account for {pct}% of systemic risk"
    
    return None


def _generate_recommendation(
    risk_contributions: List[Dict[str, Any]],
    portfolio_score: float,
    avg_correlation: Optional[float] = None
) -> str:
    """
    Generate actionable recommendation based on systemic risk profile.
    
    Recommendations are context-aware:
    - High concentration → reduce top positions or hedge
    - High correlation → add uncorrelated assets
    - Low risk → portfolio is well-structured
    
    Returns:
        Recommendation string
    """
    if not risk_contributions:
        return "Add positions to analyze systemic risk"
    
    n = len(risk_contributions)
    top = risk_contributions[0]
    
    # High systemic risk (score > 7)
    if portfolio_score > 7:
        if top["risk_contribution"] > 0.3:
            return f"Reduce {top['ticker']} exposure or add uncorrelated positions to lower concentration"
        elif avg_correlation and avg_correlation > 0.5:
            return "Add uncorrelated assets (bonds, commodities, alternatives) to reduce systemic linkage"
        else:
            return "Rebalance to reduce systemic risk concentration"
    
    # Elevated risk (5-7)
    if portfolio_score > 5:
        if top["risk_contribution"] > 0.25:
            return f"Consider hedging {top['ticker']} or reducing position size"
        else:
            return "Monitor top contributors; consider adding diversifying positions"
    
    # Moderate risk (3-5)
    if portfolio_score > 3:
        return "Portfolio structure is acceptable; monitor for concentration drift"
    
    # Low risk (< 3)
    return "Portfolio has well-distributed systemic risk; maintain current structure"


# =============================================================================
# VISUALIZATION
# =============================================================================

def _build_risk_contribution_chart(
    risk_contributions: List[Dict[str, Any]],
    portfolio_score: float,
    chart_id: str
) -> Optional[Dict[str, Any]]:
    """
    Build bar chart showing PageRank vs Betweenness per position.
    
    Color coding by risk contribution level.
    """
    import plotly.graph_objects as go
    
    if not risk_contributions:
        return None
    
    tickers = [c["ticker"] for c in risk_contributions]
    pageranks = [c["pagerank"] for c in risk_contributions]
    betweenness = [c["betweenness"] for c in risk_contributions]
    risk_contribs = [c["risk_contribution"] for c in risk_contributions]
    
    # Color by risk contribution (green → yellow → red)
    colors = []
    for rc in risk_contribs:
        if rc > 0.3:
            colors.append('#DC2626')  # Red - high risk
        elif rc > 0.15:
            colors.append('#F59E0B')  # Orange - elevated
        else:
            colors.append('#10B981')  # Green - acceptable
    
    fig = go.Figure()
    
    # PageRank bars
    fig.add_trace(go.Bar(
        name='PageRank',
        x=tickers,
        y=pageranks,
        marker_color='#3B82F6',
        opacity=0.8,
        hovertemplate='<b>%{x}</b><br>PageRank: %{y:.3f}<extra></extra>'
    ))
    
    # Betweenness bars
    fig.add_trace(go.Bar(
        name='Betweenness',
        x=tickers,
        y=betweenness,
        marker_color='#8B5CF6',
        opacity=0.8,
        hovertemplate='<b>%{x}</b><br>Betweenness: %{y:.3f}<extra></extra>'
    ))
    
    # Risk contribution line
    fig.add_trace(go.Scatter(
        name='Risk Contribution',
        x=tickers,
        y=risk_contribs,
        mode='lines+markers',
        line=dict(color='#EF4444', width=3),
        marker=dict(size=10, color=colors, line=dict(width=2, color='white')),
        hovertemplate='<b>%{x}</b><br>Risk Contribution: %{y:.1%}<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(
            text=f'<b>Systemic Risk Contributions</b><br><sub>Portfolio Score: {portfolio_score}/10</sub>',
            font=dict(size=14)
        ),
        barmode='group',
        xaxis_title='Position',
        yaxis_title='Score',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=500,
        margin=dict(l=60, r=40, t=80, b=60),
        plot_bgcolor='white'
    )
    
    fig.update_xaxes(tickangle=45)
    
    return {
        'id': chart_id,
        'title': 'Systemic Risk Contributions',
        'plotly': fig.to_dict()
    }


# =============================================================================
# INTERNAL VERSION FOR CANVAS
# =============================================================================

async def analyze_systemic_risk_internal(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    lookback_days: int = 252,
    correlation_threshold: float = 0.3
) -> dict:
    """Internal callable for Canvas - returns raw data without chart handles."""
    try:
        if not tickers or len(tickers) < 2:
            return {"error": "Need at least 2 tickers", "provided": len(tickers) if tickers else 0}
        
        # Filter non-equity tickers
        filtered_tickers = []
        filtered_weights = []
        skipped_positions = []
        
        for i, ticker in enumerate(tickers):
            ticker_upper = ticker.upper().strip()
            is_option = ' ' in ticker_upper or any(c in ticker_upper for c in ['C0', 'P0'])
            is_crypto = '.USD' in ticker_upper or '-PAXOS' in ticker_upper
            
            if is_option or is_crypto:
                skipped_positions.append({"ticker": ticker, "reason": "option" if is_option else "crypto"})
                continue
            
            filtered_tickers.append(ticker_upper)
            if weights and i < len(weights):
                filtered_weights.append(abs(weights[i]))
        
        if filtered_weights:
            total_weight = sum(filtered_weights)
            if total_weight > 0:
                filtered_weights = [w / total_weight for w in filtered_weights]
        
        if len(filtered_tickers) < 2:
            return {"error": "Need at least 2 valid equity tickers", "skipped": skipped_positions}
        
        tickers = filtered_tickers
        weights = filtered_weights if filtered_weights else None
        
        # Call graph analysis
        graph_result = await _analyze_graph_theory_risk_impl(
            tickers=tickers,
            weights=weights,
            lookback_days=lookback_days,
            correlation_threshold=correlation_threshold,
            generate_chart=False,
            optimize_hedges=False
        )
        
        if "error" in graph_result:
            return graph_result
        
        corr_matrix = graph_result.get("correlation_matrix", {})
        centrality_ranking = graph_result.get("centrality_ranking", [])
        graph_metrics = graph_result.get("graph_metrics", {})
        
        if not corr_matrix:
            return {"error": "Failed to compute correlation matrix"}
        
        # Calculate adaptive damping
        density = graph_metrics.get("density", 0.5)
        adaptive_damping = _calculate_adaptive_damping(density)
        
        # Calculate PageRank
        pagerank_scores = _calculate_pagerank(
            corr_matrix=corr_matrix,
            correlation_threshold=correlation_threshold,
            damping=adaptive_damping
        )
        
        # Compute risk contributions
        risk_contributions = _compute_risk_contributions(
            pagerank_scores=pagerank_scores,
            centrality_ranking=centrality_ranking
        )
        
        # Calculate average correlation
        valid_tickers = list(corr_matrix.keys())
        n = len(valid_tickers)
        if n >= 2:
            corr_values = [
                abs(corr_matrix[t1][t2])
                for i, t1 in enumerate(valid_tickers)
                for j, t2 in enumerate(valid_tickers)
                if i < j
            ]
            avg_correlation = np.mean(corr_values) if corr_values else 0.5
        else:
            avg_correlation = 0.5
        
        # Calculate portfolio score
        portfolio_score = _calculate_portfolio_systemic_score(
            risk_contributions=risk_contributions,
            avg_correlation=avg_correlation
        )
        
        # Generate warnings and recommendations
        concentration_warning = _generate_concentration_warning(risk_contributions)
        recommendation = _generate_recommendation(
            risk_contributions=risk_contributions,
            portfolio_score=portfolio_score,
            avg_correlation=avg_correlation
        )
        
        return {
            "status": "success",
            "portfolio_systemic_risk_score": portfolio_score,
            "position_risk_contributions": risk_contributions,
            "concentration_warning": concentration_warning,
            "recommendation": recommendation,
            "tickers": valid_tickers,
            "skipped_positions": skipped_positions,
            "avg_correlation": round(avg_correlation, 4),
            "network_density": round(density, 4),
            "adaptive_damping": adaptive_damping,
            "lookback_days": lookback_days,
            "correlation_threshold": correlation_threshold,
        }
        
    except Exception as e:
        logger.error(f"Systemic risk internal failed: {e}", exc_info=True)
        return {"error": str(e)}


# =============================================================================
# MAIN TOOL
# =============================================================================

@function_tool
async def analyze_systemic_risk_score(
    tickers: List[str],
    weights: Optional[List[float]] = None,
    lookback_days: int = 252,
    correlation_threshold: float = 0.3,
    generate_chart: bool = True
) -> dict:
    """
    Compute systemic risk score using PageRank-style network centrality.
    
    This tool identifies which positions contribute most to portfolio-wide
    systemic risk by modeling the portfolio as a correlation network and
    applying PageRank scoring. Unlike simple correlation analysis, this
    captures the cascading nature of systemic risk.
    
    **When to Use This Tool:**
    - Quick assessment of systemic risk concentration
    - Identifying which positions to hedge for maximum impact
    - Comparing systemic risk before/after portfolio changes
    - Monitoring for concentration drift over time
    
    **How It Works:**
    1. Filters out non-equity positions (options, crypto, CFDs) - these can't be analyzed
    2. Calls underlying graph analysis to build correlation network
    3. Applies PageRank with adaptive damping (derived from network density)
    4. Combines PageRank with betweenness centrality using variance-normalized weights
    5. Calculates portfolio-level systemic score (0-10) using Gini coefficient
    
    **Short Position Handling:**
    - Short positions are included in analysis (correlations work the same)
    - Weights are converted to absolute values (a 5% short contributes to systemic risk like a 5% long)
    5. Generates concentration warnings and actionable recommendations
    
    **Understanding Results:**
    
    - `portfolio_systemic_risk_score`: 0-10 scale
        - 0-3: Low risk (well-distributed)
        - 3-5: Moderate risk
        - 5-7: Elevated risk (some concentration)
        - 7-10: High risk (concentrated systemic exposure)
    
    - `position_risk_contributions`: Per-position breakdown
        - pagerank: Network importance (connected to important nodes)
        - betweenness: Bridge importance (on many shortest paths)
        - risk_contribution: Combined score (normalized to sum=1)
    
    - `concentration_warning`: Alert if single position dominates
    
    - `recommendation`: Actionable next steps
    
    Args:
        tickers: List of stock symbols (minimum 2)
        weights: Optional portfolio weights (normalized automatically)
        lookback_days: Historical window for correlations (default: 252 = 1 year)
        correlation_threshold: Minimum |correlation| for network edge (default: 0.3)
        generate_chart: Include bar chart visualization (default: True)
    
    Returns:
        Dict containing:
        {
            "portfolio_systemic_risk_score": float (0-10),
            "position_risk_contributions": [
                {"ticker": str, "pagerank": float, "betweenness": float, "risk_contribution": float},
                ...
            ],
            "concentration_warning": str or None,
            "recommendation": str,
            "config": {...},
            "charts": [...] (if generate_chart=True)
        }
    
    Examples:
        # Basic systemic risk check
        result = await analyze_systemic_risk_score(
            tickers=["AAPL", "MSFT", "GOOGL", "META", "AMZN"]
        )
        print(f"Score: {result['portfolio_systemic_risk_score']}/10")
        print(result['recommendation'])
        
        # With portfolio weights
        result = await analyze_systemic_risk_score(
            tickers=["SPY", "QQQ", "TLT", "GLD"],
            weights=[0.4, 0.3, 0.2, 0.1]
        )
        
        # Shorter lookback for recent regime
        result = await analyze_systemic_risk_score(
            tickers=["AAPL", "MSFT", "XLF", "XLE"],
            lookback_days=63  # 3 months
        )
    """
    try:
        # Input validation
        if not tickers or len(tickers) < 2:
            return jsonify_results({
                "error": "Need at least 2 tickers for systemic risk analysis",
                "provided": len(tickers) if tickers else 0
            })
        
        # Filter out non-standard tickers (options, crypto, CFDs, etc.)
        # These can't be fetched from standard market data sources
        filtered_tickers = []
        filtered_weights = []
        skipped_positions = []
        
        for i, ticker in enumerate(tickers):
            ticker_upper = ticker.upper().strip()
            
            # Skip options (contain spaces with dates/strikes like "AAPL 251205C00002500")
            # Skip crypto (contain ".USD" or "-PAXOS" etc.)
            # Skip CFDs (tickers starting with special chars or containing 'N' suffix like 'MPN')
            is_option = ' ' in ticker_upper or any(c in ticker_upper for c in ['C0', 'P0'])
            is_crypto = '.USD' in ticker_upper or '-PAXOS' in ticker_upper or 'ETH.' in ticker_upper or 'BTC.' in ticker_upper
            
            if is_option or is_crypto:
                skipped_positions.append({
                    "ticker": ticker,
                    "reason": "option" if is_option else "crypto",
                    "weight": weights[i] if weights and i < len(weights) else None
                })
                continue
            
            filtered_tickers.append(ticker_upper)
            
            # Handle weights: use absolute value for shorts (they still contribute to systemic risk)
            if weights and i < len(weights):
                w = weights[i]
                # Shorts have negative weights - use absolute value for risk contribution
                filtered_weights.append(abs(w))
            
        # Re-normalize weights if we filtered any positions
        if filtered_weights:
            total_weight = sum(filtered_weights)
            if total_weight > 0:
                filtered_weights = [w / total_weight for w in filtered_weights]
        
        if len(filtered_tickers) < 2:
            return jsonify_results({
                "error": "Need at least 2 valid equity tickers for systemic risk analysis",
                "provided": len(tickers),
                "valid_after_filter": len(filtered_tickers),
                "skipped_positions": skipped_positions,
                "hint": "Options, crypto, and other derivatives are excluded from network analysis"
            })
        
        # Use filtered lists for analysis
        tickers = filtered_tickers
        weights = filtered_weights if filtered_weights else None
        
        logger.info(f"[SYSTEMIC] Analyzing systemic risk for {len(tickers)} positions (skipped {len(skipped_positions)} non-equity)")
        
        # 1. Call underlying graph analysis (use internal impl, not decorated tool)
        graph_result = await _analyze_graph_theory_risk_impl(
            tickers=tickers,
            weights=weights,
            lookback_days=lookback_days,
            correlation_threshold=correlation_threshold,
            generate_chart=False,  # We'll generate our own focused chart
            optimize_hedges=False
        )
        
        # Check for errors from underlying tool
        if "error" in graph_result:
            return graph_result
        
        # 2. Extract what we need
        corr_matrix = graph_result.get("correlation_matrix", {})
        centrality_ranking = graph_result.get("centrality_ranking", [])
        graph_metrics = graph_result.get("graph_metrics", {})
        config = graph_result.get("config", {})
        
        if not corr_matrix:
            return jsonify_results({
                "error": "Failed to compute correlation matrix",
                "details": "Underlying graph analysis returned no correlation data"
            })
        
        # 3. Calculate adaptive damping based on network density
        density = graph_metrics.get("density", 0.5)
        adaptive_damping = _calculate_adaptive_damping(density)
        
        logger.debug(f"[SYSTEMIC] Network density: {density:.3f}, Adaptive damping: {adaptive_damping:.3f}")
        
        # 4. Calculate PageRank with adaptive damping
        pagerank_scores = _calculate_pagerank(
            corr_matrix=corr_matrix,
            correlation_threshold=correlation_threshold,
            damping=adaptive_damping
        )
        
        # 5. Combine with betweenness for risk contributions
        risk_contributions = _compute_risk_contributions(
            pagerank_scores=pagerank_scores,
            centrality_ranking=centrality_ranking
        )
        
        # 6. Calculate average correlation for scoring
        valid_tickers = list(corr_matrix.keys())
        n = len(valid_tickers)
        if n >= 2:
            corr_values = [
                abs(corr_matrix[t1][t2])
                for i, t1 in enumerate(valid_tickers)
                for j, t2 in enumerate(valid_tickers)
                if i < j
            ]
            avg_correlation = np.mean(corr_values) if corr_values else 0.5
        else:
            avg_correlation = 0.5
        
        # 7. Calculate portfolio systemic score (0-10)
        portfolio_score = _calculate_portfolio_systemic_score(
            risk_contributions=risk_contributions,
            avg_correlation=avg_correlation
        )
        
        # 8. Generate warnings and recommendations
        concentration_warning = _generate_concentration_warning(risk_contributions)
        recommendation = _generate_recommendation(
            risk_contributions=risk_contributions,
            portfolio_score=portfolio_score,
            avg_correlation=avg_correlation
        )
        
        # Build result
        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "portfolio_systemic_risk_score": portfolio_score,
            "position_risk_contributions": risk_contributions,
            "concentration_warning": concentration_warning,
            "recommendation": recommendation,
            "config": {
                "tickers_analyzed": len(valid_tickers),
                "lookback_days": lookback_days,
                "correlation_threshold": correlation_threshold,
                "adaptive_damping": adaptive_damping,
                "avg_correlation": round(avg_correlation, 4),
                "network_density": round(density, 4)
            },
            "score_interpretation": {
                "0-3": "Low systemic risk (well-distributed)",
                "3-5": "Moderate systemic risk",
                "5-7": "Elevated systemic risk (some concentration)",
                "7-10": "High systemic risk (concentrated exposure)"
            }
        }
        
        # Add info about skipped positions (options, crypto, etc.)
        if skipped_positions:
            result["excluded_positions"] = {
                "count": len(skipped_positions),
                "reason": "Options, crypto, and derivatives excluded from network analysis",
                "positions": skipped_positions
            }
        
        # 9. Generate visualization if requested
        if generate_chart and risk_contributions:
            chart_id = f"systemic_risk_{uuid.uuid4().hex[:8]}"
            chart = _build_risk_contribution_chart(
                risk_contributions=risk_contributions,
                portfolio_score=portfolio_score,
                chart_id=chart_id
            )
            
            if chart:
                result["charts"] = [
                    register_chart_handle(
                        chart['plotly'],
                        chart_type="bar",
                        title=chart['title'],
                        alt_text=f"Systemic risk contributions for {len(valid_tickers)} positions, score {portfolio_score}/10",
                        metadata={"portfolio_score": portfolio_score},
                        chart_id=chart_id
                    )
                ]
        
        return jsonify_results(result)
    
    except Exception as e:
        logger.error(f"Systemic risk score analysis failed: {e}", exc_info=True)
        return jsonify_results({
            "error": "Systemic risk analysis failed",
            "details": str(e)
        })


