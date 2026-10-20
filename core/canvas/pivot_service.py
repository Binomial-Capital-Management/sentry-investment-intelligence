"""
Pivot Service - Computation engine for pivot tables and statistical analysis.

Provides:
- Pivot table aggregation
- Descriptive statistics
- Correlation analysis
- Linear regression
- Distribution analysis
- Statistical hypothesis tests
"""

import logging
from typing import List, Dict, Any, Optional, Literal
from collections import defaultdict
import statistics
import math

logger = logging.getLogger(__name__)

# Try to import numpy and scipy for advanced stats
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not available, some statistical functions will be limited")

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available, statistical tests will not be available")


class PivotService:
    """Service for pivot table computation and statistical analysis."""
    
    # ========================================================================
    # Pivot Table Computation
    # ========================================================================
    
    def compute_pivot(
        self,
        data: List[Dict[str, Any]],
        rows: List[str],
        columns: List[str],
        values: List[Dict[str, Any]],
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compute a pivot table from data.
        
        Args:
            data: List of row dictionaries
            rows: Fields to use as row headers
            columns: Fields to use as column headers  
            values: List of {field, aggregation} configs
            filters: Optional filters to apply
            
        Returns:
            Dict with row_headers, col_headers, cells, totals
        """
        if not data:
            return {"row_headers": [], "col_headers": [], "cells": [], "totals": {}}
        
        # Apply filters
        filtered_data = self._apply_filters(data, filters) if filters else data
        
        # Collect unique row and column keys
        row_keys = set()
        col_keys = set()
        
        # Group data by row+column keys
        grouped: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
        
        for row in filtered_data:
            row_key = self._make_key(row, rows) if rows else "_total"
            col_key = self._make_key(row, columns) if columns else "_total"
            
            row_keys.add(row_key)
            col_keys.add(col_key)
            grouped[row_key][col_key].append(row)
        
        # Sort keys
        row_headers = sorted(row_keys)
        col_headers = sorted(col_keys)
        
        # Compute aggregations for each cell
        cells = []
        
        for row_key in row_headers:
            for col_key in col_headers:
                cell_data = grouped[row_key][col_key]
                cell_values = {}
                
                for value_config in values:
                    field = value_config.get("field") if isinstance(value_config, dict) else value_config.field
                    agg = value_config.get("aggregation", "sum") if isinstance(value_config, dict) else value_config.aggregation
                    
                    field_values = [
                        self._to_float(r.get(field)) 
                        for r in cell_data 
                        if r.get(field) is not None
                    ]
                    field_values = [v for v in field_values if v is not None]
                    
                    agg_value = self._aggregate(field_values, agg)
                    cell_values[field] = agg_value
                
                cells.append({
                    "row_key": row_key,
                    "col_key": col_key,
                    "values": cell_values
                })
        
        # Compute totals from ALL raw data using the total aggregation for each field
        final_totals = {}
        for value_config in values:
            field = value_config.get("field") if isinstance(value_config, dict) else value_config.field
            # Use totalAggregation if provided, otherwise fall back to aggregation
            total_agg = value_config.get("totalAggregation") if isinstance(value_config, dict) else getattr(value_config, 'totalAggregation', None)
            if not total_agg:
                total_agg = value_config.get("aggregation", "sum") if isinstance(value_config, dict) else value_config.aggregation
            
            # Collect ALL values for this field from the filtered data
            all_field_values = [
                self._to_float(r.get(field))
                for r in filtered_data
                if r.get(field) is not None
            ]
            all_field_values = [v for v in all_field_values if v is not None]
            
            # Apply the total aggregation function
            final_totals[field] = self._aggregate(all_field_values, total_agg)
        
        # Compute row totals (grand total column) - aggregate per row across all columns
        row_totals = {}
        for row_key in row_headers:
            row_totals[row_key] = {}
            for value_config in values:
                field = value_config.get("field") if isinstance(value_config, dict) else value_config.field
                agg = value_config.get("aggregation", "sum") if isinstance(value_config, dict) else value_config.aggregation
                
                # Collect all values for this row across all columns
                row_field_values = []
                for col_key in col_headers:
                    cell_data = grouped[row_key][col_key]
                    for r in cell_data:
                        v = self._to_float(r.get(field))
                        if v is not None:
                            row_field_values.append(v)
                
                row_totals[row_key][field] = self._aggregate(row_field_values, agg)
        
        # Compute subtotals for hierarchical rows (when multiple row fields)
        subtotals = {}
        if len(rows) > 1:
            # Group by first-level row field for subtotals
            first_field = rows[0]
            groups: Dict[str, List[Dict]] = defaultdict(list)
            for row_data in filtered_data:
                group_key = str(row_data.get(first_field, ""))
                groups[group_key].append(row_data)
            
            for group_key, group_rows in groups.items():
                subtotals[group_key] = {}
                for value_config in values:
                    field = value_config.get("field") if isinstance(value_config, dict) else value_config.field
                    agg = value_config.get("aggregation", "sum") if isinstance(value_config, dict) else value_config.aggregation
                    
                    group_values = [
                        self._to_float(r.get(field))
                        for r in group_rows
                        if r.get(field) is not None
                    ]
                    group_values = [v for v in group_values if v is not None]
                    subtotals[group_key][field] = self._aggregate(group_values, agg)
        
        return {
            "row_headers": row_headers,
            "col_headers": col_headers,
            "cells": cells,
            "totals": final_totals,
            "row_totals": row_totals,
            "subtotals": subtotals
        }
    
    def _make_key(self, row: Dict[str, Any], fields: List[str]) -> str:
        """Create a composite key from multiple fields."""
        parts = [str(row.get(f, "")) for f in fields]
        return " | ".join(parts) if len(parts) > 1 else parts[0] if parts else ""
    
    def _to_float(self, value: Any) -> Optional[float]:
        """Convert value to float, return None if not possible."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Remove common formatting
                cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
                if cleaned == "" or cleaned == "-":
                    return None
                return float(cleaned)
            except (ValueError, TypeError):
                return None
        return None
    
    def _aggregate(self, values: List[float], aggregation: str) -> Optional[float]:
        """Apply aggregation function to values."""
        if not values:
            return None
        
        try:
            if aggregation == "none":
                # Return first value as-is (no aggregation - for single values)
                return values[0]
            elif aggregation == "sum":
                return sum(values)
            elif aggregation == "avg":
                return statistics.mean(values)
            elif aggregation == "count":
                return float(len(values))
            elif aggregation == "min":
                return min(values)
            elif aggregation == "max":
                return max(values)
            elif aggregation == "first":
                return values[0]
            elif aggregation == "last":
                return values[-1]
            elif aggregation == "median":
                return statistics.median(values)
            elif aggregation == "stddev":
                return statistics.stdev(values) if len(values) > 1 else 0.0
            else:
                return sum(values)
        except Exception:
            return None
    
    def _apply_filters(self, data: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply filters to data."""
        result = data
        for field, condition in filters.items():
            if isinstance(condition, dict):
                op = condition.get("operator", "eq")
                val = condition.get("value")
                result = [r for r in result if self._matches_filter(r.get(field), op, val)]
            else:
                # Simple equality
                result = [r for r in result if r.get(field) == condition]
        return result
    
    def _matches_filter(self, value: Any, operator: str, target: Any) -> bool:
        """Check if value matches filter condition."""
        # "all" operator means no filtering - always pass
        if operator == "all" or operator == "none":
            return True
        if value is None:
            return operator == "is_null"  # Special case for null checks
        try:
            if operator == "eq":
                return value == target
            elif operator == "ne":
                return value != target
            elif operator == "gt":
                return float(value) > float(target)
            elif operator == "gte":
                return float(value) >= float(target)
            elif operator == "lt":
                return float(value) < float(target)
            elif operator == "lte":
                return float(value) <= float(target)
            elif operator == "contains":
                return str(target).lower() in str(value).lower()
            elif operator == "not_contains":
                return str(target).lower() not in str(value).lower()
            elif operator == "starts_with":
                return str(value).lower().startswith(str(target).lower())
            elif operator == "ends_with":
                return str(value).lower().endswith(str(target).lower())
            elif operator == "in":
                return value in target
            elif operator == "not_in":
                return value not in target
            elif operator == "is_not_null":
                return True  # We already know value is not None
            else:
                return value == target
        except (ValueError, TypeError):
            return False
    
    # ========================================================================
    # Descriptive Statistics
    # ========================================================================
    
    def compute_descriptive(
        self, 
        data: List[Dict[str, Any]], 
        fields: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Compute descriptive statistics for specified fields.
        
        Returns list of stats dicts, one per field.
        """
        results = []
        
        for field in fields:
            values = [self._to_float(r.get(field)) for r in data]
            values = [v for v in values if v is not None]
            
            if not values:
                results.append({
                    "field": field,
                    "count": 0,
                    "mean": None, "median": None, "mode": None,
                    "std": None, "variance": None,
                    "min": None, "max": None, "range": None,
                    "q1": None, "q2": None, "q3": None, "iqr": None,
                    "skewness": None, "kurtosis": None
                })
                continue
            
            n = len(values)
            mean_val = statistics.mean(values)
            
            # Basic stats
            stats_dict = {
                "field": field,
                "count": n,
                "mean": mean_val,
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "range": max(values) - min(values),
            }
            
            # Mode (most common value)
            try:
                stats_dict["mode"] = statistics.mode(values)
            except statistics.StatisticsError:
                stats_dict["mode"] = None
            
            # Variance and std
            if n > 1:
                stats_dict["variance"] = statistics.variance(values)
                stats_dict["std"] = statistics.stdev(values)
            else:
                stats_dict["variance"] = 0.0
                stats_dict["std"] = 0.0
            
            # Quartiles
            sorted_vals = sorted(values)
            stats_dict["q1"] = self._percentile(sorted_vals, 25)
            stats_dict["q2"] = self._percentile(sorted_vals, 50)
            stats_dict["q3"] = self._percentile(sorted_vals, 75)
            stats_dict["iqr"] = stats_dict["q3"] - stats_dict["q1"] if stats_dict["q1"] and stats_dict["q3"] else None
            
            # Skewness and Kurtosis (using scipy if available)
            if HAS_SCIPY and n > 2:
                stats_dict["skewness"] = float(scipy_stats.skew(values))
                stats_dict["kurtosis"] = float(scipy_stats.kurtosis(values))
            else:
                stats_dict["skewness"] = None
                stats_dict["kurtosis"] = None
            
            results.append(stats_dict)
        
        return results
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> Optional[float]:
        """Calculate percentile of sorted values."""
        if not sorted_values:
            return None
        n = len(sorted_values)
        k = (n - 1) * percentile / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)
    
    # ========================================================================
    # Correlation Analysis
    # ========================================================================
    
    def compute_correlation(
        self, 
        data: List[Dict[str, Any]], 
        fields: List[str]
    ) -> Dict[str, Any]:
        """
        Compute correlation matrix for specified fields.
        
        Returns correlation coefficients and p-values.
        """
        if not HAS_NUMPY or not HAS_SCIPY:
            return {
                "fields": fields,
                "matrix": [],
                "p_values": []
            }
        
        # Extract values for each field
        field_values = {}
        for field in fields:
            values = [self._to_float(r.get(field)) for r in data]
            field_values[field] = values
        
        # Build correlation matrix
        n_fields = len(fields)
        matrix = [[0.0] * n_fields for _ in range(n_fields)]
        p_values = [[0.0] * n_fields for _ in range(n_fields)]
        
        for i, field_i in enumerate(fields):
            for j, field_j in enumerate(fields):
                if i == j:
                    matrix[i][j] = 1.0
                    p_values[i][j] = 0.0
                elif i < j:
                    # Get paired values (both non-null)
                    pairs = [
                        (field_values[field_i][k], field_values[field_j][k])
                        for k in range(len(data))
                        if field_values[field_i][k] is not None and field_values[field_j][k] is not None
                    ]
                    
                    if len(pairs) >= 3:
                        x_vals = [p[0] for p in pairs]
                        y_vals = [p[1] for p in pairs]
                        corr, pval = scipy_stats.pearsonr(x_vals, y_vals)
                        matrix[i][j] = float(corr)
                        matrix[j][i] = float(corr)
                        p_values[i][j] = float(pval)
                        p_values[j][i] = float(pval)
        
        return {
            "fields": fields,
            "matrix": matrix,
            "p_values": p_values
        }
    
    # ========================================================================
    # Regression Analysis
    # ========================================================================
    
    def compute_regression(
        self, 
        data: List[Dict[str, Any]], 
        x_field: str, 
        y_field: str
    ) -> Dict[str, Any]:
        """
        Compute linear regression between two fields.
        
        Returns slope, intercept, R-squared, and other metrics.
        """
        if not HAS_SCIPY:
            return {
                "x_field": x_field,
                "y_field": y_field,
                "slope": 0.0,
                "intercept": 0.0,
                "r_squared": 0.0,
                "adj_r_squared": 0.0,
                "std_error": 0.0,
                "p_value": 1.0
            }
        
        # Get paired values
        pairs = []
        for row in data:
            x_val = self._to_float(row.get(x_field))
            y_val = self._to_float(row.get(y_field))
            if x_val is not None and y_val is not None:
                pairs.append((x_val, y_val))
        
        if len(pairs) < 3:
            return {
                "x_field": x_field,
                "y_field": y_field,
                "slope": 0.0,
                "intercept": 0.0,
                "r_squared": 0.0,
                "adj_r_squared": 0.0,
                "std_error": 0.0,
                "p_value": 1.0
            }
        
        x_vals = np.array([p[0] for p in pairs])
        y_vals = np.array([p[1] for p in pairs])
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x_vals, y_vals)
        
        n = len(pairs)
        r_squared = r_value ** 2
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - 2) if n > 2 else r_squared
        
        return {
            "x_field": x_field,
            "y_field": y_field,
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_squared),
            "adj_r_squared": float(adj_r_squared),
            "std_error": float(std_err),
            "p_value": float(p_value)
        }
    
    # ========================================================================
    # Distribution Analysis
    # ========================================================================
    
    def compute_distribution(
        self, 
        data: List[Dict[str, Any]], 
        fields: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Compute distribution analysis for specified fields.
        
        Returns histogram bins, quartiles, and outlier detection.
        """
        results = []
        
        for field in fields:
            values = [self._to_float(r.get(field)) for r in data]
            values = [v for v in values if v is not None]
            
            if not values:
                results.append({
                    "field": field,
                    "histogram_bins": [],
                    "histogram_counts": [],
                    "quartiles": {},
                    "outliers": [],
                    "outlier_indices": []
                })
                continue
            
            sorted_vals = sorted(values)
            
            # Quartiles
            q1 = self._percentile(sorted_vals, 25)
            q2 = self._percentile(sorted_vals, 50)
            q3 = self._percentile(sorted_vals, 75)
            iqr = q3 - q1 if q1 and q3 else 0
            
            quartiles = {"q1": q1, "q2": q2, "q3": q3, "iqr": iqr}
            
            # Outlier detection (IQR method)
            lower_bound = q1 - 1.5 * iqr if q1 else float('-inf')
            upper_bound = q3 + 1.5 * iqr if q3 else float('inf')
            
            outliers = []
            outlier_indices = []
            for i, v in enumerate(values):
                if v < lower_bound or v > upper_bound:
                    outliers.append(v)
                    outlier_indices.append(i)
            
            # Histogram
            if HAS_NUMPY:
                counts, bin_edges = np.histogram(values, bins='auto')
                histogram_bins = [float(b) for b in bin_edges]
                histogram_counts = [int(c) for c in counts]
            else:
                # Simple histogram without numpy
                n_bins = min(10, len(set(values)))
                min_val, max_val = min(values), max(values)
                bin_width = (max_val - min_val) / n_bins if n_bins > 0 else 1
                histogram_bins = [min_val + i * bin_width for i in range(n_bins + 1)]
                histogram_counts = [0] * n_bins
                for v in values:
                    bin_idx = min(int((v - min_val) / bin_width), n_bins - 1) if bin_width > 0 else 0
                    histogram_counts[bin_idx] += 1
            
            results.append({
                "field": field,
                "histogram_bins": histogram_bins,
                "histogram_counts": histogram_counts,
                "quartiles": quartiles,
                "outliers": outliers,
                "outlier_indices": outlier_indices
            })
        
        return results
    
    # ========================================================================
    # Statistical Hypothesis Tests
    # ========================================================================
    
    def run_statistical_test(
        self,
        data: List[Dict[str, Any]],
        test_type: str,
        field_a: str,
        field_b: Optional[str] = None,
        group_by: Optional[str] = None,
        population_mean: Optional[float] = None,
        expected_freq: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Run a statistical hypothesis test.
        
        Returns test statistic, p-value, and interpretation.
        """
        if not HAS_SCIPY:
            return {
                "test_type": test_type,
                "test_name": "N/A",
                "statistic": 0.0,
                "p_value": 1.0,
                "interpretation": "scipy not available for statistical tests",
                "significant_at_05": False,
                "significant_at_01": False
            }
        
        # Extract values
        values_a = [self._to_float(r.get(field_a)) for r in data]
        values_a = [v for v in values_a if v is not None]
        
        values_b = None
        if field_b:
            values_b = [self._to_float(r.get(field_b)) for r in data]
            values_b = [v for v in values_b if v is not None]
        
        result = None
        
        if test_type == "ttest_one":
            result = self._ttest_one_sample(values_a, population_mean or 0)
        elif test_type == "ttest_two":
            result = self._ttest_two_sample(values_a, values_b or [])
        elif test_type == "ttest_paired":
            result = self._ttest_paired(values_a, values_b or [])
        elif test_type == "anova_one":
            result = self._anova_one_way(data, field_a, group_by or "")
        elif test_type == "anova_two":
            result = self._anova_two_way(data, field_a, group_by or "", field_b or "")
        elif test_type == "chi_square_independence":
            result = self._chi_square_independence(data, field_a, field_b or "")
        elif test_type == "chi_square_goodness":
            result = self._chi_square_goodness(values_a, expected_freq)
        elif test_type == "shapiro_wilk":
            result = self._shapiro_wilk(values_a)
        elif test_type == "kolmogorov_smirnov":
            result = self._kolmogorov_smirnov(values_a)
        else:
            result = {
                "test_type": test_type,
                "test_name": "Unknown Test",
                "statistic": 0.0,
                "p_value": 1.0,
                "interpretation": f"Unknown test type: {test_type}",
                "significant_at_05": False,
                "significant_at_01": False
            }
        
        return result
    
    def _ttest_one_sample(self, values: List[float], population_mean: float) -> Dict:
        """One-sample t-test."""
        if len(values) < 2:
            return self._empty_test_result("ttest_one", "One-Sample T-Test", "Insufficient data")
        
        statistic, p_value = scipy_stats.ttest_1samp(values, population_mean)
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        interp = f"Sample mean ({statistics.mean(values):.4f}) is "
        interp += "significantly " if sig_05 else "not significantly "
        interp += f"different from {population_mean}"
        
        return {
            "test_type": "ttest_one",
            "test_name": "One-Sample T-Test",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "degrees_of_freedom": float(len(values) - 1),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01,
            "additional_info": {
                "sample_mean": statistics.mean(values),
                "population_mean": population_mean,
                "n": len(values)
            }
        }
    
    def _ttest_two_sample(self, values_a: List[float], values_b: List[float]) -> Dict:
        """Independent two-sample t-test."""
        if len(values_a) < 2 or len(values_b) < 2:
            return self._empty_test_result("ttest_two", "Two-Sample T-Test", "Insufficient data")
        
        statistic, p_value = scipy_stats.ttest_ind(values_a, values_b)
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        mean_a = statistics.mean(values_a)
        mean_b = statistics.mean(values_b)
        
        interp = f"Group means ({mean_a:.4f} vs {mean_b:.4f}) are "
        interp += "significantly " if sig_05 else "not significantly "
        interp += "different"
        
        return {
            "test_type": "ttest_two",
            "test_name": "Two-Sample T-Test (Independent)",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "degrees_of_freedom": float(len(values_a) + len(values_b) - 2),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01,
            "additional_info": {
                "mean_a": mean_a,
                "mean_b": mean_b,
                "n_a": len(values_a),
                "n_b": len(values_b)
            }
        }
    
    def _ttest_paired(self, values_a: List[float], values_b: List[float]) -> Dict:
        """Paired t-test."""
        n = min(len(values_a), len(values_b))
        if n < 2:
            return self._empty_test_result("ttest_paired", "Paired T-Test", "Insufficient data")
        
        statistic, p_value = scipy_stats.ttest_rel(values_a[:n], values_b[:n])
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        interp = "Paired differences are "
        interp += "significantly " if sig_05 else "not significantly "
        interp += "different from zero"
        
        return {
            "test_type": "ttest_paired",
            "test_name": "Paired T-Test",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "degrees_of_freedom": float(n - 1),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01,
            "additional_info": {"n_pairs": n}
        }
    
    def _anova_one_way(self, data: List[Dict], value_field: str, group_field: str) -> Dict:
        """One-way ANOVA."""
        # Group values by category
        groups = defaultdict(list)
        for row in data:
            group = row.get(group_field)
            value = self._to_float(row.get(value_field))
            if group is not None and value is not None:
                groups[str(group)].append(value)
        
        group_values = [v for v in groups.values() if len(v) >= 2]
        
        if len(group_values) < 2:
            return self._empty_test_result("anova_one", "One-Way ANOVA", "Need at least 2 groups with 2+ observations")
        
        statistic, p_value = scipy_stats.f_oneway(*group_values)
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        interp = "Group means are "
        interp += "significantly " if sig_05 else "not significantly "
        interp += f"different (F = {statistic:.4f})"
        
        return {
            "test_type": "anova_one",
            "test_name": "One-Way ANOVA",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01,
            "additional_info": {
                "n_groups": len(group_values),
                "group_sizes": [len(g) for g in group_values]
            }
        }
    
    def _anova_two_way(self, data: List[Dict], value_field: str, factor1: str, factor2: str) -> Dict:
        """Two-way ANOVA (simplified - returns one-way result with note)."""
        # For proper two-way ANOVA, we'd need statsmodels
        # This is a simplified placeholder
        return self._anova_one_way(data, value_field, factor1)
    
    def _chi_square_independence(self, data: List[Dict], field_a: str, field_b: str) -> Dict:
        """Chi-square test of independence."""
        # Build contingency table
        contingency = defaultdict(lambda: defaultdict(int))
        for row in data:
            a = row.get(field_a)
            b = row.get(field_b)
            if a is not None and b is not None:
                contingency[str(a)][str(b)] += 1
        
        if not contingency:
            return self._empty_test_result("chi_square_independence", "Chi-Square Independence", "No data")
        
        # Convert to matrix
        rows = sorted(contingency.keys())
        cols = sorted(set(c for r in contingency.values() for c in r.keys()))
        matrix = [[contingency[r][c] for c in cols] for r in rows]
        
        if len(matrix) < 2 or len(matrix[0]) < 2:
            return self._empty_test_result("chi_square_independence", "Chi-Square Independence", "Need at least 2x2 table")
        
        chi2, p_value, dof, expected = scipy_stats.chi2_contingency(matrix)
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        interp = f"Variables are "
        interp += "" if sig_05 else "not "
        interp += "significantly associated"
        
        return {
            "test_type": "chi_square_independence",
            "test_name": "Chi-Square Test of Independence",
            "statistic": float(chi2),
            "p_value": float(p_value),
            "degrees_of_freedom": float(dof),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01
        }
    
    def _chi_square_goodness(self, observed: List[float], expected: Optional[List[float]]) -> Dict:
        """Chi-square goodness of fit test."""
        if not observed:
            return self._empty_test_result("chi_square_goodness", "Chi-Square Goodness of Fit", "No data")
        
        # If no expected provided, assume uniform
        if expected is None:
            expected = [sum(observed) / len(observed)] * len(observed)
        
        if len(observed) != len(expected):
            return self._empty_test_result("chi_square_goodness", "Chi-Square Goodness of Fit", "Observed and expected must have same length")
        
        chi2, p_value = scipy_stats.chisquare(observed, f_exp=expected)
        
        sig_05 = p_value < 0.05
        sig_01 = p_value < 0.01
        
        interp = "Distribution "
        interp += "significantly differs from" if sig_05 else "does not significantly differ from"
        interp += " expected"
        
        return {
            "test_type": "chi_square_goodness",
            "test_name": "Chi-Square Goodness of Fit",
            "statistic": float(chi2),
            "p_value": float(p_value),
            "degrees_of_freedom": float(len(observed) - 1),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": sig_01
        }
    
    def _shapiro_wilk(self, values: List[float]) -> Dict:
        """Shapiro-Wilk normality test."""
        if len(values) < 3:
            return self._empty_test_result("shapiro_wilk", "Shapiro-Wilk Normality Test", "Need at least 3 observations")
        
        # Shapiro-Wilk has a limit of 5000 samples
        sample = values[:5000] if len(values) > 5000 else values
        
        statistic, p_value = scipy_stats.shapiro(sample)
        
        sig_05 = p_value < 0.05
        
        interp = "Data is "
        interp += "not " if sig_05 else ""
        interp += "normally distributed"
        
        return {
            "test_type": "shapiro_wilk",
            "test_name": "Shapiro-Wilk Normality Test",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": p_value < 0.01,
            "additional_info": {"n": len(sample)}
        }
    
    def _kolmogorov_smirnov(self, values: List[float]) -> Dict:
        """Kolmogorov-Smirnov normality test."""
        if len(values) < 3:
            return self._empty_test_result("kolmogorov_smirnov", "Kolmogorov-Smirnov Test", "Need at least 3 observations")
        
        # Standardize values for testing against standard normal
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 1
        standardized = [(v - mean_val) / std_val for v in values] if std_val > 0 else values
        
        statistic, p_value = scipy_stats.kstest(standardized, 'norm')
        
        sig_05 = p_value < 0.05
        
        interp = "Data is "
        interp += "not " if sig_05 else ""
        interp += "normally distributed"
        
        return {
            "test_type": "kolmogorov_smirnov",
            "test_name": "Kolmogorov-Smirnov Test",
            "statistic": float(statistic),
            "p_value": float(p_value),
            "interpretation": interp,
            "significant_at_05": sig_05,
            "significant_at_01": p_value < 0.01,
            "additional_info": {"n": len(values)}
        }
    
    def _empty_test_result(self, test_type: str, test_name: str, reason: str) -> Dict:
        """Return an empty test result with error message."""
        return {
            "test_type": test_type,
            "test_name": test_name,
            "statistic": 0.0,
            "p_value": 1.0,
            "interpretation": reason,
            "significant_at_05": False,
            "significant_at_01": False
        }
    
    # ========================================================================
    # Field Analysis
    # ========================================================================
    
    def analyze_fields(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze field types from data.
        
        Returns classification of each field as numeric, categorical, etc.
        """
        if not data:
            return []
        
        # Sample first 100 rows
        sample = data[:100]
        
        # Collect all field names
        all_fields = set()
        for row in sample:
            all_fields.update(row.keys())
        
        results = []
        
        for field in sorted(all_fields):
            values = [row.get(field) for row in sample]
            non_null_values = [v for v in values if v is not None]
            
            # Count types
            numeric_count = 0
            string_count = 0
            bool_count = 0
            date_count = 0
            
            for v in non_null_values:
                if isinstance(v, bool):
                    bool_count += 1
                elif isinstance(v, (int, float)):
                    numeric_count += 1
                elif isinstance(v, str):
                    # Check if it's a date
                    if self._looks_like_date(v):
                        date_count += 1
                    # Check if it's a numeric string
                    elif self._to_float(v) is not None:
                        numeric_count += 1
                    else:
                        string_count += 1
            
            total = len(non_null_values)
            if total == 0:
                field_type = "unknown"
            elif bool_count / total > 0.8:
                field_type = "boolean"
            elif date_count / total > 0.5:
                field_type = "datetime"
            elif numeric_count / total > 0.8:
                field_type = "numeric"
            elif string_count / total > 0.5:
                # Check cardinality for categorical vs text
                unique_count = len(set(str(v) for v in non_null_values))
                if unique_count / total < 0.3:
                    field_type = "categorical"
                else:
                    field_type = "text"
            else:
                field_type = "unknown"
            
            results.append({
                "name": field,
                "type": field_type,
                "can_aggregate": field_type == "numeric",
                "can_group": field_type in ["categorical", "text", "datetime", "boolean"],
                "unique_count": len(set(str(v) for v in non_null_values if v is not None)),
                "null_count": len(values) - len(non_null_values),
                "sample_values": non_null_values[:5]
            })
        
        return results
    
    def _looks_like_date(self, value: str) -> bool:
        """Check if a string looks like a date."""
        import re
        date_patterns = [
            r'^\d{4}-\d{2}-\d{2}',  # 2024-01-15
            r'^\d{2}/\d{2}/\d{4}',  # 01/15/2024
            r'^\d{4}/\d{2}/\d{2}',  # 2024/01/15
        ]
        return any(re.match(p, str(value)) for p in date_patterns)


