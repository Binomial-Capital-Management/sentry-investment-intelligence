"""
BinomialHash agent tools — thin wrappers over the BinomialHash class.

These are the @function_tool definitions the SpreadsheetAgent uses to
retrieve, aggregate, query, group, export, and inspect stored datasets.
"""

import json
from typing import List, Optional

from agents import function_tool

from core.agents.binomial_hash import get_binomial_hash


def _parse_columns(columns: Optional[str]) -> Optional[List[str]]:
    """Parse columns parameter which may be a JSON string or None.
    
    LLMs sometimes send list params as JSON strings like '["a", "b"]'
    instead of actual lists. This handles both cases gracefully.
    """
    if columns is None:
        return None
    if isinstance(columns, list):
        return columns  # Already a list (shouldn't happen but defensive)
    try:
        parsed = json.loads(columns)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: treat as comma-separated string
    return [c.strip() for c in columns.split(",") if c.strip()]


# ── Retrieve ─────────────────────────────────────────────────────────────────

@function_tool
async def bh_retrieve(
    key: str,
    offset: int = 0,
    limit: int = 25,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    columns: Optional[str] = None,
) -> str:
    """Retrieve a slice of rows from a BinomialHash dataset.

    Use after a tool returns a [BH] summary. Pull rows in batches of 25
    to write to Excel. Supports sorting and column projection.

    Args:
        key: Dataset key from the [BH] message.
        offset: Starting row index (0-based).
        limit: Max rows to return (max 50).
        sort_by: Column name to sort by.
        sort_desc: Sort descending (True) or ascending (False).
        columns: Column names to include as JSON array string (omit for all).
    """
    col_list = _parse_columns(columns)
    result = get_binomial_hash().retrieve(key, offset, limit, sort_by, sort_desc, col_list)
    return json.dumps(result, default=str)


# ── Aggregate ────────────────────────────────────────────────────────────────

@function_tool
async def bh_aggregate(key: str, column: str, func: str) -> str:
    """Compute a scalar aggregate on a stored dataset column.

    Returns the result directly — no rows enter the context.
    Use this to get totals, averages, etc. before writing to Excel.

    Args:
        key: Dataset key.
        column: Column name to aggregate.
        func: One of: sum, mean, median, min, max, std, count, count_distinct.
    """
    result = get_binomial_hash().aggregate(key, column, func)
    return json.dumps(result, default=str)


@function_tool
async def bh_aggregate_batch(aggregations_json: str) -> str:
    """Compute multiple scalar aggregates in ONE call.

    Use this instead of calling bh_aggregate repeatedly — even with
    parallel tool calls, serial aggregate loops waste turns and context.

    Args:
        aggregations_json: JSON array of objects, each with keys:
            - key: Dataset key
            - column: Column name
            - func: One of sum, mean, median, min, max, std, count, count_distinct
    Returns: JSON array of {key, column, func, result} in the same order.

    Example input: '[{"key":"hist_AAPL","column":"Close","func":"max"},
                     {"key":"hist_AAPL","column":"Close","func":"min"},
                     {"key":"hist_MSFT","column":"Volume","func":"sum"}]'
    """
    try:
        specs = json.loads(aggregations_json)
    except (json.JSONDecodeError, TypeError) as exc:
        return json.dumps({"error": f"Invalid JSON: {exc}"})
    if not isinstance(specs, list) or len(specs) == 0:
        return json.dumps({"error": "Expected non-empty JSON array"})
    if len(specs) > 50:
        return json.dumps({"error": f"Too many aggregations ({len(specs)}), max 50"})

    bh = get_binomial_hash()
    results = []
    for spec in specs:
        key = spec.get("key", "")
        column = spec.get("column", "")
        func = spec.get("func", "")
        try:
            val = bh.aggregate(key, column, func)
            results.append({
                "key": key, "column": column, "func": func,
                "result": val.get("result") if isinstance(val, dict) else val,
            })
        except Exception as exc:
            results.append({
                "key": key, "column": column, "func": func, "error": str(exc),
            })
    return json.dumps(results, default=str)


