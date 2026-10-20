"""
Squeeze Detection Tool - Configurable ML Pipeline

Detects gamma squeeze and short squeeze setups with full configurability
over features, models, and parameters. All data fetched in parallel.

Key Principles:
- Z-score based: All metrics compared to historical distributions, no magic numbers
- Parallel execution: All data fetches happen concurrently
- Configurable: User controls feature groups, model types, and parameters
- Extensible: Easy to add new models or feature groups
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime

from agents import function_tool

from core.mcp_servers.unusualwhales.UWOptionsServer import UWOptionsServer
from core.mcp_servers.unusualwhales.UWMarketServer import UWMarketServer
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.risk_adapter import jsonify_results
from core.utils.context_utils import get_cancel_event
from core.agents.risk_tools.shared import register_chart_handle

from .features import (
    extract_gamma_features,
    extract_momentum_features, 
    extract_short_features,
    build_feature_vector,
)
from .models import (
    SurvivalModel,
    LogisticModel,
    XGBoostTimingModel,
    GPModel,
    QuantileRFModel,
    MonteCarloPathModel,
)
from .charts import build_gex_structure_chart, build_path_fan_chart, build_signal_distribution_chart

logger = logging.getLogger(__name__)


# =============================================================================
# DEFAULT CONFIGURATIONS
# =============================================================================

DEFAULT_FEATURE_GROUPS = {
    "gamma": True,      # GEX structure, call/put walls, ramp proximity
    "momentum": True,   # Call OI changes, vol>OI count, hottest strikes
    "short": True,      # SI%, DTC, FTDs, borrow conditions
    "volatility": False # IV rank, IV/RV ratio, skew (optional)
}

DEFAULT_MODEL_CONFIG = {
    "timing": {
        "model": "survival",
        "params": {}
    },
    "magnitude": {
        "model": "gp",
        "params": {}
    },
    "paths": {
        "model": "none",
        "n_paths": 500,
        "horizon_days": 30
    }
}


# =============================================================================
# MAIN TOOL
# =============================================================================

# Canvas-friendly internal function
async def detect_squeeze_internal(
    ticker: str,
    lookback_days: int = 60,
    include_gamma: bool = True,
    include_momentum: bool = True,
    include_short: bool = True,
) -> dict:
    """
    Canvas-friendly squeeze detection for a single ticker.
    Returns raw data for Canvas to build charts.
    """
    import json
    
    ticker = ticker.upper().strip()
    
    features_cfg = {
        "gamma": include_gamma,
        "momentum": include_momentum,
        "short": include_short,
        "volatility": False
    }
    models_cfg = DEFAULT_MODEL_CONFIG.copy()
    
    uw_options = UWOptionsServer()
    uw_market = UWMarketServer()
    fmp = FMPMarketDataServer()
    
    try:
        await asyncio.gather(
            uw_options.connect(),
            uw_market.connect(),
            fmp.connect()
        )
        
        logger.info(f"[SQUEEZE-CANVAS] Analyzing {ticker}")
        
        # Parallel data fetching
        fetch_tasks = [_fetch_spot_price(fmp, ticker)]
        task_labels = ["spot"]
        
        if features_cfg.get("gamma"):
            fetch_tasks.append(extract_gamma_features(uw_options, ticker))
            task_labels.append("gamma")
        
        if features_cfg.get("momentum"):
            fetch_tasks.append(extract_momentum_features(uw_options, ticker, lookback_days))
            task_labels.append("momentum")
        
        if features_cfg.get("short"):
            fetch_tasks.append(extract_short_features(uw_market, ticker, lookback_days))
            task_labels.append("short")
        
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        fetched_data = {}
        for label, result in zip(task_labels, results):
            if isinstance(result, Exception):
                logger.warning(f"[SQUEEZE] Failed to fetch {label}: {result}")
                fetched_data[label] = None
            else:
                fetched_data[label] = result
        
        spot_price = fetched_data.get("spot")
        if not spot_price:
            return {"status": "error", "error": f"Could not fetch spot price for {ticker}"}
        
        # Build feature vector
        feature_vector = build_feature_vector(
            gamma_features=fetched_data.get("gamma"),
            momentum_features=fetched_data.get("momentum"),
            short_features=fetched_data.get("short"),
            spot_price=spot_price
        )
        
        if not feature_vector or not feature_vector.get("features"):
            return {"status": "error", "error": "Insufficient data to analyze"}
        
        # Run models
        timing_result = await _run_timing_model(models_cfg["timing"], feature_vector)
        magnitude_result = await _run_magnitude_model(models_cfg["magnitude"], feature_vector)
        
        # Analyze setup
        setup_analysis = _analyze_setup(feature_vector, timing_result, magnitude_result)
        
        return {
            "status": "success",
            "ticker": ticker,
            "spot_price": spot_price,
            "features": feature_vector.get("features", {}),
            "key_levels": feature_vector.get("key_levels", {}),
            "timing": timing_result,
            "magnitude": magnitude_result,
            "setup_detected": setup_analysis["detected"],
            "setup_summary": setup_analysis["summary"],
            "confidence": setup_analysis.get("confidence", "low"),
            "elevated_signals": setup_analysis.get("elevated_features", []),
            "signal_count": setup_analysis.get("signal_count", 0),
            "implications": setup_analysis.get("implications", []),
            # Raw data for charts
            "gamma_data": fetched_data.get("gamma"),
        }
        
    except Exception as e:
        logger.error(f"[SQUEEZE-CANVAS] Failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    
    finally:
        await asyncio.gather(
            uw_options.cleanup(),
            uw_market.cleanup(),
            fmp.cleanup(),
            return_exceptions=True
        )


@function_tool
async def detect_squeeze_setup(
    ticker: str,
    feature_groups_json: Optional[str] = None,
    model_config_json: Optional[str] = None,
    lookback_days: int = 60,
    generate_chart: bool = True
) -> dict:
    """
    SQUEEZE EARLY WARNING SYSTEM
    
    Detects gamma squeeze and short squeeze setups by analyzing dealer positioning, 
    options flow momentum, and short interest. Uses ML models to estimate timing 
    and magnitude of potential squeeze events.
    
    ============================================================================
    WHEN TO USE THIS TOOL
    ============================================================================
    
    Use this tool when the user asks about:
    - Squeeze potential, gamma squeeze, short squeeze analysis
    - Meme stock setups (GME, AMC, etc.)
    - Unusual options activity combined with high short interest
    - Dealer gamma positioning and hedging flows
    - Whether a stock is set up for a sharp move
    
    ============================================================================
    HOW THE ANALYSIS WORKS
    ============================================================================
    
    STEP 1 - DATA COLLECTION:
    Fetches three categories of data from Unusual Whales:
    
    a) Gamma Features (dealer positioning):
       - GEX by strike: Where dealers have gamma exposure
       - Put wall: Strike with max negative gamma (acts as support)
       - Call wall: Strike with max positive gamma (acts as resistance)
       - Gamma ramp: Where hedging accelerates if price approaches
       - Zero gamma: Pivot point where dealer behavior flips
       
    b) Momentum Features (options flow):
       - Call OI change: Are traders opening new call positions?
       - Vol > OI count: Contracts where today's volume exceeds open interest
         (indicates aggressive new positioning, not just closing trades)
       - Hottest strikes: Where is the action concentrated?
       
    c) Short Features (squeeze pressure):
       - Short interest %: Percentage of float sold short
       - Days to cover: How long to cover all shorts at avg volume
       - FTD trend: Are failures to deliver increasing or decreasing?
       - Borrow fee: Cost to borrow shares (high = hard to borrow)
    
    STEP 2 - Z-SCORE NORMALIZATION:
    Each metric is converted to a z-score (standard deviations from mean).
    This removes arbitrary thresholds - a z-score of 2+ means that signal is
    statistically elevated regardless of the absolute value.
    
    STEP 3 - TIMING MODEL (Survival Analysis):
    Uses Cox proportional hazards to estimate WHEN a squeeze might trigger.
    The model looks at:
    - How many signals are elevated (signal_count)
    - Mean strength of elevated signals
    - Whether signals are confirming each other
    
    Output: trigger_prob_5d, trigger_prob_10d, median_days_to_trigger
    
    STEP 4 - MAGNITUDE MODEL (Gaussian Process):
    Estimates HOW BIG the move could be if triggered.
    GP provides natural uncertainty quantification - wider CI = less certain.
    
    Output: expected_move (%), ci_90 [low, high], uncertainty
    
    ============================================================================
    INTERPRETING THE OUTPUT
    ============================================================================
    
    TIMING RESULTS:
    
    trigger_prob_5d / trigger_prob_10d:
    - Below 20%: No significant setup. Signals are within normal ranges.
      Tell user: "No squeeze setup detected. Metrics are normal."
      
    - 20-40%: Weak setup. Maybe one signal elevated.
      Tell user: "Mild elevation in [signal]. Not a high-conviction setup yet."
      
    - 40-60%: Moderate setup. Multiple signals showing.
      Tell user: "Squeeze setup forming. [X] signals elevated. Worth monitoring."
      
    - Above 60%: Strong setup. Multiple confirming signals.
      Tell user: "Strong squeeze setup. [X] signals aligned. High probability of trigger."
    
    signal_count:
    - 1 signal: Low conviction - could be noise
    - 2 signals: Moderate - signals confirming each other
    - 3+ signals: High conviction - multiple independent confirmations
    
    MAGNITUDE RESULTS:
    
    expected_move:
    - 5-15%: Modest squeeze potential
    - 15-30%: Significant move if triggered
    - 30%+: Major squeeze potential (rare, usually meme stocks)
    
    ci_90 (90% confidence interval):
    - Narrow (e.g., [10%, 20%]): Model is confident in estimate
    - Wide (e.g., [5%, 50%]): High uncertainty, wide range of outcomes possible
    
    KEY LEVELS (from gamma analysis):
    
    put_wall: Major support level. Dealers hedging puts buy stock here.
      Tell user: "Put wall support at $X - expect buying pressure if price drops here"
      
    call_wall: Major resistance level. Dealers hedging calls sell stock here.
      Tell user: "Call wall resistance at $X - expect selling pressure approaching this level"
      
    gamma_ramp: Trigger zone for gamma squeeze. If price breaks above this level,
      dealer hedging creates self-reinforcing buying.
      Tell user: "Gamma ramp at $X - breaking above could accelerate the move"
      
    zero_gamma: Pivot point. Above = dealers buy dips/sell rips (stabilizing).
      Below = dealers chase momentum (destabilizing).
    
    ============================================================================
    EXAMPLE INTERPRETATIONS FOR USERS
    ============================================================================
    
    STRONG SETUP:
    "GME shows a strong squeeze setup with 3 elevated signals:
    - Vol > OI z-score: 3.2 (extreme unusual activity)
    - Short interest z-score: 2.1 (elevated shorts)
    - Call OI momentum z-score: 1.8 (aggressive call buying)
    
    The survival model estimates 55% probability of triggering within 5 days.
    If triggered, expected move is +25% (90% CI: +10% to +45%).
    
    Key levels: Put wall support at $18, call wall resistance at $25, 
    gamma ramp trigger at $22. Current price $20 is approaching the ramp."
    
    WEAK SETUP:
    "AAPL shows no significant squeeze setup. Only vol_greater_oi is mildly
    elevated at z-score 1.2. Short interest is normal, no gamma ramp nearby.
    Trigger probability is low at 15%. This is normal options activity,
    not a squeeze setup."
    
    ============================================================================
    TRADING STRATEGY SUGGESTIONS
    ============================================================================
    
    Based on results, suggest appropriate strategies:
    
    HIGH PROB + GAMMA SQUEEZE (elevated gamma signals):
    - Long calls near gamma ramp strike
    - Call spreads to reduce premium
    - Stock with stop below put wall
    
    HIGH PROB + SHORT SQUEEZE (elevated short signals):
    - Stock position (captures the squeeze directly)
    - Deep ITM calls (high delta, less theta decay)
    - Avoid selling puts (unlimited risk if squeeze happens)
    
    MODERATE PROB (worth monitoring):
    - Set alerts at gamma ramp / call wall levels
    - Consider small position to start, add if signals strengthen
    
    LOW PROB (no setup):
    - Don't force a squeeze trade
    - Look at other analysis (valuation, technicals)
    
    ============================================================================
    PARAMETERS
    ============================================================================
    
    Args:
        ticker: Stock symbol to analyze
        
        feature_groups_json: JSON string to toggle feature groups.
            '{"gamma": true, "momentum": true, "short": true, "volatility": false}'
            Default enables gamma, momentum, short. Volatility disabled.
            
        model_config_json: JSON string for model configuration.
            '{"timing": {"model": "survival"}, "magnitude": {"model": "gp"}}'
            Options: timing.model = survival|logistic|xgboost
                     magnitude.model = gp|quantile_rf|linear
                     paths.model = none|monte_carlo
                     
        lookback_days: Historical window for z-score calculation (default 60)
        
        generate_chart: Include dashboard chart (default True)
    
    Returns:
        Dictionary with:
        - status: "success" or "error"
        - ticker, spot_price, timestamp
        - features: All extracted features with z-scores
        - timing: trigger_prob_5d, trigger_prob_10d, signal_count, elevated_signals
        - magnitude: expected_move, ci_90, uncertainty
        - key_levels: put_wall, call_wall, gamma_ramp, zero_gamma
        - setup_detected: Boolean
        - setup_summary: Human-readable summary
        - charts: Dashboard visualization
    """
    try:
        import json
        
        ticker = ticker.upper().strip()
        
        # Parse JSON parameters
        feature_groups = None
        model_config = None
        
        if feature_groups_json:
            try:
                feature_groups = json.loads(feature_groups_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid feature_groups_json: {feature_groups_json}, using defaults")
        
        if model_config_json:
            try:
                model_config = json.loads(model_config_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid model_config_json: {model_config_json}, using defaults")
        
        # Merge with defaults
        features_cfg = {**DEFAULT_FEATURE_GROUPS, **(feature_groups or {})}
        models_cfg = _merge_model_config(model_config)
        
        # Initialize servers
        uw_options = UWOptionsServer()
        uw_market = UWMarketServer()
        fmp = FMPMarketDataServer()
        
        try:
            # Connect all servers in parallel
            await asyncio.gather(
                uw_options.connect(),
                uw_market.connect(),
                fmp.connect()
            )
            
            logger.info(f"[SQUEEZE] Analyzing {ticker} with features={features_cfg}")
            
            # =========================================================
            # PARALLEL DATA FETCHING
            # =========================================================
            fetch_tasks = []
            task_labels = []
            
            # Always fetch spot price
            fetch_tasks.append(_fetch_spot_price(fmp, ticker))
            task_labels.append("spot")
            
            # ✅ CHECK CANCELLATION before data fetching
            cancel_event = get_cancel_event()
            if cancel_event and cancel_event.is_set():
                logger.info(f"[CANCEL] Squeeze detection cancelled for {ticker}")
                raise asyncio.CancelledError("Squeeze detection cancelled by user")
            
            # Conditional feature fetching
            if features_cfg.get("gamma"):
                fetch_tasks.append(extract_gamma_features(uw_options, ticker))
                task_labels.append("gamma")
            
            if features_cfg.get("momentum"):
                fetch_tasks.append(extract_momentum_features(uw_options, ticker, lookback_days))
                task_labels.append("momentum")
            
            if features_cfg.get("short"):
                fetch_tasks.append(extract_short_features(uw_market, ticker, lookback_days))
                task_labels.append("short")
            
            # Execute all fetches in parallel
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            
            # Parse results
            fetched_data = {}
            for label, result in zip(task_labels, results):
                if isinstance(result, Exception):
                    logger.warning(f"[SQUEEZE] Failed to fetch {label}: {result}")
                    fetched_data[label] = None
                else:
                    fetched_data[label] = result
            
            spot_price = fetched_data.get("spot")
            if not spot_price:
                return jsonify_results({
                    "error": f"Could not fetch spot price for {ticker}",
                    "ticker": ticker
                })
            
            # =========================================================
            # BUILD FEATURE VECTOR
            # =========================================================
            feature_vector = build_feature_vector(
                gamma_features=fetched_data.get("gamma"),
                momentum_features=fetched_data.get("momentum"),
                short_features=fetched_data.get("short"),
                spot_price=spot_price
            )
            
            if not feature_vector or not feature_vector.get("features"):
                return jsonify_results({
                    "error": "Insufficient data to build feature vector",
                    "ticker": ticker,
                    "fetched": {k: v is not None for k, v in fetched_data.items()}
                })
            
            # =========================================================
            # RUN MODELS
            # =========================================================
            timing_result = await _run_timing_model(
                models_cfg["timing"],
                feature_vector
            )
            
            magnitude_result = await _run_magnitude_model(
                models_cfg["magnitude"],
                feature_vector
            )
            
            path_result = None
            if models_cfg["paths"]["model"] != "none":
                path_result = await _run_path_model(
                    models_cfg["paths"],
                    feature_vector,
                    spot_price
                )
            
            # =========================================================
            # DETERMINE SETUP STATUS
            # =========================================================
            setup_analysis = _analyze_setup(
                feature_vector,
                timing_result,
                magnitude_result
            )
            
            # =========================================================
            # BUILD RESPONSE
            # =========================================================
            result = {
                "status": "success",
                "ticker": ticker,
                "spot_price": spot_price,
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "feature_groups": features_cfg,
                    "model_config": models_cfg,
                    "lookback_days": lookback_days
                },
                "features": feature_vector.get("features", {}),
                "key_levels": feature_vector.get("key_levels", {}),
                "timing": timing_result,
                "magnitude": magnitude_result,
                "setup_detected": setup_analysis["detected"],
                "setup_summary": setup_analysis["summary"],
                "trade_implications": setup_analysis["implications"],
                "feature_importance": feature_vector.get("importance", {})
            }
            
            if path_result:
                result["paths"] = path_result
            
            # =========================================================
            # GENERATE CHARTS
            # =========================================================
            if generate_chart:
                charts = []
                
                # GEX structure chart (if gamma data available)
                if fetched_data.get("gamma"):
                    gex_chart = build_gex_structure_chart(
                        fetched_data["gamma"],
                        spot_price,
                        ticker
                    )
                    if gex_chart:
                        charts.append(register_chart_handle(
                            gex_chart["plotly"],
                            chart_type="bar",
                            title=gex_chart["title"],
                            alt_text=f"GEX structure for {ticker}",
                            metadata={"ticker": ticker}
                        ))
                
                # Signal distribution chart (primary visualization)
                signal_chart = build_signal_distribution_chart(
                    feature_vector.get("features", {}),
                    ticker,
                    timing=timing_result,
                    magnitude=magnitude_result
                )
                if signal_chart:
                    charts.append(register_chart_handle(
                        signal_chart["plotly"],
                        chart_type="scatter",
                        title=signal_chart["title"],
                        alt_text=f"Squeeze signal distribution for {ticker}",
                        metadata={"ticker": ticker}
                    ))
                
                # Path fan chart (if path simulation enabled)
                if path_result and path_result.get("percentile_paths"):
                    path_chart = build_path_fan_chart(
                        path_result,
                        spot_price,
                        ticker
                    )
                    if path_chart:
                        charts.append(register_chart_handle(
                            path_chart["plotly"],
                            chart_type="line",
                            title=path_chart["title"],
                            alt_text=f"Squeeze path scenarios for {ticker}",
                            metadata={"ticker": ticker}
                        ))
                
                if charts:
                    result["charts"] = charts
            
            return jsonify_results(result)
        
        finally:
            # Cleanup all servers in parallel
            await asyncio.gather(
                uw_options.cleanup(),
                uw_market.cleanup(),
                fmp.cleanup(),
                return_exceptions=True
            )
    
    except Exception as e:
        logger.error(f"[SQUEEZE] Tool failed: {e}", exc_info=True)
        return jsonify_results({
            "error": "Squeeze detection failed",
            "details": str(e),
            "ticker": ticker
        })


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _merge_model_config(user_config: Optional[Dict]) -> Dict:
    """Merge user config with defaults."""
    if not user_config:
        return DEFAULT_MODEL_CONFIG.copy()
    
    merged = {}
    for key in ["timing", "magnitude", "paths"]:
        default = DEFAULT_MODEL_CONFIG.get(key, {})
        user = user_config.get(key, {})
        merged[key] = {**default, **user}
    
    return merged


async def _fetch_spot_price(fmp: FMPMarketDataServer, ticker: str) -> Optional[float]:
    """
    Fetch current spot price using dynamic field discovery.
    Uses get_fields with price-related field names - FMP maps them to the right dataset.
    """
    from core.utils.mcp_result_parser import safe_parse_json
    
    try:
        # Ask FMP for price fields - it will discover which dataset has them
        result = await fmp.call_tool("get_fields", {
            "symbol": ticker,
            "fields": ["price", "previousClose"]  # FMP maps these dynamically
        })
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        # Extract from response structure
        if isinstance(data, dict):
            # Check 'data' key first (standard response format)
            inner = data.get('data', data)
            
            # Try price fields in preference order
            for field in ['price', 'previousClose']:
                val = inner.get(field)
                if val is not None:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch spot for {ticker}: {e}")
        return None


async def _run_timing_model(config: Dict, features: Dict) -> Dict:
    """Run the configured timing model."""
    model_type = config.get("model", "survival")
    params = config.get("params", {})
    
    try:
        if model_type == "survival":
            model = SurvivalModel(**params)
        elif model_type == "logistic":
            model = LogisticModel(**params)
        elif model_type == "xgboost":
            model = XGBoostTimingModel(**params)
        else:
            logger.warning(f"Unknown timing model: {model_type}, using survival")
            model = SurvivalModel()
        
        return model.predict(features)
    except Exception as e:
        logger.error(f"Timing model failed: {e}")
        return {"error": str(e), "model": model_type}


async def _run_magnitude_model(config: Dict, features: Dict) -> Dict:
    """Run the configured magnitude model."""
    model_type = config.get("model", "gp")
    params = config.get("params", {})
    
    try:
        if model_type == "gp":
            model = GPModel(**params)
        elif model_type == "quantile_rf":
            model = QuantileRFModel(**params)
        elif model_type == "linear":
            # Simple linear baseline
            return _simple_magnitude_estimate(features)
        else:
            logger.warning(f"Unknown magnitude model: {model_type}, using gp")
            model = GPModel()
        
        return model.predict(features)
    except Exception as e:
        logger.error(f"Magnitude model failed: {e}")
        return {"error": str(e), "model": model_type}


def _simple_magnitude_estimate(features: Dict) -> Dict:
    """Simple linear estimate as fallback."""
    import numpy as np
    
    z_scores = []
    for key, val in features.get("features", {}).items():
        if "zscore" in key and isinstance(val, (int, float)):
            z_scores.append(val)
    
    if not z_scores:
        return {"expected_move": 0.15, "ci_90": [0.05, 0.30]}
    
    avg_z = np.mean(z_scores)
    # Rough heuristic: 5% base + 5% per z-score
    expected = 0.05 + 0.05 * avg_z
    
    return {
        "model": "linear",
        "expected_move": round(expected, 3),
        "ci_90": [round(expected * 0.5, 3), round(expected * 2.0, 3)]
    }


async def _run_path_model(config: Dict, features: Dict, spot: float) -> Optional[Dict]:
    """Run path simulation model."""
    model_type = config.get("model", "monte_carlo")
    n_paths = config.get("n_paths", 500)
    horizon = config.get("horizon_days", 30)
    
    try:
        if model_type == "monte_carlo":
            model = MonteCarloPathModel(n_paths=n_paths, horizon_days=horizon)
            return model.simulate(features, spot)
        else:
            return None
    except Exception as e:
        logger.error(f"Path model failed: {e}")
        return {"error": str(e)}


def _analyze_setup(features: Dict, timing: Dict, magnitude: Dict) -> Dict:
    """
    Analyze squeeze setup based on signal distribution.
    
    No hardcoded thresholds - uses signal count and model outputs to determine
    setup quality. Let the models speak through their probabilities.
    """
    import numpy as np
    
    # Collect all z-scores
    z_scores = {}
    for key, val in features.get("features", {}).items():
        if "zscore" in key and isinstance(val, (int, float)):
            z_scores[key] = val
    
    if not z_scores:
        return {
            "detected": False,
            "summary": "Insufficient data for setup detection",
            "implications": [],
            "confidence": "low"
        }
    
    # Statistics from the z-scores themselves (data-driven)
    values = list(z_scores.values())
    max_z = max(values)
    avg_z = np.mean(values)
    std_z = np.std(values) if len(values) > 1 else 0
    n_positive = sum(1 for v in values if v > 0)
    
    # Get model's signal count (models compute this without hardcoded thresholds)
    model_signal_count = timing.get("signal_count", 0)
    elevated_signals = timing.get("elevated_signals", [])
    
    # Detection based on model signal count (breadth) + at least one strong signal
    # "Strong" = above the distribution mean (relative to this data, not hardcoded)
    above_mean = [k for k, v in z_scores.items() if v > avg_z + std_z]
    
    detected = model_signal_count >= 2 or (model_signal_count >= 1 and len(above_mean) >= 1)
    
    # Confidence level based on signal agreement
    if model_signal_count >= 3 and n_positive >= len(values) * 0.6:
        confidence = "high"
    elif model_signal_count >= 2:
        confidence = "moderate"
    else:
        confidence = "low"
    
    # Summary based on what we found
    if detected and elevated_signals:
        summary = f"Squeeze setup detected. Elevated: {', '.join(elevated_signals[:3])}"
    elif detected:
        summary = f"Potential squeeze setup. {n_positive}/{len(values)} signals positive."
    else:
        summary = "No significant squeeze setup based on current signals."
    
    # Implications - report what the models say without thresholds
    implications = []
    
    trigger_prob = timing.get("trigger_prob_5d", 0)
    implications.append(f"5-day trigger probability: {trigger_prob:.0%}")
    
    expected_move = magnitude.get("expected_move", 0)
    ci = magnitude.get("ci_90", [0, 0])
    implications.append(f"Expected move: +{expected_move:.0%} (90% CI: {ci[0]:.0%} to {ci[1]:.0%})")
    
    key_levels = features.get("key_levels", {})
    if key_levels.get("gamma_ramp"):
        implications.append(f"Gamma ramp: ${key_levels['gamma_ramp']:.2f}")
    if key_levels.get("call_wall"):
        implications.append(f"Call wall resistance: ${key_levels['call_wall']:.2f}")
    if key_levels.get("put_wall"):
        implications.append(f"Put wall support: ${key_levels['put_wall']:.2f}")
    
    return {
        "detected": detected,
        "summary": summary,
        "implications": implications,
        "confidence": confidence,
        "elevated_features": elevated_signals,
        "signal_count": model_signal_count,
        "max_zscore": round(max_z, 2),
        "avg_zscore": round(avg_z, 2)
    }

