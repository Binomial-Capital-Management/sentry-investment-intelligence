"""
RIM (Residual Income Model) Tool
Valuation framework for banks, insurance, and financial institutions.
Status: Production
Created: December 2025

PURPOSE
- Value companies where FCF is hard to define (banks, insurance, REITs)
- Book value is meaningful (assets marked to market, regulatory capital)
- ROE is the key driver, not revenue/FCF growth
- If ROE > Cost of Equity → trades at premium to book; ROE = k_e → at book; ROE < k_e → discount

FORMULA
    Residual Income = (ROE - Cost of Equity) × Book Value
    Intrinsic Value = Book Value + PV(Residual Income stream)
    Terminal Value = RI_terminal / (k_e - g)

FEATURES
- Automatic ROE calculation from historical net income / book value
- ROE trajectory projection with linear decay to terminal ROE
- Cost of equity via CAPM (auto-calculated from beta)
- P/B analysis with justified P/B calculation
- Sensitivity grid: Terminal ROE × Cost of Equity
- Support for tangible book value (excludes goodwill/intangibles)
- Monte Carlo simulation (optional): samples ROE, terminal ROE, cost of equity, BV growth

USE CASE
- Banks: JPM, BAC, WFC, C, GS, MS
- Insurance: BRK, MET, PRU, AIG
- REITs and capital-intensive financials
- Any business where book value matters

FIELD MAPPINGS (from FMP MCP server):
- roe → key-metrics
- bookValuePerShare → ratios
- tangibleBookValuePerShare → ratios
- beta → company-profile
- price, marketCap → company-quote
- netIncome, weightedAverageShsOut → income-statement
- totalStockholdersEquity → balance-sheet-statement
"""

import json
import logging
import statistics
from typing import Dict, Any, List, Optional

import numpy as np
from scipy import stats
import plotly.graph_objects as go

from agents import function_tool
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.risk_tools.shared import register_chart_handle

logger = logging.getLogger(__name__)


def _safe_numeric(value: Any) -> Optional[float]:
    """Safely extract a numeric value, handling dicts and other edge cases."""
    if value is None:
        return None
    if isinstance(value, dict):
        # Some FMP fields return nested dicts - try to extract a value
        return value.get("value") or value.get("v") or None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_scalar(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Extract first available scalar value from nested data."""
    for key in keys:
        if key in data:
            val = data[key]
            if isinstance(val, list) and len(val) > 0:
                if isinstance(val[0], dict):
                    # Try to get the value from the first dict
                    for k in keys:
                        if k in val[0]:
                            return val[0][k]
                    return val[0].get(key, default)
                return val[0]
            elif val is not None:
                return val
    return default


def _normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize RIM parameters with minimal validation."""
    normalized = {}

    # Float parameters
    float_keys = [
        "terminal_roe", "cost_of_equity", "risk_free_rate", "market_risk_premium",
        "book_value_growth", "current_price", "current_book_value", "shares_outstanding"
    ]
    for key in float_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (int, float)):
                normalized[key] = float(val)

    # Integer parameters
    int_keys = ["forecast_years"]
    for key in int_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (int, float)):
                normalized[key] = int(val)

    # Boolean parameters
    bool_keys = ["include_sensitivity", "include_historical_roe", "use_tangible_book", "monte_carlo"]
    for key in bool_keys:
        if key in params:
            normalized[key] = bool(params[key])

    # List parameters (ranges for sensitivity)
    list_keys = ["roe_range", "coe_range"]
    for key in list_keys:
        if key in params and params[key] is not None:
            val = params[key]
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                normalized[key] = [float(val[0]), float(val[1])]

    # String parameters
    str_keys = ["roe_decay_method"]
    for key in str_keys:
        if key in params and params[key] is not None:
            normalized[key] = str(params[key])

    # Monte Carlo parameters
    if "iterations" in params and params["iterations"] is not None:
        normalized["iterations"] = int(params["iterations"])
    if "seed" in params and params["seed"] is not None:
        normalized["seed"] = int(params["seed"])

    return normalized