# ── Query (compound AND/OR) ─────────────────────────────────────────────────

@function_tool
async def bh_query(
    key: str,
    where_json: str,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    limit: int = 25,
    columns: Optional[str] = None,
) -> str:
    """Filter and retrieve rows from a stored dataset.

    Like bh_retrieve but with a WHERE clause. Supports compound AND/OR.

    Args:
        key: Dataset key.
        where_json: JSON filter spec. Single or compound conditions.
            Single:  '{"column": "volume", "op": ">", "value": 1000000}'
            AND:     '{"and": [{"column": "ticker", "op": "=", "value": "AAPL"},
                               {"column": "volume", "op": ">", "value": 1000000}]}'
            OR:      '{"or": [{"column": "sector", "op": "=", "value": "Tech"},
                              {"column": "sector", "op": "=", "value": "Finance"}]}'
            Nested:  '{"and": [{"column": "volume", "op": ">", "value": 1000000},
                               {"or": [{"column": "ticker", "op": "=", "value": "AAPL"},
                                       {"column": "ticker", "op": "=", "value": "MSFT"}]}]}'
            Ops: =, !=, >, <, >=, <=, in, not_in, contains
        sort_by: Column to sort by after filtering.
        sort_desc: Sort descending (True) or ascending (False).
        limit: Max rows to return (max 50).
        columns: Column names to include as JSON array string.
    """
    col_list = _parse_columns(columns)
    result = get_binomial_hash().query(key, where_json, sort_by, sort_desc, limit, col_list)
    return json.dumps(result, default=str)


# ── Schema ───────────────────────────────────────────────────────────────────

@function_tool
async def bh_schema(key: str) -> str:
    """Get full schema info for a stored dataset.

    Returns column names, inferred types (numeric/string/date/bool),
    and per-column statistics (min, max, mean, unique count, etc.).
    Call this to understand a dataset before deciding what to write.

    Args:
        key: Dataset key.
    """
    result = get_binomial_hash().schema(key)
    return json.dumps(result, default=str)


# ── Group-by ─────────────────────────────────────────────────────────────────

@function_tool
async def bh_group_by(
    key: str,
    group_cols: str,
    agg_json: str,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    limit: int = 50,
) -> str:
    """Group rows by column(s) and aggregate — like SQL GROUP BY.

    Returns grouped results with computed aggregates. No raw rows enter
    the context — only the grouped summaries.

    Args:
        key: Dataset key.
        group_cols: Column(s) to group by as JSON array string. E.g. '["sector"]' or '["sector", "industry"]'.
        agg_json: JSON list of aggregations.
            Each item: {"column": "...", "func": "...", "alias": "..."}.
            func: sum, mean, median, min, max, std, count, count_distinct.
            alias is optional (defaults to "func_column").
            Examples:
                '[{"column": "revenue", "func": "sum", "alias": "total_revenue"}]'
                '[{"column": "price", "func": "mean"}, {"column": "ticker", "func": "count"}]'
        sort_by: Column or alias to sort results by.
        sort_desc: Sort descending (True) or ascending (False).
        limit: Max groups to return (max 50).
    """
    group_list = _parse_columns(group_cols) or []
    result = get_binomial_hash().group_by(key, group_list, agg_json, sort_by, sort_desc, limit)
    return json.dumps(result, default=str)


# ── Batch Excel export ───────────────────────────────────────────────────────

@function_tool
async def bh_to_excel(
    key: str,
    columns: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    max_rows: int = 200,
) -> str:
    """DEPRECATED — use bh_dump_to_excel instead. This tool loads ALL rows into LLM context
    (1,750+ tokens per 252-row dataset), bloating context and wasting budget.
    bh_dump_to_excel pipes data directly BH → Excel with zero context cost.

    If you are reading this, call bh_dump_to_excel(key, sheet, start_cell) instead.

    Args:
        key: Dataset key.
        columns: Column names to include as JSON array string (omit for all).
        sort_by: Column to sort by.
        sort_desc: Sort descending (True) or ascending (False).
        max_rows: Maximum rows to export (default 200, max 500).
    """
    col_list = _parse_columns(columns)
    result = get_binomial_hash().to_excel_batch(key, col_list, sort_by, sort_desc, max_rows)
    return json.dumps(result, default=str)


