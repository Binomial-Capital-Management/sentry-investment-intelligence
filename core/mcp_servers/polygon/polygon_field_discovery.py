"""
Field discovery orchestration for Polygon datasets.

This module coordinates ticker validation, dataset selection, HTTP probing, and
field caching so that downstream agents can understand the shape of Polygon
responses without hardcoding schemas.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Union

from .polygon_data_fetcher import PolygonAPIError, PolygonDataFetcher
from .polygon_ddc_loader import (
    PolygonAssetClass,
    PolygonAssetGroup,
    PolygonDDCLoader,
    PolygonDatasetClass,
    PolygonDatasetEntry,
    PolygonPlaceholderConfig,
)
from .polygon_field_map_manager import PolygonFieldMapManager
from .ticker_validator import TickerValidationResult, TickerValidator


class PolygonFieldDiscovery:
    """Drive field discovery requests while respecting rate limits."""

    def __init__(
        self,
        loader: PolygonDDCLoader,
        fetcher: PolygonDataFetcher,
        field_map: PolygonFieldMapManager,
        validator: Optional[TickerValidator] = None,
        placeholder_rules: Optional[Union[PolygonPlaceholderConfig, Dict[str, Any]]] = None,
    ) -> None:
        self._loader = loader
        self._fetcher = fetcher
        self._field_map = field_map
        self._validator = validator or TickerValidator()

        if placeholder_rules is None and hasattr(loader, "placeholder_rules"):
            placeholder_rules = loader.placeholder_rules

        if isinstance(placeholder_rules, PolygonPlaceholderConfig):
            rules_payload = placeholder_rules.model_dump()
        else:
            rules_payload = placeholder_rules or {}

        placeholders = rules_payload.get("placeholders", {})
        dataset_overrides = rules_payload.get("dataset_overrides", {})

        self._global_placeholder_rules: Dict[str, Dict[str, Any]] = {
            key.lower(): value for key, value in placeholders.items()
        }
        self._dataset_placeholder_rules: Dict[str, Dict[str, Dict[str, Any]]] = {
            dataset_name: {key.lower(): value for key, value in mapping.items()}
            for dataset_name, mapping in dataset_overrides.items()
        }

    async def discover_fields(
        self,
        ticker: str,
        dataset_names: Optional[Iterable[str]] = None,
        max_datasets: int = 6,
    ) -> Dict[str, List[str]]:
        """
        Discover fields for datasets relevant to the provided ticker.

        Returns a mapping of dataset name to discovered field paths.
        """

        validation = self._validator.normalize(ticker)
        asset_group = validation.asset_group
        asset_class = validation.asset_class

        candidates = self._loader.list_datasets(asset_group=asset_group)
        selected = self._select_datasets(candidates, dataset_names, max_datasets, asset_class)

        results: Dict[str, List[str]] = {}
        for dataset in selected:
            paths = await self._probe_dataset(dataset, validation)
            if paths:
                results[dataset.dataset] = paths

        return results

    def build_path_params_for(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
    ) -> Optional[Dict[str, Any]]:
        """Expose path-parameter builder externally."""

        return self._build_path_params(dataset, validation)

    def build_query_params_for(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
    ) -> Dict[str, Any]:
        """Expose query-parameter builder externally."""

        return self._build_query_params(dataset, validation)

    def _select_datasets(
        self,
        candidates: List[PolygonDatasetEntry],
        dataset_filter: Optional[Iterable[str]],
        max_datasets: int,
        asset_class: PolygonAssetClass,
    ) -> List[PolygonDatasetEntry]:
        """Prioritise datasets for discovery."""

        dataset_names = set(dataset_filter) if dataset_filter else None
        filtered: List[PolygonDatasetEntry] = []

        for dataset in candidates:
            if dataset_names and dataset.dataset not in dataset_names:
                continue
            if asset_class not in dataset.asset_classes:
                continue
            filtered.append(dataset)

        filtered.sort(key=lambda entry: entry.class_.value)
        return filtered[:max_datasets]

    async def _probe_dataset(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
    ) -> List[str]:
        """Fetch dataset sample and record discovered fields."""

        try:
            path_params = self.build_path_params_for(dataset, validation)
            if path_params is None:
                return []

            query_params = self.build_query_params_for(dataset, validation)

            payload = await self._fetcher.fetch(dataset, path_params=path_params, query_params=query_params)
        except (ValueError, PolygonAPIError):
            return []

        field_map = self._flatten_payload(payload)
        if not field_map:
            return []

        required_params = [
            name
            for name, descriptor in dataset.params_schema.items()
            if not descriptor.endswith("?")
        ]
        notes = dataset.notes
        for info in field_map.values():
            info.setdefault("required_params", list(required_params) if required_params else [])
            if notes:
                info.setdefault("notes", notes)

        self._field_map.save_discovered_fields(dataset, field_map)
        return list(field_map.keys())

    def _build_path_params(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
    ) -> Optional[Dict[str, Any]]:
        """Build path parameters using catalog-driven placeholder rules."""

        placeholders = self._extract_placeholders(dataset.url)
        if not placeholders:
            return {}

        params: Dict[str, Any] = {}
        for placeholder in placeholders:
            rule = self._get_placeholder_rule(dataset.dataset, placeholder)
            if rule is None:
                return None

            try:
                value = self._resolve_placeholder_rule(rule, validation)
            except ValueError:
                return None

            if value is None:
                return None

            params[placeholder] = value

        return params

    def _build_query_params(
        self,
        dataset: PolygonDatasetEntry,
        validation: TickerValidationResult,
    ) -> Dict[str, Any]:
        """Provide defaults for required query parameters."""

        params: Dict[str, Any] = {}

        for name, descriptor in dataset.params_schema.items():
            required = not descriptor.endswith("?")
            base_descriptor = descriptor.rstrip("?")

            if not required:
                continue

            value = self._default_query_value(name, base_descriptor, validation)
            if value is not None:
                params[name] = value

        return params

    def _default_query_value(
        self,
        name: str,
        descriptor: str,
        validation: TickerValidationResult,
    ) -> Optional[Any]:
        """Return a heuristic default for a required query parameter."""

        if descriptor.startswith("enum["):
            values = descriptor[5:-1].split(",")
            values = [v.strip() for v in values if v.strip()]
            if not values:
                return None
            if name == "market":
                if validation.asset_class is PolygonAssetClass.FOREX:
                    return "fx"
                if validation.asset_class is PolygonAssetClass.CRYPTO:
                    return "crypto"
            return values[0]

        if descriptor.startswith("integer"):
            return 50

        if descriptor.startswith("boolean"):
            return False

        if name == "ticker":
            return validation.normalized

        if name == "direction":
            return "gainers"

        return None

    def _flatten_payload(self, payload: Any, prefix: str = "") -> Dict[str, Dict[str, Optional[str]]]:
        """Recursively extract field paths from an API response."""

        fields: Dict[str, Dict[str, Optional[str]]] = {}

        if isinstance(payload, dict):
            for key, value in payload.items():
                child_prefix = f"{prefix}.{key}" if prefix else key
                fields.update(self._flatten_payload(value, child_prefix))
        elif isinstance(payload, list):
            if not payload:
                fields[prefix or "[]"] = {"type": "list", "value": "[]"}
            else:
                first = payload[0]
                list_prefix = f"{prefix}[]" if prefix else "[]"
                fields.update(self._flatten_payload(first, list_prefix))
        else:
            fields[prefix] = {
                "type": type(payload).__name__,
                "value": self._stringify_value(payload),
            }

        return fields

    @staticmethod
    def _stringify_value(value: Any) -> Optional[str]:
        """Convert primitive values to short strings for storage."""

        if value is None:
            return None
        text = str(value)
        return text[:120]

    @staticmethod
    def _extract_placeholders(url_template: str) -> List[str]:
        """Extract placeholder names from a URL template."""

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

    def _get_placeholder_rule(self, dataset_name: str, placeholder: str) -> Optional[Dict[str, Any]]:
        """Retrieve placeholder rule with dataset overrides taking precedence."""

        data_rules = self._dataset_placeholder_rules.get(dataset_name, {})
        key = placeholder
        key_lower = placeholder.lower()
        return (
            data_rules.get(key_lower)
            or data_rules.get(key)
            or self._global_placeholder_rules.get(key_lower)
            or self._global_placeholder_rules.get(key)
        )

    def _resolve_placeholder_rule(
        self,
        rule: Dict[str, Any],
        validation: TickerValidationResult,
    ) -> Optional[Any]:
        """Resolve a placeholder rule to a concrete value."""

        if rule.get("type") == "unsupported":
            raise ValueError("Placeholder marked unsupported")

        if "value" in rule:
            return rule["value"]

        source = rule.get("source")
        if source == "normalized":
            return validation.normalized

        if source == "component":
            component = rule.get("name")
            if not component:
                raise ValueError("Component name required for placeholder rule")
            value = validation.components.get(component)
            if value is None:
                raise ValueError(f"Missing component '{component}'")
            return value

        rule_type = rule.get("type")
        if rule_type == "today":
            return datetime.utcnow().date().isoformat()
        if rule_type == "date_offset":
            days = int(rule.get("days", 0))
            date_value = datetime.utcnow().date() + timedelta(days=days)
            return date_value.isoformat()

        raise ValueError("Unsupported placeholder rule configuration")

__all__ = ["PolygonFieldDiscovery"]
