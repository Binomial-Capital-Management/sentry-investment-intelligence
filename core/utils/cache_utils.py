"""
Cache utilities for consistent cache key generation.
Following CODING_RULES.md: Simple, reusable, single responsibility.
"""

import hashlib
import json
from typing import Any, Dict, Optional


def stable_cache_key(
    namespace: str,
    session_id: str,
    tool: Optional[str] = None,
    version: str = "v1",
    params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a stable cache key using SHA256 of deterministic JSON.
    Session-based caching for better hit rates (not user-specific).
    
    Args:
        namespace: Cache namespace (e.g., "agent", "risk")
        session_id: Session identifier (primary key component)
        tool: Optional tool name
        version: Cache version for invalidation
        params: Additional parameters to include in key
        
    Returns:
        SHA256 hash as hex string
    """
    # Build deterministic payload string
    params_str = ""
    if params:
        # Sort and compact JSON for stable params
        params_str = json.dumps(params, sort_keys=True, separators=(',', ':'))
    
    # Create raw key string
    raw_key = f"{namespace}:{version}:{session_id}:{tool or ''}:{params_str}"
    
    # Return SHA256 hash
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def cache_key_for_agent(
    agent_type: str,
    query: str,
    session_id: str,
    portfolio_state: Optional[Dict[str, Any]] = None,
    attachments: bool = False
) -> str:
    """
    Generate cache key for agent responses.
    
    Args:
        agent_type: Type of agent (e.g., "generalist", "risk_specialist")
        query: User query
        session_id: Session identifier
        user_id: Optional user ID
        portfolio_state: Optional portfolio context
        attachments: Whether attachments are present
        
    Returns:
        Stable cache key
    """
    params = {
        "query": query,
        "attachments": attachments
    }
    
    if portfolio_state:
        # Include portfolio ID to differentiate cache
        params["portfolio_id"] = portfolio_state.get("id")
    
    return stable_cache_key(
        namespace="agent",
        session_id=session_id,
        tool=agent_type,
        params=params
    )