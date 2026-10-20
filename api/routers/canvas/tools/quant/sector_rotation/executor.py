"""Canvas executor for Sector Rotation tool."""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def execute_sector_rotation(
    user_id: str,
    org_id: Optional[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute sector rotation analysis for Canvas.
    
    Detects capital rotation between market sectors using options flow data
    (delta, vega, premium) to identify where institutional money is flowing.
    """
    from core.agents.quant_tools.sector_rotation import analyze_sector_rotation_flow_internal
    from .charts import (
        build_sector_signals_chart,
        build_factor_heatmap_chart,
        build_regime_indicator_chart,
    )
    
    # Extract parameters
    use_regime = params.get("use_regime", True)
    use_anomaly = params.get("use_anomaly", False)
    include_vega = params.get("include_vega", True)
    
    logger.info("Executing sector rotation analysis")
    
    try:
        # Call internal function
        result = await analyze_sector_rotation_flow_internal(
            sectors=None,  # Use all 11 GICS sectors
            date=None,  # Today
            include_vega_flow=include_vega,
            use_regime_classifier=use_regime,
            use_anomaly_detector=use_anomaly,
            generate_charts=False,  # We build our own Canvas-style charts
        )
        
        if result.get("status") == "error":
            return {
                "status": "error",
                "error": result.get("error", "Sector rotation analysis failed"),
                "charts": {},
                "metric_cards": [],
                "stats_table": [],
            }
        
        # Extract data
        rankings = result.get("rankings", [])
        sectors_data = result.get("sectors", {})
        regime_data = result.get("regime", {})
        anomalies_data = result.get("anomalies", {})
        summary = result.get("summary", {})
        
        # Get top bullish and bearish sectors
        top_bullish = [r for r in rankings[:3] if r.get("score", 0) > 0]
        top_bearish = [r for r in rankings[-3:] if r.get("score", 0) < 0]
        
        # Current regime
        current_regime = regime_data.get("regime", "unknown") if regime_data else "N/A"
        regime_confidence = regime_data.get("confidence", 0) if regime_data else 0
        
        # Sector signal scores for charts
        signal_scores = {r["sector"]: r["score"] for r in rankings}
        
        # Build factor matrix for heatmap
        factor_matrix = {}
        for sector, data in sectors_data.items():
            if isinstance(data, dict) and "factors" in data:
                factors = data["factors"]
                factor_matrix[sector] = {
                    "Delta": factors.get("delta_flow", {}).get("zscore", 0),
                    "Vega": factors.get("vega_flow", {}).get("zscore", 0),
                    "Premium": factors.get("net_premium", {}).get("zscore", 0),
                }
        
        # Build charts
        charts = {}
        
        # Chart 1: Sector signals bar chart
        signals_chart = build_sector_signals_chart(signal_scores)
        if signals_chart:
            charts["sector_signals"] = signals_chart
        
        # Chart 2: Factor heatmap
        if factor_matrix:
            heatmap_chart = build_factor_heatmap_chart(factor_matrix)
            if heatmap_chart:
                charts["factor_heatmap"] = heatmap_chart
        
        # Chart 3: Regime indicator (if regime detection enabled)
        if regime_data:
            regime_chart = build_regime_indicator_chart(current_regime, regime_confidence)
            if regime_chart:
                charts["regime"] = regime_chart
        
        logger.info(f"Built {len(charts)} charts for sector rotation")
        
        # Determine regime sentiment
        if current_regime == "risk_on":
            regime_sentiment = "positive"
        elif current_regime == "risk_off":
            regime_sentiment = "negative"
        else:
            regime_sentiment = "neutral"
        
        # Build metric cards
        metric_cards = [
            {
                "id": "regime",
                "label": "Market Regime",
                "value": current_regime.replace("_", " ").title() if current_regime != "N/A" else "N/A",
                "sentiment": regime_sentiment,
            },
            {
                "id": "top_bullish",
                "label": "Top Bullish",
                "value": top_bullish[0]["sector"].title() if top_bullish else "None",
                "sentiment": "positive" if top_bullish else "neutral",
            },
            {
                "id": "top_bearish",
                "label": "Top Bearish",
                "value": top_bearish[-1]["sector"].title() if top_bearish else "None",
                "sentiment": "negative" if top_bearish else "neutral",
            },
            {
                "id": "bullish_count",
                "label": "Bullish Sectors",
                "value": str(summary.get("bullish_count", 0)),
                "sentiment": "positive" if summary.get("bullish_count", 0) > 5 else "neutral",
            },
            {
                "id": "bearish_count",
                "label": "Bearish Sectors",
                "value": str(summary.get("bearish_count", 0)),
                "sentiment": "negative" if summary.get("bearish_count", 0) > 5 else "neutral",
            },
        ]
        
        # Add anomaly count if enabled
        if anomalies_data:
            anomaly_count = anomalies_data.get("detected_count", 0)
            metric_cards.append({
                "id": "anomalies",
                "label": "Anomalies",
                "value": str(anomaly_count),
                "sentiment": "negative" if anomaly_count > 0 else "positive",
                "description": "Unusual flow patterns detected",
            })
        
        # Build stats table
        stats_table = []
        
        # Rankings section
        for i, r in enumerate(rankings[:5]):
            sector = r["sector"]
            score = r["score"]
            signal = "BULLISH" if score > 0.5 else ("BEARISH" if score < -0.5 else "NEUTRAL")
            stats_table.append({
                "category": "Top Rankings",
                "metric": f"#{i+1} {sector.title()}",
                "value": f"{score:.2f}σ ({signal})",
            })
        
        # Bottom rankings
        for i, r in enumerate(rankings[-3:]):
            sector = r["sector"]
            score = r["score"]
            stats_table.append({
                "category": "Bottom Rankings",
                "metric": sector.title(),
                "value": f"{score:.2f}σ",
            })
        
        # Regime details
        if regime_data:
            stats_table.extend([
                {"category": "Regime", "metric": "Current", "value": current_regime.replace("_", " ").title()},
                {"category": "Regime", "metric": "Confidence", "value": f"{regime_confidence*100:.0f}%"},
                {"category": "Regime", "metric": "Market Delta Z", "value": f"{regime_data.get('market_delta_zscore', 0):.2f}"},
                {"category": "Regime", "metric": "Market Vega Z", "value": f"{regime_data.get('market_vega_zscore', 0):.2f}"},
            ])
        
        # Factor details for top sectors
        for sector in [r["sector"] for r in rankings[:3]]:
            sector_info = sectors_data.get(sector, {})
            factors = sector_info.get("factors", {})
            flow = sector_info.get("flow_snapshot", {})
            
            if factors:
                delta_z = factors.get("delta_flow", {}).get("zscore", 0)
                vega_z = factors.get("vega_flow", {}).get("zscore", 0)
                delta_raw = flow.get("delta_flow", 0)
                
                stats_table.append({
                    "category": f"{sector.title()} Details",
                    "metric": "Delta Flow",
                    "value": f"{delta_raw/1e6:.1f}M (z={delta_z:.2f})",
                })
                stats_table.append({
                    "category": f"{sector.title()} Details",
                    "metric": "Vega Flow Z",
                    "value": f"{vega_z:.2f}",
                })
        
        # Anomalies
        if anomalies_data:
            anomaly_sectors = anomalies_data.get("sectors", {})
            flagged = [s for s, is_anom in anomaly_sectors.items() if is_anom]
            if flagged:
                stats_table.append({
                    "category": "Anomalies",
                    "metric": "Flagged Sectors",
                    "value": ", ".join([s.title() for s in flagged[:4]]),
                })
        
        # Build summary text
        bullish_names = [r["sector"].title() for r in top_bullish[:2]]
        bearish_names = [r["sector"].title() for r in top_bearish[-2:]]
        
        summary_text = f"Sector rotation analysis: {current_regime.replace('_', ' ').title()} regime. "
        if bullish_names:
            summary_text += f"Bullish flow into {', '.join(bullish_names)}. "
        if bearish_names:
            summary_text += f"Bearish flow from {', '.join(bearish_names)}."
        
        return {
            "status": "success",
            "tool_id": "sector_rotation",
            "tickers": [r["sector"] for r in rankings],
            "weights": [],
            "metrics": {
                "regime": current_regime,
                "regime_confidence": regime_confidence,
                "bullish_count": summary.get("bullish_count", 0),
                "bearish_count": summary.get("bearish_count", 0),
            },
            "charts": charts,
            "metric_cards": metric_cards,
            "stats_table": stats_table,
            "summary": summary_text,
        }
        
    except Exception as e:
        logger.error(f"Sector rotation execution failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)[:300],
            "charts": {},
            "metric_cards": [],
            "stats_table": [],
        }
