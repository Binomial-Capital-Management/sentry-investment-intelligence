"""
Chart builders for Dealer Gamma Regime tool.
"""
import logging
from typing import Dict, Any, List
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def build_gamma_profile_chart(
    ticker: str,
    gamma_profile: List[Dict[str, Any]],
    spot_price: float,
    key_levels: Dict[str, Any],
    regime_estimate: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build gamma profile chart with key levels and regime annotation.
    
    Shows:
    - Gross gamma exposure by strike (bar chart)
    - Spot price (red solid line)
    - Max gamma strike (orange dotted line)
    - Put wall (green dashed line)
    - Call wall (red dashed line)
    - Regime label in title
    """
    try:
        if not gamma_profile:
            logger.warning("No gamma profile data to chart")
            return None
        
        # Extract strikes and GEX values
        strikes = [entry["strike"] for entry in gamma_profile]
        gross_gex_millions = [entry["gross_gex_millions"] for entry in gamma_profile]
        
        # Extract key levels
        max_gamma_strike = key_levels.get("max_gamma_strike", 0)
        put_wall = key_levels.get("put_wall", 0)
        call_wall = key_levels.get("call_wall", 0)
        
        # Extract regime info
        regime = regime_estimate.get("regime", "unknown")
        confidence = regime_estimate.get("confidence", 0)
        method = regime_estimate.get("method", "autocorrelation")
        
        # Create figure
        fig = go.Figure()
        
        # Add gross gamma bars
        fig.add_trace(go.Bar(
            x=strikes,
            y=gross_gex_millions,
            name="Gross Gamma Exposure",
            marker=dict(
                color="#6366f1",
                line=dict(width=0)
            ),
            hovertemplate=(
                "<b>Strike:</b> $%{x:.2f}<br>"
                "<b>Gross GEX:</b> $%{y:.2f}M<br>"
                "<extra></extra>"
            )
        ))
        
        # Spot price line
        fig.add_vline(
            x=spot_price,
            line=dict(color="#ef4444", width=2.5, dash="solid"),
            annotation=dict(
                text=f"Spot ${spot_price:.2f}",
                font=dict(color="#ef4444", size=11, family="Inter, sans-serif"),
                yshift=10,
                xanchor="center"
            )
        )
        
        # Max gamma strike line
        if max_gamma_strike and abs(max_gamma_strike - spot_price) > (spot_price * 0.01):
            fig.add_vline(
                x=max_gamma_strike,
                line=dict(color="#f59e0b", width=2, dash="dot"),
                annotation=dict(
                    text=f"Max γ ${max_gamma_strike:.2f}",
                    font=dict(color="#f59e0b", size=10, family="Inter, sans-serif"),
                    yshift=-20,
                    xanchor="center"
                )
            )
        
        # Put wall line (below spot)
        if put_wall and put_wall < spot_price:
            fig.add_vline(
                x=put_wall,
                line=dict(color="#22c55e", width=1.5, dash="dash"),
                annotation=dict(
                    text="Put Wall",
                    font=dict(color="#22c55e", size=9, family="Inter, sans-serif"),
                    yshift=30,
                    xshift=-10,
                    xanchor="right"
                )
            )
        
        # Call wall line (above spot)
        if call_wall and call_wall > spot_price:
            fig.add_vline(
                x=call_wall,
                line=dict(color="#ef4444", width=1.5, dash="dash"),
                annotation=dict(
                    text="Call Wall",
                    font=dict(color="#ef4444", size=9, family="Inter, sans-serif"),
                    yshift=30,
                    xshift=10,
                    xanchor="left"
                )
            )
        
        # Regime text for title
        regime_display_map = {
            "short_gamma": f"SHORT γ ({confidence:.0%})",
            "long_gamma": f"LONG γ ({confidence:.0%})",
            "neutral": "Neutral",
            "SHORT_GAMMA": f"SHORT γ ({confidence:.0%}) [HMM]",
            "LONG_GAMMA": f"LONG γ ({confidence:.0%}) [HMM]",
            "NEUTRAL": "Neutral [HMM]",
            "insufficient_data": "Insufficient Data",
            "estimation_failed": "Estimation Failed",
            "no_history": "No History"
        }
        regime_text = regime_display_map.get(regime, regime.replace("_", " ").title())
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b> Gross Gamma Profile · Regime: {regime_text}",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title=dict(
                    text="Strike Price ($)",
                    font=dict(size=12, color="#475569", family="Inter, sans-serif")
                ),
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b", family="Inter, sans-serif"),
                showgrid=True
            ),
            yaxis=dict(
                title=dict(
                    text="Gross Gamma Exposure ($M)",
                    font=dict(size=12, color="#475569", family="Inter, sans-serif")
                ),
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b", family="Inter, sans-serif"),
                showgrid=True
            ),
            width=900,
            height=500,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            showlegend=False,
            hovermode="x unified"
        )
        
        return {
            "id": f"gamma_profile_{ticker.lower()}",
            "title": f"{ticker} Gamma Profile",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build gamma profile chart: {e}", exc_info=True)
        return None
