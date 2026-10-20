"""
Universe presets for stock screener.
Following CODING_RULES.md: No hardcoding, these are configurable presets.
"""
from typing import Dict, List

# Preset universes for quick selection
UNIVERSE_PRESETS: Dict[str, List[str]] = {
    "tech": [
        # Mega-cap tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
        # Semiconductors
        'AMD', 'INTC', 'AVGO', 'QCOM', 'MU', 'MRVL', 'AMAT',
        # Software
        'CRM', 'ORCL', 'ADBE', 'NOW', 'INTU', 'UBER', 'SNAP',
        # Streaming & Entertainment
        'NFLX', 'DIS', 'ROKU', 'SPOT',
        # E-commerce & Payments
        'SHOP', 'PYPL', 'SQ', 'MELI'
    ],
    
    "healthcare": [
        # Pharma Giants
        'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK', 'BMY', 'AMGN',
        # Biotech
        'GILD', 'BIIB', 'REGN', 'VRTX', 'MRNA',
        # Health Services
        'UNH', 'CVS', 'HUM', 'CI', 'ELV',
        # Medical Devices
        'ABT', 'TMO', 'DHR', 'MDT', 'ISRG'
    ],
    
    "finance": [
        # Major Banks
        'JPM', 'BAC', 'WFC', 'C', 'USB', 'PNC', 'TFC',
        # Investment Banks
        'GS', 'MS', 'BLK', 'SCHW',
        # Credit Cards & Payments
        'V', 'MA', 'AXP', 'COF',
        # Insurance
        'BRK-B', 'UNH', 'PGR', 'CB', 'AIG',
        # Fintech
        'PYPL', 'SQ', 'COIN'
    ],
    
    "energy": [
        # Oil & Gas Majors
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'MPC',
        # Refiners
        'VLO', 'PSX', 'MRO',
        # Pipelines
        'KMI', 'WMB', 'EPD', 'ET',
        # Clean Energy
        'NEE', 'ENPH', 'SEDG', 'PLUG', 'FSLR'
    ],
    
    "consumer": [
        # Retail
        'WMT', 'AMZN', 'HD', 'COST', 'TGT', 'LOW',
        # Consumer Staples
        'PG', 'KO', 'PEP', 'PM', 'MO', 'CL',
        # Restaurants
        'MCD', 'SBUX', 'CMG', 'YUM', 'DPZ',
        # Apparel
        'NKE', 'LULU', 'TJX', 'ROST',
        # Auto
        'TSLA', 'F', 'GM', 'TM'
    ],
    
    "sp100": [
        # Top 100 S&P 500 by market cap (abbreviated list for demo)
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
        'V', 'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'UNH', 'DIS', 'HD', 'PYPL',
        'BAC', 'VZ', 'ADBE', 'NFLX', 'CMCSA', 'KO', 'NKE', 'MRK', 'PEP',
        'TMO', 'PFE', 'ABT', 'ABBV', 'CRM', 'AVGO', 'COST', 'CVX', 'ACN',
        'MCD', 'NEE', 'TXN', 'DHR', 'UNP', 'LIN', 'BMY', 'WFC', 'MDT',
        'QCOM', 'PM', 'T', 'RTX', 'HON', 'IBM', 'SBUX', 'GE', 'CAT',
        'BA', 'MMM', 'AMGN', 'CVS', 'GS', 'BLK', 'CHTR', 'AXP', 'GILD',
        'MO', 'SCHW', 'ZTS', 'ISRG', 'PLD', 'TGT', 'BKNG', 'MDLZ', 'SYK',
        'CI', 'SPGI', 'LMT', 'BDX', 'CSX', 'ADP', 'CME', 'CL', 'FISV',
        'BSX', 'REGN', 'ATVI', 'EQIX', 'HUM', 'CCI', 'PNC', 'DUK', 'SHW',
        'ITW', 'MU', 'GD', 'COP', 'ICE', 'MCO', 'EL', 'USB', 'SO', 'MS'
    ],
    
    "etfs": [
        # Major Index ETFs
        'SPY', 'QQQ', 'DIA', 'IWM', 'VTI', 'VOO',
        # Sector ETFs
        'XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLY', 'XLP', 'XLB', 'XLRE', 'XLU',
        # International
        'EFA', 'EEM', 'VEA', 'VWO', 'IEFA', 'IEMG',
        # Bonds
        'AGG', 'BND', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG',
        # Commodities
        'GLD', 'SLV', 'USO', 'UNG', 'DBA'
    ],
    
    "momentum": [
        # High momentum stocks (this would be dynamically updated in production)
        'NVDA', 'META', 'NFLX', 'TSLA', 'AMD', 'AVGO', 'CRM', 'NOW',
        'PANW', 'ANET', 'MELI', 'SHOP', 'COIN', 'UBER', 'ABNB',
        'DDOG', 'SNOW', 'NET', 'CRWD', 'ZS'
    ],
    
    "dividend": [
        # High dividend yield stocks
        'T', 'VZ', 'MO', 'PM', 'XOM', 'CVX', 'KMI', 'WMB', 'EPD',
        'KO', 'PEP', 'JNJ', 'PG', 'MMM', 'CAT', 'IBM', 'CSCO',
        'PFE', 'MRK', 'ABBV', 'BMY', 'GILD', 'CVS', 'WBA'
    ],
    
    "small_cap": [
        # Russell 2000 components (sample)
        'AMC', 'BBBY', 'CLOV', 'WISH', 'RKT', 'SOFI', 'PLTR',
        'PLUG', 'FCEL', 'NIO', 'XPEV', 'LI', 'RIDE', 'NKLA'
    ]
}


def get_universe(name: str) -> List[str]:
    """
    Get a preset universe by name.
    
    Args:
        name: Universe name (e.g., 'tech', 'healthcare')
        
    Returns:
        List of symbols in the universe, or empty list if not found
    """
    return UNIVERSE_PRESETS.get(name.lower(), [])


def combine_universes(*names: str) -> List[str]:
    """
    Combine multiple preset universes.
    
    Args:
        names: Universe names to combine
        
    Returns:
        Deduplicated list of symbols from all universes
    """
    symbols = set()
    for name in names:
        symbols.update(get_universe(name))
    return sorted(list(symbols))


def validate_symbols(symbols: List[str]) -> List[str]:
    """
    Validate and clean symbol list.
    
    Args:
        symbols: List of symbols to validate
        
    Returns:
        Cleaned list of valid symbols
    """
    # In production, this would check against a master symbol list
    # For now, just clean and uppercase
    return [s.strip().upper() for s in symbols if s and s.strip()]


def get_available_universes() -> Dict[str, int]:
    """
    Get all available universe presets with their sizes.
    
    Returns:
        Dictionary of universe name to symbol count
    """
    return {name: len(symbols) for name, symbols in UNIVERSE_PRESETS.items()}