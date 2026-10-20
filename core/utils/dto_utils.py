"""
DTO utilities for converting database records to API models.
Following CODING_RULES.md: Single responsibility, clean conversions.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


def safe_record_access(record: Any, key: str, default: Any = None) -> Any:
    """
    Safely access asyncpg.Record or dict fields.
    
    Args:
        record: asyncpg.Record or dict
        key: Field name to access
        default: Default value if key not found
        
    Returns:
        Field value or default
    """
    if record is None:
        return default
    
    try:
        # Try dict-style access first (works for both dict and asyncpg.Record)
        if hasattr(record, '__getitem__'):
            return record[key]
    except (KeyError, IndexError):
        pass
    
    try:
        # Try attribute access for objects
        if hasattr(record, key):
            return getattr(record, key)
    except AttributeError:
        pass
    
    # Try get method if available
    if hasattr(record, 'get'):
        return record.get(key, default)
    
    return default


def record_to_dict(row: Any) -> Dict[str, Any]:
    """
    Convert asyncpg.Record to dict once with proper type conversions.
    
    Args:
        row: Database row (asyncpg.Record or dict)
        
    Returns:
        Dict with UUID→str and datetime→ISO string conversions
    """
    import json
    
    if row is None:
        return {}
    
    # Convert to dict once
    if isinstance(row, dict):
        row_dict = row
    else:
        # asyncpg.Record - convert to dict once
        try:
            row_dict = dict(row)
        except Exception as e:
            logger.warning(f"Failed to convert row to dict: {e}")
            return {}
    
    # Fields that should be parsed as JSON if they come back as strings
    json_fields = {'metadata', 'reference_metadata', 'chart_config', 'data_summary'}
    
    # Convert types for JSON serialization
    result = {}
    for key, value in row_dict.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            # Handle lists (e.g., tickers, weights)
            result[key] = list(value)
        elif key in json_fields and isinstance(value, str):
            # Parse JSON string fields back to dicts
            try:
                result[key] = json.loads(value) if value else None
            except (json.JSONDecodeError, TypeError):
                result[key] = value
        else:
            result[key] = value
    
    return result


def row_to_dto(row: Any) -> Dict[str, Any]:
    """
    Alias for record_to_dict for backwards compatibility.
    
    Args:
        row: Database row (asyncpg.Record or dict)
        
    Returns:
        Dict with UUID→str and datetime→ISO string conversions
    """
    return record_to_dict(row)


def rows_to_dtos(rows: List[Any]) -> List[Dict[str, Any]]:
    """
    Convert multiple database rows to DTOs.
    
    Args:
        rows: List of database rows
        
    Returns:
        List of DTOs with proper type conversions
    """
    return [row_to_dto(row) for row in rows]


def portfolio_row_to_dto(row: Any) -> Dict[str, Any]:
    """
    Convert portfolio database row to API DTO.
    
    Args:
        row: Portfolio database row
        
    Returns:
        Portfolio DTO with normalized fields
    """
    if row is None:
        return {}
    
    dto = row_to_dto(row)
    
    # Ensure required portfolio fields
    if 'tickers' in dto and dto['tickers'] and 'weights' not in dto:
        # Default to equal weights if missing
        dto['weights'] = [1.0 / len(dto['tickers'])] * len(dto['tickers'])
    
    # Normalize metadata
    if 'metadata' in dto:
        metadata = dto['metadata']
        if isinstance(metadata, str):
            try:
                import json
                dto['metadata'] = json.loads(metadata)
            except:
                dto['metadata'] = {}
        elif not isinstance(metadata, dict):
            dto['metadata'] = {}
    
    return dto


def chat_session_row_to_dto(row: Any) -> Dict[str, Any]:
    """
    Convert chat session database row to API DTO.
    
    Args:
        row: Chat session database row
        
    Returns:
        Chat session DTO with normalized fields
    """
    if row is None:
        return {}
    
    dto = row_to_dto(row)
    
    # Ensure ID is string
    if 'id' in dto and dto['id'] is not None:
        dto['id'] = str(dto['id'])
    
    # Handle timestamps
    for field in ['created_at', 'updated_at']:
        if field in dto and dto[field]:
            if isinstance(dto[field], datetime):
                dto[field] = dto[field].isoformat()
            elif not isinstance(dto[field], str):
                dto[field] = str(dto[field])
    
    return dto