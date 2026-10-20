"""
Dynamic Dataset Catalog (DDC) Loader for Unusual Whales Integration.

Loads, validates, and provides access to UW dataset catalogs.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from .uw_models import UWDatasetEntry, UWCatalog

logger = logging.getLogger(__name__)


class UWDDCLoader:
    """
    Dynamic Dataset Catalog loader for Unusual Whales.
    
    Loads and merges multiple catalog files, providing:
    - Schema validation via Pydantic
    - Filtering by class and discoverable status
    - Fast dataset lookup via index
    """
    
    def __init__(self, catalog_paths: Optional[Union[str, Path, List[Union[str, Path]]]] = None):
        """
        Initialize the UW DDC loader.

        Args:
            catalog_paths: Path(s) to catalog JSON file(s). 
                None = load all catalogs from same directory
        """
        catalog_dir = Path(__file__).parent

        if catalog_paths is None:
            self.catalog_paths = [
                catalog_dir / "uw_options_catalog.json",
                catalog_dir / "uw_institutional_catalog.json",
                catalog_dir / "uw_market_catalog.json",
            ]
        elif isinstance(catalog_paths, (list, tuple)):
            self.catalog_paths = [Path(p) for p in catalog_paths]
        else:
            self.catalog_paths = [Path(catalog_paths)]

        self.catalog: Optional[UWCatalog] = None
        self._dataset_index: Dict[str, UWDatasetEntry] = {}
        self._enums: Dict[str, List[str]] = {}
        self.base_url = "https://api.unusualwhales.com"

        self.load_catalogs()

    def load_catalogs(self, force_reload: bool = False) -> UWCatalog:
        """Load and merge multiple catalog files."""
        if self.catalog is not None and not force_reload:
            return self.catalog

        all_datasets = []
        dataset_names_seen = set()
        merged_enums: Dict[str, List[str]] = {}
        merged_last_updated = None

        for catalog_path in self.catalog_paths:
            if not catalog_path.exists():
                logger.warning(f"UW Catalog not found, skipping: {catalog_path}")
                continue

            try:
                with open(catalog_path, 'r') as f:
                    data = json.load(f)

                catalog = UWCatalog(**data)

                # Merge enums
                if catalog.enums:
                    for enum_name, values in catalog.enums.items():
                        if enum_name not in merged_enums:
                            merged_enums[enum_name] = values
                        else:
                            existing = set(merged_enums[enum_name])
                            merged_enums[enum_name] = list(existing.union(set(values)))

                # Merge datasets
                for dataset in catalog.datasets:
                    if dataset.dataset not in dataset_names_seen:
                        all_datasets.append(dataset)
                        dataset_names_seen.add(dataset.dataset)

                if merged_last_updated is None or catalog.last_updated > merged_last_updated:
                    merged_last_updated = catalog.last_updated

                logger.info(f"Loaded {catalog_path.name}: {len(catalog.datasets)} datasets")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {catalog_path}: {e}")
            except Exception as e:
                logger.error(f"Failed to load {catalog_path}: {e}")

        if not all_datasets:
            raise ValueError("No valid UW catalogs loaded")

        self.catalog = UWCatalog(
            version="merged",
            last_updated=merged_last_updated or "unknown",
            source="Unusual Whales (all catalogs)",
            base_url=self.base_url,
            enums=merged_enums,
            datasets=all_datasets
        )
        
        self._enums = merged_enums
        self._build_index()

        logger.info(f"UW catalog: {len(self.catalog.datasets)} datasets loaded")
        return self.catalog

    def _build_index(self):
        """Build index for fast dataset lookup."""
        self._dataset_index = {d.dataset: d for d in self.catalog.datasets} if self.catalog else {}
    
    def get_dataset(self, name: str) -> Optional[UWDatasetEntry]:
        """Get a specific dataset by name."""
        return self._dataset_index.get(name)
    
    def get_enum_values(self, enum_name: str) -> List[str]:
        """Get allowed values for an enum."""
        return self._enums.get(enum_name, [])
    
    def filter_by_class(self, dataset_class: str) -> List[UWDatasetEntry]:
        """Filter datasets by class."""
        if not self.catalog:
            return []
        return [d for d in self.catalog.datasets if d.class_ == dataset_class]
    
    def filter_discoverable(self, discoverable: bool = True) -> List[UWDatasetEntry]:
        """Filter datasets by discoverable status."""
        if not self.catalog:
            return []
        return [d for d in self.catalog.datasets if d.discoverable == discoverable]
    
    def get_datasets_by_catalog_source(self, catalog_name: str) -> List[UWDatasetEntry]:
        """
        Get datasets from a specific catalog source (dynamically discovered).
        
        Args:
            catalog_name: One of 'options', 'institutional', 'market'
        """
        if not self.catalog:
            return []
        
        catalog_dir = Path(__file__).parent
        catalog_map = {
            'options': catalog_dir / "uw_options_catalog.json",
            'institutional': catalog_dir / "uw_institutional_catalog.json",
            'market': catalog_dir / "uw_market_catalog.json",
        }
        
        catalog_path = catalog_map.get(catalog_name)
        if not catalog_path or not catalog_path.exists():
            return []
        
        try:
            with open(catalog_path, 'r') as f:
                data = json.load(f)
            source_names = {d['dataset'] for d in data.get('datasets', [])}
            return [d for d in self.catalog.datasets if d.dataset in source_names]
        except Exception:
            return []
    
    def get_options_datasets(self) -> List[UWDatasetEntry]:
        """Get all options-related datasets (dynamically discovered)."""
        return self.get_datasets_by_catalog_source('options')
    
    def get_institutional_datasets(self) -> List[UWDatasetEntry]:
        """Get all institutional-related datasets (dynamically discovered)."""
        return self.get_datasets_by_catalog_source('institutional')
    
    def get_market_datasets(self) -> List[UWDatasetEntry]:
        """Get all market-related datasets (dynamically discovered)."""
        return self.get_datasets_by_catalog_source('market')
    
    def search_datasets(self, keyword: str) -> List[UWDatasetEntry]:
        """Search datasets by keyword in name or notes."""
        if not self.catalog:
            return []
        
        keyword_lower = keyword.lower()
        results = []
        for dataset in self.catalog.datasets:
            if keyword_lower in dataset.dataset.lower():
                results.append(dataset)
            elif dataset.notes and keyword_lower in dataset.notes.lower():
                results.append(dataset)
        return results
    
    def get_datasets_by_identifier(self, identifier: str) -> List[UWDatasetEntry]:
        """Get datasets that use a specific identifier parameter."""
        if not self.catalog:
            return []
        return [d for d in self.catalog.datasets if d.identifier_param == identifier]
    
    def validate_catalog_integrity(self) -> Dict[str, Any]:
        """Validate catalog integrity and return report."""
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
        
        for dataset in self.catalog.datasets:
            path_params = dataset.get_path_params()
            for param in path_params:
                if param not in dataset.params_schema:
                    report["issues"].append(f"{dataset.dataset}: Path param '{param}' not in params_schema")
            
            if dataset.cache_ttl == 0:
                report["issues"].append(f"{dataset.dataset}: Cache TTL is 0")
        
        report["valid"] = len(report["issues"]) == 0
        return report
    
    def get_catalog_summary(self) -> str:
        """Get a human-readable summary of the catalog."""
        if not self.catalog:
            return "Catalog not loaded"
        
        lines = [
            f"Unusual Whales Dataset Catalog v{self.catalog.version}",
            f"Last Updated: {self.catalog.last_updated}",
            f"Total Datasets: {len(self.catalog.datasets)}",
            "",
            "Breakdown by Class:"
        ]
        
        for class_name, count in sorted(self.catalog.get_dataset_count().items()):
            lines.append(f"  - {class_name}: {count}")
        
        lines.append(f"\nEnums: {', '.join(self._enums.keys())}" if self._enums else "")
        return "\n".join(lines)


# Module-level convenience functions
_default_loader: Optional[UWDDCLoader] = None


def get_default_loader() -> UWDDCLoader:
    """Get or create the default UW DDC loader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = UWDDCLoader()
    return _default_loader


def load_catalog(catalog_path: Optional[Union[str, Path]] = None) -> UWCatalog:
    """Load catalog from specified path or default location."""
    if catalog_path:
        return UWDDCLoader(catalog_path).catalog
    return get_default_loader().catalog


def get_dataset(name: str) -> Optional[UWDatasetEntry]:
    """Get a dataset by name from the default catalog."""
    return get_default_loader().get_dataset(name)


def search_datasets(keyword: str) -> List[UWDatasetEntry]:
    """Search datasets by keyword."""
    return get_default_loader().search_datasets(keyword)
