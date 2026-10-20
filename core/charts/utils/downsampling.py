"""
Downsampling utilities for chart data.

Uses tsdownsample for LTTB algorithm when available,
falls back to simple stride sampling otherwise.
"""

from typing import List, Union, Any
import numpy as np

# Try to import tsdownsample, fallback to simple sampling
try:
    from tsdownsample import LTTBDownsampler
    HAS_TSDOWNSAMPLE = True
except ImportError:
    HAS_TSDOWNSAMPLE = False


def downsample_if_needed(
    data: Union[List, np.ndarray], 
    max_points: int = 2000
) -> Union[List, np.ndarray]:
    """
    Downsample data if it exceeds max_points threshold.
    
    Args:
        data: Input data array
        max_points: Maximum number of points to retain
    
    Returns:
        Downsampled data (same type as input)
    """
    if not data or len(data) <= max_points:
        return data
    
    # Convert to numpy for processing
    is_list = isinstance(data, list)
    arr = np.array(data) if is_list else data
    
    # Use LTTB if available, otherwise stride sampling
    if HAS_TSDOWNSAMPLE:
        downsampled = downsample_lttb(arr, max_points)
    else:
        # Simple stride sampling
        stride = len(arr) // max_points
        downsampled = arr[::stride][:max_points]
    
    # Return same type as input
    return downsampled.tolist() if is_list else downsampled


def downsample_lttb(data: np.ndarray, target_points: int) -> np.ndarray:
    """
    Downsample using Largest Triangle Three Buckets (LTTB) algorithm.
    
    This preserves visual similarity while reducing data points.
    Falls back to stride sampling if tsdownsample not available.
    
    Args:
        data: Input numpy array
        target_points: Target number of points
    
    Returns:
        Downsampled numpy array
    """
    if len(data) <= target_points:
        return data
    
    if HAS_TSDOWNSAMPLE:
        # Use LTTB algorithm
        downsampler = LTTBDownsampler()
        x = np.arange(len(data))
        
        # Get indices to keep
        indices = downsampler.downsample(x, data, n_out=target_points)
        return data[indices]
    else:
        # Fallback to stride sampling
        stride = max(1, len(data) // target_points)
        return data[::stride][:target_points]


def downsample_ohlc(
    open_data: List,
    high_data: List,
    low_data: List,
    close_data: List,
    max_points: int = 500
) -> tuple:
    """
    Downsample OHLC data preserving candlestick integrity.
    
    Groups data into buckets and creates representative OHLC values.
    
    Args:
        open_data: Opening prices
        high_data: High prices
        low_data: Low prices  
        close_data: Closing prices
        max_points: Maximum candles to retain
    
    Returns:
        Tuple of (open, high, low, close) downsampled arrays
    """
    n = len(open_data)
    if n <= max_points:
        return open_data, high_data, low_data, close_data
    
    # Calculate bucket size
    bucket_size = n // max_points
    
    # Initialize result lists
    new_open = []
    new_high = []
    new_low = []
    new_close = []
    
    for i in range(0, n, bucket_size):
        end_idx = min(i + bucket_size, n)
        
        # Take first open, last close, max high, min low for each bucket
        new_open.append(open_data[i])
        new_high.append(max(high_data[i:end_idx]))
        new_low.append(min(low_data[i:end_idx]))
        new_close.append(close_data[end_idx - 1])
    
    return new_open[:max_points], new_high[:max_points], new_low[:max_points], new_close[:max_points]