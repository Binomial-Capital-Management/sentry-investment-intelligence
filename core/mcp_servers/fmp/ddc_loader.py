"""
Dynamic Dataset Catalog (DDC) Loader for FMP Integration.

This module provides a robust loader for the FMP dataset catalog with:
- Pydantic validation for schema enforcement
- Filtering by class and discoverable status
- URL template substitution
- Caching support preparation
- Error handling and logging
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator, HttpUrl
import os

logger = logging.getLogger(__name__)


class DatasetClass(str, Enum):
    """Valid dataset classes in the catalog."""
    MARKET = "market"
    DOCUMENT = "document"
    MARKET_DATA = "market-data"
    ECONOMIC = "economic"
    VALUATION = "valuation"
    FORECAST = "forecast"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITIES = "commodities"
    ANALYST = "analyst"
    ESG = "esg"
    CORPORATE_ACTIONS = "corporate_actions"
    OWNERSHIP = "ownership"
    DOCUMENTS = "documents"
    INSIDER = "insider"
    POLITICAL = "political"
    NEWS = "news"
    TECHNICAL = "technical"
    MARKET_WIDE = "market_wide"
    ECONOMICS = "economics"
    ETF = "etf"
    INSTITUTIONAL = "institutional"
    CONGRESSIONAL = "congressional"
    MA = "ma"  # Mergers & Acquisitions
    IPO = "ipo"  # Initial Public Offerings
    COMPANY = "company"  # Company information (executives, etc.)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration for a dataset."""
    rps: int = Field(default=10, ge=1, le=100, description="Requests per second")
    burst: int = Field(default=30, ge=1, le=200, description="Burst capacity")


