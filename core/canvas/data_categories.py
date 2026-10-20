"""
Data Categories - Maps datasets to user-friendly categories.

Provides a mapping from technical dataset names (like "ratios-ttm")
to user-friendly categories (like "Valuation") that users can browse.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Set, Optional

from .object_registry import get_object_type, OBJECT_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class Category:
    """A user-friendly data category."""
    name: str
    description: str
    icon: str
    datasets: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "datasets": self.datasets,
        }


# Category definitions - maps datasets to user-friendly categories
# NOTE: Only include datasets that exist in the FMP DDC catalog
CATEGORY_DEFINITIONS: Dict[str, Dict] = {
    "Valuation": {
        "description": "P/E, P/B, EV/EBITDA, price multiples",
        "icon": "chart-bar",
        "datasets": [
            "ratios-ttm",
            "ratios",
            "key-metrics-ttm",
            "key-metrics",
            "enterprise-values",
            "dcf",
            "advanced-dcf",
            "price-target",
            "price-target-consensus",
        ],
    },
    "Financials": {
        "description": "Income statement, balance sheet, cash flow",
        "icon": "document-text",
        "datasets": [
            "income-statement",
            "balance-sheet-statement",
            "cash-flow-statement",
            "income-statement-growth",
            "financial-growth",
            "financial-statement-full-as-reported",
            "financial-reports-json",
        ],
    },
    "Price & Volume": {
        "description": "Historical prices, quotes, changes",
        "icon": "trending-up",
        "datasets": [
            "company-quote",
            "historical-price-full",
            "stock-price-change",
            "market-capitalization",
        ],
    },
    "Technicals": {
        "description": "RSI, MACD, moving averages, Bollinger Bands",
        "icon": "activity",
        "datasets": [
            "technical-indicator-sma",
            "technical-indicator-ema",
            "technical-indicator-rsi",
            "technical-indicator-bbands",
            "technical-indicator-stoch",
        ],
    },
    "Analyst Estimates": {
        "description": "EPS estimates, revenue forecasts, ratings",
        "icon": "users",
        "datasets": [
            "analyst-estimates",
            "grade",
            "grades-consensus",
            "grades-historical",
            "rating",
            "historical-rating",
            "price-target-news",
        ],
    },
    "Ownership": {
        "description": "Institutional holders, insider transactions",
        "icon": "briefcase",
        "datasets": [
            "institutional-holder",
            "mutual-fund-holder",
            "etf-holder",
            "insider-trading",
        ],
    },
    "Company Profile": {
        "description": "Company info, sector, employees, description",
        "icon": "building",
        "datasets": [
            "company-profile",
            "shares-float",
        ],
    },
    "Dividends & Splits": {
        "description": "Dividend history, stock splits",
        "icon": "gift",
        "datasets": [
            "stock-dividend",
            "stock-split",
        ],
    },
    "Earnings": {
        "description": "Earnings calendar, confirmed dates",
        "icon": "megaphone",
        "datasets": [
            "earning-call-calendar",
            "earnings-confirmed",
        ],
    },
    "News & Filings": {
        "description": "Press releases, news, SEC filings",
        "icon": "newspaper",
        "datasets": [
            "press-releases",
            "fmp-articles",
            "rss-feed",
            "rss-feed-8k",
            "stock-news",
            "sec-filings",
        ],
    },
    "ESG": {
        "description": "Environmental, social, governance scores",
        "icon": "leaf",
        "datasets": [
            "esg-ratings",
            "esg-scores",
        ],
    },
    "ETF Data": {
        "description": "ETF holdings, sector weights",
        "icon": "pie-chart",
        "datasets": [
            "etf-holder",
        ],
    },
    "Congress & Insider": {
        "description": "Congressional trades, insider activity",
        "icon": "landmark",
        "datasets": [
            "senate-trading",
            "senate-disclosure",
            "insider-trading",
            "insider-trading-rss-feed",
        ],
    },
    "Economic Data": {
        "description": "GDP, inflation, unemployment, rates",
        "icon": "globe",
        "datasets": [
            "economic-calendar",
            "treasury",
            "market-risk-premium",
        ],
    },
    "Market Overview": {
        "description": "Sector performance, gainers, losers",
        "icon": "trending-up",
        "datasets": [
            "sector-performance",
            "industry-performance",
            "biggest-gainers",
            "biggest-losers",
            "most-actives",
        ],
    },
}


def get_all_categories() -> List[Category]:
    """Get all defined categories."""
    return [
        Category(
            name=name,
            description=info["description"],
            icon=info["icon"],
            datasets=info["datasets"],
        )
        for name, info in CATEGORY_DEFINITIONS.items()
    ]


def get_categories_for_object(object_type: str) -> List[Category]:
    """
    Get categories available for a specific object type.
    
    Only returns categories that have at least one dataset
    that the object type provides.
    
    Args:
        object_type: The object type name (e.g., "equity", "crypto")
        
    Returns:
        List of Category objects with available datasets
    """
    obj = get_object_type(object_type)
    if not obj:
        logger.warning(f"Unknown object type: {object_type}")
        return []
    
    available_datasets = obj.provides
    available_categories = []
    
    for name, info in CATEGORY_DEFINITIONS.items():
        # Find datasets that are both in category and provided by object
        matching_datasets = [
            ds for ds in info["datasets"]
            if ds in available_datasets
        ]
        
        if matching_datasets:
            available_categories.append(Category(
                name=name,
                description=info["description"],
                icon=info["icon"],
                datasets=matching_datasets,
            ))
    
    return available_categories


def get_category_by_name(name: str) -> Optional[Category]:
    """Get a specific category by name."""
    if name in CATEGORY_DEFINITIONS:
        info = CATEGORY_DEFINITIONS[name]
        return Category(
            name=name,
            description=info["description"],
            icon=info["icon"],
            datasets=info["datasets"],
        )
    return None


def get_datasets_for_category(category_name: str) -> List[str]:
    """Get all datasets for a category."""
    if category_name in CATEGORY_DEFINITIONS:
        return CATEGORY_DEFINITIONS[category_name]["datasets"]
    return []


def get_category_for_dataset(dataset: str) -> Optional[str]:
    """Find which category a dataset belongs to."""
    for name, info in CATEGORY_DEFINITIONS.items():
        if dataset in info["datasets"]:
            return name
    return None


def get_category_for_field(field_name: str, endpoint: str) -> Optional[str]:
    """
    Determine category for a field based on its endpoint.
    
    Args:
        field_name: The field name (e.g., "priceEarningsRatioTTM")
        endpoint: The endpoint/dataset name (e.g., "ratios-ttm")
        
    Returns:
        Category name or None
    """
    return get_category_for_dataset(endpoint)





