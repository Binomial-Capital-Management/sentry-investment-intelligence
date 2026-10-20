"""
MCP Result Parser - Provider-agnostic tool result extraction.
Handles differences between OpenAI/Anthropic/Gemini response formats.
"""

import json
import logging
from typing import Any, Optional, Union, Dict

logger = logging.getLogger(__name__)


def safe_extract_content(result: Any) -> Optional[str]:
    """
    Safely extract content from MCP tool result, handling all provider formats.

    Provider differences:
    - OpenAI/Anthropic: result.content[0].text
    - Gemini: May have empty content[], no .text attribute, or different structure

    Args:
        result: MCP tool result from any provider

    Returns:
        Extracted content as string, or None if extraction fails
    """
    if not result:
        return None

    # Handle error results
    if hasattr(result, 'isError') and result.isError:
        logger.debug(f"Result is an error: {result}")
        return None

    try:
        # Check if content exists and is not empty
        if hasattr(result, 'content') and result.content:
            # Ensure content is a list/array
            if hasattr(result.content, '__len__') and len(result.content) > 0:
                first_item = result.content[0]

                # Standard format: has .text attribute (OpenAI/Anthropic)
                if hasattr(first_item, 'text'):
                    return first_item.text

                # Gemini variant 1: Direct string in content array
                if isinstance(first_item, str):
                    return first_item

                # Gemini variant 2: Dict with 'text' or 'value' key
                if isinstance(first_item, dict):
                    text_val = first_item.get('text') or first_item.get('value')
                    if text_val:
                        return text_val
                    # Full dict fallback
                    return json.dumps(first_item)

                # Fallback: Convert to string
                return str(first_item)

        # Some providers might put content directly on result
        if hasattr(result, 'text'):
            return result.text

        # Last resort: stringify the result if it looks meaningful
        result_str = str(result)
        if result_str and not result_str.startswith('<') and not result_str.startswith('CallToolResult'):
            return result_str

    except (IndexError, AttributeError, TypeError) as e:
        logger.debug(f"Failed to extract content from result: {e}, result type: {type(result)}")

    return None


def safe_parse_json(result: Any, default: Optional[Dict] = None) -> Dict:
    """
    Safely parse JSON from MCP tool result.

    Args:
        result: MCP tool result from any provider
        default: Default value if parsing fails (defaults to empty dict)

    Returns:
        Parsed JSON as dict, or default value
    """
    if default is None:
        default = {}

    content = safe_extract_content(result)
    if not content:
        logger.debug(f"No content extracted, returning default: {default}")
        return default

    try:
        # Try parsing as JSON
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list):
            # Some endpoints return arrays directly - wrap in dict
            return {"data": parsed}
        else:
            logger.debug(f"Parsed content is not a dict or list: {type(parsed)}")
            return default
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse JSON from content: {e}, content preview: {content[:100]}")
        return default
    except Exception as e:
        logger.warning(f"Unexpected error parsing JSON: {e}")
        return default


def safe_extract_text(result: Any, default: str = "") -> str:
    """
    Safely extract text content from MCP tool result.

    Args:
        result: MCP tool result from any provider
        default: Default value if extraction fails

    Returns:
        Extracted text or default value
    """
    content = safe_extract_content(result)
    return content if content is not None else default