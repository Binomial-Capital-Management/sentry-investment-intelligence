"""
Chart builders for Swaption Pricing Canvas tool.
Creates meaningful charts: payoff diagram and rate sensitivity.
"""

import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def build_pricing_chart(
    swaption_price: float,
    forward_swap_rate: float,
    strike: float,
    annuity_factor: float,
    option_type: str,
    tenor: str,
    notional: float = 10_000_000
) -> Optional[Dict[str, Any]]:
    """
    Build swaption payoff diagram showing P&L at expiry vs forward rate.
    The classic hockey stick chart that traders actually use.
    """
    try:
        # Generate wide range of forward rates to show the hockey stick
        # Center around strike, extend ±300bps
        center = strike
        rate_range = np.linspace(
            max(0.001, center - 0.03),  # -300bps from strike
            center + 0.03,               # +300bps from strike
            100
        )
        
        # Calculate payoff at expiry for each rate
        # Payoff = max(0, (Forward - Strike) × Annuity × Notional) for payer
        # Payoff = max(0, (Strike - Forward) × Annuity × Notional) for receiver
        payoffs = []
        for rate in rate_range:
            if option_type.lower() == "payer":
                # Payer profits when rates rise above strike
                intrinsic = max(0, (rate - strike)) * annuity_factor * notional
            else:
                # Receiver profits when rates fall below strike
                intrinsic = max(0, (strike - rate)) * annuity_factor * notional
            
            # Net P&L = Intrinsic at expiry - Premium paid
            pnl = intrinsic - swaption_price
            payoffs.append(pnl)
        
        # Find breakeven
        breakeven_rate = None
        for i in range(len(payoffs) - 1):
            if payoffs[i] * payoffs[i+1] < 0:  # Sign change
                # Linear interpolation
                breakeven_rate = rate_range[i] + (rate_range[i+1] - rate_range[i]) * (-payoffs[i]) / (payoffs[i+1] - payoffs[i])
                break
        
        # Create chart
        return {
            "plotly": {
                "data": [
                    {
                        "type": "scatter",
                        "mode": "lines",
                        "x": [r * 100 for r in rate_range],  # Convert to %
                        "y": payoffs,
                        "name": "P&L at Expiry",
                        "line": {"color": "#3B82F6", "width": 3},
                        "hovertemplate": "Rate: %{x:.2f}%<br>P&L: $%{y:,.0f}<extra></extra>"
                    },
                    {
                        "type": "scatter",
                        "mode": "markers",
                        "x": [forward_swap_rate * 100],
                        "y": [0 - swaption_price],  # Current forward = no intrinsic, just lost premium
                        "name": f"Current Forward ({forward_swap_rate:.2%})",
                        "marker": {"color": "#10B981", "size": 12, "symbol": "diamond"},
                        "hovertemplate": f"Current Forward: {forward_swap_rate:.2%}<br>P&L if unchanged: $%{{y:,.0f}}<extra></extra>"
                    },
                    {
                        "type": "scatter",
                        "mode": "markers",
                        "x": [strike * 100],
                        "y": [-swaption_price],
                        "name": f"Strike ({strike:.2%})",
                        "marker": {"color": "#EF4444", "size": 12, "symbol": "x"},
                        "hovertemplate": f"Strike: {strike:.2%}<br>P&L at strike: $%{{y:,.0f}}<extra></extra>"
                    }
                ],
                "layout": {
                    "title": {
                        "text": f"{option_type.capitalize()} Swaption Payoff at Expiry",
                        "x": 0.5,
                        "xanchor": "center",
                        "font": {"size": 14}
                    },
                    "xaxis": {
                        "title": "Forward Swap Rate (%)",
                        "gridcolor": "#E5E7EB",
                        "zeroline": False
                    },
                    "yaxis": {
                        "title": "P&L ($)",
                        "gridcolor": "#E5E7EB",
                        "zeroline": True,
                        "zerolinecolor": "#9CA3AF",
                        "zerolinewidth": 2
                    },
                    "shapes": [
                        {
                            "type": "line",
                            "x0": strike * 100,
                            "x1": strike * 100,
                            "y0": min(payoffs) * 1.1,
                            "y1": max(payoffs) * 1.1,
                            "line": {"color": "#EF4444", "width": 1, "dash": "dash"}
                        }
                    ],
                    "annotations": [
                        {
                            "text": f"Strike: {strike:.2%}",
                            "x": strike * 100,
                            "y": max(payoffs) * 0.9,
                            "showarrow": False,
                            "font": {"size": 10, "color": "#EF4444"}
                        }
                    ] + ([{
                        "text": f"Breakeven: {breakeven_rate:.2%}",
                        "x": breakeven_rate * 100,
                        "y": 0,
                        "showarrow": True,
                        "arrowhead": 2,
                        "ax": 40,
                        "ay": -40,
                        "font": {"size": 10, "color": "#059669"}
                    }] if breakeven_rate else []),
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "font": {"family": "Inter, sans-serif", "size": 11},
                    "margin": {"l": 70, "r": 40, "t": 60, "b": 60},
                    "height": 350,
                    "showlegend": True,
                    "legend": {
                        "orientation": "h",
                        "yanchor": "bottom",
                        "y": -0.25,
                        "xanchor": "center",
                        "x": 0.5
                    }
                }
            },
            "type": "line",
            "label": "Payoff Diagram"
        }
        
    except Exception as e:
        logger.error(f"Error building payoff chart: {e}")
        return None