def _calculate_cost_of_equity(
    beta: float,
    risk_free_rate: float = 0.042,
    market_risk_premium: float = 0.05
) -> float:
    """Calculate cost of equity using CAPM.
    
    Defaults calibrated for current market conditions:
    - Risk-free: 10Y Treasury ~4.2%
    - Market risk premium: 5.0% (slightly lower than historical 5.5% given lower vol)
    """
    if beta is None or beta <= 0:
        beta = 1.0  # Market beta fallback
    return risk_free_rate + beta * market_risk_premium


def _calculate_historical_roe(
    net_income_history: List[float],
    equity_history: List[float]
) -> Dict[str, Any]:
    """
    Calculate historical ROE from net income and equity.
    ROE = Net Income / Beginning Book Value (prior period equity)
    """
    if not net_income_history or not equity_history:
        return {"values": [], "average": None, "error": "Insufficient data"}

    roe_values = []
    # Use beginning book value (prior period equity) for accuracy
    for i in range(len(net_income_history)):
        ni = net_income_history[i]
        # Use prior period equity as beginning book value
        eq = equity_history[i + 1] if i + 1 < len(equity_history) else equity_history[i]
        if ni is not None and eq is not None and eq > 0:
            roe_values.append(ni / eq)

    if not roe_values:
        return {"values": [], "average": None, "error": "No valid ROE calculations"}

    return {
        "values": roe_values,
        "average": statistics.mean(roe_values),
        "median": statistics.median(roe_values),
        "years": len(roe_values)
    }


def _project_roe(
    current_roe: float,
    terminal_roe: float,
    years: int,
    decay_method: str = "linear"
) -> List[float]:
    """
    Project ROE trajectory from current to terminal.
    
    Methods:
    - linear: Straight-line decay
    - exponential: Faster initial decay, slower convergence
    """
    if years <= 0:
        return []

    trajectory = []
    for year in range(1, years + 1):
        if decay_method == "exponential":
            # Exponential decay: faster initial convergence
            decay_factor = 1 - (1 - np.exp(-year / (years / 2))) / (1 - np.exp(-2))
            projected_roe = terminal_roe + (current_roe - terminal_roe) * decay_factor
        else:
            # Linear decay (default)
            projected_roe = current_roe + (terminal_roe - current_roe) * (year / years)
        trajectory.append(projected_roe)

    return trajectory


def _calculate_residual_income(
    roe: float,
    cost_of_equity: float,
    book_value: float
) -> float:
    """Calculate residual income for a period."""
    return (roe - cost_of_equity) * book_value


