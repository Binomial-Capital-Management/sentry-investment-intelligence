"""
Canvas Pivot Router - API endpoints for pivot table computation and statistical analysis.

Provides endpoints for:
- Pivot table aggregation
- Descriptive statistics
- Correlation analysis
- Statistical hypothesis tests
- Field type analysis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pivot", tags=["canvas-pivot"])


# ============================================================================
# Request/Response Models
# ============================================================================

class PivotValueConfig(BaseModel):
    """Configuration for a value field in the pivot table."""
    field: str
    aggregation: Literal["none", "sum", "avg", "count", "min", "max", "median", "stddev", "first", "last"] = "sum"
    showTotal: Optional[bool] = True
    totalAggregation: Optional[Literal["none", "sum", "avg", "count", "min", "max", "median", "stddev", "first", "last"]] = None


class PivotRequest(BaseModel):
    """Request to compute a pivot table."""
    data: List[Dict[str, Any]]
    rows: List[str] = []
    columns: List[str] = []
    values: List[PivotValueConfig] = []
    filters: Optional[Dict[str, Any]] = None


class PivotCell(BaseModel):
    """A single cell in the pivot table."""
    row_key: str
    col_key: str
    values: Dict[str, Optional[float]]  # field -> aggregated value


class PivotResponse(BaseModel):
    """Response containing the computed pivot table."""
    success: bool
    row_headers: List[str]
    col_headers: List[str]
    cells: List[PivotCell]
    totals: Optional[Dict[str, Optional[float]]] = None  # Allow None values for fields with no data
    row_totals: Optional[Dict[str, Dict[str, Optional[float]]]] = None  # Row-level totals
    error: Optional[str] = None


class StatisticsRequest(BaseModel):
    """Request for statistical analysis."""
    data: List[Dict[str, Any]]
    fields: List[str]  # Which numeric fields to analyze
    analysis_types: List[Literal["descriptive", "correlation", "regression", "distribution"]] = ["descriptive"]
    regression_x: Optional[str] = None  # For regression: independent variable
    regression_y: Optional[str] = None  # For regression: dependent variable


class DescriptiveStats(BaseModel):
    """Descriptive statistics for a single field."""
    field: str
    count: int
    mean: Optional[float]
    median: Optional[float]
    mode: Optional[float]
    std: Optional[float]
    variance: Optional[float]
    min: Optional[float]
    max: Optional[float]
    range: Optional[float]
    q1: Optional[float]
    q2: Optional[float]
    q3: Optional[float]
    iqr: Optional[float]
    skewness: Optional[float]
    kurtosis: Optional[float]


class CorrelationResult(BaseModel):
    """Correlation matrix result."""
    fields: List[str]
    matrix: List[List[float]]  # correlation coefficients
    p_values: List[List[float]]  # p-values for each correlation


class RegressionResult(BaseModel):
    """Linear regression result."""
    x_field: str
    y_field: str
    slope: float
    intercept: float
    r_squared: float
    adj_r_squared: float
    std_error: float
    p_value: float


class DistributionResult(BaseModel):
    """Distribution analysis for a field."""
    field: str
    histogram_bins: List[float]
    histogram_counts: List[int]
    quartiles: Dict[str, float]
    outliers: List[float]
    outlier_indices: List[int]


class StatisticsResponse(BaseModel):
    """Response containing statistical analysis results."""
    success: bool
    descriptive: Optional[List[DescriptiveStats]] = None
    correlation: Optional[CorrelationResult] = None
    regression: Optional[RegressionResult] = None
    distribution: Optional[List[DistributionResult]] = None
    error: Optional[str] = None


class StatisticalTestRequest(BaseModel):
    """Request to run a statistical hypothesis test."""
    data: List[Dict[str, Any]]
    test_type: Literal[
        "ttest_one", "ttest_two", "ttest_paired",
        "anova_one", "anova_two",
        "chi_square_independence", "chi_square_goodness",
        "shapiro_wilk", "kolmogorov_smirnov"
    ]
    field_a: str
    field_b: Optional[str] = None  # For two-sample tests
    group_by: Optional[str] = None  # For ANOVA grouping
    population_mean: Optional[float] = None  # For one-sample t-test
    expected_freq: Optional[List[float]] = None  # For chi-square goodness of fit


class StatisticalTestResult(BaseModel):
    """Result of a statistical hypothesis test."""
    test_type: str
    test_name: str
    statistic: float
    p_value: float
    degrees_of_freedom: Optional[float] = None
    interpretation: str
    significant_at_05: bool
    significant_at_01: bool
    additional_info: Optional[Dict[str, Any]] = None


class StatisticalTestResponse(BaseModel):
    """Response containing test results."""
    success: bool
    result: Optional[StatisticalTestResult] = None
    error: Optional[str] = None


class FieldAnalysisRequest(BaseModel):
    """Request to analyze field types from data."""
    data: List[Dict[str, Any]]


class FieldInfo(BaseModel):
    """Information about a field."""
    name: str
    type: Literal["numeric", "categorical", "datetime", "text", "boolean", "unknown"]
    can_aggregate: bool
    can_group: bool
    unique_count: int
    null_count: int
    sample_values: List[Any]


class FieldAnalysisResponse(BaseModel):
    """Response containing field analysis."""
    success: bool
    fields: List[FieldInfo]
    error: Optional[str] = None


# ============================================================================
# Service Import (lazy)
# ============================================================================

_pivot_service = None

def get_pivot_service():
    global _pivot_service
    if _pivot_service is None:
        from core.canvas.pivot_service import PivotService
        _pivot_service = PivotService()
    return _pivot_service


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/compute", response_model=PivotResponse)
async def compute_pivot(request: PivotRequest):
    """
    Compute a pivot table from the provided data.
    
    Groups data by row and column dimensions, then aggregates value fields.
    """
    try:
        service = get_pivot_service()
        result = service.compute_pivot(
            data=request.data,
            rows=request.rows,
            columns=request.columns,
            values=request.values,
            filters=request.filters
        )
        return PivotResponse(
            success=True,
            row_headers=result["row_headers"],
            col_headers=result["col_headers"],
            cells=result["cells"],
            totals=result.get("totals"),
            row_totals=result.get("row_totals")
        )
    except Exception as e:
        logger.error(f"Error computing pivot: {e}")
        return PivotResponse(
            success=False,
            row_headers=[],
            col_headers=[],
            cells=[],
            error=str(e)
        )


@router.post("/statistics", response_model=StatisticsResponse)
async def compute_statistics(request: StatisticsRequest):
    """
    Compute statistical analysis on the provided data.
    
    Supports descriptive statistics, correlation, regression, and distribution analysis.
    """
    try:
        service = get_pivot_service()
        result = {}
        
        if "descriptive" in request.analysis_types:
            result["descriptive"] = service.compute_descriptive(request.data, request.fields)
        
        if "correlation" in request.analysis_types and len(request.fields) >= 2:
            result["correlation"] = service.compute_correlation(request.data, request.fields)
        
        if "regression" in request.analysis_types and request.regression_x and request.regression_y:
            result["regression"] = service.compute_regression(
                request.data, request.regression_x, request.regression_y
            )
        
        if "distribution" in request.analysis_types:
            result["distribution"] = service.compute_distribution(request.data, request.fields)
        
        return StatisticsResponse(success=True, **result)
    except Exception as e:
        logger.error(f"Error computing statistics: {e}")
        return StatisticsResponse(success=False, error=str(e))


@router.post("/tests", response_model=StatisticalTestResponse)
async def run_statistical_test(request: StatisticalTestRequest):
    """
    Run a statistical hypothesis test on the provided data.
    
    Supports t-tests, ANOVA, chi-square, and normality tests.
    """
    try:
        service = get_pivot_service()
        result = service.run_statistical_test(
            data=request.data,
            test_type=request.test_type,
            field_a=request.field_a,
            field_b=request.field_b,
            group_by=request.group_by,
            population_mean=request.population_mean,
            expected_freq=request.expected_freq
        )
        return StatisticalTestResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Error running statistical test: {e}")
        return StatisticalTestResponse(success=False, error=str(e))


@router.post("/field-analysis", response_model=FieldAnalysisResponse)
async def analyze_fields(request: FieldAnalysisRequest):
    """
    Analyze field types from the provided data.
    
    Classifies each field as numeric, categorical, datetime, etc.
    and determines which fields can be used for aggregation vs grouping.
    """
    try:
        service = get_pivot_service()
        fields = service.analyze_fields(request.data)
        return FieldAnalysisResponse(success=True, fields=fields)
    except Exception as e:
        logger.error(f"Error analyzing fields: {e}")
        return FieldAnalysisResponse(success=False, fields=[], error=str(e))


