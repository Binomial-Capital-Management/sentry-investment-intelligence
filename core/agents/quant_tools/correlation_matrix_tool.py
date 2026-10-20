"""
Correlation Matrix Analysis Tool

Computes correlation matrix with advanced analytics including hierarchical clustering,
tail dependence, and empirical copula analysis.

NO HARDCODING: Uses dynamic field discovery for market data.
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import uuid
import json

# Agent framework
from agents import function_tool

# Internal utilities
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.utils.risk_adapter import jsonify_results

# Visualization
from core.visualization.plotly_charts import RiskCharts
from core.agents.risk_tools.shared import register_chart_handle

# Scipy for clustering
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


def _discover_price_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the price field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing price data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    # Priority order for price-related keys (case-insensitive search)
    price_indicators = ['close', 'price', 'adj_close', 'adjusted']

    available_keys = list(data.keys())

    # Search for price-related keys
    for indicator in price_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:  # Ensure non-empty
                    return key

    return None


def _discover_date_field(data: Dict[str, Any]) -> Optional[str]:
    """
    Dynamically discover the date field in FMP data without hardcoding.

    Args:
        data: FMP API response dictionary

    Returns:
        Key name containing date data, or None if not found
    """
    if not data or not isinstance(data, dict):
        return None

    date_indicators = ['date', 'time', 'timestamp']
    available_keys = list(data.keys())

    for indicator in date_indicators:
        for key in available_keys:
            if indicator in key.lower() and isinstance(data[key], (list, np.ndarray)):
                if len(data[key]) > 0:
                    return key

    return None


def _extract_from_row_based(data: Dict[str, Any]) -> Optional[Tuple[List[str], List[float]]]:
    """Extract (dates, prices) from row-based format: {"data": [{"date": ..., "close": ...}, ...]}."""
    if not data or not isinstance(data, dict):
        return None
    rows = data.get("data")
    if not isinstance(rows, list) or len(rows) == 0:
        return None
    dates, prices = [], []
    date_keys, price_keys = ("date", "Date"), ("close", "Close", "price", "Price", "adjClose", "adj_close")
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_val = None
        for k in date_keys:
            if k in row and row[k]:
                date_val = str(row[k]).split()[0] if " " in str(row[k]) else str(row[k])
                break
        price_val = None
        for k in price_keys:
            if k in row and row[k] is not None:
                try:
                    price_val = float(row[k])
                    break
                except (TypeError, ValueError):
                    pass
        if date_val and price_val is not None:
            dates.append(date_val)
            prices.append(price_val)
    return (dates, prices) if len(dates) >= 2 and len(dates) == len(prices) else None


async def _fetch_price_data(
    fmp_server: FMPMarketDataServer,
    ticker: str,
    lookback_days: int
) -> pd.DataFrame:
    """
    Fetch historical price data with dynamic field discovery.

    Args:
        fmp_server: Connected FMP server instance
        ticker: Stock symbol
        lookback_days: Days of historical data

    Returns:
        DataFrame with date and price columns

    Raises:
        ValueError: If data cannot be fetched or parsed
    """
    # Calculate exact date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    data = await fmp_server.fetch_historical_data(
        ticker,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
    )

    if not data or not isinstance(data, dict):
        raise ValueError(f"No data returned for {ticker}")

    date_field = _discover_date_field(data)
    price_field = _discover_price_field(data)

    if date_field and price_field:
        dates, prices = data[date_field], data[price_field]
    else:
        extracted = _extract_from_row_based(data)
        if not extracted:
            raise ValueError(f"No date/price fields for {ticker}. Keys: {list(data.keys())}")
        dates, prices = extracted

    if not dates or not prices:
        raise ValueError(f"Empty data for {ticker}")

    if len(dates) != len(prices):
        raise ValueError(f"Date/price length mismatch for {ticker}: {len(dates)} vs {len(prices)}")

    # Create DataFrame
    df = pd.DataFrame({
        'date': pd.to_datetime(dates),
        'price': prices
    })

    df = df.sort_values('date').reset_index(drop=True)
    df = df.dropna()

    return df


def _calculate_returns_matrix(
    price_data: Dict[str, pd.DataFrame],
    window: Optional[int] = None
) -> pd.DataFrame:
    """
    Calculate returns matrix from price data.

    Args:
        price_data: Dict mapping ticker -> DataFrame with 'date' and 'price'
        window: Optional rolling window for windowed returns

    Returns:
        DataFrame with returns for each ticker (columns = tickers)

    Raises:
        ValueError: If insufficient data or mismatched dates
    """
    # Merge all price data on date
    merged = None
    for ticker, df in price_data.items():
        df_copy = df[['date', 'price']].copy()
        df_copy = df_copy.rename(columns={'price': ticker})

        if merged is None:
            merged = df_copy
        else:
            merged = pd.merge(merged, df_copy, on='date', how='inner')

    if merged is None or len(merged) < 2:
        raise ValueError("Insufficient overlapping data for return calculation")

    # Calculate log returns
    returns_df = merged.copy()
    returns_df = returns_df.set_index('date')

    for ticker in price_data.keys():
        returns_df[ticker] = np.log(returns_df[ticker] / returns_df[ticker].shift(1))

    # Drop first row (NaN from log return)
    returns_df = returns_df.iloc[1:].dropna()

    # Apply rolling window if specified
    if window is not None and window > 1:
        if len(returns_df) < window:
            raise ValueError(f"Insufficient data for window={window}. Have {len(returns_df)} points")
        returns_df = returns_df.iloc[-window:]

    return returns_df


def _calculate_correlation_matrix(
    returns_df: pd.DataFrame,
    method: str = "pearson"
) -> Dict[str, Dict[str, float]]:
    """
    Calculate correlation matrix and convert to nested dict.

    Args:
        returns_df: DataFrame with returns (columns = tickers)
        method: Correlation method ('pearson', 'spearman', 'kendall')

    Returns:
        Nested dictionary: ticker -> ticker -> correlation

    Raises:
        ValueError: If invalid method or insufficient data
    """
    valid_methods = ['pearson', 'spearman', 'kendall']
    if method not in valid_methods:
        raise ValueError(f"Invalid method: {method}. Must be one of {valid_methods}")

    # Calculate correlation matrix
    corr_matrix = returns_df.corr(method=method)

    # Convert to nested dict for OpenAI compatibility
    corr_dict = {}
    for ticker_i in corr_matrix.index:
        corr_dict[ticker_i] = {}
        for ticker_j in corr_matrix.columns:
            corr_dict[ticker_i][ticker_j] = float(corr_matrix.loc[ticker_i, ticker_j])

    return corr_dict


def _calculate_eigenvalues(corr_matrix: pd.DataFrame) -> Tuple[List[float], List[List[float]], float, float]:
    """
    Calculate eigenvalues and diagnostics from correlation matrix.

    Args:
        corr_matrix: pandas DataFrame correlation matrix

    Returns:
        Tuple of (eigenvalues, eigenvectors, condition_number, determinant)
    """
    # Convert to numpy array
    corr_array = corr_matrix.values

    # Calculate eigenvalues and eigenvectors
    eigenvalues, eigenvectors = np.linalg.eigh(corr_array)

    # Sort in descending order
    idx = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Calculate diagnostics
    condition_number = float(eigenvalues[0] / eigenvalues[-1]) if eigenvalues[-1] != 0 else float('inf')
    determinant = float(np.linalg.det(corr_array))

    # Convert to lists for JSON serialization
    eigenvalues_list = [float(ev) for ev in eigenvalues]
    eigenvectors_list = [[float(val) for val in vec] for vec in eigenvectors.T]

    return eigenvalues_list, eigenvectors_list, condition_number, determinant


def _perform_hierarchical_clustering(
    corr_matrix: pd.DataFrame,
    tickers: List[str],
    cluster_count: Optional[int] = None
) -> Dict[str, Any]:
    """
    Perform hierarchical clustering on correlation matrix.

    Args:
        corr_matrix: pandas DataFrame correlation matrix
        tickers: List of ticker symbols
        cluster_count: Number of clusters (auto-determined if None)

    Returns:
        Dictionary with clustering results
    """
    # Convert correlation to distance: distance = 1 - correlation
    distance_matrix = 1 - corr_matrix.values

    # Ensure distance matrix is symmetric and non-negative
    distance_matrix = np.abs(distance_matrix)
    distance_matrix = (distance_matrix + distance_matrix.T) / 2

    # Convert to condensed distance matrix
    condensed_distance = squareform(distance_matrix, checks=False)

    # Perform linkage (Ward's method)
    linkage_matrix = linkage(condensed_distance, method='ward')

    # Determine number of clusters
    if cluster_count is None:
        # Auto-determine: sqrt(n/2) heuristic
        cluster_count = max(2, int(np.sqrt(len(tickers) / 2)))

    # Ensure cluster_count is valid
    cluster_count = min(cluster_count, len(tickers))

    # Assign clusters
    cluster_labels = fcluster(linkage_matrix, cluster_count, criterion='maxclust')

    # Build clusters dict: cluster_id -> list of tickers
    clusters = {}
    for i, ticker in enumerate(tickers):
        cluster_id = int(cluster_labels[i])
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(ticker)

    # Calculate within-cluster average correlation
    cluster_correlations = {}
    for cluster_id, cluster_tickers in clusters.items():
        if len(cluster_tickers) < 2:
            cluster_correlations[cluster_id] = 1.0
            continue

        # Get correlations within cluster
        cluster_indices = [tickers.index(t) for t in cluster_tickers]
        cluster_corr_values = []
        for i in cluster_indices:
            for j in cluster_indices:
                if i < j:
                    cluster_corr_values.append(corr_matrix.iloc[i, j])

        cluster_correlations[cluster_id] = float(np.mean(cluster_corr_values))

    return {
        "cluster_count": int(cluster_count),
        "clusters": {str(k): v for k, v in clusters.items()},
        "cluster_avg_correlation": {str(k): float(v) for k, v in cluster_correlations.items()},
        "method": "ward"
    }


def _calculate_tail_dependence(
    returns_df: pd.DataFrame,
    tail_threshold: float = 0.95
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Calculate tail dependence coefficients (empirical estimator).

    Args:
        returns_df: DataFrame with returns (columns = tickers)
        tail_threshold: Quantile threshold for tail events (default: 0.95)

    Returns:
        Nested dict: ticker_i -> ticker_j -> {'upper': λ_U, 'lower': λ_L}
    """
    tickers = list(returns_df.columns)
    tail_dep = {}

    for i, ticker_i in enumerate(tickers):
        tail_dep[ticker_i] = {}
        returns_i = returns_df[ticker_i].values

        for j, ticker_j in enumerate(tickers):
            if i >= j:
                # Skip diagonal and lower triangle
                continue

            returns_j = returns_df[ticker_j].values

            # Upper tail dependence
            threshold_i_upper = np.quantile(returns_i, tail_threshold)
            threshold_j_upper = np.quantile(returns_j, tail_threshold)

            both_exceed = np.sum((returns_i > threshold_i_upper) & (returns_j > threshold_j_upper))
            either_exceed = np.sum((returns_i > threshold_i_upper) | (returns_j > threshold_j_upper))
            lambda_upper = float(both_exceed / either_exceed) if either_exceed > 0 else 0.0

            # Lower tail dependence
            threshold_i_lower = np.quantile(returns_i, 1 - tail_threshold)
            threshold_j_lower = np.quantile(returns_j, 1 - tail_threshold)

            both_below = np.sum((returns_i < threshold_i_lower) & (returns_j < threshold_j_lower))
            either_below = np.sum((returns_i < threshold_i_lower) | (returns_j < threshold_j_lower))
            lambda_lower = float(both_below / either_below) if either_below > 0 else 0.0

            tail_dep[ticker_i][ticker_j] = {
                "upper": lambda_upper,
                "lower": lambda_lower
            }

    return tail_dep


