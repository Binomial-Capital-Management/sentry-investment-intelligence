"""
XGBoost Feature Importance Tool
Identifies predictive features for stock returns using XGBoost-based importance analysis
Based on StockPredictionAI approach following PCA and ARIMA tool patterns
"""

from agents import function_tool
from typing import List, Optional, Dict, Any, Tuple
import ast
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import re
import json

# XGBoost and ML imports
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.inspection import permutation_importance
import shap

# Project imports
from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer
from core.utils.mcp_result_parser import safe_parse_json
from core.charts.models import ChartSpec, ChartType, ChartPriority
from core.utils.risk_adapter import jsonify_results
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
import plotly.graph_objects as go
from plotly.subplots import make_subplots

load_dotenv()
logger = logging.getLogger(__name__)


async def analyze_feature_importance_internal(
    tickers: List[str],
    target_variable: str = "future_5day_return",
    period: str = "1Y",
    features: Optional[List[str]] = None,
    train_test_split_ratio: float = 0.8,
    importance_methods: Optional[List[str]] = None,
    cv_folds: int = 3,
    top_n_features: int = 15,
    include_technical_indicators: bool = True,
    feature_windows_json: Optional[str] = None,
    n_estimators: int = 50,
    learning_rate: float = 0.1,
    max_depth: int = 5,
    base_score: float = 0.5,
    early_stopping_rounds: Optional[int] = 5,
    min_data_points: int = 100,
    permutation_repeats: int = 8,
    random_seed: Optional[int] = None
) -> dict:
    """
    Internal implementation for Canvas and direct calls.
    Returns raw dict (not JSON string).
    """
    logger.info(f"🎯 Starting XGBoost feature importance analysis for {tickers}")

    try:
        # Normalize requested importance methods
        if not importance_methods:
            importance_methods = ["gain", "permutation", "shap"]
        else:
            importance_methods = [m.lower() for m in importance_methods]

        # Parse feature windows JSON if provided
        feature_windows_config = None
        if feature_windows_json:
            try:
                feature_windows_config = json.loads(feature_windows_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in feature_windows_json: {e}")

        # Set default windows if not provided
        feature_windows = feature_windows_config if feature_windows_config else {
            'returns': [1, 5, 20],
            'momentum': [10, 20],
            'volatility': [10, 20],
            'volume_ma': [20],
            'ma': [5, 20]
        }

        # Validate inputs
        if not tickers:
            raise ValueError("At least one ticker symbol is required")
        if not 0 < train_test_split_ratio < 1:
            raise ValueError("train_test_split_ratio must be between 0 and 1")
        if cv_folds < 2:
            raise ValueError("cv_folds must be at least 2")

        # Step 1: Fetch and engineer features
        logger.info("📊 Fetching historical data and engineering features...")
        feature_df = await _fetch_and_engineer_features(
            tickers=tickers,
            period=period,
            features=features,
            include_technical_indicators=include_technical_indicators,
            feature_windows_config=feature_windows
        )

        if len(feature_df) < min_data_points:
            raise ValueError(
                f"Insufficient data: {len(feature_df)} points, minimum {min_data_points} required"
            )

        # Step 2: Create target variable and prepare data
        logger.info(f"🎯 Creating target variable: {target_variable}")
        X, y, feature_names = await _prepare_features_and_target(
            feature_df=feature_df,
            target_variable=target_variable
        )

        # Step 3: Train XGBoost model
        logger.info("🤖 Training XGBoost model...")
        model, train_metrics, test_metrics = await _train_xgboost_model(
            X=X,
            y=y,
            train_test_split_ratio=train_test_split_ratio,
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            base_score=base_score,
            early_stopping_rounds=early_stopping_rounds,
            cv_folds=cv_folds,
            random_seed=random_seed
        )

        # Step 4: Calculate importance scores
        logger.info("📈 Calculating feature importance...")
        importance_scores = await _calculate_importance_scores(
            model=model,
            X=X,
            y=y,
            feature_names=feature_names,
            importance_methods=importance_methods,
            train_test_split_ratio=train_test_split_ratio,
            permutation_repeats=permutation_repeats,
            random_seed=random_seed
        )

        # Step 5: Generate top features ranking
        top_features = _rank_top_features(
            importance_scores=importance_scores,
            top_n=top_n_features
        )

        # Step 6: Calculate feature correlations
        correlation_matrix = _calculate_feature_correlations(
            X=X,
            feature_names=feature_names,
            top_features=top_features
        )

        # Compile results (no charts - Canvas builds its own)
        results = {
            'tickers': tickers,
            'feature_importance': importance_scores,
            'model_metrics': {
                'train': train_metrics,
                'test': test_metrics
            },
            'top_features': top_features,
            # Removed: feature_correlations matrix (embedded in cached heatmap chart)
            'feature_correlations_summary': {
                'n_features': len([f["feature"] for f in top_features[:top_n_features]]),
                'feature_names': [f["feature"] for f in top_features[:top_n_features]]
            },
            'metadata': {
                'target_variable': target_variable,
                'period': period,
                'n_features': len(feature_names),
                'n_samples': len(X),
                'train_test_split': train_test_split_ratio,
                'importance_methods': importance_methods,
                'feature_windows': feature_windows,
                'model_params': {
                    'n_estimators': n_estimators,
                    'learning_rate': learning_rate,
                    'max_depth': max_depth,
                    'base_score': base_score
                },
                'analysis_date': datetime.now().isoformat()
            }
        }

        logger.info(f"✅ Feature importance analysis complete: {len(top_features)} features ranked")

        return {
            'status': 'success',
            'results': results
        }

    except Exception as e:
        logger.error(f"❌ Feature importance analysis failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'tickers': tickers
        }


@function_tool
async def analyze_feature_importance(
    tickers: List[str],
    target_variable: str = "future_5day_return",
    period: str = "1Y",
    features: Optional[List[str]] = None,
    train_test_split_ratio: float = 0.8,
    importance_methods: Optional[List[str]] = None,
    cv_folds: int = 3,
    top_n_features: int = 15,
    include_technical_indicators: bool = True,
    feature_windows_json: Optional[str] = None,
    n_estimators: int = 50,
    learning_rate: float = 0.1,
    max_depth: int = 5,
    base_score: float = 0.5,
    early_stopping_rounds: Optional[int] = 5,
    min_data_points: int = 100,
    permutation_repeats: int = 8,
    random_seed: Optional[int] = None
) -> dict:
    """
    Perform XGBoost feature importance analysis to identify predictive factors for stock returns.

    This tool trains an XGBoost regression model to predict future returns and analyzes which features
    (technical indicators, fundamental metrics, computed features) have the most predictive power.

    ALL PARAMETERS EXPOSED - NO HARDCODING

    Args:
        tickers: List of stock symbols to analyze (minimum 1 required)
        target_variable: What to predict (e.g., "future_5day_return", "future_20day_return")
        period: Historical data period ("1M", "3M", "6M", "1Y", "2Y", "5Y", "max")
        features: Explicit feature list OR None for auto-discovery via FMP technical fields
        train_test_split_ratio: Proportion of data for training (default: 0.8)
        importance_methods: Methods to compute ["gain", "permutation", "shap"] (default: all three)
        cv_folds: Cross-validation folds for model robustness (default: 5)
        top_n_features: Show top N features in charts (default: 20)
        include_technical_indicators: Auto-compute MA, RSI, MACD, momentum, etc. (default: True)
        feature_windows_json: JSON string specifying windows for feature engineering
            Example: '{{"returns": [1, 5, 20], "momentum": [10, 20], "volatility": [10, 20]}}'
            If None, uses defaults: returns=[1,5,20], momentum=[10,20], volatility=[10,20], volume_ma=[20], ma=[5,20]
        n_estimators: Number of boosting rounds (default: 50)
        learning_rate: XGBoost learning rate (default: 0.1)
        max_depth: Maximum tree depth (default: 5)
        base_score: Initial prediction score for XGBoost (default: 0.5, required for SHAP compatibility with XGBoost 2.0+)
        early_stopping_rounds: Stop if no improvement (default: 5, None = disable)
        min_data_points: Minimum required data points (default: 100)
        permutation_repeats: Number of permutations for importance calculation (default: 8)
        random_seed: Random seed for reproducibility (None = use 42)

    Returns:
        Dict containing:
        - feature_importance: {method: {feature: score}} for each method
        - model_metrics: R², MAE, RMSE, CV scores
        - top_features: Ranked list with contribution percentages
        - feature_correlations: Correlation matrix for top features
        - charts: [importance_bars, permutation_comparison, shap_summary, correlation_heatmap]
        - metadata: Analysis configuration and parameters

    Example:
        # Analyze AAPL with default settings
        result = await analyze_feature_importance(
            tickers=['AAPL'],
            period="1Y"
        )

        # Custom configuration with custom windows and parameters
        result = await analyze_feature_importance(
            tickers=['AAPL', 'MSFT'],
            target_variable="future_20day_return",
            period="2Y",
            importance_methods=["gain", "shap"],
            top_n_features=15,
            feature_windows_json='{"returns": [1, 5, 10, 20], "momentum": [5, 10, 20, 50]}',
            n_estimators=150,
            base_score=0.5  # Required for SHAP compatibility with XGBoost 2.0+
        )
    """
    # Call internal implementation and wrap with jsonify_results for agent use
    result = await analyze_feature_importance_internal(
        tickers=tickers,
        target_variable=target_variable,
        period=period,
        features=features,
        train_test_split_ratio=train_test_split_ratio,
        importance_methods=importance_methods,
        cv_folds=cv_folds,
        top_n_features=top_n_features,
        include_technical_indicators=include_technical_indicators,
        feature_windows_json=feature_windows_json,
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        base_score=base_score,
        early_stopping_rounds=early_stopping_rounds,
        min_data_points=min_data_points,
        permutation_repeats=permutation_repeats,
        random_seed=random_seed
    )
    
    # Generate charts for agent use
    if result.get('status') == 'success':
        results = result.get('results', {})
        importance_scores = results.get('feature_importance', {})
        top_features = results.get('top_features', [])
        correlation_matrix = results.get('feature_correlations', {}).get('matrix', [])
        feature_names = [f['feature'] for f in top_features]
        
        charts = []
        
        # Chart 1: Feature Importance Bars (Gain)
        if "gain" in importance_scores:
            chart = await _build_importance_bars(
                importance_scores=importance_scores["gain"],
                feature_names=feature_names,
                top_n=top_n_features,
                tickers=tickers,
                chart_id=f"feature_importance_gain_{'_'.join(tickers)}"
            )
            charts.append(chart)
        
        # Chart 2: Permutation vs Gain Comparison
        if "permutation" in importance_scores and "gain" in importance_scores:
            chart = await _build_permutation_comparison(
                gain_scores=importance_scores["gain"],
                perm_scores=importance_scores["permutation"],
                feature_names=feature_names,
                tickers=tickers,
                chart_id=f"permutation_comparison_{'_'.join(tickers)}"
            )
            charts.append(chart)
        
        # Chart 3: SHAP Summary Plot
        if "shap" in importance_scores and importance_scores["shap"]:
            chart = await _build_shap_summary(
                shap_scores=importance_scores["shap"],
                feature_names=feature_names,
                top_n=top_n_features,
                tickers=tickers,
                chart_id=f"shap_summary_{'_'.join(tickers)}"
            )
            charts.append(chart)
        
        # Chart 4: Feature Correlation Heatmap
        if correlation_matrix and feature_names:
            import numpy as np
            chart = await _build_correlation_heatmap(
                correlation_matrix=np.array(correlation_matrix),
                feature_names=feature_names,
                tickers=tickers,
                chart_id=f"feature_correlation_{'_'.join(tickers)}"
            )
            charts.append(chart)
        
        charts = wrap_plotly_charts(charts, default_type="feature_importance_chart")
        result['charts'] = charts
    
    return jsonify_results(result)


# Legacy implementation below - kept for reference but no longer used directly
async def _analyze_feature_importance_legacy(tickers: List[str]) -> dict:
    """Legacy - see analyze_feature_importance_internal instead."""
    logger.info(f"🎯 Starting XGBoost feature importance analysis for {tickers}")

    try:
        # Normalize requested importance methods
        if not importance_methods:
            importance_methods = ["gain", "permutation", "shap"]
        else:
            importance_methods = [m.lower() for m in importance_methods]

        # Parse feature windows JSON if provided (resolved per-ticker based on data length)
        feature_windows_config = None
        if feature_windows_json:
            try:
                feature_windows_config = json.loads(feature_windows_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in feature_windows_json: {e}")

        # Set default windows if not provided
        feature_windows = feature_windows_config if feature_windows_config else {
            'returns': [1, 5, 20],
            'momentum': [10, 20],
            'volatility': [10, 20],
            'volume_ma': [20],
            'ma': [5, 20]
        }

        # Validate inputs
        if not tickers:
            raise ValueError("At least one ticker symbol is required")
        if not 0 < train_test_split_ratio < 1:
            raise ValueError("train_test_split_ratio must be between 0 and 1")
        if cv_folds < 2:
            raise ValueError("cv_folds must be at least 2")

        # Step 1: Fetch and engineer features
        logger.info("📊 Fetching historical data and engineering features...")
        feature_df = await _fetch_and_engineer_features(
            tickers=tickers,
            period=period,
            features=features,
            include_technical_indicators=include_technical_indicators,
            feature_windows_config=feature_windows
        )

        if len(feature_df) < min_data_points:
            raise ValueError(
                f"Insufficient data: {len(feature_df)} points, minimum {min_data_points} required"
            )

        # Step 2: Create target variable and prepare data
        logger.info(f"🎯 Creating target variable: {target_variable}")
        X, y, feature_names = await _prepare_features_and_target(
            feature_df=feature_df,
            target_variable=target_variable
        )

        # Step 3: Train XGBoost model
        logger.info("🤖 Training XGBoost model...")
        model, train_metrics, test_metrics = await _train_xgboost_model(
            X=X,
            y=y,
            train_test_split_ratio=train_test_split_ratio,
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            base_score=base_score,
            early_stopping_rounds=early_stopping_rounds,
            cv_folds=cv_folds,
            random_seed=random_seed
        )

        # Step 4: Calculate importance scores
        logger.info("📈 Calculating feature importance...")
        importance_scores = await _calculate_importance_scores(
            model=model,
            X=X,
            y=y,
            feature_names=feature_names,
            importance_methods=importance_methods,
            train_test_split_ratio=train_test_split_ratio,
            permutation_repeats=permutation_repeats,
            random_seed=random_seed
        )

        # Step 5: Generate top features ranking
        top_features = _rank_top_features(
            importance_scores=importance_scores,
            top_n=top_n_features
        )

        # Step 6: Calculate feature correlations
        correlation_matrix = _calculate_feature_correlations(
            X=X,
            feature_names=feature_names,
            top_features=top_features
        )

        # Step 7: Generate charts
        logger.info("📊 Generating visualization charts...")
        charts = []

        # Chart 1: Feature Importance Bars (Gain)
        if "gain" in importance_methods:
            chart = await _build_importance_bars(
                importance_scores=importance_scores["gain"],
                feature_names=feature_names,
                top_n=top_n_features,
                tickers=tickers,
                chart_id=f"feature_importance_gain_{'_'.join(tickers)}"
            )
            charts.append(chart)

        # Chart 2: Permutation vs Gain Comparison
        if "permutation" in importance_methods and "gain" in importance_methods:
            chart = await _build_permutation_comparison(
                gain_scores=importance_scores["gain"],
                perm_scores=importance_scores["permutation"],
                feature_names=feature_names,
                tickers=tickers,
                chart_id=f"permutation_comparison_{'_'.join(tickers)}"
            )
            charts.append(chart)

        # Chart 3: SHAP Summary Plot
        if "shap" in importance_methods:
            chart = await _build_shap_summary(
                shap_scores=importance_scores["shap"],
                feature_names=feature_names,
                top_n=top_n_features,
                tickers=tickers,
                chart_id=f"shap_summary_{'_'.join(tickers)}"
            )
            charts.append(chart)

        # Chart 4: Feature Correlation Heatmap
        chart = await _build_correlation_heatmap(
            correlation_matrix=correlation_matrix,
            feature_names=[f["feature"] for f in top_features[:top_n_features]],
            tickers=tickers,
            chart_id=f"feature_correlation_{'_'.join(tickers)}"
        )
        charts.append(chart)

        charts = wrap_plotly_charts(charts, default_type="feature_importance_chart")

        # Compile results
        results = {
            'tickers': tickers,
            'feature_importance': importance_scores,
            'model_metrics': {
                'train': train_metrics,
                'test': test_metrics
            },
            'top_features': top_features,
            # Removed: feature_correlations matrix (embedded in cached heatmap chart)
            'feature_correlations_summary': {
                'n_features': len([f["feature"] for f in top_features[:top_n_features]]),
                'feature_names': [f["feature"] for f in top_features[:top_n_features]]
            },
            'metadata': {
                'target_variable': target_variable,
                'period': period,
                'n_features': len(feature_names),
                'n_samples': len(X),
                'train_test_split': train_test_split_ratio,
                'importance_methods': importance_methods,
                'feature_windows': feature_windows,
                'model_params': {
                    'n_estimators': n_estimators,
                    'learning_rate': learning_rate,
                    'max_depth': max_depth,
                    'base_score': base_score
                },
                'analysis_date': datetime.now().isoformat()
            }
        }

        logger.info(f"✅ Feature importance analysis complete: {len(top_features)} features ranked")

        return jsonify_results({
            'status': 'success',
            'results': results,
            'charts': charts
        })

    except Exception as e:
        logger.error(f"❌ Feature importance analysis failed: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__,
            'tickers': tickers
        }


async def _fetch_and_engineer_features(
    tickers: List[str],
    period: str,
    features: Optional[List[str]],
    include_technical_indicators: bool,
    feature_windows_config: Optional[Dict[str, List[int]]]
) -> pd.DataFrame:
    """
    Fetch historical data from FMP and engineer features for XGBoost analysis.

    Returns:
        DataFrame with all features including technical indicators and computed metrics
    """
    fmp_server = FMPMarketDataServer()

    try:
        # Connect to FMP server (initializes aiohttp session)
        await fmp_server.connect()

        all_data = []

        for ticker in tickers:
            try:
                # Fetch historical price data
                result = await fmp_server.call_tool("get_historical_data", {
                    "symbol": ticker,
                    "period": period
                })

                # FIX: Use result directly, not result.content (which is a list)
                data = safe_parse_json(result)

                if not data:
                    logger.warning(f"No data received for {ticker}")
                    continue

                # FIX: Build DataFrame from dates, opens, highs, lows, closes, volumes
                # The FMP server returns: {"dates": [...], "opens": [...], "highs": [...], ...}
                if 'dates' not in data:
                    logger.warning(f"No dates in data for {ticker}")
                    continue

                # Create DataFrame from time series arrays
                df_dict = {'date': data['dates']}

                # Add OHLCV data if available
                if 'opens' in data:
                    df_dict['open'] = data['opens']
                if 'highs' in data:
                    df_dict['high'] = data['highs']
                if 'lows' in data:
                    df_dict['low'] = data['lows']
                if 'closes' in data:
                    df_dict['close'] = data['closes']
                elif 'prices' in data:
                    # Fallback to prices if closes not available
                    df_dict['close'] = data['prices']
                if 'volumes' in data:
                    df_dict['volume'] = data['volumes']

                # Check if we have minimum required data
                if 'close' not in df_dict:
                    logger.warning(f"No price data for {ticker}")
                    continue

                df = pd.DataFrame(df_dict)

                # Convert date column
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                df.set_index('date', inplace=True)

                # Engineer additional features with configurable windows
                # feature_windows_config is already populated with defaults if needed
                df = _engineer_custom_features(df, ticker, feature_windows_config)

                # Add ticker column for multi-ticker analysis
                df['ticker'] = ticker

                all_data.append(df)

            except Exception as e:
                logger.error(f"Error fetching data for {ticker}: {e}", exc_info=True)
                continue

        if not all_data:
            raise ValueError("No valid data fetched for any ticker")

        # Combine all ticker data
        combined_df = pd.concat(all_data, axis=0)

        # Drop any rows with NaN values
        combined_df = combined_df.dropna()

        logger.info(f"Engineered {len(combined_df.columns)} features from {len(combined_df)} data points")

        return combined_df

    finally:
        # FIX: Always cleanup FMP server to close aiohttp session
        await fmp_server.cleanup()


def _engineer_custom_features(
    df: pd.DataFrame,
    ticker: str,
    feature_windows: Dict[str, List[int]]
) -> pd.DataFrame:
    """
    Engineer custom features from OHLCV data using configurable windows.

    All windows are parameterized - NO HARDCODING

    Gracefully handles missing OHLCV columns - only creates features when data is available.

    Computes:
    - Returns (configurable periods) - requires 'close'
    - Momentum indicators (configurable periods) - requires 'close'
    - Volatility measures (configurable periods) - requires 'close'
    - Volume ratios (configurable windows) - requires 'volume'
    - Price ratios - requires 'high', 'low', 'open'
    - Moving average crossovers (configurable windows) - requires 'close'
    """
    # Check what columns are available
    has_close = 'close' in df.columns
    has_volume = 'volume' in df.columns
    has_open = 'open' in df.columns
    has_high = 'high' in df.columns
    has_low = 'low' in df.columns

    if not has_close:
        logger.warning(f"No close prices for {ticker}, cannot create features")
        return df

    # Returns with configurable windows (requires close only)
    for window in feature_windows.get('returns', []):
        df[f'returns_{window}d'] = df['close'].pct_change(window)

    # Momentum with configurable windows (requires close only)
    for window in feature_windows.get('momentum', []):
        df[f'momentum_{window}'] = df['close'] / df['close'].shift(window) - 1

    # Volatility (rolling standard deviation) with configurable windows (requires close only)
    for window in feature_windows.get('volatility', []):
        df[f'volatility_{window}'] = df['returns_1d'].rolling(window=window).std() if 'returns_1d' in df.columns else df['close'].pct_change(1).rolling(window=window).std()

    # Volume features with configurable windows (requires volume)
    if has_volume:
        for window in feature_windows.get('volume_ma', []):
            df[f'volume_ma{window}'] = df['volume'].rolling(window=window).mean()
            df[f'volume_ratio_{window}'] = df['volume'] / df[f'volume_ma{window}']

        # Volume change (always 1-day)
        df['volume_change'] = df['volume'].pct_change(1)
    else:
        logger.info(f"Volume data not available for {ticker}, skipping volume-based features")

    # Price features (ratios require OHLC)
    if has_high and has_low:
        df['high_low_ratio'] = df['high'] / df['low']
    else:
        logger.info(f"High/Low data not available for {ticker}, skipping high_low_ratio")

    if has_close and has_open:
        df['close_open_ratio'] = df['close'] / df['open']
    else:
        logger.info(f"Open data not available for {ticker}, skipping close_open_ratio")

    # Moving averages with configurable windows (requires close only)
    ma_windows = feature_windows.get('ma', [])
    for window in ma_windows:
        df[f'ma{window}'] = df['close'].rolling(window=window).mean()

    # MA crossover ratios (all pairs) (requires close only)
    if len(ma_windows) >= 2:
        for i, window1 in enumerate(ma_windows):
            for window2 in ma_windows[i+1:]:
                df[f'ma{window1}_ma{window2}_ratio'] = df[f'ma{window1}'] / df[f'ma{window2}']

    return df


async def _prepare_features_and_target(
    feature_df: pd.DataFrame,
    target_variable: str
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Prepare feature matrix X and target vector y from feature DataFrame.

    Dynamically parses target_variable to extract prediction window - NO HARDCODING

    Returns:
        X: Feature matrix (n_samples, n_features)
        y: Target vector (n_samples,)
        feature_names: List of feature column names
    """
    # Parse target variable to extract window (e.g., "future_5day_return" -> 5)
    match = re.search(r'future_(\d+)day_return', target_variable)
    if match:
        window = int(match.group(1))
    else:
        # Default to 5 if pattern doesn't match
        logger.warning(f"Could not parse window from '{target_variable}', defaulting to 5 days")
        window = 5

    # Create target variable (future returns)
    feature_df['target'] = feature_df.groupby('ticker')['close'].pct_change(window).shift(-window)

    # Drop rows with NaN target
    feature_df = feature_df.dropna(subset=['target'])

    # Exclude non-feature columns
    exclude_cols = ['target', 'ticker', 'open', 'high', 'low', 'close', 'volume', 'date']
    feature_cols = [col for col in feature_df.columns if col not in exclude_cols]

    X = feature_df[feature_cols].values
    y = feature_df['target'].values

    return X, y, feature_cols


def _coerce_base_score_to_scalar(base_score_raw: Any) -> Optional[float]:
    """
    Normalize XGBoost base_score to a scalar float.

    Handles XGBoost 3.1+ strings like "[5E-1]" that SHAP cannot parse directly.
    """
    if base_score_raw is None:
        return None

    if isinstance(base_score_raw, str):
        cleaned = base_score_raw.strip()
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1].strip()

        try:
            return float(cleaned)
        except Exception:
            try:
                parsed = ast.literal_eval(base_score_raw)
                if isinstance(parsed, (list, tuple, np.ndarray)):
                    parsed = parsed[0] if len(parsed) else None
                return float(parsed) if parsed is not None else None
            except Exception:
                return None

    if isinstance(base_score_raw, (list, tuple, np.ndarray)):
        if len(base_score_raw) == 0:
            return None
        try:
            return float(base_score_raw[0])
        except Exception:
            return None

    try:
        return float(base_score_raw)
    except Exception:
        return None


def _normalize_xgboost_base_score(model: XGBRegressor) -> Optional[float]:
    """
    Ensure XGBoost base_score is scalar for SHAP compatibility (XGBoost 3.1+).
    """
    try:
        booster = model.get_booster()
        config = json.loads(booster.save_config())
        learner_params = config.get('learner', {}).get('learner_model_param', {})
        base_score_raw = learner_params.get('base_score')

        base_score_val = _coerce_base_score_to_scalar(base_score_raw)
        if base_score_val is None:
            return None

        learner_params['base_score'] = str(float(base_score_val))
        config['learner']['learner_model_param'] = learner_params

        booster.load_config(json.dumps(config))
        booster.set_param({'base_score': base_score_val})

        # Verify normalization stuck
        verify_config = json.loads(booster.save_config())
        verify_raw = verify_config.get('learner', {}).get('learner_model_param', {}).get('base_score')
        verify_val = _coerce_base_score_to_scalar(verify_raw)
        if verify_val is None:
            return None

        return verify_val
    except Exception as exc:
        logger.warning(f"Could not normalize XGBoost base_score for SHAP: {exc}")
        return None


async def _train_xgboost_model(
    X: np.ndarray,
    y: np.ndarray,
    train_test_split_ratio: float,
    n_estimators: int,
    learning_rate: float,
    max_depth: int,
    base_score: float,
    early_stopping_rounds: Optional[int],
    cv_folds: int,
    random_seed: Optional[int] = None
) -> Tuple[XGBRegressor, Dict[str, float], Dict[str, float]]:
    """
    Train XGBoost model and return model with metrics.

    Args:
        base_score: Initial prediction score (set to scalar for SHAP compatibility with XGBoost 2.0+)

    Returns:
        model: Trained XGBRegressor
        train_metrics: Training set metrics {r2, mae, rmse}
        test_metrics: Test set metrics {r2, mae, rmse, cv_mean, cv_std}
    """
    # Use provided random seed or default
    seed = random_seed if random_seed is not None else 42

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=train_test_split_ratio, random_state=seed
    )

    # Initialize model with early stopping in constructor (XGBoost 3.x requirement)
    # Note: base_score must be scalar for SHAP compatibility with XGBoost 2.0+
    # XGBoost 2.0+ stores base_score as JSON array by default, but SHAP expects scalar
    model = XGBRegressor(
        objective='reg:squarederror',
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        base_score=base_score,  # Configurable for SHAP compatibility
        early_stopping_rounds=early_stopping_rounds,  # Set in constructor for XGBoost 3.x
        random_state=seed,
        n_jobs=-1
    )

    # Train with eval_set for early stopping
    # XGBoost 3.x requires early_stopping_rounds in constructor, NOT in fit()
    if early_stopping_rounds:
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
    else:
        model.fit(X_train, y_train)

    # Normalize base_score for SHAP compatibility (XGBoost 3.1+ writes arrays)
    normalized_base_score = _normalize_xgboost_base_score(model)
    if normalized_base_score is not None:
        logger.info(f"Patched XGBoost base_score for SHAP compatibility: {normalized_base_score}")
    else:
        logger.warning("Could not normalize XGBoost base_score for SHAP; continuing with original value")

    # Calculate metrics on training set
    y_train_pred = model.predict(X_train)
    train_metrics = {
        'r2': r2_score(y_train, y_train_pred),
        'mae': mean_absolute_error(y_train, y_train_pred),
        'rmse': np.sqrt(mean_squared_error(y_train, y_train_pred))
    }

    # Calculate metrics on test set
    y_test_pred = model.predict(X_test)
    test_metrics = {
        'r2': r2_score(y_test, y_test_pred),
        'mae': mean_absolute_error(y_test, y_test_pred),
        'rmse': np.sqrt(mean_squared_error(y_test, y_test_pred))
    }

    # Cross-validation with a model WITHOUT early stopping
    # (CV doesn't provide eval_set, so early stopping would fail)
    cv_model = XGBRegressor(
        objective='reg:squarederror',
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        base_score=base_score,
        random_state=seed,
        n_jobs=-1
        # No early_stopping_rounds for CV
    )
    cv_scores = cross_val_score(
        cv_model, X, y, cv=cv_folds, scoring='r2', n_jobs=-1
    )
    test_metrics['cv_mean'] = cv_scores.mean()
    test_metrics['cv_std'] = cv_scores.std()
    test_metrics['cv_scores'] = cv_scores.tolist()

    logger.info(f"Model trained: R²={test_metrics['r2']:.3f}, CV={test_metrics['cv_mean']:.3f}±{test_metrics['cv_std']:.3f}")

    return model, train_metrics, test_metrics


async def _calculate_importance_scores(
    model: XGBRegressor,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    importance_methods: List[str],
    train_test_split_ratio: float,
    permutation_repeats: int = 8,
    random_seed: Optional[int] = None
) -> Dict[str, Dict[str, float]]:
    """
    Calculate feature importance using multiple methods.

    Returns:
        Dict with importance scores for each method: {method: {feature: score}}
    """
    importance_scores = {}

    # Use provided random seed or default
    seed = random_seed if random_seed is not None else 42

    # Split for permutation importance (needs test set)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, train_size=train_test_split_ratio, random_state=seed
    )

    # Method 1: Gain importance (built-in)
    if "gain" in importance_methods:
        gain_importance = model.feature_importances_
        importance_scores["gain"] = {
            feature_names[i]: float(gain_importance[i])
            for i in range(len(feature_names))
        }

    # Method 2: Permutation importance
    if "permutation" in importance_methods:
        perm_result = permutation_importance(
            model, X_test, y_test, n_repeats=permutation_repeats, random_state=seed, n_jobs=-1
        )
        importance_scores["permutation"] = {
            feature_names[i]: float(perm_result.importances_mean[i])
            for i in range(len(feature_names))
        }

    # Method 3: SHAP values
    if "shap" in importance_methods:
        try:
            normalized_base_score = _normalize_xgboost_base_score(model)
            if normalized_base_score is None:
                logger.warning("Skipping SHAP importance because base_score could not be normalized")
                importance_scores["shap"] = {}
            else:
                logger.info(f"Normalized base_score for SHAP calculation: {normalized_base_score}")

                # Patch SHAP's UBJSON decoder to coerce base_score strings like "[5E-1]" to scalars
                from shap.explainers import _tree as shap_tree
                original_decode_ubjson = shap_tree.decode_ubjson_buffer

                def patched_decode_ubjson(fd):
                    jmodel = original_decode_ubjson(fd)
                    try:
                        learner_params = jmodel.get("learner", {}).get("learner_model_param", {})
                        base_raw = learner_params.get("base_score")
                        coerced = _coerce_base_score_to_scalar(base_raw)
                        if coerced is not None:
                            learner_params["base_score"] = float(coerced)
                    except Exception:
                        pass
                    return jmodel

                shap_tree.decode_ubjson_buffer = patched_decode_ubjson

                try:
                    explainer = shap.TreeExplainer(model)
                    shap_values = explainer.shap_values(X_test)
                finally:
                    shap_tree.decode_ubjson_buffer = original_decode_ubjson

                # Use mean absolute SHAP value as importance
                shap_importance = np.abs(shap_values).mean(axis=0)
                importance_scores["shap"] = {
                    feature_names[i]: float(shap_importance[i])
                    for i in range(len(feature_names))
                }
        except Exception as shap_exc:
            logger.warning(f"SHAP importance failed; returning empty SHAP scores: {shap_exc}")
            importance_scores["shap"] = {}

    return importance_scores


def _rank_top_features(
    importance_scores: Dict[str, Dict[str, float]],
    top_n: int
) -> List[Dict[str, Any]]:
    """
    Rank features across all importance methods and return top N.

    Returns:
        List of dicts: [{feature, gain_rank, perm_rank, shap_rank, avg_score}, ...]
    """
    # Get all features
    all_features = set()
    for method_scores in importance_scores.values():
        all_features.update(method_scores.keys())

    # Rank features for each method
    rankings = {}
    for feature in all_features:
        rankings[feature] = {}

        for method, scores in importance_scores.items():
            if feature in scores:
                # Sort and get rank
                sorted_features = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                rank = next(i for i, (f, _) in enumerate(sorted_features) if f == feature) + 1
                rankings[feature][f"{method}_rank"] = rank
                rankings[feature][f"{method}_score"] = scores[feature]
            else:
                rankings[feature][f"{method}_rank"] = len(all_features)
                rankings[feature][f"{method}_score"] = 0.0

    # Calculate average score across methods
    feature_list = []
    for feature, ranks in rankings.items():
        scores = [ranks.get(f"{m}_score", 0.0) for m in importance_scores.keys()]
        avg_score = np.mean(scores) if scores else 0.0

        feature_dict = {'feature': feature, 'avg_score': avg_score}
        feature_dict.update(ranks)
        feature_list.append(feature_dict)

    # Sort by average score
    feature_list.sort(key=lambda x: x['avg_score'], reverse=True)

    return feature_list[:top_n] if len(feature_list) > top_n else feature_list


def _calculate_feature_correlations(
    X: np.ndarray,
    feature_names: List[str],
    top_features: List[Dict[str, Any]]
) -> np.ndarray:
    """
    Calculate correlation matrix for top features.

    Returns:
        Correlation matrix as numpy array
    """
    # Get indices of top features
    top_feature_names = [f['feature'] for f in top_features]
    indices = [feature_names.index(fname) for fname in top_feature_names if fname in feature_names]

    # Calculate correlation
    X_top = X[:, indices]
    correlation_matrix = np.corrcoef(X_top, rowvar=False)

    return correlation_matrix


async def _build_importance_bars(
    importance_scores: Dict[str, float],
    feature_names: List[str],
    top_n: int,
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """
    Build horizontal bar chart showing feature importance (gain method).
    """
    # Sort by importance
    sorted_features = sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features = [f[0] for f in sorted_features]
    scores = [f[1] for f in sorted_features]

    # Reverse for plotting (top feature at top)
    features = features[::-1]
    scores = scores[::-1]

    # Create horizontal bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=features,
        x=scores,
        orientation='h',
        marker=dict(
            color=scores,
            colorscale='Blues',
            line=dict(color='white', width=0.5)
        ),
        text=[f'{s:.4f}' for s in scores],
        textposition='auto',
        textfont=dict(size=10)
    ))

    fig.update_layout(
        title=f'XGBoost Feature Importance (Gain Method)<br><sub>{", ".join(tickers)}</sub>',
        xaxis_title='Importance Score',
        yaxis_title='Feature',
        height=400 + (len(features) * 15),
        width=900,
        margin=dict(l=150, r=50, t=80, b=60),
        showlegend=False
    )

    return {
        'id': chart_id,
        'title': f'XGBoost Feature Importance (Gain) - {", ".join(tickers)}',
        'plotly': fig.to_dict(),
        'type': ChartType.BAR.value,
        'priority': ChartPriority.PRIMARY.value
    }


async def _build_permutation_comparison(
    gain_scores: Dict[str, float],
    perm_scores: Dict[str, float],
    feature_names: List[str],
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """
    Build scatter plot comparing gain vs permutation importance.
    """
    # Get common features
    common_features = set(gain_scores.keys()) & set(perm_scores.keys())

    gain_vals = [gain_scores[f] for f in common_features]
    perm_vals = [perm_scores[f] for f in common_features]
    labels = list(common_features)

    fig = go.Figure()

    # Scatter plot
    fig.add_trace(go.Scatter(
        x=gain_vals,
        y=perm_vals,
        mode='markers',
        marker=dict(
            size=10,
            color=gain_vals,
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Gain Score")
        ),
        text=labels,
        hovertemplate='<b>%{text}</b><br>Gain: %{x:.4f}<br>Permutation: %{y:.4f}<extra></extra>'
    ))

    # Diagonal reference line (perfect agreement)
    max_val = max(max(gain_vals), max(perm_vals))
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        line=dict(color='red', dash='dash', width=2),
        name='Perfect Agreement',
        showlegend=True
    ))

    fig.update_layout(
        title=f'Permutation vs Gain Importance<br><sub>{", ".join(tickers)}</sub>',
        xaxis_title='Gain Importance',
        yaxis_title='Permutation Importance',
        height=600,
        width=800,
        showlegend=True
    )

    return {
        'id': chart_id,
        'title': f'Permutation vs Gain Comparison - {", ".join(tickers)}',
        'plotly': fig.to_dict(),
        'type': ChartType.SCATTER.value,
        'priority': ChartPriority.SECONDARY.value
    }


async def _build_shap_summary(
    shap_scores: Dict[str, float],
    feature_names: List[str],
    top_n: int,
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """
    Build SHAP summary plot (simplified bar chart for mean absolute SHAP values).
    """
    # Sort by SHAP importance
    sorted_features = sorted(shap_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features = [f[0] for f in sorted_features]
    scores = [f[1] for f in sorted_features]

    # Reverse for plotting
    features = features[::-1]
    scores = scores[::-1]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=features,
        x=scores,
        orientation='h',
        marker=dict(
            color=scores,
            colorscale='Reds',
            line=dict(color='white', width=0.5)
        ),
        text=[f'{s:.4f}' for s in scores],
        textposition='auto',
        textfont=dict(size=10)
    ))

    fig.update_layout(
        title=f'SHAP Feature Importance (Mean |SHAP|)<br><sub>{", ".join(tickers)}</sub>',
        xaxis_title='Mean Absolute SHAP Value',
        yaxis_title='Feature',
        height=400 + (len(features) * 15),
        width=900,
        margin=dict(l=150, r=50, t=80, b=60),
        showlegend=False
    )

    return {
        'id': chart_id,
        'title': f'SHAP Summary - {", ".join(tickers)}',
        'plotly': fig.to_dict(),
        'type': ChartType.BAR.value,
        'priority': ChartPriority.SECONDARY.value
    }


async def _build_correlation_heatmap(
    correlation_matrix: np.ndarray,
    feature_names: List[str],
    tickers: List[str],
    chart_id: str
) -> Dict[str, Any]:
    """
    Build correlation heatmap for top features.
    """
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix,
        x=feature_names,
        y=feature_names,
        colorscale='RdBu',
        zmid=0,
        text=np.round(correlation_matrix, 2),
        texttemplate='%{text}',
        textfont=dict(size=10),
        colorbar=dict(title='Correlation')
    ))

    fig.update_layout(
        title=f'Top Features Correlation Matrix<br><sub>{", ".join(tickers)}</sub>',
        xaxis=dict(tickangle=-45),
        height=600 + (len(feature_names) * 10),
        width=700 + (len(feature_names) * 10),
        margin=dict(l=150, r=50, t=80, b=150)
    )

    return {
        'id': chart_id,
        'title': f'Feature Correlation Heatmap - {", ".join(tickers)}',
        'plotly': fig.to_dict(),
        'type': ChartType.HEATMAP.value,
        'priority': ChartPriority.TERTIARY.value
    }
