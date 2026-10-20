"""
Comparable Companies Analysis Module
Production-grade peer analysis with football field visualization support.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValuationRange:
    """Structured valuation range for a single method/multiple."""
    method: str
    bear_case: float
    base_case: float
    bull_case: float
    current_price: Optional[float] = None
    implied_value: Optional[float] = None


class ComparableAnalysis:
    """
    Comparable companies analysis using trading multiples.
    Supports statistical peer comparison, fair value estimation,
    and football field visualization data generation.
    """
    
    # Constants for outlier detection
    OUTLIER_IQR_MULTIPLIER = 1.5
    MIN_PEERS_FOR_STATS = 2
    MIN_PEERS_FOR_QUARTILES = 3
    
    def __init__(self, percentiles: List[float] = None):
        """
        Initialize comparable analysis.
        
        Args:
            percentiles: Percentile levels for ranges (default: [10, 25, 50, 75, 90])
        """
        self.percentiles = percentiles or [10, 25, 50, 75, 90]
    
    def analyze_comparables(
        self,
        target: str,
        peers: List[str],
        data: Dict[str, Any],
        method: str = "all"
    ) -> Dict[str, Any]:
        """
        Calculate peer statistics and valuation ranges.
        
        Args:
            target: Target ticker symbol
            peers: List of peer ticker symbols
            data: Combined data from FMP with structure:
                  {"ticker_data": {ticker: {field: value}}, ...}
            method: Analysis method - "all", "median", "mean"
        
        Returns:
            Dictionary with peer statistics, rankings, valuation ranges, and football field data
        """
        try:
            ticker_data = data.get("ticker_data", {})
            
            # Validate target data exists
            if target not in ticker_data:
                raise ValueError(f"No data found for target {target}")
            
            target_data = ticker_data[target]
            
            # Check for target fetch errors
            if "error" in target_data:
                raise ValueError(f"Error fetching target {target}: {target_data['error']}")
            
            # Build peer data, tracking which peers have valid data
            peer_data = {}
            failed_peers = []
            for peer in peers:
                if peer in ticker_data:
                    peer_info = ticker_data[peer]
                    if "error" not in peer_info:
                        peer_data[peer] = peer_info
                    else:
                        failed_peers.append(peer)
                        logger.warning(f"Peer {peer} had fetch error: {peer_info.get('error')}")
                else:
                    failed_peers.append(peer)
                    logger.warning(f"Peer {peer} not found in data")
            
            if not peer_data:
                raise ValueError(f"No valid peer data available. Failed peers: {failed_peers}")
            
            # Calculate statistics for each field
            field_statistics = self._calculate_field_statistics(target_data, peer_data)
            
            if not field_statistics:
                raise ValueError("No valid numeric fields found for comparison")
            
            # Build comparison table
            comparison_table = self._build_comparison_table(
                target, target_data, peer_data, field_statistics
            )
            
            # Generate valuation ranges
            valuation_ranges = self._generate_valuation_ranges(field_statistics, target_data)
            
            # Generate football field data
            football_field = self._generate_football_field(
                target, target_data, field_statistics
            )
            
            # Create summary
            summary = {
                "target": target,
                "peer_count": len(peer_data),
                "failed_peers": failed_peers if failed_peers else None,
                "fields_analyzed": len(field_statistics),
                "data_quality": self._assess_data_quality(field_statistics)
            }
            
            return {
                "summary": summary,
                "field_statistics": field_statistics,
                "comparison_table": comparison_table,
                "valuation_ranges": valuation_ranges,
                "football_field": football_field
            }
            
        except Exception as e:
            logger.error(f"Error in analyze_comparables: {e}")
            raise
    
    # Fields to exclude from comparable analysis (not valuation multiples)
    EXCLUDED_FIELDS = {"price", "marketCap", "market_cap", "stockPrice", "marketCapitalization"}
    
    def _calculate_field_statistics(
        self,
        target_data: Dict,
        peer_data: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Calculate statistics for each numeric field across peers."""
        field_statistics = {}
        
        # Get all numeric fields that exist in at least one peer
        all_fields = set()
        for peer_values in peer_data.values():
            for field, value in peer_values.items():
                # Skip excluded fields (not valuation multiples)
                if field.lower() in {f.lower() for f in self.EXCLUDED_FIELDS}:
                    continue
                if field != "error" and self._is_valid_numeric(value):
                    all_fields.add(field)
        
        for field in all_fields:
            # Collect peer values for this field
            peer_values = []
            peer_tickers = []
            
            for peer, values in peer_data.items():
                if field in values:
                    val = values[field]
                    if self._is_valid_numeric(val):
                        float_val = float(val)
                        # Only include positive values for multiple-type fields
                        if float_val > 0:
                            peer_values.append(float_val)
                            peer_tickers.append(peer)
            
            if len(peer_values) < self.MIN_PEERS_FOR_STATS:
                continue
            
            # Calculate core statistics
            stats = self._compute_statistics(peer_values)
            stats["peer_count"] = len(peer_values)
            stats["peers_included"] = peer_tickers
            
            # Add percentiles
            for p in self.percentiles:
                stats[f"p{int(p)}"] = round(float(np.percentile(peer_values, p)), 2)
            
            # Add target comparison if target has this field
            if field in target_data and self._is_valid_numeric(target_data[field]):
                target_value = float(target_data[field])
                if target_value > 0:
                    stats["target_value"] = round(target_value, 2)
                    
                    # Calculate relative position vs median
                    if stats["median"] and stats["median"] != 0:
                        stats["target_vs_median_pct"] = round(
                            ((target_value / stats["median"]) - 1) * 100, 1
                        )
                    
                    # Calculate percentile rank of target
                    stats["target_percentile"] = round(
                        float(np.sum(np.array(peer_values) <= target_value) / len(peer_values) * 100),
                        1
                    )
                    
                    # Determine if target is outlier
                    q1 = stats.get("p25", stats.get("p10", stats["min"]))
                    q3 = stats.get("p75", stats.get("p90", stats["max"]))
                    iqr = q3 - q1
                    lower_bound = q1 - (self.OUTLIER_IQR_MULTIPLIER * iqr)
                    upper_bound = q3 + (self.OUTLIER_IQR_MULTIPLIER * iqr)
                    stats["target_is_outlier"] = target_value < lower_bound or target_value > upper_bound
            
            field_statistics[field] = stats
        
        return field_statistics
    
    def _compute_statistics(self, values: List[float]) -> Dict[str, Any]:
        """Compute core statistics for a list of values."""
        arr = np.array(values)
        return {
            "mean": round(float(np.mean(arr)), 2),
            "median": round(float(np.median(arr)), 2),
            "std": round(float(np.std(arr)), 2) if len(arr) > 1 else 0.0,
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
        }
    
    def _is_valid_numeric(self, value: Any) -> bool:
        """Check if a value is a valid finite scalar number."""
        # Reject None
        if value is None:
            return False
        
        # Reject pandas Series, numpy arrays, lists (non-scalar types)
        if isinstance(value, (list, tuple)):
            return False
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # This catches pandas Series, numpy arrays, etc.
            return False
        
        # Accept numpy scalar types
        if isinstance(value, np.number):
            return bool(np.isfinite(value))
        
        # Accept Python int/float
        if isinstance(value, (int, float)):
            return bool(np.isfinite(value))
        
        return False
    
    def _build_comparison_table(
        self,
        target: str,
        target_data: Dict,
        peer_data: Dict,
        field_statistics: Dict
    ) -> pd.DataFrame:
        """Build a comparison table as DataFrame."""
        try:
            rows = []
            fields = list(field_statistics.keys())
            
            # Add target row first (highlighted)
            target_row = {"Company": f"► {target}"}
            for field in fields:
                if field in target_data and self._is_valid_numeric(target_data[field]):
                    target_row[field] = round(float(target_data[field]), 2)
                else:
                    target_row[field] = None
            rows.append(target_row)
            
            # Add peer rows sorted by first available field value
            peer_rows = []
            for peer, data in peer_data.items():
                peer_row = {"Company": peer}
                for field in fields:
                    if field in data and self._is_valid_numeric(data[field]):
                        peer_row[field] = round(float(data[field]), 2)
                    else:
                        peer_row[field] = None
                peer_rows.append(peer_row)
            
            # Sort peers by first field value if available
            if fields and peer_rows:
                first_field = fields[0]
                peer_rows.sort(key=lambda x: x.get(first_field) or float('inf'))
            
            rows.extend(peer_rows)
            
            # Add separator and statistics rows
            rows.append({"Company": "─" * 12})  # Visual separator
            
            stats_rows = [
                {"Company": "Peer Median", "_type": "median"},
                {"Company": "Peer Mean", "_type": "mean"},
                {"Company": f"Peer P{int(self.percentiles[1]) if len(self.percentiles) > 1 else 25}", "_type": "p_low"},
                {"Company": f"Peer P{int(self.percentiles[-2]) if len(self.percentiles) > 1 else 75}", "_type": "p_high"},
            ]
            
            for row in stats_rows:
                row_type = row.pop("_type")
                for field, stats in field_statistics.items():
                    if row_type == "median":
                        row[field] = stats.get("median")
                    elif row_type == "mean":
                        row[field] = stats.get("mean")
                    elif row_type == "p_low":
                        p_key = f"p{int(self.percentiles[1])}" if len(self.percentiles) > 1 else "p25"
                        row[field] = stats.get(p_key)
                    elif row_type == "p_high":
                        p_key = f"p{int(self.percentiles[-2])}" if len(self.percentiles) > 1 else "p75"
                        row[field] = stats.get(p_key)
            
            rows.extend(stats_rows)
            
            df = pd.DataFrame(rows)
            
            # Ensure unique index by adding suffix to duplicates
            company_counts = {}
            unique_companies = []
            for company in df["Company"]:
                if company in company_counts:
                    company_counts[company] += 1
                    unique_companies.append(f"{company} ({company_counts[company]})")
                else:
                    company_counts[company] = 1
                    unique_companies.append(company)
            df["Company"] = unique_companies
            
            df = df.set_index("Company")
            
            return df
            
        except Exception as e:
            logger.error(f"Error building comparison table: {e}")
            return pd.DataFrame()
    
    def _generate_valuation_ranges(
        self,
        field_statistics: Dict,
        target_data: Dict
    ) -> Dict[str, Any]:
        """Generate valuation ranges based on peer multiples."""
        ranges = {}
        
        for field, stats in field_statistics.items():
            if stats.get("peer_count", 0) < self.MIN_PEERS_FOR_QUARTILES:
                continue
            
            # Use P25 for bear, median for base, P75 for bull
            p_low = self.percentiles[1] if len(self.percentiles) > 1 else 25
            p_high = self.percentiles[-2] if len(self.percentiles) > 1 else 75
            
            bear_val = stats.get(f"p{int(p_low)}")
            base_val = stats.get("median")
            bull_val = stats.get(f"p{int(p_high)}")
            
            if bear_val is None or base_val is None or bull_val is None:
                continue
            
            range_data = {
                "bear": round(bear_val, 2),
                "base": round(base_val, 2),
                "bull": round(bull_val, 2),
                "peer_count": stats.get("peer_count"),
                "spread_pct": round((bull_val - bear_val) / base_val * 100, 1) if base_val else None
            }
            
            # Add target position if available
            if "target_value" in stats:
                range_data["target_value"] = stats["target_value"]
                range_data["target_percentile"] = stats.get("target_percentile")
                range_data["target_is_outlier"] = stats.get("target_is_outlier", False)
            
            ranges[field] = range_data
        
        return ranges
    
    def _generate_football_field(
        self,
        target: str,
        target_data: Dict,
        field_statistics: Dict
    ) -> Dict[str, Any]:
        """
        Generate football field visualization data.
        
        Returns a structure with valuation ranges from different methods
        that can be rendered as a horizontal bar chart showing:
        - Low/High range as bar
        - Median/base case as marker
        - Current price as vertical line
        """
        current_price = target_data.get("price")
        if current_price is None or not self._is_valid_numeric(current_price):
            # Try alternate price fields
            for price_field in ["stockPrice", "currentPrice", "lastPrice"]:
                if price_field in target_data and self._is_valid_numeric(target_data[price_field]):
                    current_price = float(target_data[price_field])
                    break
        
        if current_price is None:
            current_price = None
        else:
            current_price = round(float(current_price), 2)
        
        # Build valuation methods
        methods = []
        implied_values = []
        
        # Multiple-based implied values
        for field, stats in field_statistics.items():
            if "target_value" not in stats:
                continue
            if stats.get("peer_count", 0) < self.MIN_PEERS_FOR_QUARTILES:
                continue
            
            target_multiple = stats["target_value"]
            if target_multiple <= 0:
                continue
            
            peer_median = stats.get("median")
            if not peer_median or peer_median <= 0:
                continue
            
            # Get percentile values for range
            p_low = self.percentiles[1] if len(self.percentiles) > 1 else 25
            p_high = self.percentiles[-2] if len(self.percentiles) > 1 else 75
            
            peer_p25 = stats.get(f"p{int(p_low)}")
            peer_p75 = stats.get(f"p{int(p_high)}")
            
            if not peer_p25 or not peer_p75:
                continue
            
            if current_price and target_multiple > 0:
                # Calculate target's underlying fundamental: Fundamental = Price / Multiple
                # Then apply peer multiples: Implied Price = Fundamental × Peer Multiple
                target_fundamental = current_price / target_multiple

                implied_low = round(target_fundamental * peer_p25, 2)
                implied_base = round(target_fundamental * peer_median, 2)
                implied_high = round(target_fundamental * peer_p75, 2)
                
                methods.append({
                    "method": f"Comps: {field}",
                    "low": implied_low,
                    "base": implied_base,
                    "high": implied_high,
                    "peer_count": stats.get("peer_count"),
                    "target_multiple": target_multiple,
                    "peer_median_multiple": peer_median
                })
                
                implied_values.append(implied_base)
        
        # Calculate composite fair value
        composite = None
        if implied_values:
            composite = {
                "mean": round(float(np.mean(implied_values)), 2),
                "median": round(float(np.median(implied_values)), 2),
                "min": round(float(np.min(implied_values)), 2),
                "max": round(float(np.max(implied_values)), 2),
            }
            
            if current_price:
                composite["upside_to_mean_pct"] = round(
                    (composite["mean"] / current_price - 1) * 100, 1
                )
                composite["upside_to_median_pct"] = round(
                    (composite["median"] / current_price - 1) * 100, 1
                )
        
        return {
            "target": target,
            "current_price": current_price,
            "methods": methods,
            "method_count": len(methods),
            "composite_fair_value": composite,
            "visualization_hint": (
                "Render as horizontal bars: each method shows low-high range with base marker. "
                "Add vertical line for current_price. Sort by base case value."
            )
        }
    
    def _assess_data_quality(self, field_statistics: Dict) -> Dict[str, Any]:
        """Assess the quality of the data."""
        total_fields = len(field_statistics)
        if total_fields == 0:
            return {
                "total_fields": 0,
                "quality_score": "poor",
                "recommendation": "Insufficient data for comparison"
            }
        
        good_coverage = sum(
            1 for stats in field_statistics.values()
            if stats.get("peer_count", 0) >= 4
        )
        
        with_target = sum(
            1 for stats in field_statistics.values()
            if "target_value" in stats
        )
        
        coverage_ratio = good_coverage / total_fields
        target_ratio = with_target / total_fields
        
        # Determine quality score
        if coverage_ratio >= 0.7 and target_ratio >= 0.7:
            quality = "excellent"
        elif coverage_ratio >= 0.5 and target_ratio >= 0.5:
            quality = "good"
        elif coverage_ratio >= 0.3 or target_ratio >= 0.3:
            quality = "fair"
        else:
            quality = "poor"
        
        return {
            "total_fields": total_fields,
            "fields_with_good_coverage": good_coverage,
            "fields_with_target_data": with_target,
            "coverage_ratio": round(coverage_ratio, 2),
            "target_data_ratio": round(target_ratio, 2),
            "quality_score": quality
        }
    
    def calculate_simple_fair_value(
        self,
        target_data: Dict,
        field_stats: Dict
    ) -> Optional[Dict]:
        """
        Calculate fair value using peer multiples.
        Fair value = Current Price × (Peer Multiple / Target Multiple)
        """
        current_price = target_data.get("price")
        if current_price is None or not self._is_valid_numeric(current_price):
            return None
        
        current_price = float(current_price)
        fair_values = []
        valuations_by_multiple = []
        
        # Fields to skip - not valuation multiples
        skip_fields = {"price", "marketCap", "market_cap", "stockPrice", "marketCapitalization"}
        
        for field, stats in field_stats.items():
            # Skip non-ratio fields
            if field.lower() in {f.lower() for f in skip_fields}:
                continue
                
            target_val = stats.get("target_value")
            if not target_val or target_val <= 0:
                continue
            
            peer_median = stats.get("median")
            if not peer_median or peer_median <= 0:
                continue
            
            # Calculate fair value
            fair_val = current_price * (peer_median / target_val)
            discount_premium = (target_val / peer_median - 1) * 100
            
            valuations_by_multiple.append({
                "field": field,
                "fair_value": round(fair_val, 2),
                "peer_multiple": round(peer_median, 2),
                "target_multiple": round(target_val, 2),
                "discount_premium_pct": round(discount_premium, 1),
                "peer_count": stats.get("peer_count", 0)
            })
            fair_values.append(fair_val)
        
        if not fair_values:
            return None
        
        avg_fair_value = float(np.mean(fair_values))
        median_fair_value = float(np.median(fair_values))
        
        return {
            "current_price": round(current_price, 2),
            "fair_value_mean": round(avg_fair_value, 2),
            "fair_value_median": round(median_fair_value, 2),
            "upside_pct_mean": round((avg_fair_value / current_price - 1) * 100, 1),
            "upside_pct_median": round((median_fair_value / current_price - 1) * 100, 1),
            "valuations_by_multiple": valuations_by_multiple,
            "multiples_used": len(valuations_by_multiple)
        }
