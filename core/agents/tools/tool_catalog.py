"""
Tool Catalog Generator for Canvas AI Agent.

Generates a compact, readable catalog of all Canvas tool workflows
for injection into the agent's system prompt. This allows the AI to:
1. Know what tools are available
2. Understand what each tool does
3. Know the key parameters for each tool

The catalog is generated dynamically from registry.yaml at startup,
ensuring it stays in sync with actual available tools.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _summarize_params(params_schema: Dict[str, Any], max_params: int = 6) -> str:
    """
    Summarize tool parameters into a compact string.
    
    Args:
        params_schema: The params_schema dict from registry.yaml
        max_params: Maximum number of params to show
    
    Returns:
        Compact param summary like "n_simulations(int,1000), time_horizon(int,252)"
    """
    if not params_schema:
        return ""
    
    # Skip common params that are handled automatically
    skip_params = {"portfolio_id", "tickers", "weights"}
    
    summaries = []
    for name, schema in params_schema.items():
        if name in skip_params:
            continue
        
        if len(summaries) >= max_params:
            summaries.append("...")
            break
        
        # Handle different schema formats
        if isinstance(schema, dict):
            param_type = schema.get("type", "any")
            default = schema.get("default")
            
            # Build compact representation
            if default is not None:
                if isinstance(default, str):
                    summaries.append(f"{name}={default}")
                elif isinstance(default, bool):
                    summaries.append(f"{name}={str(default).lower()}")
                elif isinstance(default, (int, float)):
                    summaries.append(f"{name}={default}")
                else:
                    summaries.append(f"{name}")
            elif schema.get("required"):
                summaries.append(f"{name}*")
            else:
                summaries.append(name)
        else:
            summaries.append(name)
    
    return ", ".join(summaries) if summaries else ""


def _format_catalog_compact(categories: Dict[str, List[Dict]]) -> str:
    """
    Format the catalog in a compact format for prompt injection.
    
    Uses minimal tokens while preserving essential information.
    """
    lines = []
    
    # Define category display order
    category_order = [
        "risk", "quant", "valuation", "structuring", "sentiment", "alternatives"
    ]
    
    # Sort categories by order, then alphabetically for any extras
    sorted_cats = []
    for cat in category_order:
        if cat in categories:
            sorted_cats.append(cat)
    for cat in sorted(categories.keys()):
        if cat not in sorted_cats:
            sorted_cats.append(cat)
    
    for cat in sorted_cats:
        tools = categories[cat]
        
        # Category header
        lines.append(f"\n## {cat.upper()} ({len(tools)} tools)")
        
        for tool in tools:
            tool_id = tool["id"]
            name = tool["name"]
            desc = tool["desc"]
            params = tool.get("params", "")
            
            # Format: tool_id: Name - description (params)
            line = f"- {tool_id}: {name}"
            if desc:
                # Truncate long descriptions
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                line += f" - {desc}"
            if params:
                line += f" [{params}]"
            
            lines.append(line)
    
    return "\n".join(lines)


def generate_tool_catalog(compact: bool = True, max_tools_per_category: int = 50) -> str:
    """
    Generate a catalog of all Canvas tools for agent prompt injection.
    
    Args:
        compact: If True, generate compact format. If False, include full details.
        max_tools_per_category: Maximum tools to include per category.
    
    Returns:
        Formatted string catalog of all tools.
    """
    try:
        from api.routers.canvas.tool_workflow.tools.loader import TOOL_REGISTRY
    except ImportError:
        logger.warning("Could not import TOOL_REGISTRY - tool catalog unavailable")
        return "Tool catalog unavailable. Ask user which tool to run."
    
    if not TOOL_REGISTRY:
        logger.warning("TOOL_REGISTRY is empty")
        return "No tools available."
    
    # Group tools by category
    categories: Dict[str, List[Dict]] = {}
    
    for tool_id, info in TOOL_REGISTRY.items():
        cat = info.get("category", "general")
        
        if cat not in categories:
            categories[cat] = []
        
        if len(categories[cat]) >= max_tools_per_category:
            continue
        
        # Extract key info
        params_summary = _summarize_params(info.get("params_schema", {}))
        
        categories[cat].append({
            "id": tool_id,
            "name": info.get("name", tool_id),
            "desc": info.get("description", "")[:100],
            "params": params_summary,
        })
    
    # Sort tools within each category by name
    for cat in categories:
        categories[cat] = sorted(categories[cat], key=lambda x: x["name"])
    
    if compact:
        return _format_catalog_compact(categories)
    else:
        return _format_catalog_full(categories)


def _format_catalog_full(categories: Dict[str, List[Dict]]) -> str:
    """
    Format the catalog with full details (for documentation/debugging).
    """
    lines = ["# Canvas Tool Catalog\n"]
    
    total_tools = sum(len(tools) for tools in categories.values())
    lines.append(f"Total tools: {total_tools}\n")
    
    for cat, tools in sorted(categories.items()):
        lines.append(f"\n## {cat.title()} ({len(tools)} tools)\n")
        
        for tool in tools:
            lines.append(f"### {tool['id']}")
            lines.append(f"**{tool['name']}**")
            lines.append(f"{tool['desc']}")
            if tool.get("params"):
                lines.append(f"Params: {tool['params']}")
            lines.append("")
    
    return "\n".join(lines)


def get_tool_guidance() -> str:
    """
    Generate tool selection guidance for the agent prompt.
    
    This helps the AI choose the right tool based on user intent.
    """
    return """
