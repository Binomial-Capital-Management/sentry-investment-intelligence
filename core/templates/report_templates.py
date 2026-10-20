"""
Report templates for automated and scheduled reports.
Following KISS principle - simple, clear templates that users actually need.
"""

from typing import Dict, List, Any

# Professional report templates
REPORT_TEMPLATES = {
    'full_risk_review': {
        'name': 'Full Risk Review',
        'description': 'Comprehensive institutional-grade portfolio risk analysis',
        'prompt': '''Provide a comprehensive institutional risk analysis report including:

1. Executive Summary
   - Portfolio composition and current value
   - Key risk metrics summary
   - Major findings and recommendations

2. Risk Metrics Analysis
   - Value at Risk (VaR) at 95% and 99% confidence levels
   - Conditional VaR (CVaR)
   - Portfolio volatility and Sharpe ratio
   - Maximum drawdown analysis

3. Factor Analysis (Barra Model)
   - Systematic vs specific risk decomposition
   - Factor exposures (market, size, value, momentum)
   - Risk attribution by factor

4. Stress Testing & Scenarios
   - Monte Carlo simulation results
   - Historical stress scenarios
   - Tail risk analysis

5. Portfolio Optimization
   - Current vs optimal allocation
   - Efficient frontier analysis
   - Risk-return trade-offs

6. Market Context
   - Current market regime
   - Relevant economic indicators
   - Peer comparison

7. Recommendations
   - Risk mitigation strategies
   - Rebalancing suggestions
   - Hedging opportunities''',
        'calculations': ['basic_risk', 'barra', 'monte_carlo', 'optimize'],
        'estimated_time': '2-3 minutes',
        'frequency_suggestion': 'Weekly or Monthly'
    },
    
    'market_intelligence': {
        'name': 'Market Intelligence Report',
        'description': 'Real-time market insights and company analysis',
        'prompt': '''Generate a market intelligence report for the portfolio companies:

For each company in the portfolio:

1. Market Performance
   - Current price and daily change
   - 30-day performance vs sector and market
   - Volume analysis and liquidity

2. Recent News & Events
   - Major news in last 7 days
   - Earnings announcements
   - Management changes
   - M&A activity

3. Key Metrics & KPIs
   - P/E ratio vs sector average
   - Revenue growth (YoY and QoQ)
   - Profit margins
   - Debt/Equity ratio
   - Return on equity

4. Analyst Activity
   - Recent upgrades/downgrades
   - Consensus price targets
   - Recommendation distribution

5. Upcoming Catalysts
   - Earnings dates
   - Product launches
   - Regulatory decisions
   - Industry events

6. Risk Factors
   - Company-specific risks
   - Sector headwinds
   - Regulatory concerns
   - Competitive threats

Include data sources and timestamps for all information.''',
        'calculations': [],
        'estimated_time': '1-2 minutes',
        'frequency_suggestion': 'Daily or Weekly'
    },
    
    'daily_risk_snapshot': {
        'name': 'Daily Risk Snapshot',
        'description': 'Quick morning risk metrics and market positioning',
        'prompt': '''Provide a concise daily risk snapshot:

1. Portfolio Snapshot
   - Current value and overnight change
   - Top movers (best/worst performers)

2. Risk Metrics Update
   - Current 1-day VaR (95% confidence)
   - Portfolio volatility (rolling 30-day)
   - Risk limit utilization

3. Market Context
   - Overnight market moves (US futures, Asia, Europe)
   - VIX level and change
   - Dollar index movement
   - Key economic data releases today

4. Risk Alerts
   - Any positions exceeding risk limits
   - Correlation spikes
   - Unusual volume or volatility

5. Suggested Actions
   - Rebalancing needs
   - Hedging opportunities
   - Risk reduction if needed

Keep it concise - suitable for a 2-minute morning read.''',
        'calculations': ['basic_risk'],
        'estimated_time': '30-60 seconds',
        'frequency_suggestion': 'Daily'
    },
    
    'weekly_performance': {
        'name': 'Weekly Performance & Attribution',
        'description': 'Performance analysis with attribution breakdown',
        'prompt': '''Generate a weekly performance attribution report:

1. Performance Summary
   - Total return (week, MTD, YTD)
   - Benchmark comparison
   - Risk-adjusted returns (Sharpe, Sortino)

2. Attribution Analysis
   - Performance by position
   - Sector contribution
   - Factor contribution (if applicable)

3. Risk Metrics Evolution
   - VaR trend over the week
   - Volatility changes
   - Correlation matrix updates

4. Trading Activity Impact
   - New positions added
   - Positions closed
   - Rebalancing effects

5. Next Week Outlook
   - Earnings releases in portfolio
   - Economic calendar impact
   - Technical levels to watch

6. Recommendations
   - Profit taking opportunities
   - Risk management actions
   - Rebalancing suggestions''',
        'calculations': ['basic_risk'],
        'estimated_time': '1-2 minutes',
        'frequency_suggestion': 'Weekly'
    },
    
    'compliance_risk_report': {
        'name': 'Compliance Risk Report',
        'description': 'Risk metrics for compliance and regulatory reporting',
        'prompt': '''Generate a compliance-focused risk report:

1. Risk Limit Monitoring
   - VaR vs limits (1-day, 10-day)
   - Concentration limits
   - Sector exposure limits
   - Leverage metrics

2. Regulatory Metrics
   - Liquidity coverage ratio
   - Stressed VaR
   - Expected shortfall

3. Concentration Analysis
   - Single name concentration
   - Sector concentration
   - Geographic concentration

4. Stress Test Results
   - Regulatory scenarios
   - Custom stress tests
   - Reverse stress testing

5. Compliance Checklist
   - All limits within bounds: [Yes/No]
   - Required hedges in place: [Yes/No]
   - Documentation complete: [Yes/No]

6. Audit Trail
   - Calculation methodologies
   - Data sources
   - Timestamps

Format suitable for regulatory submission.''',
        'calculations': ['basic_risk', 'monte_carlo'],
        'estimated_time': '2-3 minutes',
        'frequency_suggestion': 'Monthly or Quarterly'
    }
}


def get_template(template_id: str) -> Dict[str, Any]:
    """Get a specific template by ID."""
    return REPORT_TEMPLATES.get(template_id, {})


def list_templates() -> List[Dict[str, str]]:
    """List all available templates with basic info."""
    return [
        {
            'id': tid,
            'name': template['name'],
            'description': template['description'],
            'frequency': template['frequency_suggestion']
        }
        for tid, template in REPORT_TEMPLATES.items()
    ]


def validate_template(template_id: str) -> bool:
    """Check if a template ID is valid."""
    return template_id in REPORT_TEMPLATES