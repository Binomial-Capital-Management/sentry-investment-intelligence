"""
Risk Tools Module - Collection of risk calculation tools
"""

from .var_tool import calculate_var
from .monte_carlo_tool import run_monte_carlo
from .optimization_tool import optimize_portfolio
from .barra_factors_tool import analyze_barra_factors
from .hedge_tool import create_hedge_portfolio
from .fft_denoising_tool import analyze_fft_trends
from .rolling_correlation_tool import calculate_rolling_correlation
from .implied_correlation_tool import calculate_implied_correlation
# Internal function import for Canvas only - not exposed to agents
from .implied_correlation_tool import calculate_implied_correlation_internal
from .fft_denoising_tool import analyze_fft_trends_internal
from .rolling_correlation_tool import calculate_rolling_correlation_internal
from .correlation_stress_test_tool import stress_test_correlation
from core.agents.quant_tools.pca_analysis_tool import analyze_pca_eigen_portfolios
from core.agents.quant_tools.correlation_swap_tool import price_correlation_swap
from core.agents.quant_tools.correlation_matrix_tool import analyze_correlation_matrix
from core.agents.quant_tools.delta_exposure_tool import calculate_delta_exposure
from core.agents.quant_tools.gamma_exposure_tool import calculate_gamma_exposure
from core.agents.quant_tools.vega_exposure_tool import calculate_vega_exposure
from core.agents.quant_tools.theta_decay_tool import calculate_theta_decay
from core.agents.quant_tools.cross_greeks_tool import calculate_cross_greeks
from core.agents.quant_tools.dynamic_hedge_tool import construct_dynamic_hedge
from core.agents.quant_tools.graph_theory_portfolio_analyzer import analyze_graph_theory_risk
from core.agents.quant_tools.systemic_risk_score_tool import analyze_systemic_risk_score
from core.agents.quant_tools.squeeze_detector import detect_squeeze_setup
from core.agents.quant_tools.optimal_hedge_path_tool import find_optimal_hedge_path

__all__ = [
    'calculate_var',
    'run_monte_carlo',
    'optimize_portfolio',
    'analyze_barra_factors',
    'create_hedge_portfolio',
    'analyze_fft_trends',
    'calculate_rolling_correlation',
    'calculate_implied_correlation',
    'stress_test_correlation',
    'analyze_pca_eigen_portfolios',
    'price_correlation_swap',
    'analyze_correlation_matrix',
    'calculate_delta_exposure',
    'calculate_gamma_exposure',
    'calculate_vega_exposure',
    'calculate_theta_decay',
    'calculate_cross_greeks',
    'construct_dynamic_hedge',
    'analyze_graph_theory_risk',
    'analyze_systemic_risk_score',
    'detect_squeeze_setup',
    'find_optimal_hedge_path'
]

RISK_TOOLS = [
    calculate_var,
    run_monte_carlo,
    optimize_portfolio,
    analyze_barra_factors,
    create_hedge_portfolio,
    analyze_fft_trends,
    calculate_rolling_correlation,
    calculate_implied_correlation,
    stress_test_correlation,
    analyze_pca_eigen_portfolios,
    price_correlation_swap,
    analyze_correlation_matrix,
    calculate_delta_exposure,
    calculate_gamma_exposure,
    calculate_vega_exposure,
    calculate_theta_decay,
    calculate_cross_greeks,
    construct_dynamic_hedge,
    analyze_graph_theory_risk,
    analyze_systemic_risk_score,
    detect_squeeze_setup,
    find_optimal_hedge_path
]