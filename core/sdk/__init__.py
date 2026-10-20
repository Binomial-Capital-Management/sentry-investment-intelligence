"""
Public SDK entrypoints for direct IDE/API usage.

For now, we expose valuation helpers (comparable companies) as the first
capability and will expand to other domains as wrappers are extracted.
"""

from .valuation import ValuationSDK, CompsResult, CompsParams


class SentrySDK:
    """Simple facade aggregating available SDK domains."""

    def __init__(self) -> None:
        self.valuation = ValuationSDK()


__all__ = [
    "SentrySDK",
    "ValuationSDK",
    "CompsParams",
    "CompsResult",
]

