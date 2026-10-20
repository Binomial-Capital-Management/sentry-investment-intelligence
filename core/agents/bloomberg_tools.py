"""
Bloomberg Excel Tools — Conditional tools for writing Bloomberg formulas into Excel.

These tools construct Bloomberg formula strings (BDP, BDH, BDS, BQL) and emit
them as write_formulas operations via the shared op queue from excel_tools.py.
Bloomberg's own Excel add-in resolves the formulas on the user's machine.

Field discovery uses pgvector semantic search over the bloomberg_fields table.

Only injected when user enables the Bloomberg toggle — never loaded by default.

Following CODING_RULES.md: KISS, no hardcoding, dynamic discovery.
"""

from agents import function_tool
from typing import Optional, List
import logging

from core.agents.excel_tools import _emit

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Bloomberg Formula Tools
# ═══════════════════════════════════════════════════════════════════════════════


def _sanitize_bloomberg_input(value: str) -> str:
    """Sanitize Bloomberg formula input to prevent injection attacks.
    
    Escapes double quotes by doubling them (Bloomberg formula convention)
    and removes dangerous control characters.
    """
    if not value:
        return value
    # Remove control characters (newlines, tabs, etc.)
    sanitized = "".join(c for c in value if ord(c) >= 32 or c in " \t")
    # Escape double quotes by doubling them
    sanitized = sanitized.replace('"', '""')
    return sanitized


@function_tool
async def bloomberg_bdp(
    security: str,
    field: str,
    sheet: str,
    cell: str,
    override_currency: Optional[str] = None,
) -> str:
    """
    Write a Bloomberg BDP (Data Point) formula into an Excel cell.

    Fetches a single data point for a security. Bloomberg add-in resolves it live.

    Args:
        security: Bloomberg security identifier (e.g. "AAPL US Equity", "SPX Index", "EUR Curncy")
        field: Bloomberg field mnemonic (e.g. "PX_LAST", "PE_RATIO", "CUR_MKT_CAP").
               Use search_bloomberg_fields to discover the correct mnemonic.
        sheet: Target worksheet name
        cell: Target cell (e.g. "B2")
        override_currency: Optional currency override (e.g. "USD")
    """
    # Sanitize inputs to prevent formula injection
    safe_security = _sanitize_bloomberg_input(security)
    safe_field = _sanitize_bloomberg_input(field)
    
    parts = [f'"{safe_security}"', f'"{safe_field}"']
    if override_currency:
        safe_currency = _sanitize_bloomberg_input(override_currency)
        parts.append(f'"EQY_FUND_CRNCY","{safe_currency}"')
    formula = f"=BDP({','.join(parts)})"

    await _emit({
        "action": "write_formulas",
        "sheet": sheet,
        "range": cell,
        "formulas": [[formula]],
    })
    return f"Wrote {formula} to {sheet}!{cell}"


@function_tool
async def bloomberg_bdh(
    security: str,
    fields: str,
    start_date: str,
    end_date: str,
    sheet: str,
    start_cell: str,
    frequency: Optional[str] = None,
    override_currency: Optional[str] = None,
) -> str:
    """
    Write a Bloomberg BDH (Data History) formula for time series data.

    Returns historical data that Bloomberg expands into a range of cells.

    Args:
        security: Bloomberg security identifier (e.g. "AAPL US Equity")
        fields: Comma-separated field mnemonics (e.g. "PX_LAST" or "PX_LAST,VOLUME")
        start_date: Start date in YYYYMMDD format (e.g. "20240101")
        end_date: End date in YYYYMMDD format (e.g. "20250101")
        sheet: Target worksheet name
        start_cell: Top-left cell where data starts (e.g. "A2"). Bloomberg expands downward.
        frequency: Optional: "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"
        override_currency: Optional currency override
    """
    # Sanitize inputs to prevent formula injection
    safe_security = _sanitize_bloomberg_input(security)
    safe_fields = _sanitize_bloomberg_input(fields)
    safe_start = _sanitize_bloomberg_input(start_date)
    safe_end = _sanitize_bloomberg_input(end_date)
    
    parts = [f'"{safe_security}"', f'"{safe_fields}"', f'"{safe_start}"', f'"{safe_end}"']
    if frequency:
        safe_freq = _sanitize_bloomberg_input(frequency)
        parts.append(f'"periodicitySelection","{safe_freq}"')
    if override_currency:
        safe_currency = _sanitize_bloomberg_input(override_currency)
        parts.append(f'"EQY_FUND_CRNCY","{safe_currency}"')
    formula = f"=BDH({','.join(parts)})"

    await _emit({
        "action": "write_formulas",
        "sheet": sheet,
        "range": start_cell,
        "formulas": [[formula]],
    })
    return f"Wrote {formula} to {sheet}!{start_cell} (Bloomberg will expand the range)"


