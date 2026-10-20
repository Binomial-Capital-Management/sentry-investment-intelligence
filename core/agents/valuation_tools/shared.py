"""
Shared utilities for valuation tools
"""

# This file is now empty after removing the anti-pattern fetch_valuation_data_batch function
# The function was fetching ALL fields for every ticker, causing API overload
# Now the AI will select specific fields as needed