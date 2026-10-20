"""
Herding Regime Detector Tool

Main entry point for the Ising model-inspired herding/crowding detector.
Computes 4 physics statistics from sector ETF returns, uses PCA for composite
weighting, and optionally fits a 3-state HMM for regime classification.

Enhanced with full Ising model parameters:
- Temperature (T) from VIX - controls disorder
- External Field (h) from RSI breadth (discretionary or macro) - participation bias
- Coupling (J) from options flow - measures spin-spin interaction

External Field Modes:
- discretionary: RSI breadth of input tickers (internal participation)
- macro: RSI breadth of all sectors + FRED factors (external pressure)

Usage:
    # For agents (decorated version):
    result = await analyze_herding_regime(
        lookback_days=252,
        window=21,
        field_mode="discretionary",
        generate_charts=True
    )
    
    # For Canvas (internal version, no chart wrapping):
    result = await analyze_herding_regime_internal(
        lookback_days=252,
        window=21,
        field_mode="discretionary",
        generate_charts=False
    )
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from agents import function_tool

from .data_fetcher import HerdingDataFetcher, SECTOR_ETFS
from .ising_stats import compute_all_ising_statistics
from .hmm_regime import detect_hmm_regime
from .charts import generate_herding_charts
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts

logger = logging.getLogger(__name__)


async def analyze_herding_regime_internal(
    tickers: Optional[List[str]] = None,
    lookback_days: int = 252,
    window: int = 21,
    sectors: Optional[List[str]] = None,
    field_mode: str = "discretionary",
    include_vix: bool = True,
    include_options_flow: bool = True,
    include_hmm: bool = True,
    generate_charts: bool = True,
    rsi_period: int = 14,
) -> Dict[str, Any]:
    """
    Internal implementation of herding regime analysis.
    
    This is the core function that does the actual work. Call this directly
    from Canvas executors with generate_charts=False to get raw data.
    
    Computes 4 physics-inspired early warning signals from any ticker universe:
    1. Magnetization - Net market sentiment (are tickers aligned?)
    2. Susceptibility - Response sensitivity (how violently does sentiment react?)
    3. Correlation Length - Herding spread (are tickers moving together?)
    4. Critical Slowing Down - Momentum persistence (is mean-reversion slowing?)
    
    Plus 3 Ising model parameters:
    - Temperature (T) from VIX: High VIX = disorder, Low VIX = ordered states
    - External Field (h) from RSI breadth: Participation-based directional bias
    - Coupling (J) from options flow: Correlation between price and options sentiment
    
    Args:
        tickers: List of ticker symbols to analyze (e.g., ["AAPL", "MSFT", "GOOGL"]).
                 If None, falls back to sectors or all 11 SPDR sector ETFs.
        lookback_days: Number of trading days of history (default 252 = 1 year)
        window: Rolling window for statistics (default 21 = 1 month)
        sectors: Optional list of sectors to analyze (used if tickers is None).
        field_mode: External field calculation mode:
            - "discretionary": RSI breadth of input tickers (participation within universe)
            - "macro": RSI breadth of all sectors + FRED factors (external pressure)
        include_vix: Fetch VIX for temperature (T) calculation
        include_options_flow: Fetch sector greek flow for coupling (J) - only for sector mode
        include_hmm: Whether to fit a 3-state Hidden Markov Model for regime detection
        generate_charts: Whether to generate Plotly visualizations (False for Canvas)
        rsi_period: RSI period for external field breadth calculation (default 14)
        
    Returns:
        Dict containing:
        - herding_index: Composite herding measure (0-1) with PCA weights
        - ising_statistics: Raw and percentile values for all 4 statistics
        - ising_parameters: Temperature (T), External Field (h), Coupling (J)
        - hmm_regime: Regime classification and probabilities (if include_hmm=True)
        - trading_implications: Crowding risk, contagion risk, momentum regime, reversal warnings
        - raw_charts: Raw Plotly dicts (if generate_charts=True), NOT wrapped
    """
    start_time = datetime.now()
    logger.info(f"[PARAMS] tickers={tickers}, sectors={sectors}, field_mode={field_mode}, generate_charts={generate_charts}")
    
    try:
        # =====================================================================
        # STEP 1: Fetch data (custom tickers or sector ETFs)
        # =====================================================================
        fetcher = HerdingDataFetcher()
        await fetcher.connect()
        
        try:
            if tickers:
                # Custom tickers mode
                logger.info(f"Fetching custom tickers: {tickers}, {lookback_days} days")
                logger.info(f"Field mode: {field_mode}, Include VIX: {include_vix}")
                
                data = await fetcher.fetch_ticker_data(
                    tickers=tickers,
                    lookback_days=lookback_days,
                    include_vix=include_vix,
                )
                greek_flow_data = None  # Greek flow only available for sectors
                
                # For macro mode with custom tickers, also fetch sector data and FRED
                sector_prices_dict = None
                fred_data = None
                if field_mode == "macro":
                    logger.info("Macro mode: fetching sector data and FRED for external field")
                    sector_data = await fetcher.fetch_all_sector_data(
                        lookback_days=lookback_days,
                        include_vix=False,
                        include_greek_flow=False,
                    )
                    sector_prices_dict = sector_data.get("prices_dict", {})
                    
                    # Fetch FRED macro indicators
                    fred_data = await fetcher.fetch_fred_data()
                    if fred_data and not fred_data.get("error"):
                        logger.info(f"FRED data fetched: {list(fred_data.keys())}")
                    else:
                        logger.warning(f"FRED fetch failed or unavailable: {fred_data.get('error', 'unknown')}")
            else:
                # Sector ETF mode (default)
                logger.info(f"Fetching sector data: {lookback_days} days, {window} day window")
                logger.info(f"Field mode: {field_mode}, Include VIX: {include_vix}, Include options flow: {include_options_flow}")
                
                data = await fetcher.fetch_all_sector_data(
                    sectors=sectors,
                    lookback_days=lookback_days,
                    include_vix=include_vix,
                    include_greek_flow=include_options_flow,
                )
                greek_flow_data = data.get("greek_flow_data")
                sector_prices_dict = data.get("prices_dict", {})  # Same as input for sectors
                
                # Fetch FRED for macro mode in sector mode too
                fred_data = None
                if field_mode == "macro":
                    logger.info("Macro mode: fetching FRED data")
                    fred_data = await fetcher.fetch_fred_data()
                    if fred_data and not fred_data.get("error"):
                        logger.info(f"FRED data fetched: {list(fred_data.keys())}")
                    else:
                        logger.warning(f"FRED fetch failed: {fred_data.get('error', 'unknown')}")
        finally:
            await fetcher.cleanup()
        
        if data["returns_df"].empty:
            return {
                "status": "error",
                "error": "Failed to fetch ticker data",
                "metadata": {
                    "lookback_days": lookback_days,
                    "window": window,
                    "tickers_requested": tickers or sectors or list(SECTOR_ETFS.keys()),
                }
            }
        
        returns_df = data["returns_df"]
        vix_data = data.get("vix_data")
        prices_dict = data.get("prices_dict", {})
        
        logger.info(f"Fetched {data['n_observations']} observations for {len(data['tickers'])} tickers")
        if vix_data:
            logger.info(f"VIX current: {vix_data.get('current', 'N/A')}")
        if prices_dict:
            logger.info(f"Prices for {len(prices_dict)} tickers (for RSI breadth)")
        if greek_flow_data:
            logger.info(f"Greek flow for {len(greek_flow_data)} sectors")
        
        # =====================================================================
        # STEP 2: Compute Ising statistics with T, h, J parameters
        # =====================================================================
        logger.info(f"Computing Ising statistics with field_mode={field_mode}...")
        
        ising_stats = compute_all_ising_statistics(
            returns_df=returns_df,
            window=window,
            use_pca=True,
            vix_data=vix_data,
            prices_dict=prices_dict,
            greek_flow_data=greek_flow_data,
            field_mode=field_mode,
            rsi_period=rsi_period,
            sector_prices_dict=sector_prices_dict if field_mode == "macro" else None,
            fred_data=fred_data if field_mode == "macro" else None,
        )
        
        if ising_stats.get("status") != "success":
            return {
                "status": "error",
                "error": ising_stats.get("error", "Ising statistics computation failed"),
                "metadata": {
                    "lookback_days": lookback_days,
                    "window": window,
                    "n_observations": data["n_observations"],
                }
            }
        
        # =====================================================================
        # STEP 3: Optional HMM regime detection
        # =====================================================================
        hmm_result = None
        if include_hmm:
            logger.info("Fitting HMM for regime detection...")
            hmm_result = detect_hmm_regime(ising_stats, n_states=3)
        
        # =====================================================================
        # STEP 4: Generate charts
        # =====================================================================
        charts = []
        if generate_charts:
            logger.info("Generating charts...")
            try:
                charts = generate_herding_charts(ising_stats, hmm_result)
                logger.info(f"Generated {len(charts)} charts")
            except Exception as e:
                logger.error(f"Chart generation failed: {e}", exc_info=True)
                charts = []
        
        # =====================================================================
        # STEP 5: Build response
        # =====================================================================
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # Clean up output (remove large history arrays from main response)
        clean_stats = {
            "magnetization": {
                k: v for k, v in ising_stats["ising_statistics"]["magnetization"].items()
                if k not in ["history", "rolling_history"]
            },
            "susceptibility": {
                k: v for k, v in ising_stats["ising_statistics"]["susceptibility"].items()
                if k != "history"
            },
            "correlation_length": {
                k: v for k, v in ising_stats["ising_statistics"]["correlation_length"].items()
                if k != "history"
            },
            "critical_slowing_down": {
                k: v for k, v in ising_stats["ising_statistics"]["critical_slowing_down"].items()
                if k != "history"
            },
        }
        
        # Clean up Ising parameters (remove history arrays)
        clean_params = {}
        if "ising_parameters" in ising_stats:
            for param_name, param_data in ising_stats["ising_parameters"].items():
                if isinstance(param_data, dict):
                    clean_params[param_name] = {
                        k: v for k, v in param_data.items()
                        if k not in ["vix_history", "history"]
                    }
                else:
                    clean_params[param_name] = param_data
        
        result = {
            "status": "success",
            "herding_index": ising_stats["herding_index"],
            "pca_weights": ising_stats["herding_index"].get("pca_weights", {}),
            "ising_parameters": clean_params,
            "ising_statistics": clean_stats,
            "signal_summary": ising_stats["signal_summary"],
            "trading_implications": ising_stats["trading_implications"],
            "metadata": {
                "lookback_days": lookback_days,
                "window": window,
                "n_observations": data["n_observations"],
                "tickers": data["tickers"],
                "mode": "custom_tickers" if tickers else "sector_etfs",
                "elapsed_seconds": elapsed_time,
                "timestamp": datetime.now().isoformat(),
                "field_mode": field_mode,
                "rsi_period": rsi_period,
                "include_vix": include_vix,
                "include_options_flow": include_options_flow if not tickers else False,
            },
        }
        
        if hmm_result:
            result["hmm_regime"] = {
                k: v for k, v in hmm_result.items()
                if k != "model_info"
            }
        
        if charts:
            logger.info(f"Generated {len(charts)} raw charts")
            # Store raw charts - wrapping done by caller if needed
            result["raw_charts"] = charts
        
        # Build interpretation with T, h, J insights
        herding_val = ising_stats["herding_index"]["value"]
        regime = ising_stats["herding_index"]["regime"]
        elevated = ising_stats["signal_summary"]["elevated_count"]
        
        # Base interpretation
        if herding_val > 0.7:
            interpretation = (
                f"CAUTION: Herding index at {herding_val:.0%} ({regime}). "
                f"{elevated}/4 early warning signals elevated. "
                "High contagion risk - consider reducing correlated positions."
            )
        elif herding_val > 0.5:
            interpretation = (
                f"Herding index moderately elevated at {herding_val:.0%} ({regime}). "
                f"{elevated}/4 signals elevated. Monitor for further deterioration."
            )
        else:
            interpretation = (
                f"Herding index normal at {herding_val:.0%} ({regime}). "
                "Market in dispersed regime - idiosyncratic stock selection may outperform."
            )
        
        # Add T, h, J context
        ising_params = ising_stats.get("ising_parameters", {})
        
        # Temperature context
        temp = ising_params.get("temperature", {})
        if temp.get("available"):
            T_regime = temp.get("T_regime", "NORMAL_TEMP")
            if T_regime == "HIGH_TEMP":
                interpretation += " VIX elevated (high temperature) - signals less reliable."
            elif T_regime == "LOW_TEMP":
                interpretation += " VIX low (low temperature) - herding signals more persistent."
        
        # External field context
        field = ising_params.get("external_field", {})
        if field.get("available"):
            bias = field.get("bias", "NEUTRAL")
            method = field.get("method", "rsi_breadth")
            breadth = field.get("breadth", field.get("h_value", 0))
            if bias in ["BULLISH", "MILDLY_BULLISH"]:
                interpretation += f" Market breadth bullish ({method}: {breadth:.0%} participation)."
            elif bias in ["BEARISH", "MILDLY_BEARISH"]:
                interpretation += f" Market breadth weak ({method}: {breadth:.0%} participation)."
        
        # Coupling / divergence warning
        coupling = ising_params.get("coupling", {})
        if coupling.get("available") and coupling.get("divergence"):
            direction = coupling.get("divergence_direction", "")
            interpretation += f" ⚠️ OPTIONS-PRICE DIVERGENCE DETECTED ({direction}) - potential reversal signal!"
        
        result["interpretation"] = interpretation
        
        logger.info(f"Analysis complete in {elapsed_time:.2f}s: {regime}, {herding_val:.2%}")
        
        return result
        
    except Exception as e:
        logger.error(f"Herding regime analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "metadata": {
                "lookback_days": lookback_days,
                "window": window,
            }
        }


@function_tool
async def analyze_herding_regime(
    tickers: Optional[List[str]] = None,
    lookback_days: int = 252,
    window: int = 21,
    sectors: Optional[List[str]] = None,
    field_mode: str = "discretionary",
    include_vix: bool = True,
    include_options_flow: bool = True,
    include_hmm: bool = True,
    generate_charts: bool = True,
    rsi_period: int = 14,
) -> Dict[str, Any]:
    """
    Detect herding/crowding risk using full Ising model statistics and parameters.
    
    This is the agent-facing version that wraps charts for the chat interface.
    For Canvas integration, use analyze_herding_regime_internal directly.
    
    Computes 4 physics-inspired early warning signals from any ticker universe:
    1. Magnetization - Net market sentiment (are tickers aligned?)
    2. Susceptibility - Response sensitivity (how violently does sentiment react?)
    3. Correlation Length - Herding spread (are tickers moving together?)
    4. Critical Slowing Down - Momentum persistence (is mean-reversion slowing?)
    
    Plus 3 Ising model parameters:
    - Temperature (T) from VIX: High VIX = disorder, Low VIX = ordered states
    - External Field (h) from RSI breadth: Participation-based directional bias
    - Coupling (J) from options flow: Correlation between price and options sentiment
    
    Args:
        tickers: List of ticker symbols to analyze (e.g., ["AAPL", "MSFT", "GOOGL"]).
                 If None, falls back to sectors or all 11 SPDR sector ETFs.
        lookback_days: Number of trading days of history (default 252 = 1 year)
        window: Rolling window for statistics (default 21 = 1 month)
        sectors: Optional list of sectors to analyze (used if tickers is None).
        field_mode: External field calculation mode:
            - "discretionary": RSI breadth of input tickers (participation within universe)
            - "macro": RSI breadth of all sectors + FRED factors (external pressure)
        include_vix: Fetch VIX for temperature (T) calculation
        include_options_flow: Fetch sector greek flow for coupling (J) - only for sector mode
        include_hmm: Whether to fit a 3-state Hidden Markov Model for regime detection
        generate_charts: Whether to generate Plotly visualizations
        rsi_period: RSI period for external field breadth calculation (default 14)
        
    Returns:
        Dict containing:
        - herding_index: Composite herding measure (0-1) with PCA weights
        - ising_statistics: Raw and percentile values for all 4 statistics
        - ising_parameters: Temperature (T), External Field (h), Coupling (J)
        - hmm_regime: Regime classification and probabilities (if include_hmm=True)
        - trading_implications: Crowding risk, contagion risk, momentum regime, reversal warnings
        - charts: Wrapped Plotly figures for agent chat (if generate_charts=True)
        
    Example usage:
        # Analyze a portfolio
        result = await analyze_herding_regime(
            tickers=["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"],
            field_mode="discretionary"  # Herding within portfolio
        )
        
        # Analyze with macro external pressure
        result = await analyze_herding_regime(
            tickers=["AAPL", "MSFT", "NVDA"],
            field_mode="macro"  # External market pressure on these stocks
        )
        
        # Default: all 11 sector ETFs
        result = await analyze_herding_regime()
    """
    # Call internal implementation
    result = await analyze_herding_regime_internal(
        tickers=tickers,
        lookback_days=lookback_days,
        window=window,
        sectors=sectors,
        field_mode=field_mode,
        include_vix=include_vix,
        include_options_flow=include_options_flow,
        include_hmm=include_hmm,
        generate_charts=generate_charts,
        rsi_period=rsi_period,
    )
    
    # Wrap charts for agent interface if present
    if result.get("status") == "success" and result.get("raw_charts"):
        raw_charts = result.pop("raw_charts")
        logger.info(f"Wrapping {len(raw_charts)} charts for agent")
        result["charts"] = wrap_plotly_charts(raw_charts, default_type="herding_regime")
        logger.info(f"Charts wrapped: {len(result.get('charts', []))} handles")
    
    return result