@function_tool
async def bloomberg_bds(
    security: str,
    field: str,
    sheet: str,
    cell: str,
) -> str:
    """
    Write a Bloomberg BDS (Data Set) formula for bulk/tabular data.

    Returns a set of data (e.g. index members, fund holdings) that expands into a range.

    Args:
        security: Bloomberg security identifier (e.g. "SPX Index")
        field: Bloomberg bulk field (e.g. "INDX_MEMBERS", "ETF_HOLDINGS", "FUND_TOP_HOLDINGS")
        sheet: Target worksheet name
        cell: Top-left cell (e.g. "A2"). Bloomberg expands downward.
    """
    # Sanitize inputs to prevent formula injection
    safe_security = _sanitize_bloomberg_input(security)
    safe_field = _sanitize_bloomberg_input(field)
    
    formula = f'=BDS("{safe_security}","{safe_field}")'

    await _emit({
        "action": "write_formulas",
        "sheet": sheet,
        "range": cell,
        "formulas": [[formula]],
    })
    return f"Wrote {formula} to {sheet}!{cell} (Bloomberg will expand the range)"


@function_tool
async def bloomberg_bql(
    expression: str,
    sheet: str,
    cell: str,
) -> str:
    """
    Write a Bloomberg BQL (Query Language) formula for advanced queries.

    BQL is Bloomberg's query language for complex data retrieval and screening.

    Args:
        expression: BQL expression (e.g. "get(px_last) for('AAPL US Equity')")
        sheet: Target worksheet name
        cell: Top-left cell (e.g. "A1")
    """
    # Sanitize input to prevent formula injection
    safe_expression = _sanitize_bloomberg_input(expression)
    
    formula = f'=BQL("{safe_expression}")'

    await _emit({
        "action": "write_formulas",
        "sheet": sheet,
        "range": cell,
        "formulas": [[formula]],
    })
    return f"Wrote BQL formula to {sheet}!{cell}"


@function_tool
async def bloomberg_formula(
    formula_string: str,
    sheet: str,
    cell: str,
) -> str:
    """
    Write any raw Bloomberg formula into an Excel cell.

    Escape hatch for Bloomberg formulas not covered by the typed tools
    (e.g. BSRCH, complex BDP overrides, custom BQL).

    Args:
        formula_string: Complete Bloomberg formula starting with = (e.g. '=BSRCH("COMDTY:ENERGY")')
        sheet: Target worksheet name
        cell: Target cell (e.g. "A1")
    """
    if not formula_string.startswith("="):
        formula_string = "=" + formula_string

    await _emit({
        "action": "write_formulas",
        "sheet": sheet,
        "range": cell,
        "formulas": [[formula_string]],
    })
    return f"Wrote Bloomberg formula to {sheet}!{cell}"


# ═══════════════════════════════════════════════════════════════════════════════
# Field Discovery (pgvector semantic search)
# ═══════════════════════════════════════════════════════════════════════════════