def build_greeks_chart(
    delta: float,
    vega: float,
    forward_swap_rate: float,
    volatility: float,
    notional: float
) -> Optional[Dict[str, Any]]:
    """
    Build rate sensitivity chart showing how premium changes with rate moves.
    More useful than just showing delta/vega numbers.
    """
    try:
        # Generate rate scenarios (±100bps)
        rate_changes_bps = list(range(-100, 101, 10))  # -100bp to +100bp in 10bp steps
        
        # Approximate premium change using delta (first-order approximation)
        # P&L ≈ Delta × ΔRate (in bps) / 100
        premium_changes = []
        for rate_change in rate_changes_bps:
            # Delta is $ change per 1bp, so multiply by bps change
            pnl = delta * rate_change / 100  # Divide by 100 because delta is per 1bp
            premium_changes.append(pnl)
        
        # Color bars based on positive/negative
        colors = ["#10B981" if p >= 0 else "#EF4444" for p in premium_changes]
        
        return {
            "plotly": {
                "data": [
                    {
                        "type": "bar",
                        "x": rate_changes_bps,
                        "y": premium_changes,
                        "marker": {"color": colors},
                        "hovertemplate": "Rate Δ: %{x}bp<br>Premium Δ: $%{y:,.0f}<extra></extra>"
                    }
                ],
                "layout": {
                    "title": {
                        "text": "Premium Sensitivity to Rate Changes",
                        "x": 0.5,
                        "xanchor": "center",
                        "font": {"size": 14}
                    },
                    "xaxis": {
                        "title": "Rate Change (bps)",
                        "gridcolor": "#E5E7EB",
                        "dtick": 25
                    },
                    "yaxis": {
                        "title": "Premium Change ($)",
                        "gridcolor": "#E5E7EB",
                        "zeroline": True,
                        "zerolinecolor": "#9CA3AF",
                        "zerolinewidth": 2
                    },
                    "annotations": [
                        {
                            "text": f"Delta: ${delta:,.0f}/bp | Vega: ${vega:,.0f}/1%vol",
                            "xref": "paper",
                            "yref": "paper",
                            "x": 0.5,
                            "y": -0.22,
                            "xanchor": "center",
                            "showarrow": False,
                            "font": {"size": 11, "color": "#6B7280"}
                        }
                    ],
                    "plot_bgcolor": "white",
                    "paper_bgcolor": "white",
                    "font": {"family": "Inter, sans-serif", "size": 11},
                    "margin": {"l": 70, "r": 40, "t": 60, "b": 80},
                    "height": 320,
                    "showlegend": False
                }
            },
            "type": "bar",
            "label": "Rate Sensitivity"
        }
        
    except Exception as e:
        logger.error(f"Error building Greeks chart: {e}")
        return None