# ── Manifold state and objective insights ─────────────────────────────────────

@function_tool
async def bh_manifold_state(key: str) -> str:
    """Build deterministic manifold state for a stored dataset.

    Returns discovered dimensions, dependency graph preview, and categorical
    complexity. Use this before asking for objective-driven insights.

    Args:
        key: Dataset key.
    """
    result = get_binomial_hash().manifold_state(key)
    return json.dumps(result, default=str)


@function_tool
async def bh_manifold_insights(key: str, objective_json: str, top_k: int = 5) -> str:
    """Generate objective-driven manifold insights on a stored dataset.

    Insights include:
      - surprises: strongest contradictions to discovered law
      - regime_boundaries: sharp transitions along the best driver axis
      - branch_divergence: same target level, different latent contexts
      - counterfactual: direction/action suggestion from fitted law

    objective_json example:
      {"target": "future_return_1d", "goal": "maximize", "target_value": 0.02}

    Args:
        key: Dataset key.
        objective_json: JSON objective definition.
        top_k: Max entries per insight block.
    """
    result = get_binomial_hash().manifold_insights(key, objective_json, top_k)
    return json.dumps(result, default=str)


@function_tool
async def bh_navigate(key: str, coord_json: str, target_field: Optional[str] = None) -> str:
    """Navigate the manifold surface at a specific coordinate.

    The manifold is built from discovered tabular axes and field values.
    You inspect an operational local neighborhood by specifying axis
    coordinates from `bh_manifold_state`.

    Returns:
      - position: field values, curvature, density at this point
      - surface: operational surface label when manifold gates pass, otherwise
        a diagnostic label such as `graph_only`
      - topology: graph/face-complex diagnostics, orientability proxy, and
        Euler/genus or crosscap estimates when applicable
      - gradients: how a target field changes toward each neighbor
      - steepest_move: the direction with the largest change

    Args:
        key: Dataset key.
        coord_json: JSON dict of axis values, e.g. '{"strike": "200", "option_type": "call"}'
        target_field: Field column to track gradients for (e.g. "implied_volatility").
    """
    result = get_binomial_hash().manifold_navigate(key, coord_json, target_field)
    return json.dumps(result, default=str)


@function_tool
async def bh_manifold_slice(key: str, condition_json: str, target_field: Optional[str] = None) -> str:
    """Build a conditional sub-manifold from filtered rows.

    Lets you ask: "what does the shape look like WHEN this condition holds?"
    Filters rows, builds a fresh manifold from the subset, returns its summary
    including topology, critical points, and interactions for the slice.

    Use this to inspect regime-dependent behavior. Changes in cycle rank,
    critical points, or interactions can indicate a structural regime shift,
    but they should be read as diagnostics rather than proof.

    Args:
        key: Dataset key.
        condition_json: JSON filter, e.g. '{"column": "realized_vol_1m", "op": ">", "value": 0.035}'
            Supported ops: >, >=, <, <=, =, !=
        target_field: Optional field to compute persistence for in the slice.
    """
    result = get_binomial_hash().manifold_slice(key, condition_json, target_field)
    return json.dumps(result, default=str)


# ── Navigation: Geodesic pathfinding ─────────────────────────────────────────

@function_tool
async def bh_geodesic(
    key: str,
    start_json: str,
    end_json: str,
    target_field: Optional[str] = None,
) -> str:
    """Walk the shortest path between two points on the manifold mesh.

    Like pathfinding in a game. Returns waypoints with field values and
    deltas at each step so you can see what changes along the route.

    Edge weight = |change in target_field| if provided, else hop count.
    When using target_field weight, the path follows the smoothest route
    (smallest total change) — diversions reveal barriers.

    Args:
        key: Dataset key.
        start_json: Starting coordinate, e.g. '{"gene_region": "Enhancer", "chromosome": "chr7"}'
        end_json: Ending coordinate, same format.
        target_field: Field to weight edges by (optional). Omit for shortest hop path.
    """
    result = get_binomial_hash().geodesic(key, start_json, end_json, target_field)
    return json.dumps(result, default=str)


