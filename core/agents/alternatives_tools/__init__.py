"""
Alternatives Tools Module - Collection of alternative assets analysis tools
for crypto, forex, and commodities.
"""

from .crypto_equity_beta_regime_tool import analyze_crypto_equity_beta_regime, analyze_crypto_equity_beta_regime_internal
from .commodity_ratio_tool import analyze_commodity_ratio, analyze_commodity_ratio_internal
from .forex_carry_screener_tool import screen_forex_carry_trades, screen_forex_carry_trades_internal
from .commodity_seasonality_tool import analyze_commodity_seasonality, analyze_commodity_seasonality_internal
from .commodity_momentum_tool import screen_commodity_momentum, screen_commodity_momentum_internal

__all__ = [
    'analyze_crypto_equity_beta_regime',
    'analyze_commodity_ratio',
    'screen_forex_carry_trades',
    'analyze_commodity_seasonality',
    'screen_commodity_momentum',
    # Internal functions are imported but NOT exported (Canvas only)
    # 'analyze_crypto_equity_beta_regime_internal',
    # 'analyze_commodity_ratio_internal',
    # 'screen_forex_carry_trades_internal',
    # 'analyze_commodity_seasonality_internal',
    # 'screen_commodity_momentum_internal',
]

ALTERNATIVES_TOOLS = [
    analyze_crypto_equity_beta_regime,
    analyze_commodity_ratio,
    screen_forex_carry_trades,
    analyze_commodity_seasonality,
    screen_commodity_momentum,
]

