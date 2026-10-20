"""
Shared Polygon MCP server scaffolding.

Provides common wiring for dataset loading, validation, discovery, fetching,
and JSON response formatting so concrete servers can focus on tool semantics.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional

from agents.mcp import MCPServer
from agents.mcp.server import CallToolResult, MCPTool

from .polygon_data_fetcher import PolygonDataFetcher
from .polygon_ddc_loader import (
    PolygonAssetClass,
    PolygonAssetGroup,
    PolygonDDCLoader,
    PolygonDatasetClass,
    PolygonDatasetEntry,
)
from .polygon_field_discovery import PolygonFieldDiscovery
from .polygon_field_map_manager import PolygonFieldMapManager
from .polygon_historical_data import PolygonHistoricalData
from .polygon_rate_limiter import PolygonRateLimiter
from .ticker_validator import TickerValidationResult, TickerValidator

logger = logging.getLogger(__name__)


class PolygonBaseServer(MCPServer):
    """Base server providing helper utilities for Polygon integrations."""

    def __init__(
        self,
        name: str,
        asset_group: PolygonAssetGroup,
        api_key: Optional[str] = None,
        placeholder_rules: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self._name = name
        self.use_structured_content = False
        self._asset_group = asset_group
        self._api_key = api_key or os.getenv("POLYGON_API_KEY")

        if not self._api_key:
            raise ValueError("POLYGON_API_KEY not provided")

        self.loader = PolygonDDCLoader()
        self.rate_limiter = PolygonRateLimiter()
        self.fetcher = PolygonDataFetcher(self._api_key, self.rate_limiter)
        self.field_manager = PolygonFieldMapManager()
        self.validator = TickerValidator(self.loader.normalization_rules)
        self.field_discovery = PolygonFieldDiscovery(
            self.loader,
            self.fetcher,
            self.field_manager,
            self.validator,
            placeholder_rules=placeholder_rules or self.loader.placeholder_rules,
        )
        self.historical_data = PolygonHistoricalData(
            self.loader,
            self.fetcher,
            self.field_discovery,
            self.validator,
            self._asset_group,
        )

    @property
    def name(self) -> str:
        return self._name

    async def list_tools(self, run_context, agent) -> List[MCPTool]:
        return self.get_available_tools()

    async def list_prompts(self, run_context, agent) -> List[str]:
        return []

    async def get_prompt(self, name: str, arguments: Dict[str, Any], run_context, agent) -> str:
        raise NotImplementedError(f"No prompts available for {self._name}")

    async def connect(self) -> None:
        await self.fetcher.connect()

    async def cleanup(self) -> None:
        await self.fetcher.cleanup()
        self.field_manager.close()

    def get_available_tools(self) -> List[MCPTool]:  # pragma: no cover - defined in subclass
        raise NotImplementedError

    def _success(self, payload: Any, label: str = "polygon", raw: bool = False) -> CallToolResult:
        from core.agents.binomial_hash import bh_ingest
        raw_text = json.dumps(payload, default=str)
        text = raw_text if raw else bh_ingest(raw_text, label)
        return CallToolResult(
            content=[{"type": "text", "text": text}],
            isError=False,
        )

    def _error(self, message: str) -> CallToolResult:
        return CallToolResult(content=[{"type": "text", "text": message}], isError=True)

    def _ensure_dataset(self, dataset_name: str) -> PolygonDatasetEntry:
        dataset = self.loader.get_dataset(dataset_name)
        if self._asset_group not in dataset.asset_group:
            raise ValueError(f"Dataset '{dataset_name}' is not available for {self._asset_group.value}")
        return dataset

    def _list_datasets(
        self,
        dataset_class: Optional[str],
        discoverable_only: bool,
    ) -> List[PolygonDatasetEntry]:
        if dataset_class:
            dataset_enum = PolygonDatasetClass(dataset_class)
        else:
            dataset_enum = None
        return self.loader.list_datasets(
            asset_group=self._asset_group,
            dataset_class=dataset_enum,
            discoverable_only=discoverable_only,
        )

    def _validation_for_dataset(
        self,
        dataset: PolygonDatasetEntry,
        ticker: str,
    ) -> TickerValidationResult:
        validation = self.validator.normalize(ticker)
        if validation.asset_class in dataset.asset_classes:
            return validation

        for asset_class in dataset.asset_classes:
            try:
                forced = self.validator.normalize(ticker, asset_class=asset_class)
            except ValueError:
                continue
            if forced.asset_class == asset_class:
                return forced

        raise ValueError(
            f"Ticker '{ticker}' ({validation.asset_class.value}) not supported by dataset '{dataset.dataset}'"
        )

    async def _fetch_dataset(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
        path_overrides: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path_params = self.field_discovery.build_path_params_for(dataset, validation)
        if path_params is None:
            raise ValueError(f"Unable to resolve path parameters for dataset '{dataset.dataset}'")

        base_query = self.field_discovery.build_query_params_for(dataset, validation) or {}
        merged_query = dict(base_query)

        if path_overrides:
            for key, value in path_overrides.items():
                if not self._update_case_insensitive(path_params, key, value):
                    merged_query[key] = value

        if query_params:
            for key, value in query_params.items():
                if value is not None:
                    merged_query[key] = value

        # Ensure query parameters that mirror path placeholders stay in sync with the final URL.
        if path_params:
            placeholder_lookup = {placeholder.lower(): value for placeholder, value in path_params.items()}
            for key in list(merged_query.keys()):
                lookup_key = key.lower()
                if lookup_key in placeholder_lookup:
                    merged_query[key] = placeholder_lookup[lookup_key]

        filtered_query = self._filter_query_params(dataset, merged_query)

        payload = await self.fetcher.fetch(dataset, path_params=path_params, query_params=filtered_query)

        # Normalize Polygon response - extract actual data from envelope
        # Polygon wraps data in various keys: results, tickers, ticker, values
        actual_data = payload
        if isinstance(payload, dict):
            # DEBUG: Log response structure
            logger.info(f"[POLYGON DEBUG] Dataset={dataset.dataset}")
            logger.info(f"[POLYGON DEBUG] Response keys: {list(payload.keys())}")
            
            # Extract data from Polygon's response envelope
            if "results" in payload:
                actual_data = payload["results"]
                logger.info(f"[POLYGON DEBUG] Extracted 'results': {len(actual_data) if isinstance(actual_data, list) else 'not a list'}")
            elif "tickers" in payload:
                actual_data = payload["tickers"]
                logger.info(f"[POLYGON DEBUG] Extracted 'tickers': {len(actual_data) if isinstance(actual_data, list) else 'not a list'}")
            elif "ticker" in payload:
                actual_data = payload["ticker"]
                logger.info(f"[POLYGON DEBUG] Extracted 'ticker' (single ticker response)")
            elif "values" in payload:
                actual_data = payload["values"]
                logger.info(f"[POLYGON DEBUG] Extracted 'values': {len(actual_data) if isinstance(actual_data, list) else 'not a list'}")
            else:
                logger.info(f"[POLYGON DEBUG] No standard wrapper keys found - using raw response")
            
            if "status" in payload:
                logger.info(f"[POLYGON DEBUG] status: {payload.get('status')}")

        return {
            "dataset": dataset.dataset,
            "path_params": path_params,
            "query_params": filtered_query,
            "data": actual_data,
            "raw_response": payload,  # Keep original for debugging
        }

    def _filter_query_params(
        self,
        dataset: PolygonDatasetEntry,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not dataset.params_schema:
            return params
        allowed = set(dataset.params_schema.keys())
        return {k: v for k, v in params.items() if k in allowed}

    @staticmethod
    def _update_case_insensitive(target: Dict[str, Any], key: str, value: Any) -> bool:
        for existing in list(target.keys()):
            if existing.lower() == key.lower():
                target[existing] = value
                return True
        return False

    def _list_cached_fields(
        self,
        asset_class: Optional[PolygonAssetClass] = None,
    ) -> List[Dict[str, Any]]:
        if asset_class:
            return self.field_manager.list_fields_for_asset_class(self._asset_group, asset_class)
        datasets = self.loader.list_datasets(asset_group=self._asset_group)
        collected: List[Dict[str, Any]] = []
        for dataset in datasets:
            collected.extend(self.field_manager.list_fields_for_dataset(dataset.dataset, self._asset_group))
        return collected

    def _default_validation(self) -> TickerValidationResult:  # pragma: no cover - override in subclass
        raise NotImplementedError

    def _fallback_validation(self, ticker: str) -> TickerValidationResult:  # pragma: no cover - override
        raise ValueError(f"Unable to normalize ticker '{ticker}' for asset group {self._asset_group.value}")

    def _resolve_validation(self, ticker: Optional[str]) -> TickerValidationResult:
        if ticker:
            try:
                return self.validator.normalize(ticker)
            except ValueError:
                return self._fallback_validation(ticker)
        return self._default_validation()

    @staticmethod
    def _json_array(values: Iterable[str]) -> str:
        return ",".join(values)

    @staticmethod
    def _build_manual_validation(underlying: str) -> TickerValidationResult:
        normalized = underlying.strip().upper()
        return TickerValidationResult(
            normalized=normalized,
            asset_class=PolygonAssetClass.OPTIONS,
            asset_group=PolygonAssetGroup.OPTIONS,
            components={"underlying": normalized, "base": normalized},
        )

    def _dataset_supports_asset_class(
        self,
        dataset: PolygonDatasetEntry,
        asset_class: PolygonAssetClass,
    ) -> bool:
        return asset_class in dataset.asset_classes