# ── Navigation: Controlled axis walk ─────────────────────────────────────────

@function_tool
async def bh_walk_axis(key: str, walk_axis: str, target_field: str) -> str:
    """Sweep one manifold axis while averaging target across all others.

    Like holding a joystick in one direction and watching the altimeter.
    Returns the target's mean/min/max at each axis value plus the total
    sensitivity (max_mean - min_mean). High sensitivity = this axis matters.

    Use this to quickly scan which axes the target responds to most.

    Args:
        key: Dataset key.
        walk_axis: Name of the axis to walk along (from manifold_state axes).
        target_field: Numeric field to track.
    """
    result = get_binomial_hash().controlled_walk(key, walk_axis, target_field)
    return json.dumps(result, default=str)


# ── Statistics: Multivariate regression ──────────────────────────────────────

@function_tool
async def bh_regress(key: str, target: str, drivers_json: str) -> str:
    """Multivariate regression. YOU pick the target and drivers.

    Fits target = β₀ + β₁·driver₁ + β₂·driver₂ + ... using OLS.
    Returns all coefficients, R², adjusted R², and individual correlations.
    The coefficient tells you how much target changes per unit of that driver,
    holding all other drivers constant.

    This is how you find hidden drivers: if driver X has a large coefficient
    but low individual correlation, it's being masked by confounders.

    Args:
        key: Dataset key.
        target: Target column name (what you're trying to explain).
        drivers_json: JSON list of driver column names,
            e.g. '["methylation_score", "expression_level", "gc_content"]'
    """
    result = get_binomial_hash().regress(key, target, drivers_json)
    return json.dumps(result, default=str)


# ── Statistics: Partial correlation ──────────────────────────────────────────

@function_tool
async def bh_partial_corr(
    key: str,
    field_a: str,
    field_b: str,
    controls_json: str,
) -> str:
    """Partial correlation: how correlated are A and B AFTER removing the effect of controls?

    Regresses A on controls, regresses B on controls, then correlates the residuals.
    If raw correlation is high but partial is low, the relationship is spurious
    (driven by the controls). If partial stays high, the relationship is real.

    Args:
        key: Dataset key.
        field_a: First field.
        field_b: Second field.
        controls_json: JSON list of control columns to remove,
            e.g. '["expression_level", "gc_content"]'
    """
    result = get_binomial_hash().partial_correlate(key, field_a, field_b, controls_json)
    return json.dumps(result, default=str)


@function_tool
async def bh_pca_surface(key: str, fields_json: str, n_components: int = 3) -> str:
    """Run PCA on selected numeric fields to expose latent low-dimensional structure."""
    result = get_binomial_hash().pca_surface(key, fields_json, n_components)
    return json.dumps(result, default=str)


@function_tool
async def bh_dependency_screen(
    key: str,
    target: str,
    candidates_json: str,
    controls_json: str = "[]",
    top_k: int = 8,
) -> str:
    """Rank candidate drivers using raw correlation, partial correlation, and coefficient strength."""
    result = get_binomial_hash().dependency_screen(key, target, candidates_json, controls_json, top_k)
    return json.dumps(result, default=str)


@function_tool
async def bh_solver(
    key: str,
    target_field: str,
    goal_json: str,
    controllable_vars_json: str,
    constraints_json: str = "[]",
    top_k: int = 5,
) -> str:
    """Goal-seek over stored rows to find feasible high-quality solutions under constraints."""
    result = get_binomial_hash().solver(key, target_field, goal_json, controllable_vars_json, constraints_json, top_k)
    return json.dumps(result, default=str)


