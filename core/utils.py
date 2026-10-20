"""Utility functions for data processing and calculations."""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy types, inf, nan, and pandas objects."""
    def default(self, obj):
        import math
        
        # Handle numpy integer types
        if isinstance(obj, (np.integer,)):
            return int(obj)
        # Handle numpy float types
        elif isinstance(obj, (np.floating,)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        # Handle numpy bool
        elif isinstance(obj, np.bool_):
            return bool(obj)
        # Handle numpy arrays
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        # Handle pandas Timestamp
        elif isinstance(obj, pd.Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(obj) else None
        # Handle pandas Series
        elif isinstance(obj, pd.Series):
            return obj.tolist()
        # Handle pandas DataFrame
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='list')
        # Handle pandas NaT
        elif pd.isna(obj):
            return None
        return super().default(obj)
    
    def encode(self, obj):
        """Override encode to handle inf/nan in regular floats too."""
        import math
        
        def sanitize(o):
            if isinstance(o, float):
                if math.isnan(o) or math.isinf(o):
                    return None
                return o
            elif isinstance(o, dict):
                return {k: sanitize(v) for k, v in o.items()}
            elif isinstance(o, (list, tuple)):
                return [sanitize(v) for v in o]
            return o
        
        return super().encode(sanitize(obj))