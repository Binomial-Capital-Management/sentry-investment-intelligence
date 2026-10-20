"""
Validation utilities for inline chart data.

Simple, clean validation following KISS principle.
No over-engineering, just what's needed for safe inline data.
"""

from typing import List, Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


def validate_inline_series(
    data: Any,
    max_points: int = 10000,
    field_name: str = "data"
) -> Optional[List]:
    """
    Validate inline data series for charts.
    
    Args:
        data: Input data to validate (should be a list)
        max_points: Maximum allowed data points
        field_name: Field name for error messages
    
    Returns:
        Validated list or None if invalid
    """
    # Must be a list
    if not isinstance(data, list):
        logger.debug(f"Inline {field_name} is not a list")
        return None
    
    # Empty lists are valid (chart will handle gracefully)
    if len(data) == 0:
        return data
    
    # Check size limit
    if len(data) > max_points:
        logger.warning(f"Inline {field_name} exceeds max points: {len(data)} > {max_points}")
        return data[:max_points]  # Truncate rather than reject
    
    # Basic type validation - allow numbers, strings, or dicts
    # Charts will handle type conversion as needed
    first_item = data[0]
    if isinstance(first_item, (int, float, str, dict)):
        return data
    
    logger.debug(f"Inline {field_name} contains unsupported type: {type(first_item)}")
    return None


def validate_inline_dict(
    data: Any,
    max_points_per_series: int = 10000
) -> Optional[Dict[str, List]]:
    """
    Validate inline dictionary data (e.g., for multi-series charts).
    
    Args:
        data: Input data to validate (should be a dict of lists)
        max_points_per_series: Maximum points per series
    
    Returns:
        Validated dict or None if invalid
    """
    if not isinstance(data, dict):
        logger.debug("Inline data_dict is not a dictionary")
        return None
    
    validated = {}
    for key, series in data.items():
        validated_series = validate_inline_series(
            series, 
            max_points_per_series,
            f"data_dict[{key}]"
        )
        if validated_series is not None:
            validated[key] = validated_series
    
    return validated if validated else None


def extract_inline_data(inputs: Dict[str, Any]) -> Optional[Union[List, Dict]]:
    """
    Extract and validate inline data from chart inputs.
    
    Checks for 'data' field first (single series),
    then 'data_dict' (multi-series), following the convention.
    
    Args:
        inputs: Chart input dictionary
    
    Returns:
        Validated inline data or None if not present/invalid
    """
    from core.config import config
    max_points = config.charts_max_inline_points
    
    # Check for single series inline data
    if 'data' in inputs:
        return validate_inline_series(inputs['data'], max_points)
    
    # Check for multi-series inline data
    if 'data_dict' in inputs:
        return validate_inline_dict(inputs['data_dict'], max_points)
    
    return None


def has_inline_data(inputs: Dict[str, Any]) -> bool:
    """
    Quick check if inputs contain inline data.
    
    Args:
        inputs: Chart input dictionary
    
    Returns:
        True if valid inline data exists
    """
    return extract_inline_data(inputs) is not None