@function_tool
async def bh_orbit(
    key: str,
    center_json: str,
    radius: int,
    target_field: Optional[str] = None,
    resolution: int = 16,
    mode: str = "ring",
) -> str:
    """Survey a neighborhood around a center point like a satellite pass."""
    result = get_binomial_hash().orbit(key, center_json, radius, target_field, resolution, mode)
    return json.dumps(result, default=str)


@function_tool
async def bh_multiscale_view(
    key: str,
    center_json: str,
    radii_json: str,
    target_field: Optional[str] = None,
    resolution: int = 16,
) -> str:
    """Inspect the same center at multiple neighborhood radii/scales."""
    result = get_binomial_hash().multiscale_view(key, center_json, radii_json, target_field, resolution)
    return json.dumps(result, default=str)


@function_tool
async def bh_frontier(
    key: str,
    condition_a_json: str,
    condition_b_json: str,
    target_field: Optional[str] = None,
    limit: int = 200,
) -> str:
    """Trace the structural frontier between two regimes or target zones."""
    result = get_binomial_hash().frontier(key, condition_a_json, condition_b_json, target_field, limit)
    return json.dumps(result, default=str)


@function_tool
async def bh_basin(key: str, seed_json: str, target_field: str, direction: str = "descend") -> str:
    """Find the basin of attraction of a local extremum around a seed point."""
    result = get_binomial_hash().basin(key, seed_json, target_field, direction)
    return json.dumps(result, default=str)


@function_tool
async def bh_ridge_trace(key: str, seed_json: str, target_field: str, max_steps: int = 25) -> str:
    """Trace a ridge / high-value structural corridor from a seed point."""
    result = get_binomial_hash().ridge_trace(key, seed_json, target_field, max_steps)
    return json.dumps(result, default=str)


@function_tool
async def bh_valley_trace(key: str, seed_json: str, target_field: str, max_steps: int = 25) -> str:
    """Trace a trough / low-value structural channel from a seed point."""
    result = get_binomial_hash().valley_trace(key, seed_json, target_field, max_steps)
    return json.dumps(result, default=str)


@function_tool
async def bh_coverage_audit(key: str) -> str:
    """Audit graph/face support quality, sparsity, occupancy, and manifold confidence."""
    result = get_binomial_hash().coverage_audit(key)
    return json.dumps(result, default=str)


@function_tool
async def bh_wrap_audit(key: str, axis: Optional[str] = None) -> str:
    """Explain boundary-wrap inference evidence and confidence for one axis or all axes."""
    result = get_binomial_hash().wrap_audit(key, axis)
    return json.dumps(result, default=str)


# ── Export list ──────────────────────────────────────────────────────────────

BINOMIAL_HASH_TOOLS = [
    bh_retrieve,
    bh_aggregate,
    bh_aggregate_batch,
    bh_query,
    bh_schema,
    bh_group_by,
    bh_to_excel,
    bh_manifold_state,
    bh_manifold_insights,
    bh_navigate,
    bh_manifold_slice,
    bh_geodesic,
    bh_walk_axis,
    bh_regress,
    bh_partial_corr,
    bh_pca_surface,
    bh_dependency_screen,
    bh_solver,
    bh_orbit,
    bh_multiscale_view,
    bh_frontier,
    bh_basin,
    bh_ridge_trace,
    bh_valley_trace,
    bh_coverage_audit,
    bh_wrap_audit,
]

BINOMIAL_HASH_CHAT_TOOLS = [
    bh_retrieve,
    bh_aggregate,
    bh_aggregate_batch,
    bh_query,
    bh_schema,
    bh_group_by,
    bh_manifold_state,
    bh_manifold_insights,
    bh_navigate,
    bh_manifold_slice,
    bh_geodesic,
    bh_walk_axis,
    bh_regress,
    bh_partial_corr,
    bh_pca_surface,
    bh_dependency_screen,
    bh_solver,
    bh_orbit,
    bh_multiscale_view,
    bh_frontier,
    bh_basin,
    bh_ridge_trace,
    bh_valley_trace,
    bh_coverage_audit,
    bh_wrap_audit,
]
