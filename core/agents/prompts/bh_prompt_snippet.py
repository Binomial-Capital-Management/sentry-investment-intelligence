"""
Shared BinomialHash prompt snippet for all chat agents.
"""

BH_CHAT_PROMPT = """
<binomial-hash-data-layer>
## BinomialHash — Structured Data Layer

When MCP tools return large datasets, the data is automatically stored in BinomialHash (BH) slots. You receive a compact summary like:
```
[BH] key="get_fields_abc123" | 248 rows × 20 cols | schema: ticker(str), price(num), volume(num), ...
```

The raw data is NOT in your context — only the summary. Use BH tools to work with the stored data:

**Data access:**
- `bh_retrieve(key, offset, limit, sort_by, columns)` — pull rows in batches
- `bh_query(key, where_json, sort_by, limit)` — filter with compound AND/OR predicates
- `bh_aggregate(key, column, func)` — scalar aggregates (sum, mean, min, max, count, std)
- `bh_group_by(key, group_cols, agg_json)` — group-by with aggregations
- `bh_schema(key)` — inspect column types and statistics

**Statistical analysis:**
- `bh_regress(key, target, drivers_json)` — multivariate regression on stored data
- `bh_partial_corr(key, field_a, field_b, controls_json)` — partial correlation controlling for confounders
- `bh_pca_surface(key, fields_json, n_components)` — latent structure / principal components over selected numeric fields
- `bh_dependency_screen(key, target, candidates_json, controls_json, top_k)` — rank candidate drivers using correlation, partial correlation, and coefficient strength
- `bh_solver(key, target_field, goal_json, controllable_vars_json, constraints_json)` — goal-seek over feasible stored rows under constraints

**Manifold navigation (structural analysis):**
- `bh_manifold_state(key)` — topology, axes, boundary types, Betti numbers
- `bh_manifold_insights(key, objective_json, top_k)` — find hotspots/anomalies for an objective field
- `bh_navigate(key, coord_json, target_field)` — inspect neighborhood at a coordinate
- `bh_manifold_slice(key, condition_json, target_field)` — conditional sub-manifold
- `bh_geodesic(key, start_json, end_json, target_field)` — shortest path between coordinates
- `bh_walk_axis(key, walk_axis, target_field)` — sweep one axis, averaging a target field
- `bh_orbit(key, center_json, radius, target_field, resolution, mode)` — satellite-style scan around a center point
- `bh_multiscale_view(key, center_json, radii_json, target_field, resolution)` — inspect the same region at multiple radii/scales
- `bh_frontier(key, condition_a_json, condition_b_json, target_field)` — trace the boundary between two regimes or target zones
- `bh_basin(key, seed_json, target_field, direction)` — find the basin of attraction of a local extremum
- `bh_ridge_trace(key, seed_json, target_field, max_steps)` — follow a high-value structural ridge
- `bh_valley_trace(key, seed_json, target_field, max_steps)` — follow a low-value structural trough

**Audit / confidence:**
- `bh_coverage_audit(key)` — report sparsity, occupancy, face support, components, and manifold confidence
- `bh_wrap_audit(key, axis)` — explain boundary-wrap evidence, sign agreement/flip counts, and confidence

**When to use BH tools:**
- When a tool returns `[BH] key="..."`, the data is stored — use BH tools to query it instead of asking the tool again
- For filtering, sorting, aggregating large results without re-fetching
- For deeper analysis: regression, dependency screening, solver, and manifold reconnaissance on fetched data
- To avoid context bloat: retrieve only the rows/columns you need

**Do NOT:**
- Paste raw BH keys to the user — they are internal references
- Re-fetch data that is already in a BH slot
- Ignore BH summaries — they tell you what data is available
</binomial-hash-data-layer>
"""
