"""
Historical data utilities for Polygon MCP servers.

Provides aggregate time-series retrieval with sensible defaults while honouring
catalog-driven placeholder rules and parameter schemas.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .polygon_data_fetcher import PolygonDataFetcher

logger = logging.getLogger(__name__)
from .polygon_ddc_loader import (
    PolygonAssetClass,
    PolygonAssetGroup,
    PolygonDDCLoader,
    PolygonDatasetEntry,
)
from .polygon_field_discovery import PolygonFieldDiscovery
from .ticker_validator import TickerValidator

_TIMESPAN_VALUES = {"minute", "hour", "day", "week", "month", "quarter", "year"}


class PolygonHistoricalData:
    """Fetch aggregated OHLC data across Polygon asset classes."""

    def __init__(
        self,
        loader: PolygonDDCLoader,
        fetcher: PolygonDataFetcher,
        discovery: PolygonFieldDiscovery,
        validator: TickerValidator,
        asset_group: PolygonAssetGroup,
    ) -> None:
        self._loader = loader
        self._fetcher = fetcher
        self._discovery = discovery
        self._validator = validator
        self._asset_group = asset_group

    async def get_aggregates(
        self,
        ticker: str,
        multiplier: int = 1,
        timespan: str = "day",
        start: Optional[str] = None,
        end: Optional[str] = None,
        adjusted: Optional[bool] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve aggregated OHLC data for the given ticker.
        """

        if multiplier <= 0:
            raise ValueError("multiplier must be positive")

        timespan_normalized = timespan.lower()
        if timespan_normalized not in _TIMESPAN_VALUES:
            raise ValueError(f"timespan must be one of {sorted(_TIMESPAN_VALUES)}")

        validation = self._validator.normalize(ticker)
        dataset = self._select_dataset(validation.asset_class)

        path_params = self._discovery.build_path_params_for(dataset, validation)
        if path_params is None:
            raise ValueError("Unable to resolve path parameters for aggregates request")

        query_params = self._discovery.build_query_params_for(dataset, validation) or {}

        overrides = self._build_overrides(
            dataset,
            multiplier,
            timespan_normalized,
            start,
            end,
            adjusted,
            limit,
            sort,
        )

        for key, value in overrides["path"].items():
            self._apply_case_insensitive(path_params, key, value)

        for key, value in overrides["query"].items():
            if value is not None:
                query_params[key] = value

        placeholder_keys = {key.lower() for key in self._extract_placeholders(dataset.url)}
        query_params = {
            key: value
            for key, value in query_params.items()
            if key.lower() not in placeholder_keys
        }

        payload = await self._fetcher.fetch(dataset, path_params=path_params, query_params=query_params)

        # Normalize Polygon response - extract actual data from envelope
        actual_data = payload
        if isinstance(payload, dict):
            logger.info(f"[POLYGON DEBUG] Historical Dataset={dataset.dataset}")
            logger.info(f"[POLYGON DEBUG] Response keys: {list(payload.keys())}")
            
            if "results" in payload:
                actual_data = payload["results"]
                logger.info(f"[POLYGON DEBUG] Extracted 'results': {len(actual_data) if isinstance(actual_data, list) else 'not a list'}")
            elif "values" in payload:
                actual_data = payload["values"]
                logger.info(f"[POLYGON DEBUG] Extracted 'values': {len(actual_data) if isinstance(actual_data, list) else 'not a list'}")
            else:
                logger.info(f"[POLYGON DEBUG] No standard wrapper keys found - using raw response")
            
            if "status" in payload:
                logger.info(f"[POLYGON DEBUG] status: {payload.get('status')}")

        return {
            "dataset": dataset.dataset,
            "ticker": validation.normalized,
            "path_params": path_params,
            "query_params": query_params,
            "data": actual_data,
            "raw_response": payload,  # Keep original for debugging
        }

    def _select_dataset(self, asset_class: PolygonAssetClass) -> PolygonDatasetEntry:
        """Select the appropriate dataset for aggregates."""

        if self._asset_group is PolygonAssetGroup.OPTIONS:
            if asset_class is PolygonAssetClass.OPTIONS:
                return self._loader.get_dataset("options-aggregates-range")
        elif self._asset_group is PolygonAssetGroup.CRYPTO_FX:
            if asset_class is PolygonAssetClass.FOREX:
                return self._loader.get_dataset("forex-aggregates-range")
            if asset_class is PolygonAssetClass.CRYPTO:
                return self._loader.get_dataset("crypto-aggregates-range")

        raise ValueError(f"Aggregates not supported for asset class '{asset_class.value}' on this server")

    def _build_overrides(
        self,
        dataset: PolygonDatasetEntry,
        multiplier: int,
        timespan: str,
        start: Optional[str],
        end: Optional[str],
        adjusted: Optional[bool],
        limit: Optional[int],
        sort: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Prepare path and query overrides respecting dataset capabilities."""

        end_date = self._ensure_iso_date(end) or datetime.utcnow().date()
        start_date = self._ensure_iso_date(start) or (end_date - timedelta(days=30))

        overrides = {"path": {}, "query": {}}

        if self._has_placeholder(dataset, "multiplier"):
            overrides["path"]["multiplier"] = multiplier
        else:
            overrides["query"]["multiplier"] = multiplier

        if self._has_placeholder(dataset, "timespan"):
            overrides["path"]["timespan"] = timespan
        else:
            overrides["query"]["timespan"] = timespan

        if self._has_placeholder(dataset, "from"):
            overrides["path"]["from"] = start_date.isoformat()
        else:
            overrides["query"]["from"] = start_date.isoformat()

        if self._has_placeholder(dataset, "to"):
            overrides["path"]["to"] = end_date.isoformat()
        else:
            overrides["query"]["to"] = end_date.isoformat()

        if adjusted is not None:
            overrides["query"]["adjusted"] = adjusted
        if limit is not None:
            overrides["query"]["limit"] = limit
        if sort is not None:
            overrides["query"]["sort"] = sort

        return overrides

    @staticmethod
    def _apply_case_insensitive(target: Dict[str, Any], key: str, value: Any) -> None:
        """Update a dict key without altering original placeholder casing."""

        for existing in list(target.keys()):
            if existing.lower() == key.lower():
                target[existing] = value
                return
        target[key] = value

    @staticmethod
    def _ensure_iso_date(value: Optional[str]) -> Optional[date]:
        """Convert incoming date to ISO date object."""

        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:
            raise ValueError(f"Invalid date format '{value}'. Expected YYYY-MM-DD") from exc

    @staticmethod
    def _has_placeholder(dataset: PolygonDatasetEntry, placeholder: str) -> bool:
        """Determine if dataset URL contains the placeholder."""

        fragment = f"{{{placeholder}}}"
        return fragment in dataset.url or fragment in dataset.url.lower()

    @staticmethod
    def _extract_placeholders(url_template: str) -> List[str]:
        placeholders: List[str] = []
        start = 0
        while True:
            start = url_template.find("{", start)
            if start == -1:
                break
            end = url_template.find("}", start)
            if end == -1:
                break
            placeholders.append(url_template[start + 1 : end])
            start = end + 1
        return placeholders