<tool-selection-guidance>
Choose tools based on what the user wants to analyze:

RISK ASSESSMENT:
- "VaR" or "risk metrics" → var
- "Monte Carlo" or "simulate" or "paths" → monte_carlo
- "stress test" or "correlation shock" → stress_test
- "drawdown" or "underwater" → drawdown
- "hedge" or "neutralize exposure" → hedge
- "factor exposure" or "Barra" → barra_factors
- "optimize portfolio" or "efficient frontier" → optimization

OPTIONS & VOLATILITY:
- "volatility surface" or "IV smile" → vol_surface
- "Greeks" or "delta/gamma/vega" → greeks_surface or gex
- "dealer positioning" or "gamma exposure" → gex or dealer_gamma
- "squeeze" → squeeze_detector
- "options pricing" → option_pricing

VALUATION:
- "DCF" or "intrinsic value" → dcf_traditional or dcf_monte_carlo
- "implied growth" or "reverse DCF" → reverse_dcf
- "comparables" or "peer multiples" → comps
- "EPV" or "earnings power" → epv
- "residual income" (banks) → rim

FORECASTING:
- "forecast" or "predict price" → arima_forecast
- "macro forecast" or "with indicators" → arimax

CORRELATION & PAIRS:
- "correlation matrix" → correlation_matrix
- "cointegration" or "pairs trading" → cointegration
- "PCA" or "principal components" → pca_analysis
- "rolling correlation" → rolling_corr

STRUCTURING:
- "variance swap" → var_swap
- "dispersion trade" → dispersion
- "exotic options" → exotic_pricing
- "interest rate swap" → irs
- "CDS" or "credit spread" → cds

ALTERNATIVES:
- "commodity" → commodity_ratio, commodity_momentum, or commodity_seasonal
- "crypto" → crypto_beta
- "FX carry" → fx_carry
</tool-selection-guidance>
"""


def get_full_prompt_injection() -> str:
    """
    Get the complete tool catalog and guidance for prompt injection.
    
    This is the main function to call when building the agent prompt.
    """
    catalog = generate_tool_catalog(compact=True)
    guidance = get_tool_guidance()
    
    # Use string concatenation instead of f-string to avoid
    # issues with curly braces in catalog content being parsed as format specifiers
    return (
        "\n<available-tool-workflows>\n"
        "Use start_tool_analysis(tool_id, tickers, weights, params) to run any analysis below.\n\n"
        + catalog
        + "\n</available-tool-workflows>\n\n"
        + guidance
    )
