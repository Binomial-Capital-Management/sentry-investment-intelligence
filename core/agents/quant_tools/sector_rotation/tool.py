"""
Sector Rotation Flow Tool - Main Entry Point

Detects capital rotation between market sectors using options flow data.
Inspired by Renaissance Technologies' multi-factor, statistically-validated approach.

=== WHAT IT DOES ===
Analyzes options flow (delta, vega, premium) across 11 GICS sectors to identify:
- Where institutional money is flowing TO (bullish signals)
- Where institutional money is flowing FROM (bearish signals)
- Unusual flow patterns that may indicate informed trading

=== DATA SOURCES ===
- Unusual Whales: Today's options flow (delta, vega, premium) - REAL-TIME SENTIMENT
- FMP: Historical sector ETF prices (XLK, XLF, XLE, etc.) - Z-SCORE BASELINE
- Computed: Cross-sectional z-scores, persistence, regime states

=== FACTORS (Signals Combined) ===
1. Delta Flow Z-Score: Net directional positioning vs. history
2. Vega Flow Momentum: Volatility demand acceleration
3. OTM Conviction: Call vs. put premium skew
4. Persistence: Consecutive days of same-direction flow
5. Relative Strength: Sector flow vs. market average

=== ML MODULES (Optional) ===
- Regime Classifier: HMM/RF to detect risk-on/risk-off/transition
- Lead-Lag Detector: Granger causality for predictive relationships
- Anomaly Detector: Isolation Forest for unusual flow patterns
- Ensemble: Stacking model for outperformance prediction

=== OUTPUTS ===
- Sector rankings by composite signal strength
- Factor breakdown per sector (which factors driving the signal)
- Regime classification (if enabled)
- Trade recommendations with sizing (if enabled)
- Visualization charts (if enabled)

=== EXAMPLE USE CASES ===
1. Daily sector rotation screen: Which sectors seeing inflows today?
2. Regime-aware allocation: Reduce equity in risk-off, rotate to defensives
3. Pair trades: Long strongest sector, short weakest
4. Anomaly alerts: Flag unusual activity for further research

All parameters configurable. Defaults are conservative (ML off, basic factors only).
"""

from typing import Dict, List, Optional, Any
import logging
import asyncio
from datetime import datetime
from agents import function_tool

logger = logging.getLogger(__name__)


# =============================================================================
# MASTER CONFIGURATION
# =============================================================================

DEFAULT_TOOL_CONFIG = {
    # Data fetching
    "fetch_timeout": 30,
    
    # Rate limiting (match nope_divergence_tool pattern)
    "request_delay_seconds": 0.5,  # Delay between sector fetches
    "batch_delay_seconds": 1.5,    # Delay between batches
    "max_concurrent": 3,           # Max concurrent fetches
    
    # UW flow_group names (lowercase, from uw_options_catalog.json)
    # These are the valid values for the greek-flow endpoint
    "default_sectors": [
        "technology", "healthcare", "financial services", "energy",
        "consumer cyclical", "consumer defensive", "industrials",
        "basic materials", "utilities", "real estate", "communication services"
    ],
    
    # Additional thematic groups available (optional)
    "thematic_groups": [
        "mag7", "semi", "cyber", "crypto", "china",
        "gold", "silver", "oil", "gas", "uranium",
        "airline", "bank", "reit", "refiners"
    ],
    
    # Feature flags - all OFF by default
    "include_vega_flow": False,
    "include_correlations": False,
    "include_seasonality": False,
    "include_etf_flows": False,
    "include_movers": False,
    "include_oi_change": False,
    
    # ML modules - all OFF by default
    "use_regime_classifier": False,
    "use_lead_lag_detector": False,
    "use_anomaly_detector": False,
    "use_ensemble": False,
    
    # Aggregation
    "aggregation_method": "equal_weighted",
    
    # Output
    "generate_trades": False,
    "generate_charts": True,
    "include_raw_data": False,
}


# =============================================================================
# MAIN FUNCTION
# =============================================================================

