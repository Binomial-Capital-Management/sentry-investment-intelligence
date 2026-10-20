"""
Chart analytics endpoints - regression computation and data filtering.

Lightweight utilities for chart visualization enhancements.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Any
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chart", tags=["chart"])


# ─── Request/Response Models ──────────────────────────────────────────────────

class RegressionRequest(BaseModel):
    """Request for regression computation."""
    x: list[float] = Field(..., min_length=2)
    y: list[float] = Field(..., min_length=2)
    regression_type: Literal["linear", "polynomial", "exponential", "logarithmic"] = "linear"
    degree: int = Field(default=2, ge=1, le=6)


class RegressionResponse(BaseModel):
    """Regression computation result."""
    line_x: list[float]
    line_y: list[float]
    equation: str
    r_squared: float
    regression_type: str


class FilterSpec(BaseModel):
    """Single filter specification."""
    field: str
    filter_type: Literal["date_range", "numeric_range"]
    min_value: float | str | None = None
    max_value: float | str | None = None


class FilterRequest(BaseModel):
    """Request for data filtering."""
    data: list[dict[str, Any]]
    filters: list[FilterSpec]


class FilterResponse(BaseModel):
    """Filtered data result."""
    data: list[dict[str, Any]]
    original_count: int
    filtered_count: int


class CorrelationRequest(BaseModel):
    """Request for correlation matrix computation."""
    data: list[dict[str, Any]]
    # Can be either price data or returns data
    ticker_field: str = Field(..., description="Field containing ticker/asset identifier")
    date_field: str = Field(..., description="Field containing date")
    value_field: str = Field(..., description="Field containing price or return value")
    # If true, compute returns from prices first
    compute_returns: bool = Field(default=False, description="If true, compute returns from price data")
    # Optional: rolling correlation window
    rolling_window: int | None = Field(default=None, ge=5, description="Rolling correlation window (None = full period)")


class CorrelationResponse(BaseModel):
    """Correlation matrix result in long-form for heatmap visualization."""
    data: list[dict[str, Any]]  # [{x: ticker1, y: ticker2, z: correlation}, ...]
    tickers: list[str]
    period: str  # Description of the correlation period


# ─── Regression Computation ───────────────────────────────────────────────────

def _compute_r_squared(y_actual: np.ndarray, y_predicted: np.ndarray) -> float:
    """Compute coefficient of determination (R²)."""
    ss_res = np.sum((y_actual - y_predicted) ** 2)
    ss_tot = np.sum((y_actual - np.mean(y_actual)) ** 2)
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return float(1 - (ss_res / ss_tot))


def _format_coefficient(coef: float, precision: int = 4) -> str:
    """Format coefficient for equation display."""
    if abs(coef) < 0.0001:
        return f"{coef:.2e}"
    return f"{coef:.{precision}g}"


def _linear_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, float]:
    """Compute linear regression: y = mx + b"""
    coeffs = np.polyfit(x, y, 1)
    poly = np.poly1d(coeffs)
    
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = poly(x_line)
    
    m, b = coeffs
    sign = "+" if b >= 0 else "-"
    equation = f"y = {_format_coefficient(m)}x {sign} {_format_coefficient(abs(b))}"
    
    r_squared = _compute_r_squared(y, poly(x))
    
    return x_line, y_line, equation, r_squared


def _polynomial_regression(x: np.ndarray, y: np.ndarray, degree: int) -> tuple[np.ndarray, np.ndarray, str, float]:
    """Compute polynomial regression: y = ax^n + bx^(n-1) + ... + c"""
    coeffs = np.polyfit(x, y, degree)
    poly = np.poly1d(coeffs)
    
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = poly(x_line)
    
    # Build equation string
    terms = []
    for i, c in enumerate(coeffs):
        power = degree - i
        if abs(c) < 1e-10:
            continue
        coef_str = _format_coefficient(c)
        if power == 0:
            terms.append(coef_str)
        elif power == 1:
            terms.append(f"{coef_str}x")
        else:
            terms.append(f"{coef_str}x^{power}")
    
    equation = "y = " + " + ".join(terms).replace("+ -", "- ")
    r_squared = _compute_r_squared(y, poly(x))
    
    return x_line, y_line, equation, r_squared


def _exponential_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, float]:
    """Compute exponential regression: y = a * e^(bx)"""
    # Filter positive y values for log transform
    mask = y > 0
    if mask.sum() < 2:
        raise ValueError("Exponential regression requires positive y values")
    
    x_valid, y_valid = x[mask], y[mask]
    
    # Linear regression on log(y) = log(a) + bx
    log_y = np.log(y_valid)
    coeffs = np.polyfit(x_valid, log_y, 1)
    b, log_a = coeffs
    a = np.exp(log_a)
    
    x_line = np.linspace(x.min(), x.max(), 100)
    y_line = a * np.exp(b * x_line)
    
    equation = f"y = {_format_coefficient(a)} × e^({_format_coefficient(b)}x)"
    
    y_pred = a * np.exp(b * x_valid)
    r_squared = _compute_r_squared(y_valid, y_pred)
    
    return x_line, y_line, equation, r_squared


def _logarithmic_regression(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, str, float]:
    """Compute logarithmic regression: y = a * ln(x) + b"""
    # Filter positive x values for log transform
    mask = x > 0
    if mask.sum() < 2:
        raise ValueError("Logarithmic regression requires positive x values")
    
    x_valid, y_valid = x[mask], y[mask]
    
    log_x = np.log(x_valid)
    coeffs = np.polyfit(log_x, y_valid, 1)
    a, b = coeffs
    
    x_line = np.linspace(max(x.min(), 0.001), x.max(), 100)
    y_line = a * np.log(x_line) + b
    
    sign = "+" if b >= 0 else "-"
    equation = f"y = {_format_coefficient(a)} × ln(x) {sign} {_format_coefficient(abs(b))}"
    
    y_pred = a * np.log(x_valid) + b
    r_squared = _compute_r_squared(y_valid, y_pred)
    
    return x_line, y_line, equation, r_squared


@router.post("/regression", response_model=RegressionResponse)
async def compute_regression(req: RegressionRequest) -> RegressionResponse:
    """
    Compute regression line for scatter plot visualization.
    
    Supports linear, polynomial, exponential, and logarithmic regression types.
    Returns line points for plotting, equation string, and R² value.
    """
    if len(req.x) != len(req.y):
        raise HTTPException(status_code=400, detail="x and y arrays must have same length")
    
    x = np.array(req.x, dtype=float)
    y = np.array(req.y, dtype=float)
    
    # Remove NaN/Inf values
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        raise HTTPException(status_code=400, detail="Insufficient valid data points")
    
    x, y = x[mask], y[mask]
    
    try:
        if req.regression_type == "linear":
            x_line, y_line, equation, r_squared = _linear_regression(x, y)
        elif req.regression_type == "polynomial":
            x_line, y_line, equation, r_squared = _polynomial_regression(x, y, req.degree)
        elif req.regression_type == "exponential":
            x_line, y_line, equation, r_squared = _exponential_regression(x, y)
        elif req.regression_type == "logarithmic":
            x_line, y_line, equation, r_squared = _logarithmic_regression(x, y)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown regression type: {req.regression_type}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Regression computation failed: {e}")
        raise HTTPException(status_code=500, detail="Regression computation failed")
    
    return RegressionResponse(
        line_x=x_line.tolist(),
        line_y=y_line.tolist(),
        equation=equation,
        r_squared=round(r_squared, 4),
        regression_type=req.regression_type,
    )


# ─── Data Filtering ───────────────────────────────────────────────────────────

def _parse_date(value: str) -> datetime | None:
    """Parse date string to datetime."""
    formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _apply_date_range_filter(
    data: list[dict], 
    field: str, 
    min_value: str | None, 
    max_value: str | None
) -> list[dict]:
    """Filter data by date range."""
    min_date = _parse_date(min_value) if min_value else None
    max_date = _parse_date(max_value) if max_value else None
    
    result = []
    for row in data:
        val = row.get(field)
        if val is None:
            continue
        
        row_date = _parse_date(str(val)) if isinstance(val, str) else None
        if row_date is None:
            continue
        
        if min_date and row_date < min_date:
            continue
        if max_date and row_date > max_date:
            continue
        
        result.append(row)
    
    return result


def _apply_numeric_range_filter(
    data: list[dict], 
    field: str, 
    min_value: float | None, 
    max_value: float | None
) -> list[dict]:
    """Filter data by numeric range."""
    result = []
    for row in data:
        val = row.get(field)
        if val is None:
            continue
        
        try:
            num_val = float(val)
        except (ValueError, TypeError):
            continue
        
        if min_value is not None and num_val < min_value:
            continue
        if max_value is not None and num_val > max_value:
            continue
        
        result.append(row)
    
    return result


@router.post("/filter", response_model=FilterResponse)
async def filter_data(req: FilterRequest) -> FilterResponse:
    """
    Apply filters to chart data.
    
    Supports date_range and numeric_range filter types.
    Filters are applied sequentially (AND logic).
    """
    original_count = len(req.data)
    filtered = req.data
    
    for f in req.filters:
        if f.filter_type == "date_range":
            filtered = _apply_date_range_filter(
                filtered, 
                f.field, 
                str(f.min_value) if f.min_value else None,
                str(f.max_value) if f.max_value else None
            )
        elif f.filter_type == "numeric_range":
            min_val = float(f.min_value) if f.min_value is not None else None
            max_val = float(f.max_value) if f.max_value is not None else None
            filtered = _apply_numeric_range_filter(filtered, f.field, min_val, max_val)
    
    return FilterResponse(
        data=filtered,
        original_count=original_count,
        filtered_count=len(filtered),
    )


# ─── Correlation Matrix ──────────────────────────────────────────────────────

def _compute_correlation_matrix(
    data: list[dict],
    ticker_field: str,
    date_field: str,
    value_field: str,
    compute_returns: bool = False,
) -> tuple[list[dict], list[str], str]:
    """
    Compute correlation matrix from time series data.
    
    Returns long-form data for heatmap: [{x, y, z}, ...]
    """
    import pandas as pd
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    if df.empty:
        return [], [], "No data"
    
    # Ensure required columns exist
    if ticker_field not in df.columns or date_field not in df.columns or value_field not in df.columns:
        raise ValueError(f"Required fields not found: {ticker_field}, {date_field}, {value_field}")
    
    # Pivot to wide format: dates as index, tickers as columns
    df[date_field] = pd.to_datetime(df[date_field])
    df[value_field] = pd.to_numeric(df[value_field], errors='coerce')
    
    pivot_df = df.pivot_table(
        index=date_field, 
        columns=ticker_field, 
        values=value_field, 
        aggfunc='mean'
    )
    
    # Sort by date
    pivot_df = pivot_df.sort_index()
    
    # Compute returns if requested (percentage change)
    if compute_returns:
        pivot_df = pivot_df.pct_change().dropna()
    
    if pivot_df.empty or len(pivot_df) < 2:
        return [], [], "Insufficient data for correlation"
    
    # Compute correlation matrix
    corr_matrix = pivot_df.corr()
    
    # Get tickers
    tickers = list(corr_matrix.columns)
    
    # Convert to long form for heatmap
    long_form = []
    for i, ticker1 in enumerate(tickers):
        for j, ticker2 in enumerate(tickers):
            corr_value = corr_matrix.loc[ticker1, ticker2]
            if pd.notna(corr_value):
                long_form.append({
                    "x": ticker1,
                    "y": ticker2,
                    "z": round(float(corr_value), 4)
                })
    
    # Build period description
    date_range = f"{pivot_df.index.min().strftime('%Y-%m-%d')} to {pivot_df.index.max().strftime('%Y-%m-%d')}"
    period = f"{len(pivot_df)} observations ({date_range})"
    
    return long_form, tickers, period


@router.post("/correlation", response_model=CorrelationResponse)
async def compute_correlation(req: CorrelationRequest) -> CorrelationResponse:
    """
    Compute correlation matrix from time series data.
    
    Input data should be in long form with ticker, date, and value columns.
    Can optionally compute returns from price data.
    
    Returns long-form correlation data suitable for heatmap visualization.
    """
    if not req.data:
        raise HTTPException(status_code=400, detail="No data provided")
    
    try:
        long_form, tickers, period = _compute_correlation_matrix(
            req.data,
            req.ticker_field,
            req.date_field,
            req.value_field,
            req.compute_returns,
        )
        
        if not long_form:
            raise HTTPException(status_code=400, detail="Could not compute correlations - insufficient data")
        
        return CorrelationResponse(
            data=long_form,
            tickers=tickers,
            period=period,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Correlation computation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Correlation computation failed: {str(e)}")

