"""
JSON Tensor Topography — Maps nested JSON to navigable surfaces and structure trees.

Two visualizations:
1. STRUCTURE TREE: The dimensional topology of the JSON — what contains what,
   where the arrays (dimensions) are, how they nest. This is the "map."

2. TENSOR SURFACES: The actual data mapped to 3D surfaces. Each nesting dimension
   becomes a spatial axis. Values become elevation. You see the landscape of the
   data — where peaks are, where it's flat, where dimensions interact.

   For a nested JSON like results[3].chain[5]:
     X = primary dimension index (which result: AAPL, MSFT, GOOGL)
     Y = secondary dimension index (which chain item: strike 0, 1, 2...)
     Z = value (bid, volume, delta — one surface per field)

   The surface IS the data. The topology shows you how values change across
   both dimensions simultaneously. An agent navigating this knows: "bid prices
   form a declining surface from low strikes to high strikes, steeper for AAPL
   than GOOGL."

Run: python benchmarks/json_tensor_map.py
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


SAMPLE_JSON = {
    "status": "OK",
    "request_id": "req_abc123",
    "results_count": 3,
    "results": [
        {
            "ticker": "AAPL",
            "price": 195.20,
            "greeks": {"delta": 0.71, "gamma": 0.023, "theta": -0.056, "vega": 0.189},
            "chain": [
                {"strike": 190, "bid": 12.3, "ask": 12.6, "volume": 3847},
                {"strike": 195, "bid": 7.8,  "ask": 8.1,  "volume": 5210},
                {"strike": 200, "bid": 4.2,  "ask": 4.5,  "volume": 8930},
                {"strike": 205, "bid": 1.9,  "ask": 2.2,  "volume": 2100},
                {"strike": 210, "bid": 0.5,  "ask": 0.8,  "volume": 780},
            ],
        },
        {
            "ticker": "MSFT",
            "price": 420.50,
            "greeks": {"delta": 0.65, "gamma": 0.019, "theta": -0.042, "vega": 0.165},
            "chain": [
                {"strike": 410, "bid": 18.0, "ask": 18.3, "volume": 2910},
                {"strike": 415, "bid": 12.5, "ask": 12.8, "volume": 4100},
                {"strike": 420, "bid": 9.5,  "ask": 9.8,  "volume": 6420},
                {"strike": 425, "bid": 5.2,  "ask": 5.5,  "volume": 3850},
                {"strike": 430, "bid": 3.1,  "ask": 3.4,  "volume": 4150},
            ],
        },
        {
            "ticker": "GOOGL",
            "price": 178.30,
            "greeks": {"delta": 0.58, "gamma": 0.031, "theta": -0.038, "vega": 0.201},
            "chain": [
                {"strike": 170, "bid": 14.1, "ask": 14.4, "volume": 1870},
                {"strike": 175, "bid": 8.9,  "ask": 9.2,  "volume": 3340},
                {"strike": 180, "bid": 4.5,  "ask": 4.8,  "volume": 5920},
                {"strike": 185, "bid": 1.8,  "ask": 2.1,  "volume": 1560},
                {"strike": 190, "bid": 0.4,  "ask": 0.7,  "volume": 890},
            ],
        },
    ],
}


# ── 1. STRUCTURE TREE — Dimensional topology ─────────────────────────────────

def walk_structure(data: Any, key: str = "root", depth: int = 0) -> Dict:
    """Build a structure tree from JSON. Each node knows its type, children, and dimension info."""
    node = {"key": key, "depth": depth, "children": []}

    if isinstance(data, dict):
        node["type"] = "object"
        node["n_fields"] = len(data)
        for k, v in data.items():
            node["children"].append(walk_structure(v, k, depth + 1))

    elif isinstance(data, list):
        node["type"] = "array"
        node["length"] = len(data)
        if data and isinstance(data[0], dict):
            node["element_type"] = "object"
            node["element_keys"] = list(data[0].keys())
            merged = {}
            for item in data:
                for k, v in item.items():
                    if k not in merged:
                        merged[k] = v
            for k, v in merged.items():
                node["children"].append(walk_structure(v, k, depth + 1))
        elif data:
            node["element_type"] = type(data[0]).__name__
    else:
        node["type"] = "scalar"
        node["value_type"] = type(data).__name__ if data is not None else "null"
        node["sample"] = str(data)[:40]

    return node


def structure_to_sankey(tree: Dict) -> go.Figure:
    """Convert structure tree to a Sankey diagram showing data flow and nesting."""
    labels, colors, sources, targets, values, link_colors = [], [], [], [], [], []
    node_x, node_y = [], []

    depth_counts: Dict[int, int] = {}

    def add_node(node: Dict, parent_idx: Optional[int] = None):
        idx = len(labels)

        d = node["depth"]
        depth_counts[d] = depth_counts.get(d, 0) + 1
        pos_in_level = depth_counts[d]

        max_depth = 6
        x = min(d / max_depth, 0.95) + 0.02
        y = pos_in_level / (depth_counts.get(d, 1) + 5)

        node_x.append(x)
        node_y.append(y)

        if node["type"] == "array":
            label = f"{node['key']}[]\n({node['length']} items)"
            color = "rgba(106, 27, 154, 0.8)"
            size = node["length"] * 2
        elif node["type"] == "object":
            n = node.get("n_fields", 0)
            label = f"{node['key']}\n({n} fields)"
            color = "rgba(31, 78, 121, 0.8)"
            size = max(n, 1)
        else:
            vt = node.get("value_type", "?")
            sample = node.get("sample", "")[:20]
            label = f"{node['key']}\n{vt}: {sample}"
            color_map = {
                "int": "rgba(33, 150, 243, 0.8)",
                "float": "rgba(33, 150, 243, 0.8)",
                "str": "rgba(76, 175, 80, 0.8)",
                "bool": "rgba(156, 39, 176, 0.8)",
                "NoneType": "rgba(158, 158, 158, 0.8)",
            }
            color = color_map.get(vt, "rgba(121, 85, 72, 0.8)")
            size = 1

        labels.append(label)
        colors.append(color)

        if parent_idx is not None:
            sources.append(parent_idx)
            targets.append(idx)
            values.append(max(size, 1))
            if node["type"] == "array":
                link_colors.append("rgba(106, 27, 154, 0.15)")
            elif node["type"] == "object":
                link_colors.append("rgba(31, 78, 121, 0.1)")
            else:
                link_colors.append("rgba(200, 200, 200, 0.1)")

        for child in node.get("children", []):
            add_node(child, idx)

    add_node(tree)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=25,
            label=labels,
            color=colors,
            x=node_x,
            y=node_y,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
        ),
    ))

    fig.update_layout(
        title=dict(
            text="JSON Structure Tree — Dimensional Topology<br>"
                 "<sub>Purple = array (dimension) | Blue = object (namespace) | "
                 "Green = string | Blue dots = numeric</sub>",
            font=dict(size=16),
        ),
        font=dict(size=11),
        width=1400,
        height=700,
    )
    return fig


# ── 2. TENSOR SURFACES — Data mapped to 3D landscapes ────────────────────────

def extract_tensor_grid(data: Dict) -> Dict[str, Any]:
    """
    Extract the 2D tensor grid from nested JSON.

    For results[i].chain[j], builds matrices where:
      X axis = primary dimension (i = which ticker)
      Y axis = secondary dimension (j = which chain item)
      Z axis = field value

    Returns grid info for each numeric field in the nested array.
    """
    results = data.get("results", [])
    if not results:
        return {}

    primary_labels = []
    primary_scalars: Dict[str, List] = {}
    nested_grids: Dict[str, List[List[Optional[float]]]] = {}
    nested_y_labels: List[List[str]] = []

    max_chain = max(len(r.get("chain", [])) for r in results)

    for i, result in enumerate(results):
        label = result.get("ticker", f"result_{i}")
        primary_labels.append(label)

        for k, v in result.items():
            if isinstance(v, (int, float)):
                primary_scalars.setdefault(k, []).append(v)
            elif isinstance(v, dict):
                for sk, sv in v.items():
                    if isinstance(sv, (int, float)):
                        col = f"{k}.{sv}" if k == "greeks" else f"{k}.{sk}"
                        col = f"{k}.{sk}"
                        primary_scalars.setdefault(col, []).append(sv)

        chain = result.get("chain", [])
        y_labels = []
        for j, item in enumerate(chain):
            strike = item.get("strike", j)
            y_labels.append(str(strike))
            for field_name, val in item.items():
                if isinstance(val, (int, float)):
                    if field_name not in nested_grids:
                        nested_grids[field_name] = [
                            [None] * max_chain for _ in range(len(results))
                        ]
                    nested_grids[field_name][i][j] = float(val)
        nested_y_labels.append(y_labels)

    all_y = []
    for j in range(max_chain):
        labels_at_j = [nested_y_labels[i][j] for i in range(len(results))
                       if j < len(nested_y_labels[i])]
        all_y.append(labels_at_j[0] if labels_at_j else str(j))

    return {
        "primary_labels": primary_labels,
        "primary_scalars": primary_scalars,
        "nested_grids": nested_grids,
        "nested_y_labels": all_y,
        "shape": (len(results), max_chain),
    }


def build_surface_figures(tensor: Dict) -> go.Figure:
    """Build 3D surface plots for each numeric field in the nested dimension."""
    grids = tensor["nested_grids"]
    x_labels = tensor["primary_labels"]
    y_labels = tensor["nested_y_labels"]
    shape = tensor["shape"]

    numeric_fields = [f for f in grids if f != "strike"]
    n_fields = len(numeric_fields)

    fig = make_subplots(
        rows=1, cols=n_fields,
        subplot_titles=[f.upper() for f in numeric_fields],
        specs=[[{"type": "surface"} for _ in range(n_fields)]],
        horizontal_spacing=0.02,
    )

    colorscales = ["Viridis", "Plasma", "Inferno"]

    for idx, field_name in enumerate(numeric_fields):
        grid = grids[field_name]
        z = np.array(grid, dtype=float)

        z_filled = np.copy(z)
        for i in range(z_filled.shape[0]):
            for j in range(z_filled.shape[1]):
                if np.isnan(z_filled[i, j]):
                    z_filled[i, j] = 0

        x = np.arange(shape[0])
        y = np.arange(shape[1])
        Y, X = np.meshgrid(y, x)

        hover_text = []
        for i in range(shape[0]):
            row = []
            for j in range(shape[1]):
                val = z_filled[i, j]
                yl = y_labels[j] if j < len(y_labels) else str(j)
                row.append(
                    f"Ticker: {x_labels[i]}<br>"
                    f"Strike: {yl}<br>"
                    f"{field_name}: {val:.2f}<br>"
                    f"Coord: D0[{i}].chain[{j}].{field_name}"
                )
            hover_text.append(row)

        fig.add_trace(
            go.Surface(
                x=X, y=Y, z=z_filled,
                colorscale=colorscales[idx % len(colorscales)],
                name=field_name,
                hovertext=hover_text,
                hoverinfo="text",
                showscale=True,
                colorbar=dict(
                    title=dict(text=field_name, side="right"),
                    len=0.8,
                    x=0.32 * (idx + 1) + 0.01,
                ),
                opacity=0.92,
                contours=dict(
                    x=dict(show=True, color="rgba(0,0,0,0.1)", width=1),
                    y=dict(show=True, color="rgba(0,0,0,0.1)", width=1),
                    z=dict(show=True, highlight=True, highlightcolor="white", highlightwidth=2),
                ),
            ),
            row=1, col=idx + 1,
        )

        scene_key = f"scene{idx + 1}" if idx > 0 else "scene"
        fig.update_layout(**{
            scene_key: dict(
                xaxis=dict(
                    title="D₀: Ticker",
                    tickvals=list(range(len(x_labels))),
                    ticktext=x_labels,
                ),
                yaxis=dict(
                    title="D₁: Strike",
                    tickvals=list(range(len(y_labels))),
                    ticktext=y_labels,
                ),
                zaxis=dict(title=field_name.upper()),
                camera=dict(eye=dict(x=1.6, y=-1.6, z=1.0)),
            ),
        })

    fig.update_layout(
        title=dict(
            text="JSON Tensor Topography — Data Surfaces<br>"
                 "<sub>X = Primary Dimension (D₀: results[i]) | "
                 "Y = Nested Dimension (D₁: chain[j]) | "
                 "Z = Value | Each surface is one field</sub>",
            font=dict(size=16),
        ),
        width=500 * n_fields,
        height=650,
    )
    return fig


# ── 3. COMBINED: Primary dimension bar landscape ─────────────────────────────

def build_primary_landscape(tensor: Dict) -> go.Figure:
    """Visualize the primary dimension scalars as a grouped landscape."""
    scalars = tensor["primary_scalars"]
    labels = tensor["primary_labels"]

    greeks = {k: v for k, v in scalars.items() if k.startswith("greeks.")}

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["D₀ Scalar Fields (per ticker)", "D₀ Greeks Sub-Object (per ticker)"],
        specs=[[{"type": "bar"}, {"type": "bar"}]],
    )

    top_scalars = {k: v for k, v in scalars.items()
                   if not k.startswith("greeks.") and k != "market_cap"}

    for field_name, values in top_scalars.items():
        fig.add_trace(
            go.Bar(name=field_name, x=labels, y=values, text=[f"{v:.1f}" for v in values],
                   textposition="auto"),
            row=1, col=1,
        )

    for field_name, values in greeks.items():
        short = field_name.replace("greeks.", "")
        fig.add_trace(
            go.Bar(name=short, x=labels, y=values, text=[f"{v:.3f}" for v in values],
                   textposition="auto"),
            row=1, col=2,
        )

    fig.update_layout(
        title=dict(
            text="Primary Dimension (D₀) Landscape — Scalars & Sub-Objects<br>"
                 "<sub>Each group = one element of D₀ (results[i]) | "
                 "Left = top-level scalars | Right = greeks sub-object</sub>",
            font=dict(size=14),
        ),
        barmode="group",
        width=1200,
        height=500,
    )
    return fig


# ── 4. CONTOUR MAP — The actual topography ────────────────────────────────────

def build_contour_topography(tensor: Dict) -> go.Figure:
    """
    2D contour map — the classic topographic view.

    X = primary dimension (ticker index)
    Y = nested dimension (chain item index)
    Z = bid price (or any field)

    Contour lines show elevation. This is literally a topographic map of the
    JSON data tensor — you can read it like a hiking map.
    """
    grids = tensor["nested_grids"]
    x_labels = tensor["primary_labels"]
    y_labels = tensor["nested_y_labels"]
    shape = tensor["shape"]

    fields = ["bid", "volume"]
    available = [f for f in fields if f in grids]

    fig = make_subplots(
        rows=1, cols=len(available),
        subplot_titles=[f"{f.upper()} — Topographic Contour" for f in available],
    )

    for idx, field_name in enumerate(available):
        z = np.array(grids[field_name], dtype=float)
        z_filled = np.nan_to_num(z, nan=0.0)

        from scipy.ndimage import zoom
        z_smooth = zoom(z_filled, 5, order=3)
        x_smooth = np.linspace(0, shape[0] - 1, z_smooth.shape[0])
        y_smooth = np.linspace(0, shape[1] - 1, z_smooth.shape[1])

        fig.add_trace(
            go.Contour(
                z=z_smooth.T,
                x=x_smooth,
                y=y_smooth,
                colorscale="Earth" if field_name == "bid" else "Hot",
                contours=dict(
                    showlabels=True,
                    labelfont=dict(size=10, color="white"),
                ),
                colorbar=dict(
                    title=field_name,
                    x=0.48 * (idx + 1),
                ),
                name=field_name,
                hovertemplate=(
                    f"Ticker idx: %{{x:.1f}}<br>"
                    f"Strike idx: %{{y:.1f}}<br>"
                    f"{field_name}: %{{z:.1f}}<extra></extra>"
                ),
            ),
            row=1, col=idx + 1,
        )

        scene = f"xaxis{idx + 1}" if idx > 0 else "xaxis"
        scene_y = f"yaxis{idx + 1}" if idx > 0 else "yaxis"
        fig.update_layout(**{
            scene: dict(
                title="D₀: Ticker",
                tickvals=list(range(len(x_labels))),
                ticktext=x_labels,
            ),
            scene_y: dict(
                title="D₁: Strike",
                tickvals=list(range(len(y_labels))),
                ticktext=y_labels,
            ),
        })

    fig.update_layout(
        title=dict(
            text="JSON Tensor Topographic Map<br>"
                 "<sub>Contour lines = equal value elevation | "
                 "Read like a terrain map: peaks, valleys, ridges across both dimensions</sub>",
            font=dict(size=16),
        ),
        width=1200,
        height=550,
    )
    return fig


# ── Structure summary for console ─────────────────────────────────────────────

def print_tensor_analysis(data: Dict, tensor: Dict):
    print("\n" + "=" * 72)
    print("  BINOMIAL HASH — JSON TENSOR TOPOGRAPHY ANALYSIS")
    print("=" * 72)

    tree = walk_structure(data)

    def count_dims(node, depth=0):
        dims = []
        if node["type"] == "array":
            dims.append({
                "key": node["key"],
                "depth": depth,
                "length": node["length"],
                "fields": node.get("element_keys", []),
            })
        for child in node.get("children", []):
            dims.extend(count_dims(child, depth + 1))
        return dims

    dims = count_dims(tree)
    shape = tensor["shape"]

    print(f"\n  Tensor shape: {shape[0]} × {shape[1]}  (D₀ × D₁)")
    print(f"  Total cells:  {shape[0] * shape[1]}")
    print(f"  Dimensions:   {len(dims)}")

    print("\n  ── Dimensions ──")
    for i, d in enumerate(dims):
        print(f"    D{i}: {d['key']}[]  length={d['length']}  depth={d['depth']}")
        if d["fields"]:
            print(f"        fields: {d['fields']}")

    print("\n  ── Tensor Grid Values (bid) ──")
    x_labels = tensor["primary_labels"]
    y_labels = tensor["nested_y_labels"]
    bid_grid = tensor["nested_grids"].get("bid", [])

    header = "            " + "  ".join(f"{y:>8s}" for y in y_labels)
    print(f"    {'':12s} {'D₁ →':>8s}")
    print(f"    {header}")
    print(f"    {'D₀ ↓':12s}" + "  ".join(["--------"] * len(y_labels)))
    for i, label in enumerate(x_labels):
        row_vals = bid_grid[i] if i < len(bid_grid) else []
        cells = []
        for j in range(len(y_labels)):
            v = row_vals[j] if j < len(row_vals) and row_vals[j] is not None else None
            cells.append(f"{v:8.2f}" if v is not None else "       -")
        print(f"    {label:12s}" + "  ".join(cells))

    print(f"\n  ── This IS the tensor ──")
    print(f"    The grid above is T[D₀, D₁, 'bid']")
    print(f"    Each cell is addressed by coordinate (i, j)")
    print(f"    Agent navigates: bh_slice(dim='D₁', where_parent='ticker=AAPL')")
    print(f"                   → returns row 0: [{', '.join(str(v) for v in bid_grid[0] if v)}]")

    print("\n" + "=" * 72)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Analyzing JSON tensor structure...")

    tensor = extract_tensor_grid(SAMPLE_JSON)
    print_tensor_analysis(SAMPLE_JSON, tensor)

    tree = walk_structure(SAMPLE_JSON)

    print("\nBuilding visualizations...")

    fig_tree = structure_to_sankey(tree)
    fig_surfaces = build_surface_figures(tensor)
    fig_landscape = build_primary_landscape(tensor)
    fig_contour = build_contour_topography(tensor)

    from plotly.io import to_html

    html_parts = [
        "<html><head><title>BinomialHash — JSON Tensor Topography</title></head><body>",
        "<h1 style='font-family:sans-serif; text-align:center'>BinomialHash — JSON Tensor Topography</h1>",
        "<h3 style='font-family:sans-serif; text-align:center; color:#666'>"
        "Nested JSON mapped to navigable multidimensional surfaces</h3>",
        "<hr>",
        "<h2 style='font-family:sans-serif'>1. Structure Tree — Dimensional Topology</h2>",
        "<p style='font-family:sans-serif; color:#555'>Purple nodes = arrays (dimensions). "
        "Blue = objects (namespaces). Width = data volume flowing through that path.</p>",
        to_html(fig_tree, full_html=False, include_plotlyjs="cdn"),
        "<hr>",
        "<h2 style='font-family:sans-serif'>2. Primary Dimension Landscape (D₀)</h2>",
        "<p style='font-family:sans-serif; color:#555'>Each group is one element of the "
        "primary array. Left = scalar fields. Right = the greeks sub-object flattened.</p>",
        to_html(fig_landscape, full_html=False, include_plotlyjs=False),
        "<hr>",
        "<h2 style='font-family:sans-serif'>3. Tensor Surfaces (D₀ × D₁)</h2>",
        "<p style='font-family:sans-serif; color:#555'>X = primary dimension (which ticker), "
        "Y = nested dimension (which strike). Z = value. <b>The surface IS the data.</b> "
        "Peaks, valleys, and ridges show how values change across both dimensions. "
        "Rotate to explore.</p>",
        to_html(fig_surfaces, full_html=False, include_plotlyjs=False),
        "<hr>",
        "<h2 style='font-family:sans-serif'>4. Topographic Contour Map (D₀ × D₁)</h2>",
        "<p style='font-family:sans-serif; color:#555'>Classic topographic view. "
        "Contour lines = equal value elevation. Read like a terrain map: "
        "peaks are high-value regions, valleys are low. The agent navigates this surface.</p>",
        to_html(fig_contour, full_html=False, include_plotlyjs=False),
        "<hr>",
        "<div style='font-family:monospace; background:#f5f5f5; padding:20px; margin:20px'>",
        "<h3>Agent Navigation Commands</h3>",
        "<pre>",
        "bh_map(key)                                    → returns the structure tree\n",
        "bh_slice(key, dim='D0')                        → 3 rows: AAPL, MSFT, GOOGL (flat scalars)\n",
        "bh_slice(key, dim='D0', expand='greeks')       → 3 rows with greeks inlined\n",
        "bh_slice(key, dim='D1')                        → 12 chain items (all tickers combined)\n",
        "bh_slice(key, dim='D1', where_parent='ticker=AAPL')  → 5 chain items for AAPL\n",
        "bh_cross(key, dim1='D0', dim2='D1')            → 15 rows: ticker × chain (full join)\n",
        "bh_aggregate(key, dim='D1', col='bid', func='mean')  → mean bid across all chains\n",
        "</pre>",
        "</div>",
        "</body></html>",
    ]

    output = "benchmarks/json_tensor_topography.html"
    with open(output, "w") as f:
        f.write("\n".join(html_parts))

    print(f"\nSaved to {output}")
    print("Open in browser to explore the 3D surfaces.")
