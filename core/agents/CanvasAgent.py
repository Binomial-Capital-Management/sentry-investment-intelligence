"""
Canvas AI Agent - Process Analysis and Re-run via Natural Language
Status: Production
Created: December 2024

PURPOSE: Standalone agent for Canvas process analysis and modification.
         Explains analysis results, performs calculations, and re-runs tools.
         Runs OUTSIDE LangGraph orchestrator - direct Runner execution.
"""

from agents import Agent, ModelSettings, CodeInterpreterTool, function_tool
from openai.types.shared import Reasoning
from typing import Any, Optional, Dict, List
import logging

from core.agents.tools.workspace_tools import set_workspace_context
from core.agents.tools.registry import get_tools_for_context, ToolContext
from core.agents.tools.data_discovery import load_endpoint_index
from core.agents.tools.tool_catalog import get_full_prompt_injection

logger = logging.getLogger(__name__)


def create_canvas_agent(
    process_context: Optional[Dict[str, Any]] = None,
    data_context: Optional[Dict[str, Any]] = None,
    model: str = None,
    user_id: str = None,
    org_id: str = None,
    market_server: Any = None,
    economic_server: Any = None,
    alternatives_server: Any = None,
) -> Agent:
    """
    Factory function to create the Canvas Agent for process analysis.

    Args:
        process_context: Current Canvas process data (tickers, metrics, stats, params)
        data_context: Data workspace context (datasets, symbols) when no process
        model: Optional model override (defaults to config.agent_model)
        user_id: User ID for tool execution (required for re-runs)
        org_id: Organization ID for tool execution
        market_server: FMPMarketDataServer for market data context (optional)
        economic_server: EconomicDataServer for macro data context (optional)
        alternatives_server: FMPAlternativesServer for ETF/fund data (optional)

    Returns:
        Configured Agent instance for Canvas analysis
    """
    from datetime import datetime

    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Load endpoint index for data discovery
    try:
        # Only load endpoint index for data workspace context
        if data_context or not process_context:
            endpoint_index = load_endpoint_index(object_type="equity", max_endpoints=80)
        else:
            endpoint_index = "Use MCP servers for data queries in process context."
    except Exception as e:
        logger.warning(f"Failed to load endpoint index: {e}")
        endpoint_index = "Endpoint catalog unavailable. Use discovery tools to explore."
    
    # Load tool workflow catalog for workspace context (allows AI to launch analyses)
    tool_workflow_catalog = ""
    if data_context or not process_context:
        try:
            tool_workflow_catalog = get_full_prompt_injection()
            logger.info(f"[CANVAS] Loaded tool workflow catalog ({len(tool_workflow_catalog)} chars)")
        except Exception as e:
            logger.warning(f"Failed to load tool workflow catalog: {e}")
            tool_workflow_catalog = ""

    # Build context section from process data
    context_section = ""
    if process_context:
        ctx_parts = []

        if process_context.get("name"):
            ctx_parts.append(f"Process Name: {process_context['name']}")
        if process_context.get("id"):
            ctx_parts.append(f"Process ID: {process_context['id']}")
        if process_context.get("tool_id"):
            ctx_parts.append(f"Analysis Type: {process_context['tool_id']}")
        if process_context.get("tickers"):
            ctx_parts.append(f"Tickers: {', '.join(process_context['tickers'])}")
        if process_context.get("weights"):
            tickers = process_context.get('tickers', [])
            weights = process_context['weights']
            weight_strs = [f"{t}: {w:.1%}" for t, w in zip(tickers, weights)]
            ctx_parts.append(f"Weights: {', '.join(weight_strs)}")

        # Add key metrics
        if process_context.get("metric_cards"):
            metrics = process_context['metric_cards'][:15]
            metrics_lines = [f"  - {m['label']}: {m['value']}" for m in metrics]
            ctx_parts.append("Key Metrics:\n" + "\n".join(metrics_lines))

        # Add stats table summary
        if process_context.get("stats_table"):
            stats = process_context['stats_table'][:25]
            stats_lines = [f"  - {s['metric']}: {s['value']}" for s in stats]
            ctx_parts.append("Statistics:\n" + "\n".join(stats_lines))

        # Add parameters used
        if process_context.get("params"):
            params_items = list(process_context['params'].items())[:15]
            params_str = ", ".join([f"{k}={v}" for k, v in params_items])
            ctx_parts.append(f"Parameters Used: {params_str}")

        # HMM regime info
        if process_context.get("hmm_enabled"):
            ctx_parts.append("HMM Regime Detection: Enabled")
            if process_context.get("current_regime"):
                ctx_parts.append(f"Current Regime: {process_context['current_regime']}")

        if ctx_parts:
            context_section = (
                "\n\n<current-process-context>\n"
                + "\n".join(ctx_parts)
                + "\n</current-process-context>"
            )

    # Build workspace context (additive — can coexist with process context)
    if data_context:
        ctx_parts = []

        if data_context.get("description"):
            ctx_parts.append(f"Context: {data_context['description']}")

        if data_context.get("symbols"):
            ctx_parts.append(f"Symbols: {', '.join(data_context['symbols'])}")

        if data_context.get("datasets"):
            datasets = data_context['datasets']
            ctx_parts.append("Datasets in workspace:")
            for ds in datasets[:5]:
                ds_id = ds.get('id', 'unknown')
                group_tag = f" (group: {ds['groupId']})" if ds.get('groupId') else ""
                ds_info = f"  - [{ds_id}] {ds.get('symbol', 'Unknown')}: {ds.get('endpoint', 'unknown endpoint')}{group_tag}"
                if ds.get('fields'):
                    ds_info += f" (fields: {', '.join(ds['fields'][:10])})"
                if ds.get('rowCount'):
                    ds_info += f" [{ds['rowCount']} rows]"
                ctx_parts.append(ds_info)
            if len(datasets) > 5:
                ctx_parts.append(f"  ... and {len(datasets) - 5} more")

        if data_context.get("datasetGroups"):
            groups = data_context["datasetGroups"]
            ctx_parts.append("Dataset groups (merged tables):")
            active_gid = data_context.get("activeGroupId")
            for g in groups[:10]:
                marker = " [ACTIVE]" if g.get("id") == active_gid else ""
                ctx_parts.append(f"  - [{g.get('id', '?')}] {g.get('name', 'Unnamed')}: {g.get('datasetCount', 0)} dataset(s){marker}")

        if data_context.get("charts"):
            charts = data_context['charts']
            ctx_parts.append("Charts in workspace:")
            for chart in charts[:10]:
                chart_id = chart.get('id', 'unknown')
                chart_name = chart.get('name', 'Untitled')
                chart_type = chart.get('chartType', 'unknown')
                ctx_parts.append(f"  - [{chart_id}] {chart_type} chart: {chart_name}")
            if len(charts) > 10:
                ctx_parts.append(f"  ... and {len(charts) - 10} more")

        if data_context.get("pivots"):
            pivots = data_context['pivots']
            ctx_parts.append("Pivot tables in workspace:")
            for pivot in pivots[:10]:
                pivot_id = pivot.get('id', 'unknown')
                pivot_name = pivot.get('name', 'Untitled')
                parts = []
                if pivot.get('rows'):
                    parts.append(f"rows: {', '.join(pivot['rows'][:3])}")
                if pivot.get('columns'):
                    parts.append(f"cols: {', '.join(pivot['columns'][:3])}")
                if pivot.get('values'):
                    val_strs = [f"{v['field']}({v['aggregation']})" for v in pivot['values'][:3]]
                    parts.append(f"values: {', '.join(val_strs)}")
                config_str = f" ({'; '.join(parts)})" if parts else ""
                group_tag = f" [group: {pivot['groupId']}]" if pivot.get('groupId') else ""
                ctx_parts.append(f"  - [{pivot_id}] {pivot_name}{config_str}{group_tag}")
            if len(pivots) > 10:
                ctx_parts.append(f"  ... and {len(pivots) - 10} more")

        # Tool tab summaries — shows tool analyses alongside data
        if data_context.get("tools"):
            tools = data_context["tools"]
            ctx_parts.append("Tool analyses in workspace:")
            for tool in tools[:5]:
                tab_name = tool.get("tabName", "Untitled")
                tool_id = tool.get("toolId", "unknown")
                tickers = ", ".join(tool.get("tickers", [])[:5])
                status = "completed" if tool.get("hasResults") else f"step {tool.get('step', 1)}/4"
                process_id = tool.get("processId", "unsaved")
                ctx_parts.append(f"  - [{tool.get('tabId')}] {tab_name}: {tool_id} ({tickers}) [{status}] (process: {process_id})")
                if tool.get("metricCards"):
                    for mc in tool["metricCards"][:3]:
                        ctx_parts.append(f"    {mc.get('label')}: {mc.get('value')}")
            if len(tools) > 5:
                ctx_parts.append(f"  ... and {len(tools) - 5} more")

        view_parts = []
        if data_context.get("sidebarViewMode"):
            view_parts.append(f"sidebar: {data_context['sidebarViewMode']}")
        if data_context.get("contentView"):
            cv = data_context["contentView"]
            cv_type = cv.get("type", "data")
            if cv_type == "pivot" and cv.get("pivotLocalId"):
                view_parts.append(f"content: pivot [{cv['pivotLocalId']}]")
            elif cv_type == "chart" and cv.get("chartLocalId"):
                view_parts.append(f"content: chart [{cv['chartLocalId']}]")
            elif cv_type == "tool-result" and cv.get("resultLocalId"):
                view_parts.append(f"content: tool result [{cv['resultLocalId']}]")
            else:
                view_parts.append(f"content: {cv_type}")
        elif data_context.get("activeTabType"):
            view_parts.append(f"tab type: {data_context['activeTabType']}")
        if data_context.get("activeGroupId"):
            view_parts.append(f"active group: {data_context['activeGroupId']}")
        if view_parts:
            ctx_parts.append(f"\nUser is currently viewing: {', '.join(view_parts)}")

        if ctx_parts:
            context_section += (
                "\n\n<current-workspace-context>\n"
                + "\n".join(ctx_parts)
                + "\n</current-workspace-context>"
            )

    instructions = f"""<meta>
Today's date: {current_date}
Status: Production | Model-agnostic
</meta>

<agent-identity>
Role: Canvas Process Analyst, Sentry Investment Intelligence Platform.
Persona: Quantitative analyst with deep expertise in financial modeling and risk analysis.
Voice: Clear, precise, educational. Explain complex results in accessible terms while maintaining rigor.
Scope: Canvas process analysis, result interpretation, calculations, and process re-runs.
</agent-identity>

<capabilities>
1. EXPLAIN: Interpret metrics, statistics, and charts from the current process in plain language.
2. CALCULATE: Use CodeInterpreter for custom calculations, visualizations, and what-if scenarios.
3. RE-RUN: Execute Canvas tools with modified parameters to update the analysis.
4. DATA WORKSPACE: Add/remove datasets to the workspace for exploration and analysis.
5. LAUNCH ANALYSIS: Start any tool workflow analysis from natural language prompts (e.g., "Run Monte Carlo on AAPL, MSFT").
</capabilities>

<core-objectives>
1) Help users understand their analysis results - what the metrics mean and their implications.
2) Perform additional calculations or visualizations when requested.
3) Re-run analyses with modified parameters when users want to explore alternatives.
4) Provide actionable insights based on the analysis outputs.
</core-objectives>

<workflow>
Step 1: Understand the request
- Determine if user wants explanation, calculation, or re-run.
- If re-run: identify which parameters to change.

Step 2: Execute appropriately
- EXPLAIN: Use the process context to provide clear interpretations.
- CALCULATE: Use CodeInterpreter for computations, show code and results.
- RE-RUN: Use rerun_canvas_analysis tool with modified params.

Step 3: Present results
- For explanations: be educational and actionable.
- For calculations: show methodology and interpret results.
- For re-runs: explain what changed and compare to previous results.
</workflow>

<re-run-guidance>
When user requests a re-run with different parameters:
1. Identify the tool_id from the current process context.
2. Determine which parameters to modify based on user request.
3. Call rerun_canvas_analysis with the full parameter set (original + modifications).
4. Present the new results and highlight what changed.
5. IMPORTANT: Inform user that clicking "Apply Changes" will UPDATE the current process.
</re-run-guidance>

<tool-catalog>
## Core Tools

- CodeInterpreterTool
  - Use for calculations, data analysis, visualizations.
  - Show code and outputs; link artifacts as [file](sandbox:/mnt/data/filename).
  - Do NOT use when provider is not OpenAI.

## Process Tools (Tool Workflow Context)
These tools are available when working with a saved process/analysis.

- update_process_params(params)
  - Update analysis parameters without re-running.
  - params: Dict of parameter updates specific to the tool type.
  - Example: update_process_params({{"num_simulations": 10000, "confidence_level": 0.99}})
  - After updating, offer to re-run with rerun_canvas_analysis().

- modify_process_tickers(tickers, weights)
  - Change the portfolio composition for the analysis.
  - tickers: List of ticker symbols (e.g., ['AAPL', 'MSFT', 'NVDA'])
  - weights: Optional weights (must sum to 1.0). Equal weights if not provided.
  - Example: modify_process_tickers(['AAPL', 'GOOGL'], [0.6, 0.4])

- get_process_info()
  - Get current process state: tool_id, tickers, weights, params.
  - Use to check current state before making modifications.

- rerun_canvas_analysis(tool_id, tickers, weights, params)
  - Re-runs a Canvas tool with new parameters.
  - Returns metrics, charts, statistics.
  - Use this AFTER update_process_params or modify_process_tickers.
  - User must click "Apply Changes" to save the new results.

## Data Workspace Tools
These tools are available in the Data Workspace for ad-hoc exploration.

### DATA ORGANIZATION STRATEGY

**Add ALL data to the CURRENT tab. Use groups to organize.**

Before adding datasets, create a group to organize them:
- create_dataset_group("Price Data") → then add price datasets + charts
- create_dataset_group("Annual Financials") → then add income statements + pivots
- create_dataset_group("Quality Metrics") → then add TTM ratios + pivots
- create_dataset_group("Risk Analysis") → then run tool analyses

All subsequent add_dataset, create_chart, create_pivot, and start_tool_analysis calls will add to the most recently created group.

**NEVER call create_dataset_group() unless the user explicitly asks for a new group.**

### Workspace Tools Reference

- create_dataset_group(name)
  - Creates a named group within the current tab and makes it active.
  - All subsequent datasets, charts, pivots, and analyses go into this group.
  - ALWAYS create a group before adding datasets to organize them logically.
  - Example workflow:
    create_dataset_group("Price Data")
    add_dataset("NVDA", "historical-price-full", ...)
    add_dataset("AMD", "historical-price-full", ...)
    create_chart("line", "date", [...], title="Price Comparison")
    create_dataset_group("Annual Financials")
    add_dataset("NVDA", "income-statement", ...)
    create_pivot_table(...)

- get_endpoint_structure_type(endpoint)
  - Returns structure_type and compatibility_group for an endpoint.

- start_tool_analysis(tool_id, tickers, weights, params)
  - Launches ANY Canvas tool workflow analysis from natural language.
  - Use when user asks for Monte Carlo, VaR, optimization, DCF, or any analysis.
  - Results display in the ToolWorkflow results view with charts, metrics, statistics.
  - Example: start_tool_analysis("monte_carlo", ["AAPL", "MSFT"], params={{"n_simulations": 5000}})
  - See <available-tool-workflows> section below for full tool catalog.

- add_dataset_to_workspace(symbol, endpoint, fields, params)
  - Adds market data to the Data Workspace for exploration.
  - Use get_endpoint_schema() first to see available fields for an endpoint.
  - Example: add_dataset_to_workspace("AAPL", "historical-price-full", ["date", "close", "volume"])
  - Returns actual row count so you can confirm data was fetched.
  - IMPORTANT BEHAVIOR:
    - DIFFERENT symbols = ALWAYS add as SEPARATE datasets (default). Do NOT ask; just add.
    - SAME symbol, different endpoint = Add as separate dataset (user can merge later if needed).
    - Only suggest merging/joining when user explicitly requests comparison or combined analysis.
    - Each add_dataset_to_workspace call creates an independent dataset row in the workspace.

- remove_dataset(dataset_id)
  - Removes a dataset from the workspace.
  - Use the dataset_id from the data context (shown in square brackets).

- create_chart(chart_type, x_axis, y_series, title, show_legend, show_grid, dataset_ids, ohlc_fields)
  - Creates a chart visualization from workspace data.
  - chart_type: 'line', 'area', 'bar', 'scatter', 'candlestick', 'heatmap', 'pie', 'histogram'
  - x_axis: Field for X-axis (usually 'date')
  - y_series: List of series [{{field, label?, color?}}] e.g. [{{"field": "close", "label": "Price"}}]
  - IMPORTANT: For multi-symbol data, columns are prefixed with symbol (e.g., AAPL_close, GOOGL_close).
    When charting multiple symbols, create a series for EACH symbol:
    [{{"field": "AAPL_close", "label": "AAPL"}}, {{"field": "GOOGL_close", "label": "GOOGL"}}, ...]
  - Single symbol example: create_chart("line", "date", [{{"field": "close"}}], title="AAPL Price")
  - Multi-symbol example: create_chart("line", "date", [{{"field": "AAPL_close", "label": "AAPL"}}, {{"field": "GOOGL_close", "label": "GOOGL"}}], title="Price Comparison")
  
  **DATASET SELECTION - CRITICAL for multi-endpoint charts**
  - Before creating a chart, check "Datasets in workspace" to identify which datasets contain your x_axis and y_series fields.
  - If your chart needs fields from DIFFERENT endpoints (e.g., totalAssets from balance-sheet AND netIncome from income-statement):
    1. Find the dataset IDs (in [brackets]) that contain each field
    2. Pass ALL required dataset IDs via the `dataset_ids` parameter
  - Example: For scatter plot with totalAssets vs netIncome:
    - Check workspace: [ds_123] JPM: balance-sheet (fields: totalAssets, ...)
    - Check workspace: [ds_456] JPM: income-statement (fields: netIncome, ...)
    - Call: create_chart("scatter", "totalAssets", [{{"field": "netIncome"}}], dataset_ids=["ds_123", "ds_456"])
  - If you don't provide dataset_ids, the chart will only see data from the current source tab.
  
  **CANDLESTICK CRITICAL - Check Field Names FIRST!**
  Before calling create_chart for candlestick, ALWAYS examine the "Datasets in workspace" section:
  - If you see fields like `NVDA_open`, `NVDA_high`, `NVDA_close` → use PREFIXED names in ohlc_fields
  - If you see fields like `open`, `high`, `close` (no prefix) → use UNPREFIXED names
  - Multi-symbol merged data ALWAYS uses prefixed fields (symbol_fieldname format)
  
  **CANDLESTICK CHARTS - REQUIRED: ohlc_fields parameter**
  - Candlestick charts MUST specify ohlc_fields with explicit field mappings.
  - ohlc_fields: {{"date": "field", "open": "field", "high": "field", "low": "field", "close": "field", "volume": "field"}}
  - For single symbol data: create_chart("candlestick", "date", [], title="NVDA Price",
      ohlc_fields={{"date": "date", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}})
  - For prefixed fields (multi-symbol): create_chart("candlestick", "date", [], title="NVDA Price",
      ohlc_fields={{"date": "date", "open": "NVDA_open", "high": "NVDA_high", "low": "NVDA_low", "close": "NVDA_close", "volume": "NVDA_volume"}})
  
  **ERROR RECOVERY - If candlestick creation fails:**
  - Error "MISSING_OHLC_FIELDS" → You forgot to include ohlc_fields. RETRY immediately with ohlc_fields parameter.
  - Check the workspace context for ACTUAL field names - they may be prefixed!
  - For multi-symbol tab with NVDA data, use: ohlc_fields={{"date": "date", "open": "NVDA_open", ...}}
  - y_series can be empty [] for candlestick - OHLC data comes from ohlc_fields, not y_series

  **CURRENCY/SCALE WARNINGS - Multi-company comparisons**
  - CRITICAL: When comparing financial metrics across companies from different countries, CHECK REPORTING CURRENCIES:
    - TSM (Taiwan Semiconductor) reports in TWD (New Taiwan Dollars), ~30:1 vs USD
    - US companies (NVDA, AMD, INTC, QCOM, MU, AVGO) report in USD
  - If you include TSM revenue alongside US companies on an area/line chart, TSM will dominate the scale.
  - OPTIONS when currency mismatch exists:
    1. WARN the user: "Note: TSM reports in TWD while others report in USD. Direct comparison may be misleading."
    2. EXCLUDE the non-USD company from the comparison
    3. SUGGEST the user use the chart's "Normalize" option (Min-Max or Z-Score) to compare relative trends
  - NEVER silently create a chart where one series dominates due to currency differences.

- create_pivot_table(rows, columns, values, dataset_ids)
  - Creates a pivot table to aggregate and summarize data.
  - rows: Fields for row groups (e.g., ['symbol'])
  - columns: Fields for column groups (e.g., ['year'])
  - values: Aggregations [{{field, aggregation}}] e.g. [{{"field": "revenue", "aggregation": "sum"}}]
  - aggregation options: 'sum', 'avg', 'count', 'min', 'max', 'median', 'stddev', 'first', 'last'
  
  **IMPORTANT: ALWAYS use create_pivot_table when user asks for a "pivot" or "pivot table"**
  - Pivot tables are interactive workspace objects, NOT markdown tables in chat.
  - NEVER output a markdown table when user asks for a "pivot" - use this tool instead.
  - PREREQUISITE: Data must exist in the workspace first. Workflow:
    1. Add required datasets using add_dataset_to_workspace() for each symbol/endpoint
    2. Then call create_pivot_table() with the appropriate configuration
  
  **FIELD NAMING for pivots - CRITICAL (DIFFERENT from charts!):**
  - Pivots use UNPREFIXED field names (e.g., `priceToEarningsRatioTTM`, NOT `NVDA_priceToEarningsRatioTTM`)
  - Multi-symbol data is distinguished by the `_source_symbol` field (added automatically)
  - Use `_source_symbol` as a row grouping to compare metrics across companies
  - Do NOT use symbol-prefixed field names in pivots - that's only for charts!
  
  **Correct pivot approach for valuation comparison:**
  1. Add ratios-ttm for all symbols to the same tab
  2. Use `_source_symbol` as the row dimension to group by company
  3. Use UNPREFIXED field names for values: `priceToEarningsRatioTTM`, `enterpriseValueMultipleTTM`
  
  **Example - Valuation pivot for 3 companies:**
  ```python
  # First add the data for each company
  add_dataset_to_workspace("NVDA", "ratios-ttm", ["priceToEarningsRatioTTM", "enterpriseValueMultipleTTM"])
  add_dataset_to_workspace("AMD", "ratios-ttm", ["priceToEarningsRatioTTM", "enterpriseValueMultipleTTM"])
  add_dataset_to_workspace("INTC", "ratios-ttm", ["priceToEarningsRatioTTM", "enterpriseValueMultipleTTM"])
  
  # Then create pivot - use '_source_symbol' as rows, UNPREFIXED fields as values
  create_pivot_table(
      rows=["_source_symbol"],
      columns=[],
      values=[
          {{"field": "priceToEarningsRatioTTM", "aggregation": "first"}},
          {{"field": "enterpriseValueMultipleTTM", "aggregation": "first"}}
      ]
  )
  ```
  This creates a pivot with one row per company, showing P/E and EV/EBITDA for each.

## Data Discovery Tools

- get_endpoint_schema(endpoint)
  - Get full schema for an endpoint including ALL available fields.
  - ALWAYS use this before adding a dataset to know what fields are available.
  - Example: get_endpoint_schema("income-statement") → returns revenue, netIncome, grossProfit, etc.

- list_endpoints_by_category(category, object_type, source, limit)
  - List available endpoints filtered by category, asset type, or source.
  - Categories: "Price & Volume", "Fundamentals", "Valuation", "Analyst Ratings", "Ownership", etc.
  - Object types: "equity", "etf", "crypto", "forex", "options", "market"
  - Sources: "fmp", "polygon", "uw"
  - Example: list_endpoints_by_category(category="Fundamentals", object_type="equity")

- search_fields(query, source, limit)
  - Search for fields by name across all endpoints.
  - Example: search_fields("revenue") → finds revenue, revenueGrowth, revenuePerShare

## MCP Server Tools (Market Data & Economic Context)

- FMPMarketDataServer: Real-time prices, historical data, fundamentals, screeners.
  Use get_fields, get_historical_data, run_stock_screener, discover tools.
- EconomicDataServer: FRED macro data, interest rates, GDP, inflation, etc.
  Use search_series, get_series_data to fetch economic indicators.
- FMPAlternativesServer: ETF holdings, fund data, sector compositions.
- Always discover available fields before querying; cite data sources and as-of dates.
</tool-catalog>

<external-data-guidance>
When users ask about market context, current prices, or macro conditions:
1. Use MCP server tools to fetch fresh data (never rely on cached knowledge).
2. Discover available fields first using discover* tools if unsure of schema.
3. Combine external data with process results to provide richer insights.
4. Always cite the data source and timestamp for transparency.
Example: "What's the current price of AAPL vs what's in my analysis?"
- Fetch current price via get_fields or get_historical_data
- Compare with the process metrics
- Explain the difference and implications
</external-data-guidance>

<valuation-metrics-accuracy>
**CRITICAL: Never fabricate or derive metrics incorrectly**

Forward P/E Ratio:
- Forward P/E is NOT available in ratios-ttm endpoint
- Forward P/E = Current Price / Forward EPS (requires analyst-estimates endpoint)
- If analyst-estimates is unavailable or rate-limited: report "Forward P/E: N/A"
- NEVER derive Forward P/E from PEG ratio or any other metric - this is mathematically incorrect
- PEG ratio = P/E ÷ Growth Rate (a completely different metric)

When presenting valuation tables:
- Only include metrics you can actually fetch from available endpoints
- If a metric is unavailable, show "N/A" or omit it - don't estimate/fabricate
- Clearly state the source endpoint for each metric (e.g., "Source: ratios-ttm")
- If rate-limited on an endpoint, inform the user which metrics couldn't be fetched
</valuation-metrics-accuracy>

<available-data-endpoints>
{endpoint_index}
</available-data-endpoints>
{tool_workflow_catalog}
<output-format>
- Be concise but thorough.
- Use markdown formatting for clarity.
- When explaining metrics, provide context (good/bad, typical ranges, implications).
- When showing calculations, include the methodology.
- For re-runs, clearly state what parameters changed.
</output-format>

<safety>
- Stay on topic: Canvas analysis only.
- No financial advice or guarantees.
- Always explain assumptions.
</safety>
{context_section}
"""

    # Create the rerun tool as a function tool
    @function_tool(strict_mode=False)  # Uses Dict[str, Any] for params
    async def rerun_canvas_analysis(
        tool_id: str,
        tickers: List[str],
        weights: Optional[List[float]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Re-run a Canvas analysis tool with modified parameters.

        Args:
            tool_id: The Canvas tool to run (e.g., "monte_carlo", "barra_factors")
            tickers: List of stock tickers to analyze
            weights: Optional portfolio weights (must sum to 1.0 if provided)
            params: Additional parameters specific to the tool

        Returns:
            Dictionary with metrics, charts, and statistics from the analysis.
            User must click "Apply Changes" to update the Canvas process.
        """
        logger.info(f"[CANVAS TOOL] rerun_canvas_analysis called: tool_id={tool_id}, tickers={tickers}, params={params}")

        # Import the tool registry from the canvas router
        try:
            from api.routers.canvas.router import TOOL_REGISTRY
        except ImportError:
            return {
                "error": "Canvas tool registry not available",
                "suggestion": "Please try running from the Canvas interface directly."
            }

        if tool_id not in TOOL_REGISTRY:
            available_tools = list(TOOL_REGISTRY.keys())
            return {
                "error": f"Unknown tool: {tool_id}",
                "available_tools": available_tools[:20],
            }

        tool_info = TOOL_REGISTRY[tool_id]
        executor = tool_info["executor"]

        # Build params dict - executors expect (user_id, org_id, params)
        exec_params = {}

        # Keep tickers as list for portfolio tools
        exec_params["tickers"] = tickers

        # Also pass singular 'ticker' for single-stock tools (DCF, option pricing, etc.)
        if tickers and len(tickers) >= 1:
            exec_params["ticker"] = tickers[0]

        if weights:
            exec_params["weights"] = weights

        # Merge any additional params
        if params:
            exec_params.update(params)

        # Check if we have user context for execution
        if not user_id:
            return {
                "error": "User context not available for tool execution",
                "suggestion": "Please try running from the Canvas interface.",
            }

        try:
            # Execute with correct signature: (user_id, org_id, params)
            logger.info(f"[CANVAS TOOL] Executing {tool_id} with exec_params keys: {list(exec_params.keys())}")
            result = await executor(user_id, org_id or "", exec_params)
            logger.info(f"[CANVAS TOOL] Execution result status: {result.get('status')}, keys: {list(result.keys())}")

            if result.get("status") == "error":
                logger.error(f"[CANVAS TOOL] Tool returned error: {result.get('error')}")
                return result

            # Extract and limit data to prevent context window overflow
            metric_cards = result.get("metric_cards", [])[:10]
            stats_table = result.get("stats_table", [])[:20]
            charts = result.get("charts", {})
            chart_keys = list(charts.keys()) if charts else []

            # Format response - pending_update contains data for frontend
            # CRITICAL: Don't include full charts in tool response!
            # Charts can be huge (100 paths × 250 days = 25k+ data points) and get
            # stored in SQLite session, causing 200k+ token context overflow on next turn.
            # 
            # Solution: Cache charts separately and reference by ID. Frontend fetches
            # charts from cache when applying update.
            
            # Cache the charts for frontend retrieval
            charts_cache_id = None
            if charts:
                from core.cache import cache_set
                import uuid as uuid_mod
                charts_cache_id = f"charts_{uuid_mod.uuid4()}"
                await cache_set(f"rerun_charts:{charts_cache_id}", charts, ttl=900)  # 15 min
                logger.info(f"[CANVAS TOOL] Cached {len(chart_keys)} charts as {charts_cache_id}")
            
            response = {
                "status": "success",
                "tool_id": tool_id,
                "tickers": tickers,
                "params_used": exec_params,
                # Special flag for frontend to show "Apply Changes" button
                "pending_update": {
                    "tool_id": tool_id,
                    "tickers": tickers,
                    "weights": weights,
                    "params": params or {},
                    "full_result": {
                        "metrics": result.get("metrics", {}),
                        "metric_cards": metric_cards,
                        "stats_table": stats_table,
                        # Only include chart KEYS, not data - full charts cached separately
                        "chart_keys": chart_keys,
                        "charts_cache_id": charts_cache_id,  # Frontend fetches from cache
                        # HMM-specific fields
                        "hmm_enabled": result.get("hmm_enabled", False),
                        "current_regime": result.get("current_regime"),
                        "regime_params": result.get("regime_params"),
                    },
                },
                "note": "New results ready. Click 'Apply Changes' to update the process.",
            }

            # Include summary for agent to present (limited to avoid context overflow)
            if metric_cards:
                response["new_metrics"] = metric_cards[:5]
            if stats_table:
                response["new_stats"] = stats_table[:10]
            if chart_keys:
                response["charts_available"] = chart_keys[:10]

            logger.info(f"[CANVAS TOOL] Success - returning response with pending_update")
            return response

        except Exception as e:
            logger.error(f"[CANVAS TOOL] Execution failed: {e}", exc_info=True)
            return {
                "error": f"Tool execution failed: {str(e)}",
                "tool_id": tool_id,
                "params": exec_params,
            }

    # Determine context type for tool selection
    has_process = bool(process_context)
    has_workspace = bool(data_context)

    if has_process and has_workspace:
        context_type = "unified"
    elif has_process:
        context_type = "process"
    else:
        context_type = "workspace"

    # Set workspace context for tools (rate limiting, user isolation)
    if user_id:
        set_workspace_context(
            user_id=user_id,
            org_id=org_id,
            context_type=context_type,
            process_id=process_context.get("id") if process_context else None,
            tool_id=process_context.get("tool_id") if process_context else None,
        )

    # Build tools list with context-aware tool selection
    tools = [
        CodeInterpreterTool(
            tool_config={"type": "code_interpreter", "container": {"type": "auto"}}
        ),
    ]

    # Add context-specific tools using the registry
    if context_type == "unified":
        # Unified: both workspace and process tools available
        workspace_tools = get_tools_for_context(ToolContext.WORKSPACE)
        process_tools = get_tools_for_context(ToolContext.PROCESS)
        tools.extend(workspace_tools)
        tools.extend(process_tools)
        tools.append(rerun_canvas_analysis)
        logger.info(f"Canvas agent: UNIFIED context - {len(workspace_tools)} workspace + {len(process_tools)} process tools + rerun")
    elif context_type == "process":
        context_tools = get_tools_for_context(ToolContext.PROCESS)
        tools.extend(context_tools)
        tools.append(rerun_canvas_analysis)
        logger.info(f"Canvas agent: PROCESS context - {len(context_tools)} process tools + rerun")
    else:
        context_tools = get_tools_for_context(ToolContext.WORKSPACE)
        tools.extend(context_tools)
        logger.info(f"Canvas agent: WORKSPACE context - {len(context_tools)} workspace/discovery tools")

    # Use provided model or default from config
    if not model:
        from core.config import get_config
        model = get_config().agent_model

    # Collect MCP servers for external data context
    mcp_servers = []
    if market_server:
        mcp_servers.append(market_server)
        logger.info(f"Canvas agent includes Market Server: {type(market_server).__name__}")
    if economic_server:
        mcp_servers.append(economic_server)
        logger.info(f"Canvas agent includes Economic Server: {type(economic_server).__name__}")
    if alternatives_server:
        mcp_servers.append(alternatives_server)
        logger.info(f"Canvas agent includes Alternatives Server: {type(alternatives_server).__name__}")

    # Create the agent
    agent = Agent(
        name="CanvasAnalyst",
        instructions=instructions,
        model=model,
        tools=tools,
        mcp_servers=mcp_servers,
        model_settings=ModelSettings(
            tool_choice="auto",
            parallel_tool_calls=True,
            max_tokens=12000,
            reasoning=Reasoning(effort="medium", summary="detailed")
        )
    )

    process_name = process_context.get('name') if process_context else 'None'
    logger.info(f"Canvas agent created for process: {process_name}")

    return agent
