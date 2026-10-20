"""
Canvas module - Object-centric analysis workspace.

This module provides the foundational object registry and matching system
for the Canvas feature, enabling an object-first approach where users
select data objects and tools are auto-surfaced based on compatibility.
"""

from .object_registry import (
    ObjectType,
    DataSource,
    OBJECT_REGISTRY,
    get_object_type,
    get_all_object_types,
    list_object_types,
    get_combined_capabilities,
    get_object_with_parent_capabilities,
    get_nested_types,
    get_objects_providing,
    get_expanded_capabilities,
    get_all_data_sources,
)

from .object_type_detector import (
    ObjectTypeDetector,
    ObjectTypeResult,
    detect_object_type,
    get_detector,
)

from .data_categories import (
    Category,
    CATEGORY_DEFINITIONS,
    get_all_categories,
    get_categories_for_object,
    get_category_by_name,
    get_datasets_for_category,
    get_category_for_dataset,
    get_category_for_field,
)

from .object_data_service import (
    ObjectDataService,
    FetchResult,
    get_data_service,
)

__all__ = [
    # Object Registry
    "ObjectType",
    "DataSource",
    "OBJECT_REGISTRY",
    "get_object_type",
    "get_all_object_types",
    "list_object_types",
    "get_combined_capabilities",
    "get_object_with_parent_capabilities",
    "get_nested_types",
    "get_objects_providing",
    "get_expanded_capabilities",
    "get_all_data_sources",
    # Object Type Detector
    "ObjectTypeDetector",
    "ObjectTypeResult",
    "detect_object_type",
    "get_detector",
    # Data Categories
    "Category",
    "CATEGORY_DEFINITIONS",
    "get_all_categories",
    "get_categories_for_object",
    "get_category_by_name",
    "get_datasets_for_category",
    "get_category_for_dataset",
    "get_category_for_field",
    # Object Data Service
    "ObjectDataService",
    "FetchResult",
    "get_data_service",
]
