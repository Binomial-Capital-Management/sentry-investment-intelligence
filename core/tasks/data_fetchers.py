"""
Data hydration for Task input nodes.

Fetches data from backends and formats as text context for agent instructions.
Follows chat system pattern: pre-fetch structured data, format as readable text.
"""

from __future__ import annotations

from typing import List

from .types import TaskInputSpec, TaskNodeType
from core.database.postgres_client import get_postgres_rls_client


async def hydrate_inputs(inputs: List[TaskInputSpec], user_id: str, org_id: str = None) -> str:
    """
    Fetch data for all input nodes and format as text context.

    Reuses Chat's file handling infrastructure:
    - Portfolio: Fetches from PostgreSQL with RLS
    - Files: Validates file_id in file_uploads table
    - Cloud files: Same validation as uploaded files

    Returns formatted text block ready for injection into agent instructions,
    or empty string if no inputs exist.

    Args:
        inputs: List of input node specifications from canvas
        user_id: User ID for RLS context
        org_id: Organization ID for workspace isolation

    Returns:
        Formatted text block for agent context
    """
    if not inputs:
        return ""

    sections = []

    for spec in inputs:
        text = ""

        if spec.type == TaskNodeType.PORTFOLIO:
            text = await _hydrate_portfolio(spec, user_id, org_id)
        elif spec.type == TaskNodeType.FILE_UPLOAD:
            text = await _hydrate_file_upload(spec, user_id, org_id)
        elif spec.type == TaskNodeType.ONEDRIVE:
            text = await _hydrate_cloud_file(spec, user_id, "OneDrive", org_id)
        elif spec.type == TaskNodeType.GOOGLE_DRIVE:
            text = await _hydrate_cloud_file(spec, user_id, "Google Drive", org_id)
        # Graph node not implemented yet - skip

        if text:
            sections.append(text)

    return "\n\n".join(sections)


async def _hydrate_portfolio(spec: TaskInputSpec, user_id: str, org_id: str = None) -> str:
    """
    Fetch portfolio from database and format as readable text.

    Follows chat pattern from v6.py:load_portfolio_context()
    and context_manager.py:build_shared_context()
    """
    portfolio_id = spec.params.get("portfolioId")
    if not portfolio_id:
        return ""

    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        row = await conn.fetchrow(
            "SELECT name, tickers, weights, value FROM portfolios WHERE id = $1",
            portfolio_id
        )

    if not row:
        return ""

    # Extract and format data
    name = spec.name or row["name"] or "Portfolio"
    tickers = row["tickers"][:15]  # Limit for readability
    weights = row["weights"][:15]
    value = row.get("value", 0)

    # Format weights as percentages
    weight_strs = [f"{w:.1%}" for w in weights]

    return (
        f"=== {name} ===\n"
        f"Tickers: {', '.join(tickers)}\n"
        f"Weights: {', '.join(weight_strs)}\n"
        f"Total Value: ${value:,.2f}"
    )


async def _hydrate_file_upload(spec: TaskInputSpec, user_id: str, org_id: str = None) -> str:
    """
    Validate file upload and format instructions for agent.

    Reuses chat's file handling pattern (api/routers/v6.py:605-679):
    - Validates file_id exists in file_uploads table with RLS check
    - Formats instructions identical to langgraph_nodes.py:_build_file_context()
    - Agent uses same read_file_content() tool that Chat uses

    NOTE: Frontend needs to upload file to backend first and store fileId in params.
    """
    file_id = spec.params.get("fileId")
    if not file_id:
        # Fallback: if fileName provided but no fileId, return TODO message
        file_name = spec.params.get("fileName")
        if file_name:
            node_name = spec.name or file_name
            return (
                f"=== File: {node_name} ===\n"
                f"User selected: {file_name}\n"
                f"[File not uploaded yet - frontend needs to upload and store fileId in params]\n"
            )
        return ""

    # Validate file exists and user owns it (RLS check - same as Chat)
    pg = await get_postgres_rls_client()
    async with pg.acquire_with_org_context(user_id, org_id) as conn:
        row = await conn.fetchrow(
            "SELECT id, original_name FROM file_uploads WHERE id = $1",
            file_id
        )

    if not row:
        return ""

    file_name = row["original_name"]
    node_name = spec.name or file_name

    # Format instructions identical to Chat's _build_file_context()
    return (
        f"=== File: {node_name} ===\n"
        f"User has attached 1 file (ID: '{file_id}').\n"
        f"Use read_file_content(file_id='{file_id}', user_id='{user_id}') to access the content.\n"
    )


async def _hydrate_cloud_file(spec: TaskInputSpec, user_id: str, source: str, org_id: str = None) -> str:
    """
    Validate cloud file and format instructions for agent.

    Reuses chat's file handling pattern. Two approaches:
    1. If fileId present: File was uploaded to backend, validate and use read_file_content()
    2. If only connectedFile present: Show TODO message (frontend needs upload flow)

    NOTE: Frontend currently stores connectedFile name but not fileId.
    Frontend should either:
    - Upload cloud file to backend (like Chat does) and store fileId
    - Or store cloud item_id and download during execution
    """
    # Approach 1: File uploaded to backend storage (ideal - reuses Chat's infrastructure)
    file_id = spec.params.get("fileId")
    if file_id:
        # Same validation as _hydrate_file_upload - RLS check
        pg = await get_postgres_rls_client()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                "SELECT id, original_name FROM file_uploads WHERE id = $1",
                file_id
            )

        if row:
            file_name = row["original_name"]
            node_name = spec.name or file_name
            # Format instructions identical to Chat's _build_file_context()
            return (
                f"=== {source} File: {node_name} ===\n"
                f"User has attached 1 file (ID: '{file_id}').\n"
                f"Use read_file_content(file_id='{file_id}', user_id='{user_id}') to access the content.\n"
            )

    # Approach 2: Only name stored (current state - show TODO)
    file_name = spec.params.get("connectedFile")
    if not file_name:
        return ""

    node_name = spec.name or file_name
    return (
        f"=== {source} File: {node_name} ===\n"
        f"User selected: {file_name}\n"
        f"[{source} file not uploaded yet - frontend needs to upload and store fileId in params]\n"
    )