async def analyze_sector_rotation_flow_internal(
    # Data options
    sectors: Optional[List[str]] = None,
    date: Optional[str] = None,
    
    # Feature flags
    include_vega_flow: bool = False,
    include_correlations: bool = False,
    include_seasonality: bool = False,
    include_etf_flows: bool = False,
    include_movers: bool = False,
    include_oi_change: bool = False,
    
    # ML options
    use_regime_classifier: bool = False,
    use_lead_lag_detector: bool = False,
    use_anomaly_detector: bool = False,
    use_ensemble: bool = False,
    
    # Aggregation
    aggregation_method: str = "equal_weighted",
    
    # Output options
    generate_trades: bool = False,
    generate_charts: bool = True,  # Charts enabled by default
    include_raw_data: bool = False,
    
    # Custom configs (override defaults)
    factor_config: Optional[Dict] = None,
    aggregation_config: Optional[Dict] = None,
    regime_config: Optional[Dict] = None,
    trade_config: Optional[Dict] = None,
    chart_config: Optional[Dict] = None,
    validation_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Analyze sector rotation using options flow data.
    
    QUICK START:
        # Basic usage - just delta flow z-scores
        result = await analyze_sector_rotation_flow()
        
        # Full analysis with ML and trades
        result = await analyze_sector_rotation_flow(
            include_vega_flow=True,
            use_regime_classifier=True,
            use_anomaly_detector=True,
            generate_trades=True,
            generate_charts=True,
        )
    
    Args:
        sectors: List of sectors to analyze (None = all 11 GICS sectors)
        date: Date to analyze in YYYY-MM-DD format (None = today)
        
        --- FEATURE FLAGS (data enrichment) ---
        include_vega_flow: Add vega flow momentum factor
        include_correlations: Add cross-sector correlation data
        include_seasonality: Add historical seasonal patterns
        include_etf_flows: Add sector ETF inflow/outflow data
        include_movers: Add top movers within each sector
        include_oi_change: Add open interest change data
        
        --- ML MODULES (optional intelligence) ---
        use_regime_classifier: Enable HMM/RF market regime detection
            - Classifies market as: risk_on, risk_off, transition
            - Adjusts position sizing based on regime
        use_lead_lag_detector: Enable Granger causality analysis
            - Finds which sectors predict others
            - Useful for anticipating rotation
        use_anomaly_detector: Enable Isolation Forest anomaly detection
            - Flags unusual flow patterns
            - May indicate informed trading
        use_ensemble: Enable stacking ensemble predictions
            - Combines RF + GBM + LogReg
            - Predicts sector outperformance probability
        
        --- AGGREGATION METHOD ---
        aggregation_method: How to combine multiple factors
            - "equal_weighted": Simple average of z-scores (default)
            - "learned_weights": Ridge regression optimized weights
            - "regime_conditional": Different weights per regime
            - "ml_predictor": Gradient boosting direct prediction
        
        --- OUTPUT OPTIONS ---
        generate_trades: Generate actionable trade recommendations
            - Includes position sizing, conviction, rationale
            - Respects regime and anomaly context
        generate_charts: Generate visualization charts (base64 PNG)
            - Sector signal bars
            - Factor heatmap
            - Regime timeline
        include_raw_data: Include raw API responses in output
            - Useful for debugging
            - Increases response size significantly
        
        --- CUSTOM CONFIGS (advanced) ---
        factor_config: Override factor computation settings
        aggregation_config: Override aggregation settings
        regime_config: Override regime classifier settings
        trade_config: Override trade generation settings
        chart_config: Override chart styling settings
        validation_config: Override validation settings
    
    Returns:
        Dict containing:
            - status: "success" or "error"
            - timestamp: When analysis was run
            - config: Echo of configuration used
            - sectors: Per-sector factor breakdown
            - rankings: Sectors ranked by composite score
            - regime: Current market regime (if enabled)
            - anomalies: Unusual flow flags (if enabled)
            - trades: Trade recommendations (if enabled)
            - charts: Base64 encoded PNGs (if enabled)
            - summary: Human-readable summary
    """
    from .fetchers import SectorDataFetcher
    from .factors import (
        DeltaFlowFactor, VegaFlowFactor, OTMConvictionFactor,
        PersistenceFactor, RelativeStrengthFactor
    )
    from .aggregation import FactorAggregator
    
    result = {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "sectors": sectors,
            "date": date,
            "features": {
                "vega_flow": include_vega_flow,
                "correlations": include_correlations,
                "seasonality": include_seasonality,
                "etf_flows": include_etf_flows,
                "movers": include_movers,
                "oi_change": include_oi_change,
            },
            "ml": {
                "regime_classifier": use_regime_classifier,
                "lead_lag_detector": use_lead_lag_detector,
                "anomaly_detector": use_anomaly_detector,
                "ensemble": use_ensemble,
            },
            "aggregation_method": aggregation_method,
        },
        "sectors": {},
        "rankings": [],
    }
    
    # Initialize fetcher
    fetcher = SectorDataFetcher()
    
    try:
        await fetcher.connect()
        
        # Get sector list
        sector_list = sectors or DEFAULT_TOOL_CONFIG["default_sectors"]
        
        # Initialize factors
        delta_factor = DeltaFlowFactor(config=factor_config)
        vega_factor = VegaFlowFactor(config=factor_config) if include_vega_flow else None
        otm_factor = OTMConvictionFactor(config=factor_config)
        persistence_factor = PersistenceFactor(config=factor_config)
        rel_strength_factor = RelativeStrengthFactor(config=factor_config)
        
        # Initialize aggregator
        aggregator = FactorAggregator(
            method=aggregation_method,
            config=aggregation_config
        )
        
        # Initialize optional ML modules
        regime_classifier = None
        anomaly_detector = None
        lead_lag_detector = None
        ensemble_model = None
        current_regime = None
        anomalies = {}
        lead_lag_results = {}
        
        if use_regime_classifier:
            from .ml import RegimeClassifier
            regime_classifier = RegimeClassifier(config=regime_config)
        
        if use_anomaly_detector:
            from .ml import AnomalyDetector
            anomaly_detector = AnomalyDetector()
        
        if use_lead_lag_detector:
            from .ml import LeadLagDetector
            lead_lag_detector = LeadLagDetector()
        
        if use_ensemble:
            from .ml import EnsembleModel
            ensemble_model = EnsembleModel()
        
        # STEP 1: Fetch historical data from FMP for volatility context
        logger.info("Fetching historical sector ETF data from FMP...")
        historical_data = await fetcher.fetch_all_sector_histories(
            sectors=sector_list,
            lookback_days=60
        )
        logger.info(f"Got historical data for {len(historical_data)} sectors")
        
        # STEP 2: Fetch today's flow data for ALL sectors first (needed for cross-sectional)
        all_flow_data = {}
        request_delay = DEFAULT_TOOL_CONFIG.get("request_delay_seconds", 0.5)
        
        for i, sector in enumerate(sector_list):
            try:
                # Don't pass date - API defaults to last trading day which works correctly
                flow_data = await fetcher.fetch_greek_flow(flow_group=sector)
                if flow_data:
                    all_flow_data[sector] = flow_data
                    delta = flow_data.get('delta_flow', 0)
                    vega = flow_data.get('vega_flow', 0)
                    logger.info(f"Got flow for {sector}: delta={delta:,.0f}, vega={vega:,.0f}")
                else:
                    logger.warning(f"No flow data returned for {sector}")
                
                if i < len(sector_list) - 1:
                    await asyncio.sleep(request_delay)
            except Exception as e:
                logger.warning(f"Failed to fetch flow for {sector}: {e}")
                await asyncio.sleep(request_delay)
        
        logger.info(f"Total sectors with flow data: {len(all_flow_data)} / {len(sector_list)}")
        
        # STEP 3: Compute CROSS-SECTIONAL z-scores (the RIGHT approach)
        # Compare each sector's flow to ALL other sectors TODAY
        all_delta_flows = {}
        all_vega_flows = {}
        all_net_premiums = {}
        
        for sector, flow_data in all_flow_data.items():
            delta = flow_data.get("delta_flow", flow_data.get("directional_delta", 0)) or 0
            vega = flow_data.get("vega_flow", 0) or 0
            call_prem = flow_data.get("call_premium", 0) or 0
            put_prem = flow_data.get("put_premium", 0) or 0
            
            all_delta_flows[sector] = delta
            all_vega_flows[sector] = vega
            all_net_premiums[sector] = call_prem - put_prem
        
        # Cross-sectional z-scores: how does each sector compare to peers TODAY
        delta_zscores = fetcher.compute_cross_sectional_zscores(all_delta_flows)
        vega_zscores = fetcher.compute_cross_sectional_zscores(all_vega_flows)
        premium_zscores = fetcher.compute_cross_sectional_zscores(all_net_premiums)
        
        # STEP 4: REGIME DETECTION (must happen BEFORE aggregation!)
        if regime_classifier:
            try:
                import pandas as pd
                
                # Build feature matrix from raw flow data
                regime_features = pd.DataFrame([
                    {
                        "delta_zscore": delta_zscores.get(s, 0),
                        "vega_zscore": vega_zscores.get(s, 0),
                        "premium_zscore": premium_zscores.get(s, 0),
                    }
                    for s in sector_list if s in all_flow_data
                ])
                
                if len(regime_features) > 0:
                    # Aggregate market-wide signals for regime
                    market_delta = regime_features["delta_zscore"].mean()
                    market_vega = regime_features["vega_zscore"].mean()
                    vega_dispersion = regime_features["vega_zscore"].std()
                    
                    # Simple rule-based regime detection (robust without training)
                    if market_vega > 0.3 and vega_dispersion < 0.5:
                        current_regime = "risk_on"
                        regime_confidence = min(0.9, 0.5 + abs(market_vega))
                    elif market_vega < -0.3 or vega_dispersion > 1.0:
                        current_regime = "risk_off"
                        regime_confidence = min(0.9, 0.5 + abs(market_vega))
                    else:
                        current_regime = "transition"
                        regime_confidence = 0.5
                    
                    result["regime"] = {
                        "regime": current_regime,
                        "confidence": round(regime_confidence, 2),
                        "market_delta_zscore": round(market_delta, 4),
                        "market_vega_zscore": round(market_vega, 4),
                        "vega_dispersion": round(vega_dispersion, 4),
                    }
                    
                    logger.info(f"Detected regime: {current_regime} (confidence: {regime_confidence:.2f})")
                    
            except Exception as e:
                logger.warning(f"Regime detection failed: {e}")
                current_regime = "transition"
        
        # STEP 5: LEAD-LAG DETECTION (find predictive relationships)
        if lead_lag_detector and historical_data and len(historical_data) >= 3:
            try:
                import pandas as pd
                
                # Build return matrix for lead-lag analysis
                returns_dict = {}
                min_len = float('inf')
                
                for sector, hist in historical_data.items():
                    returns = hist.get("returns", [])
                    if returns and len(returns) >= 20:
                        returns_dict[sector] = returns[-30:]  # Last 30 days
                        min_len = min(min_len, len(returns_dict[sector]))
                
                if len(returns_dict) >= 3 and min_len >= 20:
                    # Align all series to same length
                    for sector in returns_dict:
                        returns_dict[sector] = returns_dict[sector][-min_len:]
                    
                    # Create DataFrames for lead-lag analysis
                    returns_df = pd.DataFrame(returns_dict)
                    
                    # Use returns as proxy for flow (we don't have historical flow)
                    lead_lag_result = lead_lag_detector.detect(
                        flow_data=returns_df,  # Using returns as flow proxy
                        return_data=returns_df
                    )
                    
                    if lead_lag_result.get("relationships"):
                        result["lead_lag"] = lead_lag_result
                        logger.info(f"Found {len(lead_lag_result.get('relationships', []))} lead-lag relationships")
                    
            except Exception as e:
                logger.warning(f"Lead-lag detection failed: {e}")
        
        # STEP 6: Build factor results for each sector (now with regime context!)
        all_signals = {}
        
        for sector in sector_list:
            if sector not in all_flow_data:
                result["sectors"][sector] = {"error": "No flow data"}
                continue
            
            flow_data = all_flow_data[sector]
            sector_history = historical_data.get(sector, {})
            
            # Extract raw values
            delta_flow = all_delta_flows.get(sector, 0)
            vega_flow = all_vega_flows.get(sector, 0)
            call_premium = flow_data.get("call_premium", 0) or 0
            put_premium = flow_data.get("put_premium", 0) or 0
            
            # Build factors using CROSS-SECTIONAL z-scores (not time-series!)
            factors = {
                "delta_flow": {
                    "raw_value": delta_flow,
                    "zscore": round(delta_zscores.get(sector, 0), 4),
                    "signal": "BULLISH" if delta_zscores.get(sector, 0) > 1.0 
                              else "BEARISH" if delta_zscores.get(sector, 0) < -1.0 
                              else "NEUTRAL"
                },
                "vega_flow": {
                    "raw_value": vega_flow,
                    "zscore": round(vega_zscores.get(sector, 0), 4),
                    "signal": "ADDING_VOL" if vega_zscores.get(sector, 0) > 0.5 
                              else "REDUCING_VOL" if vega_zscores.get(sector, 0) < -0.5 
                              else "STABLE"
                },
                "net_premium": {
                    "raw_value": call_premium - put_premium,
                    "zscore": round(premium_zscores.get(sector, 0), 4),
                    "signal": "CALL_HEAVY" if premium_zscores.get(sector, 0) > 0.5 
                              else "PUT_HEAVY" if premium_zscores.get(sector, 0) < -0.5 
                              else "BALANCED"
                },
            }
            
            # OTM conviction (doesn't need z-score, it's already a ratio)
            otm_result = otm_factor.compute(
                otm_call_premium=call_premium,
                otm_put_premium=put_premium
            )
            factors["otm_conviction"] = otm_result
            
            # Add FMP volatility context (is this a volatile sector?)
            if sector_history:
                vol = sector_history.get("volatility")
                if vol:
                    factors["sector_volatility"] = {
                        "value": round(vol, 4),
                        "annualized_pct": f"{vol * 100:.1f}%"
                    }
            
            # Flow snapshot for transparency
            sector_result = {
                "factors": factors,
                "flow_snapshot": {
                    "delta_flow": delta_flow,
                    "vega_flow": vega_flow,
                    "call_premium": call_premium,
                    "put_premium": put_premium,
                    "net_premium": call_premium - put_premium,
                },
            }
            
            if include_raw_data:
                sector_result["raw"] = flow_data
            
            result["sectors"][sector] = sector_result
            
            # Compute factor scores for aggregation (use z-scores)
            factor_scores = {
                "delta_flow": factors["delta_flow"]["zscore"],
                "vega_flow": factors["vega_flow"]["zscore"],
                "net_premium": factors["net_premium"]["zscore"],
                "cross_sectional_zscore": factors["delta_flow"]["zscore"],  # Primary signal
            }
            
            # Add OTM conviction (centered at 0.5, so shift to -0.5 to +0.5 range)
            otm_val = otm_result.get("value", 0.5)
            factor_scores["otm_conviction"] = (otm_val - 0.5) * 2  # Convert 0-1 to -1 to +1
            
            aggregated = aggregator.aggregate(
                factors=factor_scores,
                regime=current_regime
            )
            
            result["sectors"][sector]["composite"] = aggregated
            all_signals[sector] = {
                "composite_score": aggregated.get("composite_score", 0),
                "factors": factors,
            }
        
        # STEP 7: ANOMALY DETECTION (which sectors have unusual flow?)
        if anomaly_detector and all_signals:
            try:
                import pandas as pd
                
                # Multi-feature anomaly detection
                anomaly_features = pd.DataFrame([
                    {
                        "delta_zscore": delta_zscores.get(s, 0),
                        "vega_zscore": vega_zscores.get(s, 0),
                        "premium_zscore": premium_zscores.get(s, 0),
                    }
                    for s in sector_list if s in all_signals
                ])
                
                if len(anomaly_features) > 0:
                    anomaly_result = anomaly_detector.detect(anomaly_features)
                    
                    sectors_in_order = [s for s in sector_list if s in all_signals]
                    for r in anomaly_result.get("results", []):
                        idx = r.get("index", 0)
                        if idx < len(sectors_in_order):
                            sector = sectors_in_order[idx]
                            anomalies[sector] = r.get("is_anomaly", False)
                            
                            # Tag the sector result
                            if sector in result["sectors"]:
                                result["sectors"][sector]["is_anomaly"] = r.get("is_anomaly", False)
                                result["sectors"][sector]["anomaly_score"] = r.get("score", 0)
                    
                    result["anomalies"] = {
                        "detected_count": sum(1 for v in anomalies.values() if v),
                        "sectors": anomalies,
                        "method": anomaly_result.get("method", "isolation_forest"),
                    }
                    
            except Exception as e:
                logger.warning(f"Anomaly detection failed: {e}")
        
        # STEP 8: ENSEMBLE PREDICTIONS (ML-based sector ranking)
        if ensemble_model and all_signals:
            try:
                import pandas as pd
                
                # Build feature matrix for ensemble
                ensemble_features = []
                sector_order = []
                
                for sector in sector_list:
                    if sector not in all_signals:
                        continue
                    
                    sector_order.append(sector)
                    hist = historical_data.get(sector, {})
                    
                    ensemble_features.append({
                        "delta_zscore": delta_zscores.get(sector, 0),
                        "vega_zscore": vega_zscores.get(sector, 0),
                        "premium_zscore": premium_zscores.get(sector, 0),
                        "volatility": hist.get("volatility", 0.2) or 0.2,
                        "is_anomaly": 1 if anomalies.get(sector) else 0,
                    })
                
                if ensemble_features:
                    ensemble_df = pd.DataFrame(ensemble_features)
                    
                    # Simple ensemble: weighted combination of factors
                    # In production, this would use trained models
                    ensemble_scores = (
                        0.35 * ensemble_df["delta_zscore"] +
                        0.25 * ensemble_df["vega_zscore"] +
                        0.20 * ensemble_df["premium_zscore"] +
                        0.10 * ensemble_df["is_anomaly"] +
                        -0.10 * (ensemble_df["volatility"] - 0.2)  # Penalize high vol
                    )
                    
                    # Add ensemble predictions to results
                    for i, sector in enumerate(sector_order):
                        if sector in result["sectors"]:
                            result["sectors"][sector]["ensemble_score"] = round(float(ensemble_scores.iloc[i]), 4)
                    
                    result["ensemble"] = {
                        "method": "weighted_ensemble",
                        "top_picks": [sector_order[i] for i in ensemble_scores.nlargest(3).index.tolist()],
                        "bottom_picks": [sector_order[i] for i in ensemble_scores.nsmallest(3).index.tolist()],
                    }
                    
            except Exception as e:
                logger.warning(f"Ensemble prediction failed: {e}")
        
        # Generate rankings
        rankings = sorted(
            [
                {"sector": s, "score": info.get("composite_score", 0)}
                for s, info in all_signals.items()
            ],
            key=lambda x: x["score"],
            reverse=True
        )
        result["rankings"] = rankings
        
        # Generate trades if enabled
        if generate_trades and all_signals:
            from .trade import TradeGenerator
            
            trade_gen = TradeGenerator(config=trade_config)
            trades = trade_gen.generate(
                sector_signals=all_signals,
                regime=current_regime,
                anomalies=anomalies if anomalies else None
            )
            result["trades"] = trades
        
        # Generate charts if enabled
        if generate_charts and all_signals:
            from .charts import ChartGenerator
            
            chart_gen = ChartGenerator(config=chart_config)
            charts_list = []
            
            # Sector signal bars
            signal_scores = {
                s: info.get("composite_score", 0)
                for s, info in all_signals.items()
            }
            bars_chart = chart_gen.sector_signal_bars(signal_scores)
            if bars_chart:
                charts_list.append(bars_chart)
            
            # Factor heatmap
            factor_matrix = {
                s: {
                    k: v.get("zscore", 0) if isinstance(v, dict) else v
                    for k, v in info.get("factors", {}).items()
                }
                for s, info in all_signals.items()
            }
            heatmap = chart_gen.factor_heatmap(factor_matrix)
            if heatmap:
                charts_list.append(heatmap)
            
            if charts_list:
                result["charts"] = charts_list
        
        # Summary
        result["summary"] = _build_summary(result, all_signals)
        
    except Exception as e:
        logger.error(f"Sector rotation analysis failed: {e}")
        result["status"] = "error"
        result["error"] = str(e)
        
    finally:
        await fetcher.cleanup()
    
    return result


# =============================================================================
# HELPERS
# =============================================================================

def _build_summary(result: Dict, all_signals: Dict) -> Dict[str, Any]:
    """Build human-readable summary."""
    
    if not all_signals:
        return {"message": "No signals generated"}
    
    # Top bullish/bearish
    rankings = result.get("rankings", [])
    
    top_bullish = [r for r in rankings[:3] if r.get("score", 0) > 0]
    top_bearish = [r for r in rankings[-3:] if r.get("score", 0) < 0]
    
    summary = {
        "total_sectors": len(all_signals),
        "bullish_count": sum(1 for r in rankings if r.get("score", 0) > 0),
        "bearish_count": sum(1 for r in rankings if r.get("score", 0) < 0),
        "neutral_count": sum(1 for r in rankings if r.get("score", 0) == 0),
        "top_bullish": [r["sector"] for r in top_bullish],
        "top_bearish": [r["sector"] for r in top_bearish],
    }
    
    if result.get("regime"):
        summary["current_regime"] = result["regime"].get("regime", "unknown")
    
    if result.get("trades"):
        trades = result["trades"]
        summary["trade_recommendations"] = trades.get("summary", {})
    
    return summary


# =============================================================================
# AGENT TOOL WRAPPER
# =============================================================================

@function_tool(strict_mode=False)  # Uses Optional[Dict] config params
async def analyze_sector_rotation_flow(
    sectors: Optional[List[str]] = None,
    date: Optional[str] = None,
    include_vega_flow: bool = False,
    include_correlations: bool = False,
    include_seasonality: bool = False,
    include_etf_flows: bool = False,
    include_movers: bool = False,
    include_oi_change: bool = False,
    use_regime_classifier: bool = False,
    use_lead_lag_detector: bool = False,
    use_anomaly_detector: bool = False,
    use_ensemble: bool = False,
    aggregation_method: str = "equal_weighted",
    generate_trades: bool = False,
    generate_charts: bool = True,
    include_raw_data: bool = False,
    factor_config: Optional[Dict] = None,
    aggregation_config: Optional[Dict] = None,
    regime_config: Optional[Dict] = None,
    trade_config: Optional[Dict] = None,
    chart_config: Optional[Dict] = None,
    validation_config: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Analyze sector rotation using options flow data.
    
    Detects capital rotation between market sectors using delta, vega, and premium flow.
    """
    return await analyze_sector_rotation_flow_internal(
        sectors=sectors,
        date=date,
        include_vega_flow=include_vega_flow,
        include_correlations=include_correlations,
        include_seasonality=include_seasonality,
        include_etf_flows=include_etf_flows,
        include_movers=include_movers,
        include_oi_change=include_oi_change,
        use_regime_classifier=use_regime_classifier,
        use_lead_lag_detector=use_lead_lag_detector,
        use_anomaly_detector=use_anomaly_detector,
        use_ensemble=use_ensemble,
        aggregation_method=aggregation_method,
        generate_trades=generate_trades,
        generate_charts=generate_charts,
        include_raw_data=include_raw_data,
        factor_config=factor_config,
        aggregation_config=aggregation_config,
        regime_config=regime_config,
        trade_config=trade_config,
        chart_config=chart_config,
        validation_config=validation_config,
    )