class DatasetEntry(BaseModel):
    """A single dataset entry in the catalog."""
    dataset: str = Field(..., min_length=1, description="Unique dataset identifier")
    class_: DatasetClass = Field(..., alias="class", description="Dataset classification")
    discoverable: bool = Field(..., description="Whether dataset is discoverable")
    url: str = Field(..., description="URL template with {symbol} placeholder")
    method: str = Field(default="GET", description="HTTP method")
    params_schema: Dict[str, str] = Field(default_factory=dict, description="Parameter schema")
    required_params: List[str] = Field(default_factory=list, description="Parameters that must be provided (subset of params_schema)")
    identifier_param: Optional[str] = Field(None, description="Query parameter name for symbol/identifier")
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig, description="Rate limits")
    cache_ttl: int = Field(default=300, ge=0, description="Cache TTL in seconds")
    notes: Optional[str] = Field(None, description="Human-readable description")
    field_mappings: Optional[Dict[str, Any]] = Field(None, description="Optional field name mappings for discovery")
    allow_additional_params: bool = Field(
        default=False,
        description="Allow parameters outside the declared schema (for flexible endpoints like screeners)",
    )

    class Config:
        populate_by_name = True
    
    @validator('url')
    def validate_url_template(cls, v):
        """Ensure URL has proper template structure."""
        if not v.startswith('/'):
            raise ValueError(f"URL must start with /: {v}")
        # Allow {symbol} placeholder or query params
        if '{' in v and '}' not in v:
            raise ValueError(f"Unclosed placeholder in URL: {v}")
        return v
    
    @validator('method')
    def validate_method(cls, v):
        """Ensure HTTP method is valid."""
        allowed = ['GET', 'POST', 'PUT', 'DELETE']
        if v.upper() not in allowed:
            raise ValueError(f"Method must be one of {allowed}: {v}")
        return v.upper()
    
    def substitute_url(self, **kwargs) -> str:
        """
        Substitute placeholders in URL template.
        
        Args:
            **kwargs: Values to substitute (e.g., symbol="AAPL")
            
        Returns:
            Substituted URL string
        """
        url = self.url
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            if placeholder in url:
                url = url.replace(placeholder, str(value))
        return url
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with 'class' field name."""
        data = self.dict(by_alias=True)
        return data


class DDCCatalog(BaseModel):
    """The complete Dynamic Dataset Catalog."""
    version: str = Field(..., description="Catalog version")
    last_updated: str = Field(..., description="Last update date")
    source: str = Field(..., description="Data source description")
    datasets: List[DatasetEntry] = Field(..., description="List of datasets")
    
    @validator('datasets')
    def validate_unique_datasets(cls, v):
        """Ensure dataset names are unique."""
        names = [d.dataset for d in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate dataset names: {set(duplicates)}")
        return v
    
    def get_dataset_count(self) -> Dict[str, int]:
        """Get count of datasets by class."""
        counts = {}
        for dataset in self.datasets:
            class_name = dataset.class_.value
            counts[class_name] = counts.get(class_name, 0) + 1
        return counts


class DDCLoader:
    """
    Dynamic Dataset Catalog loader with validation and filtering.
    
    This class loads and manages the FMP dataset catalog, providing:
    - Schema validation via Pydantic
    - Filtering by class and discoverable status
    - URL template substitution
    - Error handling and logging
    """
    
    def __init__(self, catalog_paths: Optional[Union[str, Path, List[Union[str, Path]]]] = None):
        """
        Initialize the DDC loader.

        Args:
            catalog_paths: Path(s) to catalog JSON file(s). Can be:
                - None: Load ALL catalogs from same directory (ddc, valuation, alternatives, tradeflow)
                - str/Path: Single catalog file
                - List[str/Path]: Multiple catalog files to merge
        """
        catalog_dir = Path(__file__).parent

        if catalog_paths is None:
            # Default: Load ALL catalog files
            self.catalog_paths = [
                catalog_dir / "ddc_catalog.json",
                catalog_dir / "valuation_catalog.json",
                catalog_dir / "alternatives_catalog.json",
                catalog_dir / "tradeflow_catalog.json"
            ]
        elif isinstance(catalog_paths, (list, tuple)):
            self.catalog_paths = [Path(p) for p in catalog_paths]
        else:
            self.catalog_paths = [Path(catalog_paths)]

        self.catalog: Optional[DDCCatalog] = None
        self._dataset_index: Dict[str, DatasetEntry] = {}

        # Load all catalogs on initialization
        self.load_catalogs()

    def load_catalogs(self, force_reload: bool = False) -> DDCCatalog:
        """
        Load and merge multiple catalog files.

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            Merged catalog object

        Raises:
            FileNotFoundError: If any catalog file doesn't exist
            ValueError: If any catalog is invalid
        """
        if self.catalog is not None and not force_reload:
            return self.catalog

        all_datasets = []
        dataset_names_seen = set()  # Track duplicates
        merged_version = "merged"
        merged_source = "FMP (all catalogs)"
        merged_last_updated = None

        for catalog_path in self.catalog_paths:
            if not catalog_path.exists():
                logger.warning(f"Catalog not found, skipping: {catalog_path}")
                continue

            try:
                with open(catalog_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Validate using Pydantic
                catalog = DDCCatalog(**data)

                # Merge datasets, skipping duplicates
                duplicates_skipped = 0
                for dataset in catalog.datasets:
                    if dataset.dataset in dataset_names_seen:
                        duplicates_skipped += 1
                        logger.debug(f"Skipping duplicate dataset: {dataset.dataset}")
                        continue
                    all_datasets.append(dataset)
                    dataset_names_seen.add(dataset.dataset)

                # Track latest update
                if merged_last_updated is None or catalog.last_updated > merged_last_updated:
                    merged_last_updated = catalog.last_updated

                logger.info(f"Loaded {catalog_path.name}: {len(catalog.datasets)} datasets ({duplicates_skipped} duplicates skipped)")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {catalog_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Failed to load {catalog_path}: {e}")
                continue

        if not all_datasets:
            raise ValueError("No valid catalogs loaded")

        # Create merged catalog
        self.catalog = DDCCatalog(
            version=merged_version,
            last_updated=merged_last_updated or "unknown",
            source=merged_source,
            datasets=all_datasets
        )

        # Build index for fast lookup
        self._build_index()

        logger.info(f"Merged catalog: {len(self.catalog.datasets)} total datasets from {len(self.catalog_paths)} files")
        logger.info(f"Dataset breakdown: {self.catalog.get_dataset_count()}")

        return self.catalog

    def load_catalog(self, force_reload: bool = False) -> DDCCatalog:
        """
        Load or reload the catalog from disk.
        Kept for backward compatibility - calls load_catalogs().

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            Loaded catalog object
        """
        return self.load_catalogs(force_reload)
    
    def _build_index(self):
        """Build index for fast dataset lookup."""
        self._dataset_index = {}
        if self.catalog:
            for dataset in self.catalog.datasets:
                self._dataset_index[dataset.dataset] = dataset
    
    def get_dataset(self, name: str) -> Optional[DatasetEntry]:
        """
        Get a specific dataset by name.
        
        Args:
            name: Dataset name
            
        Returns:
            DatasetEntry if found, None otherwise
        """
        return self._dataset_index.get(name)
    
    def filter_by_class(self, dataset_class: Union[str, DatasetClass]) -> List[DatasetEntry]:
        """
        Filter datasets by class.
        
        Args:
            dataset_class: Class to filter by (e.g., "market", DatasetClass.MARKET)
            
        Returns:
            List of matching datasets
        """
        if not self.catalog:
            return []
        
        if isinstance(dataset_class, str):
            try:
                dataset_class = DatasetClass(dataset_class)
            except ValueError:
                logger.warning(f"Invalid dataset class: {dataset_class}")
                return []
        
        return [d for d in self.catalog.datasets if d.class_ == dataset_class]
    
    def filter_discoverable(self, discoverable: bool = True) -> List[DatasetEntry]:
        """
        Filter datasets by discoverable status.
        
        Args:
            discoverable: Whether to get discoverable datasets
            
        Returns:
            List of matching datasets
        """
        if not self.catalog:
            return []
        
        return [d for d in self.catalog.datasets if d.discoverable == discoverable]
    
    def get_discoverable_market_datasets(self) -> List[DatasetEntry]:
        """
        Get all discoverable market datasets (convenience method).
        
        Returns:
            List of discoverable market datasets
        """
        if not self.catalog:
            return []
        
        return [
            d for d in self.catalog.datasets 
            if d.discoverable and d.class_ == DatasetClass.MARKET
        ]
    
    def get_document_datasets(self) -> List[DatasetEntry]:
        """
        Get all document datasets (convenience method).
        
        Returns:
            List of document datasets
        """
        return self.filter_by_class(DatasetClass.DOCUMENT)
    
    def search_datasets(self, keyword: str) -> List[DatasetEntry]:
        """
        Search datasets by keyword in name or notes.
        
        Args:
            keyword: Search keyword (case-insensitive)
            
        Returns:
            List of matching datasets
        """
        if not self.catalog:
            return []
        
        keyword_lower = keyword.lower()
        results = []
        
        for dataset in self.catalog.datasets:
            # Search in dataset name
            if keyword_lower in dataset.dataset.lower():
                results.append(dataset)
                continue
            
            # Search in notes if available
            if dataset.notes and keyword_lower in dataset.notes.lower():
                results.append(dataset)
        
        return results
    
    def validate_catalog_integrity(self) -> Dict[str, Any]:
        """
        Validate catalog integrity and return report.
        
        Returns:
            Dictionary with validation results
        """
        if not self.catalog:
            return {"error": "Catalog not loaded"}
        
        report = {
            "valid": True,
            "total_datasets": len(self.catalog.datasets),
            "classes": self.catalog.get_dataset_count(),
            "discoverable_count": len(self.filter_discoverable(True)),
            "non_discoverable_count": len(self.filter_discoverable(False)),
            "issues": []
        }
        
        # Check for missing placeholders in URLs
        for dataset in self.catalog.datasets:
            if '{symbol}' not in dataset.url and dataset.class_ in [DatasetClass.MARKET, DatasetClass.MARKET_DATA]:
                if 'symbol' not in dataset.params_schema:
                    report["issues"].append(f"{dataset.dataset}: Missing symbol placeholder or param")
        
        # Check for reasonable cache TTLs
        for dataset in self.catalog.datasets:
            if dataset.cache_ttl == 0:
                report["issues"].append(f"{dataset.dataset}: Cache TTL is 0 (no caching)")
            elif dataset.cache_ttl > 86400:  # More than 24 hours
                report["issues"].append(f"{dataset.dataset}: Very long cache TTL ({dataset.cache_ttl}s)")
        
        if report["issues"]:
            report["valid"] = False
        
        return report
    
    def get_catalog_summary(self) -> str:
        """
        Get a human-readable summary of the catalog.
        
        Returns:
            Summary string
        """
        if not self.catalog:
            return "Catalog not loaded"
        
        lines = [
            f"FMP Dataset Catalog v{self.catalog.version}",
            f"Last Updated: {self.catalog.last_updated}",
            f"Source: {self.catalog.source}",
            f"Total Datasets: {len(self.catalog.datasets)}",
            "",
            "Breakdown by Class:"
        ]
        
        for class_name, count in self.catalog.get_dataset_count().items():
            lines.append(f"  - {class_name}: {count}")
        
        discoverable = len(self.filter_discoverable(True))
        lines.append(f"\nDiscoverable: {discoverable}")
        lines.append(f"Non-discoverable: {len(self.catalog.datasets) - discoverable}")
        
        return "\n".join(lines)


# Module-level convenience functions
_default_loader: Optional[DDCLoader] = None


def get_default_loader() -> DDCLoader:
    """
    Get or create the default DDC loader instance.
    
    Returns:
        Default DDCLoader instance
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = DDCLoader()
    return _default_loader


def load_catalog(catalog_path: Optional[Union[str, Path]] = None) -> DDCCatalog:
    """
    Load catalog from specified path or default location.
    
    Args:
        catalog_path: Optional path to catalog file
        
    Returns:
        Loaded catalog
    """
    if catalog_path:
        loader = DDCLoader(catalog_path)
    else:
        loader = get_default_loader()
    return loader.catalog


def get_discoverable_datasets() -> List[DatasetEntry]:
    """
    Get all discoverable datasets from default catalog.
    
    Returns:
        List of discoverable datasets
    """
    loader = get_default_loader()
    return loader.filter_discoverable(True)
