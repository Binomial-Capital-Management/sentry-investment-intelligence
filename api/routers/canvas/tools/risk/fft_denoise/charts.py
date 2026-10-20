"""Chart builders for FFT Denoising."""

import logging
from typing import Dict, Any, List, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


def build_fft_comparison_chart(
    ticker: str,
    dates: List[str],
    original_prices: List[float],
    fft_components: Dict[str, Dict[str, Any]],
    components_selected: List[int]
) -> Optional[Dict[str, Any]]:
    """
    Build FFT comparison chart showing original vs denoised prices at multiple component levels.
    
    Args:
        ticker: Stock ticker
        dates: List of date strings
        original_prices: Original price data
        fft_components: Dict of component level -> reconstructed data
        components_selected: List of component counts used
        
    Returns:
        Chart dict in Canvas format or None if no data
    """
    try:
        if not dates or not original_prices:
            logger.warning("No data for FFT comparison chart")
            return None
        
        # Color palette for different component levels
        colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444']
        
        # Create figure
        fig = go.Figure()
        
        # Add original price as prominent reference line
        fig.add_trace(go.Scatter(
            x=dates,
            y=original_prices,
            mode='lines',
            name='Original Price',
            line=dict(color='#64748b', width=2),
            opacity=0.85
        ))
        
        # Add each component level
        for idx, n_comp in enumerate(sorted(components_selected)):
            comp_str = str(n_comp)
            if comp_str not in fft_components:
                continue
            
            comp_data = fft_components[comp_str]
            trend_data = comp_data.get("trend_data", [])
            avg_period = comp_data.get("avg_period_days", 0)
            
            color = colors[idx % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=trend_data,
                mode='lines',
                name=f'{n_comp} Components ({avg_period:.0f}d trend)',
                line=dict(color=color, width=2.5)
            ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b> FFT Denoising - Multi-Resolution Trends",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title="Date",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            yaxis=dict(
                title="Price ($)",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            width=1200,
            height=500,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            hovermode="x unified",
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor="rgba(255, 255, 255, 0.95)",
                bordercolor="#e2e8f0",
                borderwidth=1
            )
        )
        
        return {
            "id": f"fft_comparison_{ticker.lower()}",
            "title": f"{ticker} FFT Comparison",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build FFT comparison chart: {e}", exc_info=True)
        return None


def build_frequency_spectrum_chart(
    ticker: str,
    dominant_frequencies: List[float],
    dominant_periods: List[float]
) -> Optional[Dict[str, Any]]:
    """
    Build frequency spectrum chart showing dominant periods.
    
    Args:
        ticker: Stock ticker
        dominant_frequencies: List of dominant frequency values
        dominant_periods: List of period values (in days) corresponding to frequencies
        
    Returns:
        Chart dict in Canvas format or None if no data
    """
    try:
        if not dominant_periods:
            logger.warning("No dominant periods for spectrum chart")
            return None
        
        # Take top 10 most significant periods
        periods_to_show = dominant_periods[:10]
        indices = list(range(1, len(periods_to_show) + 1))
        
        # Create bar chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=indices,
            y=periods_to_show,
            marker=dict(
                color=periods_to_show,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Period<br>(days)",
                    titlefont=dict(size=10),
                    tickfont=dict(size=9)
                )
            ),
            text=[f"{p:.1f}d" for p in periods_to_show],
            textposition='outside',
            hovertemplate='<b>Component %{x}</b><br>Period: %{y:.1f} days<extra></extra>'
        ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>{ticker}</b> Dominant Frequency Periods",
                font=dict(size=16, family="Inter, sans-serif", color="#0f172a"),
                x=0.5,
                xanchor="center"
            ),
            xaxis=dict(
                title="Frequency Component (ranked by amplitude)",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b"),
                dtick=1
            ),
            yaxis=dict(
                title="Period (days)",
                gridcolor="#e2e8f0",
                tickfont=dict(size=10, color="#64748b")
            ),
            width=1200,
            height=500,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f8fafc",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=60, r=30, t=80, b=60),
            showlegend=False
        )
        
        return {
            "id": f"fft_spectrum_{ticker.lower()}",
            "title": f"{ticker} Frequency Spectrum",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to build frequency spectrum chart: {e}", exc_info=True)
        return None


