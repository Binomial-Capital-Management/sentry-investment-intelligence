"""
Cointegration Canvas Executor
"""
from typing import Dict, List, Any, Optional
import logging

from core.agents.quant_tools.cointegration_tool import identify_cointegrated_pairs_internal
from .charts import build_pvalue_heatmap, build_spread_chart, build_pairs_ranking_chart

logger = logging.getLogger(__name__)


async def execute_cointegration(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute cointegration analysis for Canvas.
    
    Cointegration is for pairs trading - users provide specific tickers to test,
    not portfolios. Typical use: GLD vs GDX, SPY vs QQQ, etc.
    """
    try:
        # Get tickers directly - no portfolio resolution for cointegration
        tickers = params.get("tickers", [])
        
        if not tickers or len(tickers) < 2:
            return {"status": "error", "error": "Need at least 2 tickers for cointegration (e.g., GLD, GDX)"}
        
        logger.info(f"Running cointegration analysis for {len(tickers)} tickers: {tickers}")
        
        # Call internal cointegration function
        result = await identify_cointegrated_pairs_internal(
            tickers=tickers,
            lookback_period=params.get("lookback_period", 252),
            significance_level=params.get("significance_level", 0.05),
            calculate_half_life=True,
            calculate_hurst_exponent=True,
            calculate_current_zscore=True,
        )
        
        if result.get("error"):
            return {"status": "error", "error": result.get("error"), "details": result.get("details")}
        
        valid_tickers = result.get("tickers", tickers)
        skipped_tickers = result.get("skipped_tickers", [])
        cointegrated_pairs = result.get("cointegrated_pairs", [])
        pvalue_matrix = result.get("pvalue_matrix", [])
        significance_level = result.get("significance_level", 0.05)
        
        # Build charts
        heatmap_chart = build_pvalue_heatmap(valid_tickers, pvalue_matrix, significance_level)
        ranking_chart = build_pairs_ranking_chart(cointegrated_pairs)
        
        charts = {}
        if heatmap_chart:
            charts["pvalue_heatmap"] = heatmap_chart
        if ranking_chart:
            charts["pairs_ranking"] = ranking_chart
        
        # Add spread chart for best pair
        significant_pairs = [p for p in cointegrated_pairs if p.get('significant')]
        if significant_pairs:
            best_pair = significant_pairs[0]
            spread_chart = build_spread_chart(
                best_pair['ticker_a'],
                best_pair['ticker_b'],
                best_pair.get('spread_data', {}),
                best_pair.get('hedge_ratio', 1.0),
                best_pair.get('current_zscore')
            )
            if spread_chart:
                charts["best_spread"] = spread_chart
        
        # Build metric cards
        metric_cards = _build_metric_cards(result, significant_pairs)
        
        if skipped_tickers:
            skipped_names = [s.get('ticker', str(s)) for s in skipped_tickers]
            metric_cards.append({
                "id": "skipped",
                "label": "Skipped Tickers",
                "value": ", ".join(skipped_names[:5]),
                "sentiment": "negative",
            })
        
        # Build stats table
        stats_table = _build_stats_table(result, cointegrated_pairs, significant_pairs)
        
        # Build metrics dict
        metrics = _extract_metrics(result)
        
        return {
            "status": "success",
            "tool_id": "cointegration",
            "tickers": valid_tickers,
            "weights": [],
            "metrics": metrics,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "charts": charts,
        }
        
    except Exception as e:
        logger.error(f"Cointegration execution failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:300]}


def _build_metric_cards(result: Dict[str, Any], significant_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build metric cards from cointegration results."""
    cards = []
    
    cards.append({
        "id": "pairs_tested",
        "label": "Pairs Tested",
        "value": str(result.get("pairs_tested", 0)),
        "sentiment": "neutral",
    })
    
    sig_count = result.get("significant_count", 0)
    cards.append({
        "id": "significant_pairs",
        "label": "Significant Pairs",
        "value": str(sig_count),
        "sentiment": "positive" if sig_count > 0 else "neutral",
    })
    
    # Best pair info
    if significant_pairs:
        best = significant_pairs[0]
        cards.append({
            "id": "best_pair",
            "label": "Best Pair",
            "value": f"{best['ticker_a']}/{best['ticker_b']}",
            "sentiment": "positive",
        })
        
        cards.append({
            "id": "best_pvalue",
            "label": "Best P-Value",
            "value": f"{best['p_value']:.4f}",
            "sentiment": "positive",
        })
        
        if best.get('half_life_days'):
            cards.append({
                "id": "half_life",
                "label": "Half-Life",
                "value": f"{best['half_life_days']:.1f} days",
                "sentiment": "neutral",
            })
        
        if best.get('current_signal'):
            signal = best['current_signal']
            cards.append({
                "id": "signal",
                "label": "Current Signal",
                "value": signal.replace("_", " "),
                "sentiment": "positive" if signal != "NO_SIGNAL" else "neutral",
            })
    
    return cards


def _build_stats_table(
    result: Dict[str, Any],
    cointegrated_pairs: List[Dict[str, Any]],
    significant_pairs: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """Build stats table from cointegration results."""
    rows = []
    
    # Analysis summary
    pairs_tested = result.get("pairs_tested", 0)
    significant_count = len(significant_pairs)
    sig_level = result.get("significance_level", 0.05)
    lookback = result.get("lookback_period", 252)
    
    rows.append({"category": "Analysis", "metric": "Pairs Tested", "value": f"{pairs_tested:,}"})
    rows.append({"category": "Analysis", "metric": "Significant Pairs", "value": f"{significant_count}"})
    rows.append({"category": "Analysis", "metric": "Significance Level", "value": f"{sig_level:.2%}"})
    rows.append({"category": "Analysis", "metric": "Lookback Period", "value": f"{lookback} days"})
    
    # Hit rate
    if pairs_tested > 0:
        hit_rate = significant_count / pairs_tested
        rows.append({"category": "Analysis", "metric": "Cointegration Rate", "value": f"{hit_rate:.1%}"})
    
    # Best opportunity (if any significant pairs)
    if significant_pairs:
        best = significant_pairs[0]
        rows.append({"category": "Best Pair", "metric": "Tickers", "value": f"{best['ticker_a']} / {best['ticker_b']}"})
        rows.append({"category": "Best Pair", "metric": "P-Value", "value": f"{best['p_value']:.6f}"})
        rows.append({"category": "Best Pair", "metric": "Hedge Ratio", "value": f"{best.get('hedge_ratio', 0):.4f}"})
        
        half_life = best.get('half_life_days')
        if half_life:
            rows.append({"category": "Best Pair", "metric": "Half-Life", "value": f"{half_life:.1f} days"})
        
        zscore = best.get('current_zscore')
        if zscore is not None:
            rows.append({"category": "Best Pair", "metric": "Current Z-Score", "value": f"{zscore:.3f}"})
        
        signal = best.get('current_signal')
        if signal:
            rows.append({"category": "Best Pair", "metric": "Signal", "value": signal})
    
    # All cointegrated pairs details
    if cointegrated_pairs:
        rows.append({"category": "All Pairs", "metric": "─" * 20, "value": "─" * 15})  # Divider
    
    for i, pair in enumerate(cointegrated_pairs[:8], 1):  # Top 8
        pair_name = f"{pair['ticker_a']}/{pair['ticker_b']}"
        signal = pair.get('current_signal', '-')
        zscore = pair.get('current_zscore')
        zscore_str = f"Z:{zscore:.2f}" if zscore is not None else ""
        half_life = pair.get('half_life_days')
        hl_str = f"HL:{half_life:.0f}d" if half_life else ""
        
        rows.append({
            "category": f"#{i} Pair",
            "metric": pair_name,
            "value": f"p={pair['p_value']:.4f} HR={pair.get('hedge_ratio', 0):.3f}",
            "pct": " | ".join(filter(None, [hl_str, zscore_str, signal])),
        })
    
    # Trading signals summary
    long_signals = sum(1 for p in significant_pairs if p.get('current_signal') == 'Long')
    short_signals = sum(1 for p in significant_pairs if p.get('current_signal') == 'Short')
    if long_signals or short_signals:
        rows.append({"category": "Signals", "metric": "Long Signals", "value": f"{long_signals}"})
        rows.append({"category": "Signals", "metric": "Short Signals", "value": f"{short_signals}"})
    
    return rows


def _extract_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract metrics for persistence."""
    return {
        "pairs_tested": result.get("pairs_tested"),
        "significant_count": result.get("significant_count"),
        "significance_level": result.get("significance_level"),
        "lookback_period": result.get("lookback_period"),
        "cointegrated_pairs": result.get("cointegrated_pairs", [])[:5],  # Top 5 only
    }

