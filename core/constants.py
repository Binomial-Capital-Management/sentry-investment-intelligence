"""
Financial constants used throughout the Binomial Risk Analyst.
Centralized to eliminate magic numbers and improve maintainability.
"""

# Time-related constants
TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365
BUSINESS_DAYS_PER_MONTH = 21
BUSINESS_DAYS_PER_QUARTER = 63

# Risk measurement constants
CONFIDENCE_LEVEL_95 = 0.95
CONFIDENCE_LEVEL_99 = 0.99
CONFIDENCE_LEVEL_99_5 = 0.995
CONFIDENCE_LEVELS = [CONFIDENCE_LEVEL_95, CONFIDENCE_LEVEL_99, CONFIDENCE_LEVEL_99_5]

# Monte Carlo simulation defaults
DEFAULT_MC_SIMULATIONS = 1000  # Standard 1K simulations for faster performance
MAX_MC_SIMULATIONS = 100000
MIN_MC_SIMULATIONS = 100  # Allow lower for testing

# Time horizon defaults (in business days)
DEFAULT_VAR_HORIZON = 1
DEFAULT_MONTE_CARLO_HORIZON = 21  # ~1 month
DEFAULT_STRESS_TEST_HORIZON = 63  # ~1 quarter

# Portfolio defaults
DEFAULT_PORTFOLIO_VALUE = 1_000_000  # Standard 1M portfolio
MIN_PORTFOLIO_VALUE = 100_000
MAX_PORTFOLIO_VALUE = 1_000_000_000

# Risk limits (can be overridden by environment variables)
DEFAULT_MAX_VAR_95 = 0.02  # 2%
DEFAULT_MAX_CONCENTRATION = 0.25  # 25%
DEFAULT_MIN_SHARPE_RATIO = 0.5

# Optimization parameters
DEFAULT_RISK_FREE_RATE = 0.0425  # 4.25% (July 2025 3-month T-bill rate)
MIN_WEIGHT = 0.0
MAX_WEIGHT = 1.0
DEFAULT_MAX_WEIGHT = 0.4  # 40% max single position

# Data fetching constants
DEFAULT_LOOKBACK_YEARS = 3
MIN_LOOKBACK_YEARS = 1
MAX_LOOKBACK_YEARS = 10
DEFAULT_DATA_FREQUENCY = 'daily'

# Visualization constants
DEFAULT_CHART_WIDTH = 12
DEFAULT_CHART_HEIGHT = 8
DEFAULT_DPI = 300
DEFAULT_STYLE = 'seaborn-v0_8'

# Error tolerance
NUMERICAL_TOLERANCE = 1e-8
WEIGHT_TOLERANCE = 1e-6
CONVERGENCE_TOLERANCE = 1e-6
MAX_ITERATIONS = 1000

# Cache TTL constants (in seconds)
CACHE_TTL_HOUR = 3600  # 1 hour
CACHE_TTL_DAY = 86400  # 24 hours
CACHE_TTL_WEEK = 604800  # 7 days

# API rate limits
YAHOO_FINANCE_RATE_LIMIT = 2000  # requests per hour
FRED_RATE_LIMIT = 120  # requests per minute

# Calculation type constants
CALC_TYPE_BASIC = 'basic_risk'
CALC_TYPE_BARRA = 'barra'
CALC_TYPE_MONTE_CARLO = 'monte_carlo'
CALC_TYPE_HEDGE = 'hedge'
CALC_TYPE_OPTIMIZE = 'optimize'

# Word Document Professional Styling
WORD_MARGINS = {
    'top': 1.0,      # inches
    'bottom': 1.0,
    'left': 1.25,
    'right': 1.25
}

# Typography (following institutional standards)
WORD_FONTS = {
    'primary': 'Helvetica',          # Clean, modern standard
    'modern': 'Arial',               # Alternative clean option
    'fallback': 'Calibri'
}

WORD_SIZES = {
    'title': 24,      # points
    'heading1': 18,
    'heading2': 16,
    'heading3': 14,
    'body': 12,       # Increased for better readability
    'footnote': 9
}

# Professional color scheme
WORD_COLORS = {
    'binomial_blue': (0, 81, 204),     # #0051CC brand
    'heading_blue': (0, 51, 102),      # Darker professional blue
    'text_primary': (0, 0, 0),         # Pure black for body
    'text_secondary': (102, 102, 102), # Gray for dates/captions
    'table_header': (0, 81, 204),      # Brand blue for tables
    'table_alt_row': (243, 244, 246)   # Light gray alternating
}

# Layout
LINE_SPACING = 1.15   # Standard professional spacing
PARA_SPACING_AFTER = 6  # Tighter paragraph spacing
LOGO_WIDTH = 1.5  # inches
TABLE_STYLE = 'Light List Accent 1'

# Domain-specific search configuration
SEARCH_DOMAINS = {
    'financial': {
        'preferred': ['finance.yahoo.com', 'bloomberg.com', 'reuters.com', 'ft.com', 'wsj.com', 'cnbc.com', 'marketwatch.com'],
        'context': 'Focus on real-time market data, official financial sources, and institutional-grade analysis. Avoid speculation and social media.',
        'priority': 'accuracy'
    },
    'academic': {
        'preferred': ['scholar.google.com', 'arxiv.org', 'jstor.org', 'ssrn.com', 'sciencedirect.com', 'nber.org'],
        'context': 'Prioritize peer-reviewed papers, empirical studies, and academic research. Focus on methodology and evidence-based findings.',
        'priority': 'rigor'
    },
    'social': {
        'avoid': ['reddit.com', 'twitter.com', 'facebook.com', 'tiktok.com', 'instagram.com'],
        'context': 'For risk analysis, avoid social media speculation and unverified claims. Focus on authoritative sources only.',
        'priority': 'reliability'
    }
}

# Search context templates for Perplexity
SEARCH_CONTEXTS = {
    'risk_analysis': 'Use authoritative financial sources. Avoid speculation from social media or forums.',
    'market_data': 'Focus on real-time official market data from exchanges and financial data providers.',
    'academic_research': 'Cite peer-reviewed papers and academic studies with proper methodology.',
    'news_analysis': 'Use reputable financial news sources. Verify facts from multiple sources.'
}

# Data period defaults
DEFAULT_PERIOD = "1y"

# Hedge calculation constants  
HEDGE_RISK_MULTIPLIERS = {
    'total': 0.7,
    'factor': 0.3,
    'specific': 0.9
}

# Hedge strategy defaults
DEFAULT_HEDGE_STRATEGY = "market_neutral"
HEDGE_STRATEGIES = {
    'market_neutral': {"Market": 0.0},
    'sector_neutral': {"Market": 1.0, "Financials": 0.0, "Technology": 0.0}
}