def _perform_empirical_copula_analysis(
    returns_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Perform empirical copula analysis via rank transformation.

    Args:
        returns_df: DataFrame with returns (columns = tickers)

    Returns:
        Dictionary with copula analysis results
    """
    # Rank transformation to uniform margins
    uniform_marginals = pd.DataFrame()
    for ticker in returns_df.columns:
        ranks = returns_df[ticker].rank(method='average')
        uniform_marginals[ticker] = ranks / (len(returns_df) + 1)

    # Calculate Spearman rank correlation in uniform space
    rank_correlation = uniform_marginals.corr(method='spearman')

    # Convert to nested dict
    rank_corr_dict = {}
    for ticker_i in rank_correlation.index:
        rank_corr_dict[ticker_i] = {}
        for ticker_j in rank_correlation.columns:
            rank_corr_dict[ticker_i][ticker_j] = float(rank_correlation.loc[ticker_i, ticker_j])

    return {
        "rank_correlation_matrix": rank_corr_dict,
        "method": "empirical_copula_spearman",
        "description": "Rank-based correlation in uniform marginal space"
    }


async def analyze_correlation_matrix_internal(
    tickers: List[str],
    method: str = "pearson",
    window: Optional[int] = None,
    lookback_period: int = 252,
    hierarchical_clustering: bool = False,
    copula_analysis: bool = False,
    tail_dependence: bool = False,
    cluster_count: Optional[int] = None,
    tail_threshold: float = 0.95
) -> dict:
    """Internal callable for Canvas - same logic as analyze_correlation_matrix but without @function_tool decorator."""
    try:
        # Input validation
        if not tickers or len(tickers) < 2:
            return {"error": "Invalid tickers", "details": f"Need at least 2 tickers, got {len(tickers) if tickers else 0}"}

        if method not in ['pearson', 'spearman', 'kendall']:
            return {"error": "Invalid correlation method", "details": f"Method must be 'pearson', 'spearman', or 'kendall': {method}"}

        if window is not None and window < 2:
            return {"error": "Invalid window", "details": f"Window must be >= 2: {window}"}

        if lookback_period < 10:
            return {"error": "Invalid lookback period", "details": f"Lookback period must be >= 10 days: {lookback_period}"}

        if window is not None:
            min_lookback = int(window * 1.5) + 10
            if lookback_period < min_lookback:
                lookback_period = min_lookback

        if not 0.5 <= tail_threshold <= 0.99:
            return {"error": "Invalid tail threshold", "details": f"Tail threshold must be between 0.5 and 0.99: {tail_threshold}"}

        fmp_server = FMPMarketDataServer()
        price_data = {}
        skipped_tickers = []

        try:
            await fmp_server.connect()
            logger.info(f"Fetching {lookback_period} days of data for {len(tickers)} tickers")

            for ticker in tickers:
                try:
                    df = await _fetch_price_data(fmp_server, ticker, lookback_period)
                    price_data[ticker] = df
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {ticker}: {e} - skipping")
                    skipped_tickers.append(ticker)
                    continue

            # Check we have enough tickers after skipping failures
            valid_tickers = [t for t in tickers if t in price_data]
            if len(valid_tickers) < 2:
                return {"error": "Insufficient valid tickers", "details": f"Only {len(valid_tickers)} tickers had valid data. Skipped: {skipped_tickers}"}

            returns_df = _calculate_returns_matrix(price_data, window)

            if len(returns_df) < 2:
                return {"error": "Insufficient data", "details": f"Only {len(returns_df)} overlapping return observations"}

            start_date = str(returns_df.index.min().date())
            end_date = str(returns_df.index.max().date())
            sample_size = len(returns_df)

            corr_dict = _calculate_correlation_matrix(returns_df, method)
            corr_matrix_df = pd.DataFrame(corr_dict)
            eigenvalues, eigenvectors, condition_number, determinant = _calculate_eigenvalues(corr_matrix_df)

            # Return summary data (omit large arrays to prevent context overflow)
            # Raw correlation matrix is embedded in cached charts
            result = {
                "status": "success",
                "correlation_matrix": corr_dict,
                # Removed: correlation_matrix_array (duplicate, embedded in chart)
                "method": method,
                "window_days": window,
                "sample_size": sample_size,
                "eigenvalues": eigenvalues,
                # Removed: eigenvectors (can be large, not needed for LLM)
                "condition_number": condition_number,
                "determinant": determinant,
                "tickers": valid_tickers,  # Only tickers with valid data
                "skipped_tickers": skipped_tickers,  # Tickers that failed to fetch
                "start_date": start_date,
                "end_date": end_date,
                "lookback_days": lookback_period,
            }

            # Optional analytics
            if hierarchical_clustering:
                result["hierarchical_clustering"] = _perform_hierarchical_clustering(corr_matrix_df, valid_tickers, cluster_count)

            if copula_analysis:
                result["copula_analysis"] = _perform_empirical_copula_analysis(returns_df)

            if tail_dependence:
                result["tail_dependence"] = {
                    "coefficients": _calculate_tail_dependence(returns_df, tail_threshold),
                    "threshold": tail_threshold,
                }

            # Calculate average correlation
            avg_correlation = np.mean([
                corr_dict[t1][t2]
                for i, t1 in enumerate(valid_tickers)
                for j, t2 in enumerate(valid_tickers)
                if i < j
            ])
            result["avg_correlation"] = avg_correlation

            return result

        except Exception as e:
            logger.error(f"Correlation matrix analysis failed: {e}", exc_info=True)
            return {"error": "Correlation matrix analysis failed", "details": str(e)}
        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Correlation matrix tool failed: {e}", exc_info=True)
        return {"error": "Correlation matrix tool failed", "details": str(e)}


@function_tool
async def analyze_correlation_matrix(
    tickers: List[str],
    method: str = "pearson",
    window: Optional[int] = None,
    lookback_period: int = 252,
    hierarchical_clustering: bool = False,
    copula_analysis: bool = False,
    tail_dependence: bool = False,
    cluster_count: Optional[int] = None,
    tail_threshold: float = 0.95
) -> dict:
    """
    Analyze correlation matrix with advanced analytics.

    **What This Tool Does:**
    - Computes correlation matrix for multiple assets
    - Supports Pearson, Spearman, and Kendall correlations
    - Optional hierarchical clustering to identify asset groups
    - Optional tail dependence analysis for extreme co-movements
    - Optional empirical copula analysis for non-linear dependencies
    - Eigenvalue decomposition for matrix stability diagnostics

    **How to Use:**
    Just call with list of tickers. All data fetching is automatic.
    Example: analyze_correlation_matrix(tickers=['AAPL', 'MSFT', 'GOOGL'])

    **Understanding Results:**
    - correlation_matrix: Pairwise correlations between all assets
    - eigenvalues: Largest eigenvalues indicate dominant risk factors
    - condition_number: High values (>30) indicate near-singularity
    - hierarchical_clustering: Groups of highly correlated assets
    - tail_dependence: Extreme co-movement during market stress
    - copula_analysis: Rank-based correlations (robust to outliers)

    Args:
        tickers: List of asset ticker symbols
        method: Correlation method ('pearson', 'spearman', 'kendall')
        window: Optional rolling window in days (uses last N days)
        lookback_period: Days of historical data to fetch (default: 252)
        hierarchical_clustering: Perform hierarchical clustering (default: False)
        copula_analysis: Perform empirical copula analysis (default: False)
        tail_dependence: Calculate tail dependence (default: False)
        cluster_count: Number of clusters (auto if None)
        tail_threshold: Quantile for tail events (default: 0.95)

    Returns:
        Dict containing:
        {
            "correlation_matrix": Dict[str, Dict[str, float]] - Nested correlation matrix
            "method": str - Correlation method used
            "window_days": Optional[int] - Rolling window size (if used)
            "sample_size": int - Number of return observations
            "eigenvalues": List[float] - Eigenvalues in descending order
            "eigenvectors": List[List[float]] - Corresponding eigenvectors
            "condition_number": float - Matrix condition number (stability metric)
            "determinant": float - Matrix determinant
            "hierarchical_clustering": Optional[Dict] - Clustering results
            "copula_analysis": Optional[Dict] - Copula analysis results
            "tail_dependence": Optional[Dict] - Tail dependence coefficients
            "tickers": List[str] - Asset symbols analyzed
            "start_date": str - First data point date
            "end_date": str - Last data point date
            "lookback_days": int - Requested lookback period
            "summary": str - Human-readable summary
        }

        On error, returns:
        {
            "error": str - Error message
            "details": str - Additional details
        }

    Examples:
        # Basic correlation matrix
        result = await analyze_correlation_matrix(
            tickers=['SPY', 'TLT', 'GLD', 'USO']
        )
        print(result['correlation_matrix'])

        # Advanced analysis with clustering
        result = await analyze_correlation_matrix(
            tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA'],
            method='spearman',
            hierarchical_clustering=True,
            tail_dependence=True,
            copula_analysis=True
        )

        # Rolling window correlation
        result = await analyze_correlation_matrix(
            tickers=['SPY', 'QQQ', 'IWM'],
            window=60,  # Last 60 days only
            lookback_period=365
        )
    """
    try:
        # Input validation
        if not tickers or len(tickers) < 2:
            return jsonify_results({
                "error": "Invalid tickers",
                "details": f"Need at least 2 tickers, got {len(tickers) if tickers else 0}"
            })

        if method not in ['pearson', 'spearman', 'kendall']:
            return jsonify_results({
                "error": "Invalid correlation method",
                "details": f"Method must be 'pearson', 'spearman', or 'kendall': {method}"
            })

        if window is not None and window < 2:
            return jsonify_results({
                "error": "Invalid window",
                "details": f"Window must be >= 2: {window}"
            })

        if lookback_period < 10:
            return jsonify_results({
                "error": "Invalid lookback period",
                "details": f"Lookback period must be >= 10 days: {lookback_period}"
            })

        # Ensure lookback_period is sufficient for window (account for weekends/holidays)
        # Trading days ≈ 70% of calendar days, plus buffer for returns calculation
        if window is not None:
            min_lookback = int(window * 1.5) + 10  # ~1.5x for weekends + buffer
            if lookback_period < min_lookback:
                logger.info(f"Increasing lookback_period from {lookback_period} to {min_lookback} for window={window}")
                lookback_period = min_lookback

        if not 0.5 <= tail_threshold <= 0.99:
            return jsonify_results({
                "error": "Invalid tail threshold",
                "details": f"Tail threshold must be between 0.5 and 0.99: {tail_threshold}"
            })

        # Connect to FMP server
        fmp_server = FMPMarketDataServer()
        price_data = {}
        skipped_tickers = []

        try:
            await fmp_server.connect()

            # Fetch price data for all tickers - skip unknown ones
            logger.info(f"Fetching {lookback_period} days of data for {len(tickers)} tickers")

            for ticker in tickers:
                try:
                    df = await _fetch_price_data(fmp_server, ticker, lookback_period)
                    price_data[ticker] = df
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {ticker}: {e} - skipping")
                    skipped_tickers.append(ticker)
                    continue
            
            # Check we have enough valid tickers
            valid_tickers = [t for t in tickers if t in price_data]
            if len(valid_tickers) < 2:
                return jsonify_results({
                    "error": "Insufficient valid tickers",
                    "details": f"Only {len(valid_tickers)} tickers had valid data. Skipped: {skipped_tickers}"
                })

            # Calculate returns matrix
            returns_df = _calculate_returns_matrix(price_data, window)

            if len(returns_df) < 2:
                return jsonify_results({
                    "error": "Insufficient data",
                    "details": f"Only {len(returns_df)} overlapping return observations"
                })

            # Get date range
            start_date = str(returns_df.index.min().date())
            end_date = str(returns_df.index.max().date())
            sample_size = len(returns_df)

            # Calculate correlation matrix
            corr_dict = _calculate_correlation_matrix(returns_df, method)

            # Convert dict back to DataFrame for eigenvalue calculation
            corr_matrix_df = pd.DataFrame(corr_dict)

            # Calculate eigenvalues and diagnostics
            eigenvalues, eigenvectors, condition_number, determinant = _calculate_eigenvalues(corr_matrix_df)

            # Generate correlation heatmap chart
            charts_list = []
            try:
                charts = RiskCharts(color_scheme='binomial_blue')
                chart_title = f"Correlation Matrix ({method.capitalize()}) - {len(tickers)} Assets"
                correlation_chart = charts.plot_correlation_matrix(
                    correlation=corr_matrix_df,
                    title=chart_title,
                    height=600
                )
                plotly_payload = correlation_chart.to_json()
                try:
                    plotly_payload = json.loads(plotly_payload)
                except Exception:
                    pass
                if isinstance(plotly_payload, str):
                    raise ValueError("Correlation chart payload not JSON-serializable")
                charts_list.append(
                    register_chart_handle(
                        plotly_payload,
                        chart_type="correlation_matrix",
                        title=chart_title,
                        alt_text=f"Interactive heatmap showing {method} correlation coefficients between {len(tickers)} assets",
                        metadata={"method": method, "tickers": tickers},
                        chart_id=str(uuid.uuid4()),
                    )
                )
            except Exception as chart_error:
                logger.warning(f"Chart generation failed: {chart_error}")

            # Build base result (omit large arrays to prevent context overflow)
            result = {
                "correlation_matrix": corr_dict,
                "method": method,
                "window_days": window,
                "sample_size": sample_size,
                "eigenvalues": eigenvalues,
                # Removed: eigenvectors (can be large, not needed for LLM interpretation)
                "condition_number": condition_number,
                "determinant": determinant,
                "tickers": valid_tickers,
                "skipped_tickers": skipped_tickers,  # Tickers that couldn't be fetched
                "start_date": start_date,
                "end_date": end_date,
                "lookback_days": lookback_period,
                "charts": charts_list  # Chart handles (full data cached server-side)
            }

            # Optional: Hierarchical clustering
            if hierarchical_clustering:
                clustering_result = _perform_hierarchical_clustering(
                    corr_matrix_df, tickers, cluster_count
                )
                result["hierarchical_clustering"] = clustering_result

            # Optional: Copula analysis
            if copula_analysis:
                copula_result = _perform_empirical_copula_analysis(returns_df)
                result["copula_analysis"] = copula_result

            # Optional: Tail dependence
            if tail_dependence:
                tail_dep = _calculate_tail_dependence(returns_df, tail_threshold)
                result["tail_dependence"] = {
                    "coefficients": tail_dep,
                    "threshold": tail_threshold,
                    "description": "Empirical tail dependence (upper/lower)"
                }

            # Build summary
            avg_correlation = np.mean([
                corr_dict[t1][t2]
                for i, t1 in enumerate(valid_tickers)
                for j, t2 in enumerate(valid_tickers)
                if i < j
            ])

            summary = (
                f"Correlation matrix for {len(valid_tickers)} assets using {method} method. "
                f"Average pairwise correlation: {avg_correlation:.4f}. "
                f"Sample size: {sample_size} returns from {start_date} to {end_date}. "
                f"Condition number: {condition_number:.2f} (stability metric). "
            )
            
            if skipped_tickers:
                summary += f"Skipped {len(skipped_tickers)} unknown tickers: {', '.join(skipped_tickers)}. "

            if hierarchical_clustering:
                summary += f"Identified {result['hierarchical_clustering']['cluster_count']} clusters. "

            if tail_dependence:
                summary += f"Tail dependence calculated at {tail_threshold:.2%} quantile. "

            result["summary"] = summary

            return jsonify_results(result)

        except Exception as e:
            logger.error(f"Correlation matrix analysis failed: {e}", exc_info=True)
            return jsonify_results({
                "error": "Correlation matrix analysis failed",
                "details": str(e)
            })
        finally:
            await fmp_server.cleanup()

    except Exception as e:
        logger.error(f"Correlation matrix tool failed: {e}", exc_info=True)
        return jsonify_results({
            "error": "Correlation matrix tool failed",
            "details": str(e)
        })
