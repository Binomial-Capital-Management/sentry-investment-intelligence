"""
Utility helpers for the FinFeed Prediction Markets MCP server.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional


def create_outcome_slug(outcome_name: Optional[str], index: int, existing_slugs: set[str]) -> str:
    """
    Create a safe, unique slug for an outcome identifier.

    Args:
        outcome_name: Raw outcome name from the API (may be None/blank)
        index: Index of the outcome in the source list (used as fallback)
        existing_slugs: Slugs already assigned for the market to ensure uniqueness

    Returns:
        Slug containing lowercase alphanumerics and hyphens only.
    """
    if not outcome_name or not outcome_name.strip():
        return f"outcome-{index}"

    slug = outcome_name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)  # remove punctuation except spaces/hyphen
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")  # spaces/underscores -> hyphen

    if not slug:
        slug = f"outcome-{index}"

    base_slug = slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """
    Safely parse an ISO 8601 datetime string into a datetime object.

    Args:
        value: Raw value from the API (string, datetime, or None)

    Returns:
        Parsed datetime or None if parsing fails.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None

        try:
            if candidate.endswith("Z"):
                candidate = f"{candidate[:-1]}+00:00"
            return datetime.fromisoformat(candidate)
        except (ValueError, AttributeError) as exc:
            logging.warning("Failed to parse datetime value '%s': %s", value, exc)
            return None

    return None


def build_cache_key(prefix: str, tenant_id: Optional[str], **params: Any) -> str:
    """
    Build a namespaced cache key using supplied parameters.

    Args:
        prefix: Key prefix (e.g., 'prices', 'history')
        tenant_id: Tenant/user identifier for cache isolation
        **params: Additional parameters that should make the key unique

    Returns:
        String suitable for use as a cache key.
    """
    tenant = tenant_id or "shared"
    parts = [f"{k}={v}" for k, v in sorted(params.items()) if v is not None]

    if parts:
        return f"{prefix}:{tenant}:{':'.join(parts)}"

    return f"{prefix}:{tenant}"