@function_tool
async def search_bloomberg_fields(
    query: str,
    category: Optional[str] = None,
    limit: int = 10,
) -> str:
    """
    Search the Bloomberg field catalog to find the correct field mnemonic.

    Uses semantic search — describe what you need in plain English.
    Always call this before using BDP/BDH/BDS if you're unsure of the exact field name.

    Args:
        query: What you're looking for (e.g. "earnings per share", "dividend yield", "credit default swap spread")
        category: Optional filter: Pricing, Valuation, Fundamentals, Balance Sheet, Cash Flow,
                  Estimates, Risk, Sentiment, Options, Fixed Income, Credit, Reference,
                  Index, Corporate Actions, ESG
        limit: Max results (default 10)

    Returns:
        JSON list of matching fields with mnemonic, name, description, category, and similarity score.
    """
    import json as _json
    try:
        from openai import AsyncOpenAI
        from core.config import get_config

        cfg = get_config()
        client = AsyncOpenAI(api_key=cfg.openai_api_key)

        # Embed query
        resp = await client.embeddings.create(
            model=cfg.workbook_embedding_model,
            input=[query],
        )
        query_vec = resp.data[0].embedding
        vec_text = f"[{','.join(map(str, query_vec))}]"

        # pgvector cosine similarity search
        from core.database.postgres_client import get_postgres_rls_client
        pg = await get_postgres_rls_client()

        # bloomberg_fields has no RLS — use a raw connection
        pool = pg._pool if hasattr(pg, '_pool') else None
        if pool is None:
            return _json.dumps({"error": "Database not available"})

        async with pool.acquire() as conn:
            cat_filter = "AND category = $3" if category else ""
            params = [vec_text, limit]
            if category:
                params.append(category)

            rows = await conn.fetch(
                f"""
                SELECT mnemonic, name, description, category, data_type,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM bloomberg_fields
                {cat_filter}
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                *params,
            )

        results = [
            {
                "mnemonic": r["mnemonic"],
                "name": r["name"],
                "description": r["description"],
                "category": r["category"],
                "similarity": round(float(r["similarity"] or 0), 3),
            }
            for r in rows
        ]
        return _json.dumps(results, indent=2)

    except Exception as e:
        logger.warning(f"Bloomberg field search failed: {e}")
        return _json.dumps({"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════


BLOOMBERG_TOOLS: List = [
    bloomberg_bdp,
    bloomberg_bdh,
    bloomberg_bds,
    bloomberg_bql,
    bloomberg_formula,
    search_bloomberg_fields,
]

BLOOMBERG_PROMPT_ADDENDUM = """

<bloomberg>
## Bloomberg Terminal Integration

You have Bloomberg Excel tools available. The user has Bloomberg Terminal with the Excel add-in.
You write Bloomberg formulas into cells, and Bloomberg resolves them live.

### Tools
- **search_bloomberg_fields(query)** — ALWAYS call this first to find the correct field mnemonic.
  Example: search_bloomberg_fields("price to earnings ratio") → PE_RATIO
- **bloomberg_bdp(security, field, sheet, cell)** — Single data point
- **bloomberg_bdh(security, fields, start_date, end_date, sheet, start_cell)** — Time series
- **bloomberg_bds(security, field, sheet, cell)** — Bulk data (index members, holdings)
- **bloomberg_bql(expression, sheet, cell)** — Advanced BQL queries
- **bloomberg_formula(formula_string, sheet, cell)** — Raw formula escape hatch

### Security Identifier Format
- US Equity: "AAPL US Equity"
- International: "7203 JP Equity", "HSBA LN Equity"
- Index: "SPX Index", "INDU Index", "SX5E Index"
- Govt Bond: "USGG10YR Index", "GDBR10 Index"
- Currency: "EUR Curncy", "USDJPY Curncy"
- Commodity: "CL1 Comdty", "GC1 Comdty"
- Option: Use OCC format, e.g. "AAPL 1/17/26 C250 Equity"

### Usage Rules
1. ALWAYS call search_bloomberg_fields first if unsure of the exact mnemonic.
2. Use BDP for single data points, BDH for time series, BDS for bulk/list data.
3. BDH dates must be YYYYMMDD format (e.g. "20240101").
4. BDH frequency options: "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY".
5. Bloomberg formulas are live — they update when the user has a Bloomberg connection.
6. For multi-security comparisons, write one BDP per cell (not arrays).
7. Remember: formulas are written but not resolved until Bloomberg processes them.
</bloomberg>
"""
