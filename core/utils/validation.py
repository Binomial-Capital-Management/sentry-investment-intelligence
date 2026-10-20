"""
Common validation utilities to eliminate duplicate validation logic.
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Union, Tuple
from datetime import datetime, timedelta
import logging

from ..constants import MIN_WEIGHT, MAX_WEIGHT, WEIGHT_TOLERANCE

logger = logging.getLogger(__name__)


def validate_tickers(tickers: Union[List[str], str]) -> List[str]:
    """
    Validate and normalize ticker symbols.
    
    Args:
        tickers: Single ticker or list of tickers
        
    Returns:
        List of validated ticker symbols
        
    Raises:
        ValueError: If tickers are invalid
    """
    if isinstance(tickers, str):
        tickers = [tickers]
    
    if not tickers or len(tickers) == 0:
        raise ValueError("At least one ticker must be provided")
    
    # Clean and validate tickers
    cleaned_tickers = []
    for ticker in tickers:
        if not isinstance(ticker, str):
            raise ValueError(f"Ticker must be string, got {type(ticker)}")
        
        ticker = ticker.strip().upper()
        if not ticker:
            raise ValueError("Empty ticker provided")
        
        # Basic ticker format validation
        if not ticker.isalnum() and '.' not in ticker:
            logger.warning(f"Ticker '{ticker}' has unusual format")
        
        cleaned_tickers.append(ticker)
    
    return cleaned_tickers


def validate_weights(weights: Optional[np.ndarray], n_assets: int) -> np.ndarray:
    """
    Validate and normalize portfolio weights.
    Allows negative weights (short positions) - handled gracefully.
    
    Args:
        weights: Portfolio weights (None for equal weights, negative values = shorts)
        n_assets: Number of assets
        
    Returns:
        Normalized weights array
        
    Raises:
        ValueError: If weights are invalid
    """
    if weights is None:
        # Equal weights
        return np.ones(n_assets) / n_assets
    
    weights = np.asarray(weights, dtype=float)
    
    # Validate dimensions
    if weights.shape != (n_assets,):
        raise ValueError(f"Weights must have shape ({n_assets},), got {weights.shape}")
    
    # Allow negative weights (shorts) - just log them
    if np.any(weights < 0):
        short_positions = np.sum(weights < 0)
        logger.info(f"Portfolio contains {short_positions} short position(s) (negative weights)")
    
    # Warn about extreme individual weights (absolute value)
    if np.any(np.abs(weights) > MAX_WEIGHT + WEIGHT_TOLERANCE):
        logger.warning(f"Large individual weight detected: max absolute weight = {np.abs(weights).max():.6f}")
    
    # Normalize weights to sum to 1 (or 0 for market-neutral)
    weight_sum = np.sum(weights)
    if abs(weight_sum - 1.0) > WEIGHT_TOLERANCE:
        if abs(weight_sum) < WEIGHT_TOLERANCE:
            logger.info("Portfolio is market-neutral (weights sum to ~0)")
        else:
            logger.warning(f"Weights sum to {weight_sum:.6f}, normalizing to 1.0")
            weights = weights / weight_sum
    
    return weights


def validate_date_range(start_date: Optional[str], end_date: Optional[str]) -> Tuple[str, str]:
    """
    Validate and normalize date range.
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        
    Returns:
        Tuple of (start_date, end_date) strings
        
    Raises:
        ValueError: If dates are invalid
    """
    # Default end date to today if not provided
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Default start date to 3 years ago if not provided
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
    
    # Validate date formats
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"Invalid date format (use YYYY-MM-DD): {e}")
    
    # Validate date order
    if start_dt >= end_dt:
        raise ValueError(f"Start date ({start_date}) must be before end date ({end_date})")
    
    # Validate reasonable date range
    if (end_dt - start_dt).days < 30:
        raise ValueError(f"Date range too short: {(end_dt - start_dt).days} days")
    
    if (end_dt - start_dt).days > 10*365:
        logger.warning(f"Very long date range: {(end_dt - start_dt).days} days")
    
    return start_date, end_date


def validate_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Validate returns data.
    
    Args:
        returns: DataFrame of returns
        
    Returns:
        Validated returns DataFrame
        
    Raises:
        ValueError: If returns data is invalid
    """
    if returns is None or returns.empty:
        raise ValueError("Returns data cannot be empty")
    
    # Check for all NaN columns
    all_nan_cols = returns.columns[returns.isna().all()].tolist()
    if all_nan_cols:
        raise ValueError(f"Columns with all NaN values: {all_nan_cols}")
    
    # Check for excessive missing data
    missing_pct = returns.isna().sum() / len(returns)
    high_missing = missing_pct[missing_pct > 0.5].index.tolist()
    if high_missing:
        logger.warning(f"Assets with >50% missing data: {high_missing}")
    
    # Check for unrealistic returns
    extreme_returns = returns.abs() > 1.0  # >100% daily return
    if extreme_returns.any().any():
        logger.warning("Extreme returns detected (>100% daily)")
    
    return returns


def validate_portfolio_value(portfolio_value: float) -> float:
    """
    Validate portfolio value.
    
    Args:
        portfolio_value: Portfolio value in dollars
        
    Returns:
        Validated portfolio value
        
    Raises:
        ValueError: If portfolio value is invalid
    """
    if portfolio_value <= 0:
        raise ValueError(f"Portfolio value must be positive, got {portfolio_value}")
    
    if portfolio_value < 100_000:
        logger.warning(f"Small portfolio value: ${portfolio_value:,.0f}")
    
    if portfolio_value > 10_000_000_000:
        logger.warning(f"Very large portfolio value: ${portfolio_value:,.0f}")
    
    return float(portfolio_value)


def validate_confidence_level(confidence_level: float) -> float:
    """
    Validate confidence level for risk measures.
    
    Args:
        confidence_level: Confidence level (0 < x < 1)
        
    Returns:
        Validated confidence level
        
    Raises:
        ValueError: If confidence level is invalid
    """
    if not 0 < confidence_level < 1:
        raise ValueError(f"Confidence level must be between 0 and 1, got {confidence_level}")
    
    if confidence_level < 0.5:
        logger.warning(f"Low confidence level: {confidence_level}")
    
    return float(confidence_level)


def validate_simulation_params(n_simulations: int, time_horizon: int) -> Tuple[int, int]:
    """
    Validate Monte Carlo simulation parameters.
    
    Args:
        n_simulations: Number of simulations
        time_horizon: Time horizon in days
        
    Returns:
        Tuple of (n_simulations, time_horizon)
        
    Raises:
        ValueError: If parameters are invalid
    """
    if n_simulations < 100:
        raise ValueError(f"Number of simulations must be >= 100, got {n_simulations}")
    
    if n_simulations > 1_000_000:
        logger.warning(f"Very large number of simulations: {n_simulations}")
    
    if time_horizon < 1:
        raise ValueError(f"Time horizon must be >= 1 day, got {time_horizon}")
    
    if time_horizon > 252:
        logger.warning(f"Long time horizon: {time_horizon} days")
    
    return int(n_simulations), int(time_horizon)