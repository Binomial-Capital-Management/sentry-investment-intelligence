"""
Portfolio Geodesic Distance Tool

Main entry point for Information Geometry-based portfolio distance analysis.
Computes Fisher-Rao geodesic distance between portfolio return distributions.

Supports:
- Pairwise comparison (two specific portfolios)
- Baseline comparison (current vs historical regime)
- Multi-portfolio clustering (distance matrix)
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

import numpy as np

from agents import function_tool

from .data_fetcher import GeodesicDataFetcher
from .distribution_fitter import (
    fit_distribution,
    compute_fisher_information,
    format_estimation_quality
)
from .geodesic_math import (
    compute_all_distances,
    compute_reference_distances,
    interpret_distance,
    compute_distance_confidence_interval
)
from .charts import (
    generate_geodesic_charts, 
    generate_cluster_charts,
    generate_manifold_charts,
)
from .manifold import (
    compute_geodesic_path,
    embed_portfolios_on_manifold,
    compute_ricci_curvature_at_portfolio,
    compute_curvature_map,
    compute_natural_gradient,
    compute_geodesic_distance_proper,
)
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


def _build_summary(
    interpretation: Dict[str, Any],
    distances: Dict[str, Any],
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    name1: str,
    name2: str
) -> Dict[str, Any]:
    """Build user-friendly summary of the analysis."""
    
    similarity = interpretation["similarity_class"]
    percentile = interpretation["percentile"]
    breakdown = distances["fisher_rao"]["breakdown"]
    
    # Determine primary driver
    contributions = [
        ("mean return", breakdown["mean_contribution"]),
        ("volatility", breakdown["vol_contribution"]),
        ("tail behavior", breakdown.get("tail_contribution", 0)),
    ]
    primary = max(contributions, key=lambda x: x[1])
    
    # Build headline
    headline = f"These portfolios are {similarity.replace('_', ' ')}"
    
    # Build key finding
    vol1 = dist1["metrics"]["annualized_volatility"]
    vol2 = dist2["metrics"]["annualized_volatility"]
    ret1 = dist1["metrics"]["annualized_return"]
    ret2 = dist2["metrics"]["annualized_return"]
    
    vol_diff_pct = abs(vol2 - vol1) / vol1 * 100 if vol1 > 0 else 0
    ret_diff = abs(ret2 - ret1) * 100
    
    if primary[0] == "volatility":
        more_volatile = name2 if vol2 > vol1 else name1
        key_finding = f"Primary difference is volatility ({more_volatile} is {vol_diff_pct:.0f}% more volatile)"
    elif primary[0] == "mean return":
        key_finding = f"Primary difference is expected return ({ret_diff:.1f}% annualized difference)"
    else:
        key_finding = f"Primary difference is tail behavior (different extreme event frequency)"
    
    # Actionable insight
    if similarity == "NEARLY_IDENTICAL":
        actionable = "These portfolios would behave almost identically - one could substitute for the other"
    elif similarity == "SIMILAR":
        actionable = "These portfolios have similar risk profiles - limited diversification benefit from holding both"
    elif similarity == "MODERATELY_DIFFERENT":
        actionable = "Different enough to provide some diversification, but may still move together in stressed markets"
    else:
        actionable = "Statistically distinct - may provide meaningful diversification if correlations are also low"
    
    return {
        "headline": headline,
        "key_finding": key_finding,
        "actionable_insight": actionable,
        "primary_driver": primary[0],
        "primary_driver_contribution": f"{primary[1] * 100:.0f}%",
    }


def _build_practical_implications(
    dist1: Dict[str, Any],
    dist2: Dict[str, Any],
    distances: Dict[str, Any],
    interpretation: Dict[str, Any],
    correlation: Optional[float] = None
) -> Dict[str, Any]:
    """Build practical implications for trading/portfolio management."""
    
    vol1 = dist1["metrics"]["annualized_volatility"]
    vol2 = dist2["metrics"]["annualized_volatility"]
    vol_ratio = vol2 / vol1 if vol1 > 0 else 1
    
    # Diversification assessment
    if correlation is not None:
        # Use correlation percentile
        if correlation > 0.8:
            div_assessment = "LIMITED"
            div_explanation = f"High correlation ({correlation:.2f}) limits diversification benefit"
        elif correlation > 0.5:
            div_assessment = "MODERATE"
            div_explanation = f"Moderate correlation ({correlation:.2f}) provides some diversification"
        else:
            div_assessment = "GOOD"
            div_explanation = f"Lower correlation ({correlation:.2f}) suggests meaningful diversification"
    else:
        # Use distance as proxy
        percentile = interpretation["percentile"]
        if percentile > 70:
            div_assessment = "POTENTIALLY_GOOD"
            div_explanation = "Statistically different distributions may indicate diversification potential"
        else:
            div_assessment = "UNCERTAIN"
            div_explanation = "Similar distributions - check correlation for diversification benefit"
    
    # Substitution risk
    if abs(vol_ratio - 1) > 0.3:
        sub_assessment = "HIGH"
        change = "increase" if vol_ratio > 1 else "decrease"
        sub_explanation = f"Swapping would {change} volatility by ~{abs(vol_ratio - 1) * 100:.0f}%"
    elif abs(vol_ratio - 1) > 0.1:
        sub_assessment = "MODERATE"
        sub_explanation = f"Some risk profile change (volatility ratio: {vol_ratio:.2f})"
    else:
        sub_assessment = "LOW"
        sub_explanation = "Similar risk profiles - substitution impact would be minimal"
    
    # Regime sensitivity
    tail1 = dist1["tail_analysis"]["tail_fatness_ratio"]
    tail2 = dist2["tail_analysis"]["tail_fatness_ratio"]
    
    if abs(tail1 - tail2) < 0.5:
        regime_assessment = "SIMILAR"
        regime_explanation = "Similar tail behavior - both would react similarly to extreme events"
    else:
        regime_assessment = "DIFFERENT"
        fatter = "first" if tail1 > tail2 else "second"
        regime_explanation = f"Different tail risk - {fatter} portfolio more exposed to extremes"
    
    return {
        "diversification_value": {
            "assessment": div_assessment,
            "explanation": div_explanation,
        },
        "substitution_risk": {
            "assessment": sub_assessment,
            "explanation": sub_explanation,
            "volatility_ratio": float(vol_ratio),
        },
        "regime_sensitivity": {
            "assessment": regime_assessment,
            "explanation": regime_explanation,
        },
    }


async def analyze_portfolio_geodesic_distance_internal(
    # Portfolio A specification
    tickers_a: List[str],
    weights_a: Optional[List[float]] = None,
    name_a: str = "Portfolio A",
    
    # Portfolio B specification (optional - for pairwise mode)
    tickers_b: Optional[List[str]] = None,
    weights_b: Optional[List[float]] = None,
    name_b: str = "Portfolio B",
    
    # Multi-portfolio mode (JSON string)
    portfolios_json: Optional[str] = None,
    
    # Constituent comparison mode
    compare_constituents: bool = False,
    
    # Analysis settings
    lookback_days: int = 252,
    distribution: str = "auto",
    
    # Interpretation thresholds (configurable percentiles)
    threshold_very_different: float = 90.0,
    threshold_moderately_different: float = 70.0,
    threshold_similar: float = 30.0,
    
    # Output options
    generate_charts: bool = True,
    
    # ACTUAL PHYSICS OPTIONS
    include_geodesic_path: bool = False,  # Disabled by default - too complex
    include_curvature_analysis: bool = False,  # Disabled by default - too complex
    include_natural_gradient: bool = False,
    include_manifold_embedding: bool = True,  # This is the main visualization
) -> Dict[str, Any]:
    """
    Compute Fisher-Rao geodesic distance between portfolio return distributions.
    
    Uses Information Geometry to measure the "true" statistical distance between
    portfolios on the manifold of probability distributions.
    
    Args:
        tickers_a: List of ticker symbols for Portfolio A
        weights_a: Portfolio A weights (equal-weight if None)
        name_a: Display name for Portfolio A
        tickers_b: List of ticker symbols for Portfolio B (optional)
        weights_b: Portfolio B weights (equal-weight if None)
        name_b: Display name for Portfolio B
        portfolios_json: JSON string for multi-portfolio mode, e.g. '[{"tickers":["AAPL","MSFT"],"weights":[0.5,0.5],"name":"Tech"}]'
        compare_constituents: If True, compare each ticker in tickers_a against each other (NxN matrix)
        lookback_days: Number of trading days of history (default 252 = 1 year)
        distribution: Distribution to fit - "normal", "t", or "auto" (BIC-based selection)
        threshold_very_different: Percentile cutoff for VERY_DIFFERENT (default 90)
        threshold_moderately_different: Percentile cutoff for MODERATELY_DIFFERENT (default 70)
        threshold_similar: Percentile cutoff for SIMILAR (default 30)
        generate_charts: Whether to generate Plotly visualizations
        include_geodesic_path: Compute the shortest path through portfolio manifold
        include_curvature_analysis: Compute stability/curvature at portfolio position
        include_natural_gradient: Compute geometry-aware optimization direction
        include_manifold_embedding: Embed portfolios on 2D manifold (for constituents/cluster)
        
    Returns:
        Dict containing:
        - summary: Plain-English headline, key finding, and actionable insight
        - distributions: Fitted distribution parameters with explanations
        - distance_analysis: Fisher-Rao distance with breakdown and percentile
        - estimation_quality: Cramér-Rao bounds and confidence intervals
        - practical_implications: Diversification, substitution, and regime assessments
        - charts: Plotly figures (if generate_charts=True)
        
    Example:
        result = await analyze_portfolio_geodesic_distance(
            tickers_a=["AAPL", "MSFT", "GOOGL"],
            weights_a=[0.4, 0.3, 0.3],
            name_a="Tech Growth",
            tickers_b=["VTI", "BND"],
            weights_b=[0.6, 0.4],
            name_b="60/40 Balanced"
        )
    """
    start_time = datetime.now()
    
    # Build similarity thresholds from parameters
    similarity_thresholds = {
        "very_different": threshold_very_different,
        "moderately_different": threshold_moderately_different,
        "similar": threshold_similar,
    }
    
    try:
        # =====================================================================
        # STEP 1: Fetch portfolio returns
        # =====================================================================
        logger.info(f"Fetching data for geodesic distance analysis")
        
        fetcher = GeodesicDataFetcher()
        await fetcher.connect()
        
        try:
            # Fetch Portfolio A
            portfolio_a = await fetcher.fetch_portfolio_returns(
                tickers=tickers_a,
                weights=weights_a,
                lookback_days=lookback_days,
                name=name_a
            )
            
            if not portfolio_a:
                return {
                    "status": "error",
                    "error": f"Failed to fetch data for {name_a}",
                    "tickers": tickers_a,
                }
            
            # Parse portfolios_json if provided
            portfolio_list = None
            if portfolios_json:
                try:
                    import json
                    portfolio_list = json.loads(portfolios_json)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse portfolios_json: {e}")
            
            # Determine mode
            if compare_constituents and len(tickers_a) > 1:
                # Compare each ticker in tickers_a against each other
                mode = "constituents"
                portfolios = []
                for ticker in tickers_a:
                    single = await fetcher.fetch_portfolio_returns(
                        tickers=[ticker],
                        weights=[1.0],
                        lookback_days=lookback_days,
                        name=ticker
                    )
                    if single:
                        portfolios.append(single)
            elif portfolio_list:
                mode = "cluster"
                portfolios = await fetcher.fetch_multiple_portfolios(
                    portfolio_list,
                    lookback_days=lookback_days
                )
                portfolios.insert(0, portfolio_a)
            elif tickers_b:
                mode = "pairwise"
                portfolio_b = await fetcher.fetch_portfolio_returns(
                    tickers=tickers_b,
                    weights=weights_b,
                    lookback_days=lookback_days,
                    name=name_b
                )
                if not portfolio_b:
                    return {
                        "status": "error",
                        "error": f"Failed to fetch data for {name_b}",
                        "tickers": tickers_b,
                    }
                portfolios = [portfolio_a, portfolio_b]
            else:
                # Single portfolio - if 3+ tickers, treat as constituents for manifold embedding
                logger.info(f"[MODE] Single portfolio mode check: len(tickers_a)={len(tickers_a)}, include_manifold_embedding={include_manifold_embedding}")
                if len(tickers_a) >= 3 and include_manifold_embedding:
                    # Treat each ticker as a separate portfolio for manifold visualization
                    mode = "constituents"
                    logger.info(f"[MODE] Setting mode=constituents, creating {len(tickers_a)} individual ticker portfolios")
                    portfolios = []
                    for ticker in tickers_a:
                        single = await fetcher.fetch_portfolio_returns(
                            tickers=[ticker],
                            weights=[1.0],
                            lookback_days=lookback_days,
                            name=ticker
                        )
                        if single:
                            portfolios.append(single)
                    # Also add the full portfolio for comparison (ensure it has the correct name)
                    portfolio_a["name"] = name_a  # Ensure original name is preserved
                    portfolios.append(portfolio_a)
                    logger.info(f"[MODE] Created {len(portfolios)} portfolios (incl. combined)")
                else:
                    # Single portfolio - just describe its distribution
                    mode = "single"
                    portfolios = [portfolio_a]
                    logger.info(f"[MODE] mode=single")
                
        finally:
            await fetcher.cleanup()
        
        # =====================================================================
        # STEP 2: Fit distributions
        # =====================================================================
        logger.info("Fitting distributions to portfolio returns")
        
        fitted_distributions = []
        for p in portfolios:
            dist = fit_distribution(p["returns"], method=distribution)
            dist["portfolio_name"] = p["name"]
            fitted_distributions.append(dist)
        
        # =====================================================================
        # STEP 3: Compute distances and interpret
        # =====================================================================
        
        if mode == "pairwise":
            dist1, dist2 = fitted_distributions[0], fitted_distributions[1]
            
            # Compute all distance metrics
            distances = compute_all_distances(dist1, dist2)
            
            # Compute reference distances for percentile calculation
            returns_arrays = [np.array(p["returns"]) for p in portfolios]
            reference_distances = compute_reference_distances(returns_arrays, n_samples=50)
            
            # Interpret using percentiles (data-driven)
            interpretation = interpret_distance(
                distances["fisher_rao"]["value"],
                reference_distances,
                similarity_thresholds
            )
            
            # Confidence interval for distance
            distance_ci = compute_distance_confidence_interval(dist1, dist2)
            
            # Fisher information and estimation quality
            fisher1 = compute_fisher_information(dist1)
            fisher2 = compute_fisher_information(dist2)
            estimation1 = format_estimation_quality(fisher1, dist1)
            estimation2 = format_estimation_quality(fisher2, dist2)
            
            # Build summary
            summary = _build_summary(
                interpretation, distances, dist1, dist2, name_a, name_b
            )
            
            # Compute correlation for practical implications
            returns_a = np.array(portfolios[0]["returns"])
            returns_b = np.array(portfolios[1]["returns"])
            min_len = min(len(returns_a), len(returns_b))
            correlation = float(np.corrcoef(returns_a[-min_len:], returns_b[-min_len:])[0, 1])
            
            # Build practical implications
            implications = _build_practical_implications(
                dist1, dist2, distances, interpretation, correlation
            )
            
            # Build result
            result = {
                "status": "success",
                "mode": "pairwise",
                
                "summary": summary,
                
                "distributions": {
                    name_a: {
                        "type": dist1["type"],
                        "type_explanation": dist1["type_explanation"],
                        "params": dist1["params"],
                        "metrics": dist1["metrics"],
                        "tail_analysis": dist1["tail_analysis"],
                    },
                    name_b: {
                        "type": dist2["type"],
                        "type_explanation": dist2["type_explanation"],
                        "params": dist2["params"],
                        "metrics": dist2["metrics"],
                        "tail_analysis": dist2["tail_analysis"],
                    },
                },
                
                "distance_analysis": {
                    "geodesic_distance": {
                        "value": distances["fisher_rao"]["value"],
                        "percentile": interpretation["percentile"],
                        "percentile_explanation": f"This distance is larger than {interpretation['percentile']:.0f}% of portfolio pairs",
                        "interpretation": interpretation["interpretation"],
                        "similarity_class": interpretation["similarity_class"],
                    },
                    "what_drives_the_difference": {
                        "mean_return_contribution": {
                            "value": distances["fisher_rao"]["breakdown"]["mean_contribution"],
                            "percent_of_total": f"{distances['fisher_rao']['breakdown']['mean_contribution'] * 100:.0f}%",
                        },
                        "volatility_contribution": {
                            "value": distances["fisher_rao"]["breakdown"]["vol_contribution"],
                            "percent_of_total": f"{distances['fisher_rao']['breakdown']['vol_contribution'] * 100:.0f}%",
                        },
                        "tail_behavior_contribution": {
                            "value": distances["fisher_rao"]["breakdown"].get("tail_contribution", 0),
                            "percent_of_total": f"{distances['fisher_rao']['breakdown'].get('tail_contribution', 0) * 100:.0f}%",
                        },
                    },
                    "alternative_metrics": {
                        "kl_divergence_symmetric": distances["kl_divergence"]["symmetric"],
                        "wasserstein_distance": distances["wasserstein"],
                    },
                    "confidence_interval": distance_ci,
                },
                
                "estimation_quality": {
                    name_a: estimation1,
                    name_b: estimation2,
                },
                
                "practical_implications": implications,
                
                "correlation": correlation,
                
                "metadata": {
                    "lookback_days": lookback_days,
                    "observations": min(dist1["fit_quality"]["n_observations"], 
                                       dist2["fit_quality"]["n_observations"]),
                    "distribution_method": distribution,
                    "thresholds_used": similarity_thresholds,
                    "skipped_tickers": {
                        name_a: portfolios[0].get("skipped_tickers", []),
                        name_b: portfolios[1].get("skipped_tickers", []) if len(portfolios) > 1 else [],
                    },
                },
            }
            
            # =================================================================
            # ACTUAL PHYSICS COMPUTATIONS
            # =================================================================
            manifold_physics = {}
            physics_charts = []
            
            # Build returns matrix for manifold computations
            all_tickers = list(set(tickers_a) | set(tickers_b or []))
            
            if include_geodesic_path or include_curvature_analysis or include_natural_gradient:
                try:
                    # Get raw returns for each ticker
                    ticker_returns = {}
                    for p in portfolios:
                        for ticker, rets in zip(p.get("tickers", []), p.get("ticker_returns", {}).values()):
                            ticker_returns[ticker] = rets
                    
                    # Build returns matrix (T x N)
                    if ticker_returns:
                        all_tickers_sorted = sorted(ticker_returns.keys())
                        min_len = min(len(r) for r in ticker_returns.values())
                        returns_matrix = np.column_stack([
                            np.array(ticker_returns[t])[-min_len:] 
                            for t in all_tickers_sorted
                        ])
                        
                        # Build weight vectors
                        weights_a = np.zeros(len(all_tickers_sorted))
                        weights_b = np.zeros(len(all_tickers_sorted))
                        
                        w_a = portfolios[0].get("weights", [1.0/len(tickers_a)] * len(tickers_a))
                        for i, t in enumerate(tickers_a):
                            if t in all_tickers_sorted:
                                weights_a[all_tickers_sorted.index(t)] = w_a[i] if i < len(w_a) else 1.0/len(tickers_a)
                        weights_a /= weights_a.sum()
                        
                        if tickers_b:
                            w_b = portfolios[1].get("weights", [1.0/len(tickers_b)] * len(tickers_b))
                            for i, t in enumerate(tickers_b):
                                if t in all_tickers_sorted:
                                    weights_b[all_tickers_sorted.index(t)] = w_b[i] if i < len(w_b) else 1.0/len(tickers_b)
                            weights_b /= weights_b.sum()
                        
                        # Geodesic path between portfolios
                        if include_geodesic_path and tickers_b:
                            geodesic_path = compute_geodesic_path(
                                weights_a, weights_b, returns_matrix, n_steps=20
                            )
                            manifold_physics["geodesic_path"] = geodesic_path
                            
                            # Proper geodesic distance
                            geo_dist = compute_geodesic_distance_proper(
                                weights_a, weights_b, returns_matrix
                            )
                            manifold_physics["geodesic_distance_proper"] = geo_dist
                        
                        # Curvature at portfolio A
                        if include_curvature_analysis:
                            curvature_a = compute_ricci_curvature_at_portfolio(
                                weights_a, returns_matrix
                            )
                            manifold_physics["curvature_portfolio_a"] = curvature_a
                            
                            # Curvature map around portfolio A
                            curv_map = compute_curvature_map(
                                weights_a, returns_matrix, grid_size=8
                            )
                            manifold_physics["curvature_map"] = curv_map
                        
                        # Natural gradient for optimization
                        if include_natural_gradient:
                            nat_grad = compute_natural_gradient(
                                weights_a, returns_matrix, objective="sharpe"
                            )
                            manifold_physics["natural_gradient"] = nat_grad
                            
                except Exception as e:
                    logger.warning(f"Manifold physics computation failed: {e}")
                    manifold_physics["error"] = str(e)
            
            # Add manifold physics to result
            if manifold_physics:
                result["manifold_physics"] = manifold_physics
            
            # Generate charts - prioritize simplicity
            if generate_charts:
                charts = []
                
                # For pairwise mode, only show essential charts
                # Skip the complex physics visualizations unless explicitly requested
                if include_geodesic_path and manifold_physics.get("geodesic_path"):
                    # Only add geodesic path if explicitly requested
                    physics_charts = generate_manifold_charts(
                        geodesic_path=manifold_physics.get("geodesic_path"),
                        curvature_map=None,  # Skip curvature by default
                        natural_gradient=None,  # Skip natural gradient by default
                        asset_names=all_tickers,
                        name_start=name_a,
                        name_end=name_b,
                    )
                    charts.extend(physics_charts)
                else:
                    # Default: just show distribution comparison
                    basic_charts = generate_geodesic_charts(
                        dist1, dist2, distances, interpretation,
                        estimation1, estimation2, name_a, name_b
                    )
                    charts.extend(basic_charts)
                
                result["charts"] = wrap_plotly_charts(charts, default_type="geodesic_distance")
            
            # Build interpretation string
            elapsed = (datetime.now() - start_time).total_seconds()
            result["interpretation"] = (
                f"{name_a} and {name_b} are {interpretation['similarity_class'].replace('_', ' ')} "
                f"({interpretation['percentile']:.0f}th percentile). "
                f"{summary['key_finding']}. "
                f"{implications['diversification_value']['explanation']}."
            )
            
            logger.info(f"Analysis complete in {elapsed:.2f}s")
            return result
            
        elif mode in ("cluster", "constituents"):
            # Multi-portfolio / constituent clustering
            n = len(portfolios)
            distance_matrix = np.zeros((n, n))
            portfolio_names = [p["name"] for p in portfolios]
            
            for i in range(n):
                for j in range(i + 1, n):
                    distances = compute_all_distances(
                        fitted_distributions[i],
                        fitted_distributions[j]
                    )
                    distance_matrix[i, j] = distances["fisher_rao"]["value"]
                    distance_matrix[j, i] = distances["fisher_rao"]["value"]
            
            # Find most/least similar pairs
            triu_indices = np.triu_indices(n, k=1)
            triu_distances = distance_matrix[triu_indices]
            if len(triu_distances) > 0:
                min_idx = np.argmin(triu_distances)
                max_idx = np.argmax(triu_distances)
                most_similar = (portfolio_names[triu_indices[0][min_idx]], 
                               portfolio_names[triu_indices[1][min_idx]],
                               float(triu_distances[min_idx]))
                most_different = (portfolio_names[triu_indices[0][max_idx]], 
                                 portfolio_names[triu_indices[1][max_idx]],
                                 float(triu_distances[max_idx]))
            else:
                most_similar = most_different = None
            
            result = {
                "status": "success",
                "mode": mode,
                "portfolio_names": portfolio_names,
                # Removed: distance_matrix (n×n array, embedded in charts for heatmap)
                "distance_matrix_summary": {
                    "size": f"{n}x{n}",
                    "n_pairs": len(triu_distances) if len(triu_distances) > 0 else 0,
                },
                "distributions": {
                    p["name"]: {
                        "type": d["type"],
                        "metrics": d["metrics"],
                        "tail_analysis": d["tail_analysis"],
                    }
                    for p, d in zip(portfolios, fitted_distributions)
                },
                "summary": {
                    "n_items": n,
                    "mean_distance": float(triu_distances.mean()) if len(triu_distances) > 0 else 0,
                    "max_distance": float(distance_matrix.max()),
                    "min_nonzero_distance": float(triu_distances.min()) if len(triu_distances) > 0 else 0,
                    "most_similar_pair": {
                        "items": [most_similar[0], most_similar[1]] if most_similar else [],
                        "distance": most_similar[2] if most_similar else 0,
                    },
                    "most_different_pair": {
                        "items": [most_different[0], most_different[1]] if most_different else [],
                        "distance": most_different[2] if most_different else 0,
                    },
                },
                "interpretation": (
                    f"Analyzed {n} {'constituents' if mode == 'constituents' else 'portfolios'}. "
                    f"Most similar: {most_similar[0]} & {most_similar[1]} (d={most_similar[2]:.3f}). "
                    f"Most different: {most_different[0]} & {most_different[1]} (d={most_different[2]:.3f})."
                ) if most_similar and most_different else f"Analyzed {n} items.",
            }
            
            # =================================================================
            # MANIFOLD EMBEDDING FOR CLUSTER/CONSTITUENTS
            # =================================================================
            embedding_data = None
            logger.info(f"[MANIFOLD] include_manifold_embedding={include_manifold_embedding}, len(portfolios)={len(portfolios)}")
            
            if include_manifold_embedding and len(portfolios) >= 3:
                try:
                    # Build returns data dict
                    returns_data = {}
                    for p in portfolios:
                        ticker_returns = p.get("ticker_returns", {})
                        logger.info(f"[MANIFOLD] Portfolio '{p.get('name')}' has {len(ticker_returns)} ticker_returns")
                        for ticker, rets in ticker_returns.items():
                            if ticker not in returns_data:
                                returns_data[ticker] = np.array(rets)
                    
                    logger.info(f"[MANIFOLD] Built returns_data with {len(returns_data)} tickers")
                    
                    # Build portfolio specs for embedding
                    portfolio_specs = []
                    for p in portfolios:
                        portfolio_specs.append({
                            "name": p["name"],
                            "tickers": p.get("tickers", []),
                            "weights": p.get("weights", []),
                        })
                    
                    if returns_data:
                        # Pass the precomputed distance matrix to avoid expensive recomputation
                        embedding_data = embed_portfolios_on_manifold(
                            portfolio_specs, returns_data, method="mds",
                            precomputed_distances=distance_matrix
                        )
                        logger.info(f"[MANIFOLD] Embedding result: {'error' in embedding_data if embedding_data else 'None'}")
                        if embedding_data and "embedding" in embedding_data:
                            logger.info(f"[MANIFOLD] Embedding has {len(embedding_data['embedding'])} portfolios")
                        result["manifold_embedding"] = embedding_data
                    else:
                        logger.warning("[MANIFOLD] returns_data is empty, skipping embedding")
                        
                except Exception as e:
                    logger.warning(f"Manifold embedding failed: {e}", exc_info=True)
            
            if generate_charts:
                charts = []
                
                # For constituents mode: ONLY show the manifold embedding chart
                # This is the clean 3D network visualization the user wants
                if embedding_data and "embedding" in embedding_data:
                    from .charts import build_manifold_embedding_chart
                    plotly_data = build_manifold_embedding_chart(embedding_data)
                    logger.info(f"[MANIFOLD] Chart built: {type(plotly_data)}, has 'data': {'data' in plotly_data if isinstance(plotly_data, dict) else False}")
                    embedding_chart = {
                        "id": "manifold_embedding",
                        "title": "Portfolio Manifold Map",
                        "plotly": plotly_data,
                        "alt_text": "3D network map of portfolios preserving geodesic distances"
                    }
                    charts.append(embedding_chart)
                    logger.info(f"[MANIFOLD] Added embedding chart to charts list")
                else:
                    # Fallback: only show distance matrix if no embedding available
                    logger.info(f"[MANIFOLD] No embedding data, falling back to cluster charts")
                    cluster_charts = generate_cluster_charts(distance_matrix, portfolio_names)
                    charts.extend(cluster_charts)
                
                logger.info(f"[MANIFOLD] Total charts: {len(charts)}")
                result["charts"] = wrap_plotly_charts(charts, default_type="geodesic_cluster")
            
            return result
            
        else:
            # Single portfolio - just describe distribution
            dist = fitted_distributions[0]
            fisher = compute_fisher_information(dist)
            estimation = format_estimation_quality(fisher, dist)
            
            return {
                "status": "success",
                "mode": "single",
                "portfolio_name": name_a,
                "distribution": {
                    "type": dist["type"],
                    "type_explanation": dist["type_explanation"],
                    "params": dist["params"],
                    "metrics": dist["metrics"],
                    "tail_analysis": dist["tail_analysis"],
                },
                "estimation_quality": estimation,
                "interpretation": (
                    f"{name_a} returns follow a {dist['type']} distribution. "
                    f"{dist['tail_analysis']['interpretation']}. "
                    f"Estimation reliability: {estimation['reliability']}."
                ),
            }
            
    except Exception as e:
        logger.error(f"Geodesic distance analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "metadata": {
                "tickers_a": tickers_a,
                "tickers_b": tickers_b,
            }
        }


@function_tool
async def analyze_portfolio_geodesic_distance(
    tickers_a: List[str],
    weights_a: Optional[List[float]] = None,
    name_a: str = "Portfolio A",
    tickers_b: Optional[List[str]] = None,
    weights_b: Optional[List[float]] = None,
    name_b: str = "Portfolio B",
    lookback_days: int = 252,
    generate_charts: bool = True,
) -> Dict[str, Any]:
    """
    Compute Fisher-Rao geodesic distance between portfolio return distributions.
    
    For a SINGLE portfolio with 3+ tickers: generates a 3D manifold embedding chart
    showing how each ticker relates to others in risk space.
    
    For TWO portfolios: computes geodesic distance between them.
    """
    return await analyze_portfolio_geodesic_distance_internal(
        tickers_a=tickers_a,
        weights_a=weights_a,
        name_a=name_a,
        tickers_b=tickers_b,
        weights_b=weights_b,
        name_b=name_b,
        lookback_days=lookback_days,
        generate_charts=generate_charts,
        include_manifold_embedding=True,  # Always enable for 3D chart
    )

