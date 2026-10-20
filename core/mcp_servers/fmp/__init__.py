"""
FMP MCP Server Package.

This package provides MCP (Model Context Protocol) servers for Financial Modeling Prep integration:
- Dynamic Dataset Catalog (DDC) management
- FMPMarketDataServer for market data discovery and fetching
- FMPDocumentServer for document discovery and retrieval
"""

from .ddc_loader import (
    DDCLoader,
    DDCCatalog,
    DatasetEntry,
    DatasetClass,
    RateLimitConfig,
    get_default_loader,
    load_catalog,
    get_discoverable_datasets
)

__all__ = [
    # Main loader class
    'DDCLoader',
    
    # Data models
    'DDCCatalog',
    'DatasetEntry',
    'DatasetClass',
    'RateLimitConfig',
    
    # Convenience functions
    'get_default_loader',
    'load_catalog',
    'get_discoverable_datasets'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Engineering'