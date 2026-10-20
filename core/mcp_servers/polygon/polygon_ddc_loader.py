"""
Dynamic Dataset Catalog loader for Polygon MCP servers.

The loader mirrors the pattern established in the FMP integration but adds
Polygon-specific metadata such as `asset_group` (options vs crypto/FX)
and `asset_classes` to allow each server to present only applicable datasets.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger(__name__)


class PolygonAssetGroup(str, Enum):
    """Logical grouping of Polygon datasets used to split MCP servers."""

    OPTIONS = "options"
    CRYPTO_FX = "crypto_fx"


class PolygonAssetClass(str, Enum):
    """Supported asset classes exposed in the catalog."""

    OPTIONS = "options"
    FOREX = "forex"
    CRYPTO = "crypto"


class PolygonDatasetClass(str, Enum):
    """High-level dataset categories."""

    REFERENCE = "reference"
    TIMESERIES = "timeseries"
    MARKET = "market"
    SNAPSHOT = "snapshot"
    TRADES = "trades"
    QUOTES = "quotes"
    TECHNICAL = "technical"
    OPERATIONS = "operations"


class PolygonRateLimit(BaseModel):
    """Rate limit configuration for a dataset entry."""

    per_minute: int = Field(..., ge=1, description="Allowed calls per minute")
    burst: int = Field(..., ge=1, description="Burst capacity before throttling")


class PolygonDatasetEntry(BaseModel):
    """Schema for a single dataset record."""

    dataset: str = Field(..., min_length=1)
    asset_group: List[PolygonAssetGroup] = Field(..., min_items=1)
    asset_classes: List[PolygonAssetClass] = Field(..., min_items=1)
    class_: PolygonDatasetClass = Field(..., alias="class")
    discoverable: bool = Field(default=True)
    url: str = Field(..., pattern=r"^/.*")
    method: str = Field(default="GET")
    identifier_param: Optional[str] = Field(default=None)
    params_schema: Dict[str, str] = Field(default_factory=dict)
    rate_limit: PolygonRateLimit
    cache_ttl: int = Field(default=300, ge=0)
    notes: Optional[str] = Field(default=None)

    class Config:
        populate_by_name = True

    @validator("method")
    def _validate_method(cls, value: str) -> str:  # noqa: D401
        """Ensure the HTTP method is uppercase and supported."""

        method = value.upper()
        if method not in {"GET", "POST"}:
            raise ValueError(f"Unsupported HTTP method '{value}'")
        return method

    def applies_to_asset_group(self, group: PolygonAssetGroup) -> bool:
        """Return True if the dataset should be used by the requested group."""

        return group in self.asset_group

    def applies_to_asset_class(self, asset_class: PolygonAssetClass) -> bool:
        """Return True if dataset supports the provided asset class."""

        return asset_class in self.asset_classes

    def to_dict(self) -> Dict[str, object]:
        """Helper for serialising entries with the original field names."""

        return self.dict(by_alias=True)


class PolygonDetectionRule(BaseModel):
    """Detection hints for inferring asset classes from raw tickers."""

    prefixes: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)


class PolygonTransformRule(BaseModel):
    """Optional transforms applied to extracted components."""

    map: Dict[str, str] = Field(default_factory=dict)
    divide_by: Optional[float] = None
    format: Optional[str] = None


class PolygonNormalizationRule(BaseModel):
    """Ticker normalisation metadata per asset class."""

    type: str
    prefix: Optional[str] = None
    separator: Optional[str] = None
    detection: PolygonDetectionRule = Field(default_factory=PolygonDetectionRule)
    pattern: Optional[str] = None
    transforms: Dict[str, PolygonTransformRule] = Field(default_factory=dict)


class PolygonPlaceholderConfig(BaseModel):
    """Placeholder resolution configuration sourced from the catalog."""

    placeholders: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    dataset_overrides: Dict[str, Dict[str, Dict[str, Any]]] = Field(default_factory=dict)


class PolygonDDCCatalog(BaseModel):
    """Top-level catalog metadata."""

    version: str
    last_updated: str
    source: str
    normalization: Dict[str, PolygonNormalizationRule] = Field(default_factory=dict)
    placeholder_rules: PolygonPlaceholderConfig = Field(default_factory=PolygonPlaceholderConfig)
    datasets: List[PolygonDatasetEntry]

    @validator("datasets")
    def _ensure_unique_names(
        cls, entries: Sequence[PolygonDatasetEntry]
    ) -> Sequence[PolygonDatasetEntry]:
        """Ensure dataset identifiers are unique to avoid routing ambiguity."""

        seen = set()
        for entry in entries:
            if entry.dataset in seen:
                raise ValueError(f"Duplicate dataset identifier '{entry.dataset}' detected")
            seen.add(entry.dataset)
        return entries


class PolygonDDCLoader:
    """
    Loader exposing ergonomic access to the Polygon catalog.

    Usage:
        loader = PolygonDDCLoader()
        datasets = loader.list_datasets(asset_group=PolygonAssetGroup.OPTIONS)
    """

    def __init__(
        self,
        catalog_path: Optional[Path] = None,
        catalog_data: Optional[dict] = None,
    ) -> None:
        """
        Initialize the loader either from disk or an in-memory dictionary.

        Args:
            catalog_path: Optional path to the JSON catalog.
            catalog_data: Optional pre-loaded JSON payload (useful for tests).
        """

        if catalog_data and catalog_path:
            raise ValueError("Provide either 'catalog_path' or 'catalog_data', not both.")

        if catalog_data is not None:
            self._catalog = self._parse_catalog(catalog_data)
        else:
            path = catalog_path or Path(__file__).with_name("polygon_ddc_catalog.json")
            self._catalog = self._load_from_file(path)

        self._index: Dict[str, PolygonDatasetEntry] = {
            dataset.dataset: dataset for dataset in self._catalog.datasets
        }
        self.normalization_rules: Dict[str, PolygonNormalizationRule] = self._catalog.normalization
        self.placeholder_rules: PolygonPlaceholderConfig = self._catalog.placeholder_rules

    @property
    def catalog(self) -> PolygonDDCCatalog:
        """Expose the parsed catalog."""

        return self._catalog

    def list_datasets(
        self,
        asset_group: Optional[PolygonAssetGroup] = None,
        dataset_class: Optional[PolygonDatasetClass] = None,
        discoverable_only: bool = False,
    ) -> List[PolygonDatasetEntry]:
        """
        Return dataset entries filtered by the provided criteria.
        """

        datasets: Iterable[PolygonDatasetEntry] = self._catalog.datasets

        if asset_group is not None:
            datasets = filter(lambda d: d.applies_to_asset_group(asset_group), datasets)

        if dataset_class is not None:
            datasets = filter(lambda d: d.class_ == dataset_class, datasets)

        if discoverable_only:
            datasets = filter(lambda d: d.discoverable, datasets)

        return list(datasets)

    def get_dataset(self, dataset_name: str) -> PolygonDatasetEntry:
        """
        Retrieve a dataset entry by identifier.

        Raises:
            KeyError: if the dataset does not exist.
        """

        try:
            return self._index[dataset_name]
        except KeyError as exc:
            raise KeyError(f"Dataset '{dataset_name}' not found in Polygon catalog") from exc

    def filter_by_asset_class(
        self,
        asset_group: PolygonAssetGroup,
        asset_class: PolygonAssetClass,
    ) -> List[PolygonDatasetEntry]:
        """
        Convenience helper returning datasets limited to a single asset class.
        """

        return [
            entry
            for entry in self.list_datasets(asset_group=asset_group)
            if entry.applies_to_asset_class(asset_class)
        ]

    def _load_from_file(self, path: Path) -> PolygonDDCCatalog:
        """Load catalog JSON from disk with validation."""

        if not path.exists():
            raise FileNotFoundError(f"Polygon catalog not found at {path}")

        logger.debug("Loading Polygon catalog from %s", path)
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        return self._parse_catalog(raw)

    def _parse_catalog(self, payload: dict) -> PolygonDDCCatalog:
        """Parse and validate raw catalog payload."""

        try:
            catalog = PolygonDDCCatalog.parse_obj(payload)
        except ValidationError as exc:
            logger.error("Polygon catalog validation failed: %s", exc)
            raise
        return catalog


__all__ = [
    "PolygonDDCLoader",
    "PolygonDDCCatalog",
    "PolygonDatasetEntry",
    "PolygonDatasetClass",
    "PolygonAssetClass",
    "PolygonAssetGroup",
    "PolygonRateLimit",
    "PolygonNormalizationRule",
    "PolygonTransformRule",
    "PolygonPlaceholderConfig",
]