def _calculate_rim_valuation(
    current_book_value: float,
    roe_trajectory: List[float],
    cost_of_equity: float,
    terminal_roe: float,
    book_value_growth: float = 0.03,
    terminal_growth: float = 0.02
) -> Dict[str, Any]:
    """
    Calculate RIM intrinsic value.
    
    Value = BV_0 + PV(RI_1...RI_n) + PV(Terminal RI)
    """
    if cost_of_equity <= terminal_growth:
        return {"error": "Cost of equity must exceed terminal growth rate"}

    projections = []
    pv_residual_income = 0.0
    book_value = current_book_value

    for year, roe in enumerate(roe_trajectory, 1):
        # Calculate residual income for this year
        ri = _calculate_residual_income(roe, cost_of_equity, book_value)
        # Discount factor
        discount = (1 + cost_of_equity) ** year
        pv_ri = ri / discount

        projections.append({
            "year": year,
            "roe": round(roe, 4),
            "book_value": round(book_value, 2),
            "residual_income": round(ri, 2),
            "pv_residual_income": round(pv_ri, 2)
        })

        pv_residual_income += pv_ri
        # Grow book value for next period
        book_value *= (1 + book_value_growth)

    # Terminal value: perpetuity of terminal RI
    terminal_ri = _calculate_residual_income(terminal_roe, cost_of_equity, book_value)
    terminal_value = terminal_ri / (cost_of_equity - terminal_growth)
    discount_years = len(roe_trajectory)
    pv_terminal = terminal_value / ((1 + cost_of_equity) ** discount_years)

    intrinsic_value = current_book_value + pv_residual_income + pv_terminal

    return {
        "current_book_value": current_book_value,
        "pv_residual_income": round(pv_residual_income, 2),
        "terminal_residual_income": round(terminal_ri, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_terminal_value": round(pv_terminal, 2),
        "intrinsic_value": round(intrinsic_value, 2),
        "projections": projections
    }


def _build_sensitivity_grid(
    current_book_value: float,
    current_roe: float,
    cost_of_equity: float,
    terminal_roe: float,
    forecast_years: int,
    book_value_growth: float,
    roe_range: List[float],
    coe_range: List[float],
    shares: float
) -> Dict[str, Any]:
    """Build Terminal ROE × Cost of Equity sensitivity grid."""
    # Terminal ROE steps
    term_roe_steps = [
        terminal_roe + roe_range[0],
        terminal_roe + roe_range[0] / 2,
        terminal_roe,
        terminal_roe + roe_range[1] / 2,
        terminal_roe + roe_range[1],
    ]
    # Cost of equity steps
    coe_steps = [
        cost_of_equity + coe_range[0],
        cost_of_equity + coe_range[0] / 2,
        cost_of_equity,
        cost_of_equity + coe_range[1] / 2,
        cost_of_equity + coe_range[1],
    ]

    # Ensure valid ranges
    term_roe_steps = [max(0.01, r) for r in term_roe_steps]
    coe_steps = [max(0.01, c) for c in coe_steps]

    grid = {}
    for term_roe in term_roe_steps:
        roe_key = f"{term_roe:.1%}"
        grid[roe_key] = {}
        for coe in coe_steps:
            coe_key = f"{coe:.1%}"
            # Project ROE trajectory
            trajectory = _project_roe(current_roe, term_roe, forecast_years)
            # Calculate valuation
            result = _calculate_rim_valuation(
                current_book_value, trajectory, coe, term_roe, book_value_growth
            )
            if "intrinsic_value" in result:
                per_share = result["intrinsic_value"] / shares if shares > 0 else None
                grid[roe_key][coe_key] = round(per_share, 2) if per_share else None
            else:
                grid[roe_key][coe_key] = None

    return {
        "grid": grid,
        "terminal_roe_values": [f"{r:.1%}" for r in term_roe_steps],
        "cost_of_equity_values": [f"{c:.1%}" for c in coe_steps],
        "note": "Grid shows intrinsic value per share at each Terminal ROE / Cost of Equity combination"
    }


def _calculate_pb_analysis(
    current_price: float,
    book_value_per_share: float,
    intrinsic_value_per_share: float,
    current_roe: float,
    cost_of_equity: float,
    terminal_roe: float
) -> Dict[str, Any]:
    """Analyze P/B ratios and value creation."""
    current_pb = current_price / book_value_per_share if book_value_per_share > 0 else None
    implied_pb = intrinsic_value_per_share / book_value_per_share if book_value_per_share > 0 else None

    # Justified P/B using Gordon growth model approximation
    # P/B = (ROE - g) / (k_e - g) when ROE is sustainable
    g = 0.03  # Assumed long-term growth
    if cost_of_equity > g:
        justified_pb = (terminal_roe - g) / (cost_of_equity - g)
    else:
        justified_pb = None

    # ROE spread analysis
    roe_spread = current_roe - cost_of_equity
    creates_value = roe_spread > 0

    return {
        "current_pb": round(current_pb, 2) if current_pb else None,
        "implied_pb": round(implied_pb, 2) if implied_pb else None,
        "justified_pb": round(justified_pb, 2) if justified_pb else None,
        "roe_spread": round(roe_spread, 4),
        "creates_value": creates_value,
        "interpretation": (
            f"ROE ({current_roe:.1%}) {'>' if creates_value else '<'} Cost of Equity ({cost_of_equity:.1%}). "
            f"Company {'creates' if creates_value else 'destroys'} shareholder value."
        )
    }


# ======================= MONTE CARLO FUNCTIONS =======================

def _calculate_rim_values_vectorized(
    current_book_value: float,
    current_roe_samples: np.ndarray,
    terminal_roe_samples: np.ndarray,
    cost_of_equity_samples: np.ndarray,
    book_value_growth_samples: np.ndarray,
    forecast_years: int,
    terminal_growth: float = 0.02
) -> np.ndarray:
    """
    Vectorized RIM calculation for Monte Carlo.
    Returns array of intrinsic values per share.
    """
    n_samples = len(current_roe_samples)
    intrinsic_values = np.zeros(n_samples)

    for i in range(n_samples):
        current_roe = current_roe_samples[i]
        terminal_roe = terminal_roe_samples[i]
        coe = cost_of_equity_samples[i]
        bv_growth = book_value_growth_samples[i]

        # Skip invalid samples
        if coe <= terminal_growth:
            intrinsic_values[i] = np.nan
            continue

        # Project ROE trajectory (linear decay)
        roe_trajectory = []
        for year in range(1, forecast_years + 1):
            projected_roe = current_roe + (terminal_roe - current_roe) * (year / forecast_years)
            roe_trajectory.append(projected_roe)

        # Calculate PV of residual income
        pv_ri = 0.0
        bv = current_book_value
        for year, roe in enumerate(roe_trajectory, 1):
            ri = (roe - coe) * bv
            pv_ri += ri / ((1 + coe) ** year)
            bv *= (1 + bv_growth)

        # Terminal value
        terminal_ri = (terminal_roe - coe) * bv
        terminal_value = terminal_ri / (coe - terminal_growth)
        pv_terminal = terminal_value / ((1 + coe) ** forecast_years)

        intrinsic_values[i] = current_book_value + pv_ri + pv_terminal

    return intrinsic_values


def _calculate_mc_sensitivity(
    intrinsic_values: np.ndarray,
    current_roe_samples: np.ndarray,
    terminal_roe_samples: np.ndarray,
    cost_of_equity_samples: np.ndarray,
    book_value_growth_samples: np.ndarray
) -> Dict[str, float]:
    """Calculate Spearman correlation sensitivity for each input."""
    # Filter out NaN values
    valid_mask = ~np.isnan(intrinsic_values)
    valid_values = intrinsic_values[valid_mask]

    if len(valid_values) < 10:
        return {"error": "Insufficient valid samples for sensitivity analysis"}

    sensitivities = {}
    inputs = {
        "current_roe": current_roe_samples[valid_mask],
        "terminal_roe": terminal_roe_samples[valid_mask],
        "cost_of_equity": cost_of_equity_samples[valid_mask],
        "book_value_growth": book_value_growth_samples[valid_mask]
    }

    for name, samples in inputs.items():
        corr, _ = stats.spearmanr(samples, valid_values)
        sensitivities[name] = round(abs(corr), 3)

    # Sort by absolute correlation
    sorted_sens = dict(sorted(sensitivities.items(), key=lambda x: x[1], reverse=True))
    return sorted_sens


def _build_mc_histogram(
    values: np.ndarray,
    current_price: float,
    book_value_per_share: float,
    symbol: str
) -> go.Figure:
    """Build Monte Carlo distribution histogram with markers."""
    # Filter valid values
    valid_values = values[~np.isnan(values)]

    fig = go.Figure()

    # Histogram
    fig.add_trace(go.Histogram(
        x=valid_values,
        nbinsx=50,
        name="Distribution",
        marker_color="rgba(100, 149, 237, 0.7)",
        opacity=0.75
    ))

    # Add vertical lines for key values
    mean_val = np.nanmean(valid_values)
    median_val = np.nanmedian(valid_values)

    # Current price line
    fig.add_vline(
        x=current_price,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Price: ${current_price:.2f}",
        annotation_position="top"
    )

    # Book value line
    fig.add_vline(
        x=book_value_per_share,
        line_dash="dot",
        line_color="green",
        annotation_text=f"Book: ${book_value_per_share:.2f}",
        annotation_position="bottom"
    )

    # Median line
    fig.add_vline(
        x=median_val,
        line_dash="solid",
        line_color="blue",
        annotation_text=f"Median: ${median_val:.2f}",
        annotation_position="top right"
    )

    fig.update_layout(
        title=f"{symbol} RIM Monte Carlo Distribution",
        xaxis_title="Intrinsic Value per Share ($)",
        yaxis_title="Frequency",
        showlegend=False,
        template="plotly_white"
    )

    return fig


async def analyze_rim_internal(
    symbol: str,
    rim_params: Optional[str] = None,
    fields: Optional[str] = None
) -> dict:
    """Internal callable for Canvas - wraps analyze_rim logic and returns dict."""
    result_json = await _analyze_rim_impl(symbol, rim_params, fields)
    return json.loads(result_json) if isinstance(result_json, str) else result_json


async def _analyze_rim_impl(
    symbol: str,
    rim_params: Optional[str] = None,
    fields: Optional[str] = None
) -> str:
    """Implementation of RIM analysis."""
    try:
        # Parse parameters
        params = {}
        if rim_params:
            try:
                params = json.loads(rim_params)
            except json.JSONDecodeError:
                params = {}
        
        params = _normalize_params(params)
        
        # Configuration
        terminal_roe = params.get("terminal_roe", 0.10)
        forecast_years = params.get("forecast_years", 10)
        book_value_growth = params.get("book_value_growth", 0.03)
        use_tangible_book = params.get("use_tangible_book", False)
        include_sensitivity = params.get("include_sensitivity", True)
        
        # Fetch data
        market_server = FMPMarketDataServer()
        await market_server.connect()
        
        # Run discovery first to populate field cache
        await market_server.call_tool("discover_fields", {
            "symbol": symbol,
            "max_datasets": 50,
            "period": "annual"
        })
        
        rim_fields = [
            "roe", "bookValuePerShare", "tangibleBookValuePerShare",
            "price", "marketCap", "beta", "netIncome", "totalStockholdersEquity"
        ]
        
        result = await market_server.call_tool("get_fields", {
            "symbol": symbol,
            "fields": rim_fields,
            "params": {"period": "annual", "limit": 1}
        })
        
        raw_data = {}
        if result and not result.isError:
            data = safe_parse_json(result)
            # Check for both error statuses
            if data.get("status") not in ["error", "missing_required_params"]:
                raw_data = data.get("data", data)
        
        await market_server.cleanup()
        
        if not raw_data:
            return json.dumps({"error": f"No data for {symbol}", "symbol": symbol})
        
        # Extract values - use _safe_numeric for all values that may be dicts
        price = _safe_numeric(raw_data.get("price")) or 0
        roe = _safe_numeric(raw_data.get("roe")) or 0.10
        book_value = _safe_numeric(raw_data.get("tangibleBookValuePerShare" if use_tangible_book else "bookValuePerShare")) or 0
        beta = _safe_numeric(raw_data.get("beta")) or 1.0
        
        if not book_value or book_value <= 0:
            return json.dumps({"error": f"No book value for {symbol}", "symbol": symbol})
        
        # Calculate cost of equity (CAPM)
        risk_free = params.get("risk_free_rate", 0.04)
        market_premium = params.get("market_risk_premium", 0.05)
        cost_of_equity = params.get("cost_of_equity") or (risk_free + beta * market_premium)
        
        # Calculate intrinsic value using RIM
        current_bv = book_value
        total_pv_ri = 0
        
        for year in range(1, forecast_years + 1):
            # ROE decays toward terminal
            decay_factor = (forecast_years - year) / forecast_years
            current_roe = terminal_roe + (roe - terminal_roe) * decay_factor
            
            # Residual income
            ri = (current_roe - cost_of_equity) * current_bv
            pv_ri = ri / ((1 + cost_of_equity) ** year)
            total_pv_ri += pv_ri
            
            # Grow book value
            current_bv *= (1 + book_value_growth)
        
        # Terminal value
        terminal_ri = (terminal_roe - cost_of_equity) * current_bv
        terminal_value = terminal_ri / (cost_of_equity - book_value_growth) if cost_of_equity > book_value_growth else 0
        pv_terminal = terminal_value / ((1 + cost_of_equity) ** forecast_years)
        
        intrinsic_value = book_value + total_pv_ri + pv_terminal
        upside = ((intrinsic_value / price) - 1) * 100 if price > 0 else 0
        
        current_pb = price / book_value if book_value > 0 else 0
        implied_pb = intrinsic_value / book_value if book_value > 0 else 0
        
        response = {
            "status": "success",
            "symbol": symbol,
            "rim_valuation": {
                "intrinsic_value_per_share": round(intrinsic_value, 2),
                "current_price": round(price, 2),
                "upside_pct": round(upside, 1),
                "book_value_per_share": round(book_value, 2),
                "current_roe": round(roe, 4),
                "terminal_roe": round(terminal_roe, 4),
                "cost_of_equity": round(cost_of_equity, 4),
                "terminal_growth": round(book_value_growth, 4),
            },
            "price_to_book_analysis": {
                "current_pb": round(current_pb, 2),
                "implied_pb": round(implied_pb, 2),
                "justified_pb": round((terminal_roe - book_value_growth) / (cost_of_equity - book_value_growth), 2) if cost_of_equity > book_value_growth else 1.0,
            },
        }
        
        return json.dumps(response)
        
    except Exception as e:
        logger.error(f"RIM calculation failed for {symbol}: {e}")
        return json.dumps({"error": str(e), "symbol": symbol})


@function_tool
async def analyze_rim(
    symbol: str,
    rim_params: Optional[str] = None,
    fields: Optional[str] = None
) -> str:
    """
    Residual Income Model for banks, insurance, and financial institutions.
    
    Value = Book Value + PV(Residual Income).
    RI = (ROE - Cost of Equity) × Book Value.
    If ROE > k_e → premium to book; ROE = k_e → at book; ROE < k_e → discount.
    
    REQUIRED PARAMETER:
    - terminal_roe: Agent's estimate of sustainable long-term ROE
      - Strong franchise (JPM, GS): 12-14%
      - Average bank: 10-12%
      - Weak/challenged: 8-10%
    
    OPTIONAL PARAMETERS:
    - forecast_years: Projection period (default 10)
    - book_value_growth: Annual BV growth (default 3%)
    - cost_of_equity: Override CAPM calculation
    - risk_free_rate, market_risk_premium: CAPM inputs
    - use_tangible_book: Exclude goodwill/intangibles (default False)
    - include_sensitivity: Terminal ROE × CoE grid (default True)
    - monte_carlo: Run probabilistic simulation (default False)
    - iterations: MC iterations (default 1000)
    - seed: Random seed for reproducibility
    
    Args:
        symbol: Stock ticker (e.g., "BAC", "JPM", "WFC")
        rim_params: JSON with terminal_roe (required) and optional overrides
        fields: Optional additional fields to fetch
        
    Returns:
        JSON with intrinsic value, P/B analysis, projections, sensitivity grid
    """
    # Call the internal implementation
    return await _analyze_rim_impl(symbol, rim_params, fields)


# End of file - internal implementation is in _analyze_rim_impl above
