"""
FX Carry Trade Screener Canvas Executor
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def execute_fx_carry(
    user_id: str,
    org_id: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute FX carry trade screener for Canvas."""
    from core.agents.alternatives_tools.forex_carry_screener_tool import screen_forex_carry_trades_internal
    from .charts import build_carry_ranking_chart
    
    # Extract parameters
    pairs = params.get('pairs', [])
    if not pairs:
        return {"status": "error", "error": "At least one FX pair is required"}
    
    # Convert array to CSV
    if isinstance(pairs, list):
        # Parse "Name (PAIR)" format if present
        parsed_pairs = []
        for pair in pairs:
            if '(' in pair and ')' in pair:
                ticker = pair.split('(')[1].split(')')[0].strip()
                parsed_pairs.append(ticker)
            else:
                parsed_pairs.append(pair)
        pairs_csv = ",".join(parsed_pairs)
    else:
        pairs_csv = pairs
    
    lookback_days = int(params.get('lookback_days', 180))
    use_regime_detection = params.get('use_regime_detection', False)
    
    try:
        logger.info(f"Screening FX carry trades: {pairs_csv}")
        
        # Call internal function (rates_json empty = auto-fetch from FRED)
        result = await screen_forex_carry_trades_internal(
            pairs_csv=pairs_csv,
            rates_json="",  # Auto-fetch rates from FRED
            lookback_days=lookback_days,
            vol_window=30,
            high_z_threshold=1.5,
            low_z_threshold=-1.0,
            use_regime_detection=use_regime_detection,
            regime_n_states=3,
            regime_features="volatility,vol_dynamics,momentum,correlation",
            generate_chart=False  # We'll build our own chart
        )
        
        if result.get("error"):
            return {"status": "error", "error": result["error"]}
        
        # Extract values
        mode = result.get("mode", "volatility_analysis")
        rankings = result.get("rankings", [])
        regime = result.get("regime", {})
        best_trade = result.get("best_trade", {})
        rates_used = result.get("rates_used", {})
        rates_source = result.get("parameters", {}).get("rates_source", "none")
        
        has_carry = mode == "carry_analysis"
        
        # Get top pair
        top_pair = rankings[0] if rankings else {}
        
        # Build metric cards
        metric_cards = []
        
        if has_carry and top_pair:
            metric_cards.extend([
                {
                    "id": "best_pair",
                    "label": "Best Carry Trade",
                    "value": top_pair.get("pair", "N/A"),
                    "sentiment": "positive",
                    "description": top_pair.get("direction", "")
                },
                {
                    "id": "risk_adj_carry",
                    "label": "Risk-Adjusted Carry",
                    "value": f"{top_pair.get('risk_adjusted_carry', 0):.3f}",
                    "sentiment": "positive" if top_pair.get('risk_adjusted_carry', 0) > 0 else "negative",
                    "description": f"Carry: {top_pair.get('carry_pct', 0):.2f}%"
                },
                {
                    "id": "volatility",
                    "label": "Volatility",
                    "value": f"{top_pair.get('volatility_pct', 0):.1f}%",
                    "sentiment": "positive" if top_pair.get('volatility_pct', 0) < 10 else "negative",
                    "description": "Annualized"
                },
            ])
        elif top_pair:
            metric_cards.extend([
                {
                    "id": "lowest_vol",
                    "label": "Lowest Volatility",
                    "value": top_pair.get("pair", "N/A"),
                    "sentiment": "positive",
                    "description": f"{top_pair.get('volatility_pct', 0):.1f}% annualized"
                },
            ])
        
        # Add regime card
        regime_name = regime.get("regime", "UNKNOWN")
        regime_favorable = regime.get("carry_favorable")
        metric_cards.append({
            "id": "regime",
            "label": "FX Regime",
            "value": regime_name.replace("_", " "),
            "sentiment": "positive" if regime_favorable else "negative" if regime_favorable is False else "neutral",
            "description": regime.get("detection_method", "z-score").upper()
        })
        
        # Build stats table
        stats_table = [
            {"category": "Analysis", "metric": "Pairs Analyzed", "value": str(len(rankings))},
            {"category": "Analysis", "metric": "Lookback Period", "value": f"{lookback_days} days"},
            {"category": "Analysis", "metric": "Mode", "value": mode.replace("_", " ").title()},
            {"category": "Rates", "metric": "Source", "value": rates_source.replace("_", " ").upper()},
            {"category": "Regime", "metric": "Classification", "value": regime_name.replace("_", " ")},
        ]
        
        if regime.get("volatility_z_score") is not None:
            stats_table.append({
                "category": "Regime", 
                "metric": "Vol Z-Score", 
                "value": f"{regime['volatility_z_score']:.2f}σ"
            })
        
        # Add top 3 pairs to stats
        for i, pair_data in enumerate(rankings[:3], 1):
            pair_name = pair_data.get("pair", "")
            if has_carry:
                value = f"{pair_data.get('risk_adjusted_carry', 0):.3f} (Carry: {pair_data.get('carry_pct', 0):+.2f}%)"
            else:
                value = f"{pair_data.get('volatility_pct', 0):.1f}%"
            stats_table.append({
                "category": f"Rank #{i}",
                "metric": pair_name,
                "value": value
            })
        
        # Build charts
        charts = {}
        
        carry_chart = build_carry_ranking_chart(
            rankings=rankings,
            has_carry=has_carry
        )
        if carry_chart:
            charts["carry_ranking"] = carry_chart
        
        # Format summary
        if best_trade:
            if has_carry:
                summary = (
                    f"FX Carry Screener: Best trade is {best_trade.get('pair', 'N/A')} "
                    f"({best_trade.get('direction', 'LONG')}) with risk-adjusted carry of {best_trade.get('risk_adjusted_carry', 0):.3f}. "
                    f"FX regime: {regime_name.replace('_', ' ')}. "
                    f"Rates sourced from {rates_source.upper()}."
                )
            else:
                summary = (
                    f"FX Volatility Screener: Lowest volatility pair is {best_trade.get('pair', 'N/A')} "
                    f"at {best_trade.get('volatility_pct', 0):.1f}%. "
                    f"FX regime: {regime_name.replace('_', ' ')}. "
                    f"No interest rates available for carry analysis."
                )
        else:
            summary = f"FX Screener analyzed {len(rankings)} pairs. Regime: {regime_name.replace('_', ' ')}."
        
        return {
            "status": "success",
            "tool_id": "fx_carry",
            "tickers": [p.get("pair", "") for p in rankings],
            "weights": [],
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "metrics": {
                "mode": mode,
                "has_carry": has_carry,
                "regime": regime_name,
                "pairs_analyzed": len(rankings),
                "rates_source": rates_source,
            },
            "summary": summary,
        }
    
    except Exception as e:
        logger.error(f"FX carry screener failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
