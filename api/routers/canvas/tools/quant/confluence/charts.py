"""
Chart builders for Signal Confluence Detector tool.
"""
import logging
from typing import Dict, Any, List
import plotly.graph_objects as go

logger = logging.getLogger(__name__)


def build_confluence_chart(
    ticker: str,
    extreme_signals: List[Dict[str, Any]],
    z_threshold: float,
    bias: str
) -> Dict[str, Any]:
    """
    Build scatter plot showing extreme signals by category.
    Simple, clean, and actually readable.
    """
    try:
        logger.info(f"Building confluence chart for {ticker} with {len(extreme_signals)} extreme signals")
        
        if not extreme_signals:
            logger.warning("No extreme signals to chart")
            return None
        
        # Group by category for better visualization
        category_colors = {
            "volatility": "#8b5cf6",
            "flow": "#3b82f6",
            "positioning": "#10b981",
            "smart_money": "#f59e0b",
            "short": "#ef4444"
        }
        
        # Debug: log signal categories
        logger.info(f"Extreme signals by category: {[(s.get('signal'), s.get('category')) for s in extreme_signals[:5]]}")
        
        fig = go.Figure()
        
        # Plot each category separately for legend
        for category, color in category_colors.items():
            category_signals = [sig for sig in extreme_signals if sig.get("category") == category]
            
            if not category_signals:
                logger.debug(f"No signals in category: {category}")
                continue
            
            logger.info(f"Category {category}: {len(category_signals)} signals")
            
            signal_names = []
            z_scores = []
            sizes = []
            hover_texts = []
            
            for sig in category_signals:
                signal_name = sig.get("signal", "").replace("_", " ").title()
                z_score = sig.get("z_score", 0)
                direction = sig.get("direction", "NEUTRAL").upper()
                
                signal_names.append(signal_name)
                z_scores.append(z_score)
                sizes.append(15)  # Larger dots for visibility
                
                hover_texts.append(
                    f"<b>{signal_name}</b><br>"
                    f"Category: {category.title()}<br>"
                    f"Z-Score: {z_score:+.2f}σ<br>"
                    f"Direction: {direction}"
                )
            
            fig.add_trace(go.Scatter(
                x=z_scores,
                y=signal_names,
                mode='markers',
                name=category.title(),
                marker=dict(
                    size=sizes,
                    color=color,
                    line=dict(width=2, color="#ffffff"),
                    symbol='circle'
                ),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_texts
            ))
        
        # Add threshold lines
        fig.add_vline(
            x=z_threshold,
            line=dict(color="#f59e0b", width=2, dash="dash"),
            annotation=dict(text=f"+{z_threshold:.1f}σ", font=dict(size=10, color="#f59e0b"))
        )
        fig.add_vline(
            x=-z_threshold,
            line=dict(color="#f59e0b", width=2, dash="dash"),
            annotation=dict(text=f"-{z_threshold:.1f}σ", font=dict(size=10, color="#f59e0b"))
        )
        fig.add_vline(x=0, line=dict(color="#64748b", width=1, dash="solid"))
        
        # Bias color
        bias_color = {"BULLISH": "#22c55e", "BEARISH": "#ef4444", "MIXED": "#94a3b8"}.get(bias, "#94a3b8")
        
        # Adaptive height based on number of signals
        num_signals = len(extreme_signals)
        if num_signals <= 3:
            chart_height = 350
        elif num_signals <= 10:
            chart_height = 450
        else:
            chart_height = min(800, num_signals * 35 + 150)
        
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b> Extreme Signals ({num_signals}) · Bias: <span style='color:{bias_color}'>{bias}</span>",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5, xanchor="center"
            ),
            xaxis=dict(
                title="Z-Score (σ)",
                gridcolor="#e2e8f0",
                tickfont=dict(size=11, color="#64748b"),
                showgrid=True,
                zeroline=True
            ),
            yaxis=dict(
                title="Signal",
                tickfont=dict(size=11, color="#64748b"),
                showgrid=True,
                gridcolor="#f1f5f9",
                categoryorder='total ascending'
            ),
            width=900,
            height=chart_height,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=220, r=140, t=80, b=60),
            legend=dict(
                title=dict(text="Category", font=dict(size=11)),
                yanchor="top",
                y=0.98,
                xanchor="left",
                x=1.02,
                font=dict(size=10)
            ),
            hovermode="closest"
        )
        
        return {
            "id": f"confluence_{ticker.lower()}",
            "title": f"{ticker} Extreme Signals",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build confluence chart: {e}", exc_info=True)
        return None


def build_z_score_distribution_chart(
    ticker: str,
    all_signals: Dict[str, Dict[str, Any]],
    z_threshold: float
) -> Dict[str, Any]:
    """
    Build scatter plot showing ALL signals (not just extreme) by category.
    Shows the full distribution across all categories.
    """
    try:
        logger.info(f"Building distribution chart for {ticker} with {len(all_signals)} total signals")
        
        if not all_signals:
            logger.warning("No signals to chart")
            return None
        
        # Debug: log some signal data
        sample_signals = list(all_signals.items())[:3]
        logger.info(f"Sample signals: {[(name, data.get('category'), data.get('z_score')) for name, data in sample_signals]}")
        
        category_colors = {
            "volatility": "#8b5cf6",
            "flow": "#3b82f6",
            "positioning": "#10b981",
            "smart_money": "#f59e0b",
            "short": "#ef4444"
        }
        
        fig = go.Figure()
        
        # Plot each category
        for category, color in category_colors.items():
            x_vals = []
            y_vals = []
            hover_texts = []
            marker_symbols = []
            marker_sizes = []
            
            for signal_name, signal_data in all_signals.items():
                if signal_data.get("category") != category:
                    continue
                
                z_score = signal_data.get("z_score")
                if z_score is None:
                    continue
                
                clean_name = signal_name.replace("_", " ").title()
                is_extreme = abs(z_score) >= z_threshold
                
                x_vals.append(category.title())
                y_vals.append(z_score)
                marker_symbols.append('diamond' if is_extreme else 'circle')
                marker_sizes.append(14 if is_extreme else 10)
                
                status = "<b>EXTREME</b>" if is_extreme else "Normal"
                hover_texts.append(
                    f"<b>{clean_name}</b><br>"
                    f"Z-Score: {z_score:+.2f}σ<br>"
                    f"Status: {status}"
                )
            
            if x_vals:
                fig.add_trace(go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode='markers',
                    name=category.title(),
                    marker=dict(
                        size=marker_sizes,
                        color=color,
                        symbol=marker_symbols,
                        line=dict(width=1, color="#ffffff"),
                        opacity=0.8
                    ),
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=hover_texts
                ))
        
        # Add threshold lines
        fig.add_hline(
            y=z_threshold,
            line=dict(color="#f59e0b", width=2, dash="dash"),
            annotation=dict(
                text=f"Threshold: +{z_threshold:.1f}σ",
                font=dict(size=10, color="#f59e0b"),
                xanchor="left",
                x=0.02
            )
        )
        fig.add_hline(
            y=-z_threshold,
            line=dict(color="#f59e0b", width=2, dash="dash"),
            annotation=dict(
                text=f"Threshold: -{z_threshold:.1f}σ",
                font=dict(size=10, color="#f59e0b"),
                xanchor="left",
                x=0.02
            )
        )
        fig.add_hline(y=0, line=dict(color="#64748b", width=1, dash="solid"))
        
        # Count total signals for display
        num_total = len(all_signals)
        
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b> All Signals Distribution · {num_total} Total Signals",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5, xanchor="center"
            ),
            xaxis=dict(
                title="Category",
                tickfont=dict(size=12, color="#64748b"),
                showgrid=False,
                categoryorder='array',
                categoryarray=['Volatility', 'Flow', 'Positioning', 'Smart Money', 'Short']
            ),
            yaxis=dict(
                title="Z-Score (σ)",
                gridcolor="#e2e8f0",
                tickfont=dict(size=11, color="#64748b"),
                showgrid=True,
                zeroline=True,
                zerolinecolor="#64748b",
                zerolinewidth=2
            ),
            width=900,
            height=550,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=70, r=30, t=80, b=70),
            legend=dict(
                title=dict(text="Category", font=dict(size=11)),
                yanchor="top",
                y=0.98,
                xanchor="right",
                x=0.98,
                bgcolor="rgba(255,255,255,0.95)",
                bordercolor="#e2e8f0",
                borderwidth=1,
                font=dict(size=10)
            ),
            hovermode="closest"
        )
        
        return {
            "id": f"distribution_{ticker.lower()}",
            "title": f"{ticker} Signal Distribution",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build distribution chart: {e}", exc_info=True)
        return None
