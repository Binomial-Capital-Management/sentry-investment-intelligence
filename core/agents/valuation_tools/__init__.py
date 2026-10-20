"""
Valuation Tools Module
Exports all valuation tools for agents
Following the pattern from risk_tools/__init__.py
"""

from .comps_tool import analyze_comparable_companies
from .three_stage_dcf_tool import analyze_three_stage_dcf, dcf_sensitivity_analysis
from .two_stage_dcf_tool import analyze_two_stage_dcf
from .stable_stage_dcf_tool import analyze_stable_stage_dcf
from .gather_dcf_data_tool import gather_dcf_data_sources, discover_fields, discover_dcf_fields
from .reverse_dcf_tool import analyze_reverse_dcf
from .epv_tool import analyze_epv
from .monte_carlo_dcf_tool import analyze_monte_carlo_dcf
# Internal function import for Canvas only - not exposed to agents
from .monte_carlo_dcf_tool import analyze_monte_carlo_dcf_internal
from .rim_tool import analyze_rim

# Separate tool categories
COMPS_TOOLS = [
    analyze_comparable_companies
]

DCF_TOOLS = [
    # Note: discover_fields and discover_dcf_fields are provided by MCP servers
    # and should NOT be included here to avoid duplicate tool registration
    gather_dcf_data_sources,      # Fetch all data from 3 servers
    analyze_three_stage_dcf,      # Execute DCF with agent's assumptions
    dcf_sensitivity_analysis,     # Optional: Sensitivity analysis
    analyze_two_stage_dcf,        # Optional: Two-stage FCFE for slower-growth names
    analyze_stable_stage_dcf,     # Optional: Stable-stage FCFE for stagnant names
    analyze_reverse_dcf,          # Reverse DCF: back-solve for implied growth
    analyze_epv,                  # EPV: Graham/Dodd zero-growth floor valuation
    analyze_monte_carlo_dcf,      # Monte Carlo DCF: probabilistic valuation
    analyze_rim,                  # RIM: Residual Income Model for banks/financials
]

# Export all tools as a list for easy agent configuration
VALUATION_TOOLS = COMPS_TOOLS + DCF_TOOLS

__all__ = [
    'analyze_comparable_companies',
    'gather_dcf_data_sources',
    'discover_fields',
    'discover_dcf_fields',
    'analyze_three_stage_dcf',
    'dcf_sensitivity_analysis',
    'analyze_two_stage_dcf',
    'analyze_stable_stage_dcf',
    'analyze_reverse_dcf',
    'analyze_epv',
    'analyze_monte_carlo_dcf',
    'analyze_rim',
    'COMPS_TOOLS',
    'DCF_TOOLS',
    'VALUATION_TOOLS'
]
