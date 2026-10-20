"""
Quant Tools Module - Collection of quantitative analysis tools
"""

from .arima_forecast_tool import forecast_arima
from .pca_analysis_tool import analyze_pca_eigen_portfolios
from .feature_importance_tool import analyze_feature_importance
from .cointegration_tool import identify_cointegrated_pairs, screen_cointegrated_pairs
from .hedge_ratio_tool import calculate_hedge_ratio
from .mean_reversion_signals_tool import generate_mean_reversion_signals
from .correlation_swap_tool import price_correlation_swap
# Internal function import for Canvas only - not exposed to agents
from .correlation_swap_tool import price_correlation_swap_internal
from .correlation_matrix_tool import analyze_correlation_matrix
from .delta_exposure_tool import calculate_delta_exposure
from .gamma_exposure_tool import calculate_gamma_exposure
from .vega_exposure_tool import calculate_vega_exposure
from .theta_decay_tool import calculate_theta_decay
from .cross_greeks_tool import calculate_cross_greeks
# Internal function import for Canvas only - not exposed to agents
from .cross_greeks_tool import calculate_cross_greeks_internal
from .dynamic_hedge_tool import construct_dynamic_hedge
from .equity_option_pricing_tool import price_equity_options, price_equity_options_internal
from .volatility_surface_tool import model_volatility_surface, model_volatility_surface_internal
from .greeks_surface_tool import model_greeks_surface
from .dealer_gamma_regime_tool import analyze_dealer_gamma_regime, analyze_dealer_gamma_regime_internal
from .vanna_charm_flow_tool import analyze_vanna_charm_flow
from .iv_rv_screener_tool import analyze_iv_rv_vs_peers
from .signal_confluence_detector import detect_signal_confluence, scan_universe_confluence, detect_signal_confluence_internal
from .earnings_pattern_analyzer import analyze_earnings_patterns
from .arimax_macro_forecast_tool import forecast_arimax_macro
# Internal function import for Canvas only - not exposed to agents
from .arimax_macro_forecast_tool import forecast_arimax_macro_internal
from .graph_theory_portfolio_analyzer import analyze_graph_theory_risk
from .gex_support_resistance_tool import analyze_gex_levels, map_gex_support_resistance
from .squeeze_detector import detect_squeeze_setup
from .nope_divergence_tool import scan_nope_divergences, scan_nope_divergences_internal
from .sector_rotation import analyze_sector_rotation_flow
from .systemic_risk_score_tool import analyze_systemic_risk_score
from .optimal_hedge_path_tool import find_optimal_hedge_path
from .recession_field_theory import analyze_recession_field
from .herding_regime import analyze_herding_regime
from .geodesic_distance import analyze_portfolio_geodesic_distance
from .instanton_rare_event import analyze_instanton_crash

__all__ = [
    'forecast_arima',
    'forecast_arimax_macro',
    'analyze_pca_eigen_portfolios',
    'analyze_feature_importance',
    'identify_cointegrated_pairs',
    'screen_cointegrated_pairs',
    'calculate_hedge_ratio',
    'generate_mean_reversion_signals',
    'price_correlation_swap',
    'analyze_correlation_matrix',
    'calculate_delta_exposure',
    'calculate_gamma_exposure',
    'calculate_vega_exposure',
    'calculate_theta_decay',
    'calculate_cross_greeks',
    'construct_dynamic_hedge',
    'price_equity_options',
    'model_volatility_surface',
    'model_greeks_surface',
    'analyze_dealer_gamma_regime',
    'analyze_vanna_charm_flow',
    'analyze_iv_rv_vs_peers',
    'detect_signal_confluence',
    'scan_universe_confluence',
    'analyze_earnings_patterns',
    'forecast_arimax_macro',
    'analyze_graph_theory_risk',
    'analyze_gex_levels',
    'map_gex_support_resistance',  # Legacy alias for analyze_gex_levels
    'detect_squeeze_setup',
    'scan_nope_divergences',
    'analyze_sector_rotation_flow',
    'analyze_systemic_risk_score',
    'find_optimal_hedge_path',
    'analyze_recession_field',
    'analyze_herding_regime',
    'analyze_portfolio_geodesic_distance',
    'analyze_instanton_crash'
]

QUANT_TOOLS = [
    forecast_arima,
    forecast_arimax_macro,
    analyze_pca_eigen_portfolios,
    analyze_feature_importance,
    identify_cointegrated_pairs,
    screen_cointegrated_pairs,
    calculate_hedge_ratio,
    generate_mean_reversion_signals,
    price_correlation_swap,
    analyze_correlation_matrix,
    calculate_delta_exposure,
    calculate_gamma_exposure,
    calculate_vega_exposure,
    calculate_theta_decay,
    calculate_cross_greeks,
    construct_dynamic_hedge,
    price_equity_options,
    model_volatility_surface,
    model_greeks_surface,
    analyze_dealer_gamma_regime,
    analyze_vanna_charm_flow,
    analyze_iv_rv_vs_peers,
    detect_signal_confluence,
    scan_universe_confluence,
    analyze_earnings_patterns,
    forecast_arimax_macro,
    analyze_graph_theory_risk,
    analyze_gex_levels,  # Replaces map_gex_support_resistance with richer analysis
    detect_squeeze_setup,
    scan_nope_divergences,
    analyze_sector_rotation_flow,
    analyze_systemic_risk_score,
    find_optimal_hedge_path,
    analyze_recession_field,
    analyze_herding_regime,
    analyze_portfolio_geodesic_distance,
    analyze_instanton_crash
]
