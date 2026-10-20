"""
Structuring Tools Module - Collection of structured products pricing tools

Tools for pricing and analyzing structured financial products including:
- Interest rate swaps
- Swaptions (payer/receiver with Black & Bachelier models)
- Equity options (Black-Scholes, Binomial, Monte Carlo)
- Credit default swaps (Merton/KMV model)
- Variance swaps (replicating portfolio from options chain)
- Dispersion trades (long index vol, short constituent vols)
- Exotic derivatives (barrier, Asian, lookback, digital options)
- Total return swaps (future)
- Asset swaps (future)

For Canvas integration, use the *_internal functions directly.
"""

from .interest_rate_swap_tool import price_interest_rate_swap
# Internal function import for Canvas only - not exposed to agents
from .interest_rate_swap_tool import price_interest_rate_swap_internal
from .swaption_pricing_tool import price_swaption
# Internal function import for Canvas only - not exposed to agents
from .swaption_pricing_tool import price_swaption_internal
from .credit_default_swap_tool import price_credit_default_swap
# Internal function import for Canvas only - not exposed to agents
from .credit_default_swap_tool import price_credit_default_swap_internal
from .variance_swap_tool import price_variance_swap, price_variance_swap_internal
from .dispersion_trade_tool import price_dispersion_trade, price_dispersion_trade_internal
from .exotic_derivatives_pricing_tool import price_exotic_derivatives, price_exotic_derivatives_internal
from core.agents.quant_tools.equity_option_pricing_tool import price_equity_options

__all__ = [
    # Agent-facing tools (with @function_tool decorator)
    'price_interest_rate_swap',
    'price_swaption',
    'price_credit_default_swap',
    'price_variance_swap',
    'price_dispersion_trade',
    'price_exotic_derivatives',
    'price_equity_options',
    # Internal functions are imported but NOT exported (Canvas only)
    # 'price_variance_swap_internal',
    # 'price_dispersion_trade_internal',
    # 'price_exotic_derivatives_internal',
]

STRUCTURING_TOOLS = [
    price_interest_rate_swap,
    price_swaption,
    price_credit_default_swap,
    price_variance_swap,
    price_dispersion_trade,
    price_exotic_derivatives,
    # NOTE: price_equity_options is NOT included here - it's already in quant_tools
    # and including it here causes duplicate tool names which Anthropic rejects
]
