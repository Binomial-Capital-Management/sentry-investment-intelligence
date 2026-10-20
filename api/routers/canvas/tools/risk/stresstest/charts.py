"""
Stress Test Charts for Canvas

Generates visualization charts for correlation stress test results.
"""
from typing import Dict, Any, List, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


def build_risk_escalation_chart(
    baseline_metrics: Dict[str, float],
    stressed_results: Dict[float, Dict[str, float]],
    correlation_scenarios: List[float],
    portfolio_value: float
) -> Optional[Dict[str, Any]]:
    """Build chart showing VaR/CVaR escalation across scenarios."""
    try:
        import plotly.graph_objects as go
        
        scenarios = ['Baseline'] + [f'ρ→{c:.0%}' for c in sorted(correlation_scenarios)]
        var_values = [baseline_metrics['var']]
        cvar_values = [baseline_metrics['cvar']]
        
        for corr in sorted(correlation_scenarios):
            var_values.append(stressed_results[corr]['var_95'])
            cvar_values.append(stressed_results[corr]['cvar_95'])
        
        var_pct = [(v / portfolio_value) * 100 for v in var_values]
        cvar_pct = [(v / portfolio_value) * 100 for v in cvar_values]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=scenarios,
            y=var_pct,
            name='95% VaR',
            mode='lines+markers',
            line=dict(color='#f59e0b', width=3),
            marker=dict(size=10),
            hovertemplate='%{x}<br>VaR: %{y:.1f}%<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=scenarios,
            y=cvar_pct,
            name='95% CVaR',
            mode='lines+markers',
            line=dict(color='#ef4444', width=3),
            marker=dict(size=10),
            hovertemplate='%{x}<br>CVaR: %{y:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            title='Risk Escalation Under Correlation Stress',
            xaxis_title='Scenario',
            yaxis_title='Loss (% of Portfolio)',
            height=450,
            showlegend=True,
            hovermode='x unified',
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        
        fig.update_xaxes(tickangle=45)
        fig.update_yaxes(ticksuffix='%')
        
        return {
            "id": "risk_escalation",
            "title": "Risk Escalation Under Correlation Stress",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build risk escalation chart: {e}")
        return None


def build_distribution_chart(
    baseline_paths: np.ndarray,
    stressed_paths: np.ndarray,
    initial_value: float
) -> Optional[Dict[str, Any]]:
    """Build histogram comparing terminal value distributions."""
    try:
        import plotly.graph_objects as go
        
        baseline_terminal = baseline_paths[:, -1]
        stressed_terminal = stressed_paths[:, -1]
        
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=baseline_terminal,
            name='Baseline',
            opacity=0.7,
            nbinsx=50,
            marker_color='#3b82f6'
        ))
        
        fig.add_trace(go.Histogram(
            x=stressed_terminal,
            name='Crash Scenario',
            opacity=0.7,
            nbinsx=50,
            marker_color='#ef4444'
        ))
        
        fig.add_vline(
            x=initial_value,
            line_dash="dash",
            line_color="gray",
            annotation_text="Initial Value"
        )
        
        fig.update_layout(
            title='Portfolio Value Distribution',
            xaxis_title='Terminal Portfolio Value ($)',
            yaxis_title='Frequency',
            barmode='overlay',
            height=450,
            showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99),
        )
        
        return {
            "id": "distribution_comparison",
            "title": "Portfolio Value Distribution",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build distribution chart: {e}")
        return None


def build_correlation_heatmap(
    baseline_corr: np.ndarray,
    stressed_corr: np.ndarray,
    tickers: List[str]
) -> Optional[Dict[str, Any]]:
    """Build side-by-side correlation heatmaps."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        n_assets = len(tickers)
        height = max(450, n_assets * 45)
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Baseline Correlation', 'Crash Correlation'),
            horizontal_spacing=0.15
        )
        
        # Baseline
        fig.add_trace(
            go.Heatmap(
                z=baseline_corr,
                x=tickers,
                y=tickers,
                colorscale='RdBu_r',
                zmid=0,
                zmin=-1,
                zmax=1,
                text=np.round(baseline_corr, 2),
                texttemplate='%{text}',
                textfont={"size": 9},
                colorbar=dict(x=0.45, title='ρ', len=0.8)
            ),
            row=1, col=1
        )
        
        # Stressed
        fig.add_trace(
            go.Heatmap(
                z=stressed_corr,
                x=tickers,
                y=tickers,
                colorscale='RdBu_r',
                zmid=0,
                zmin=-1,
                zmax=1,
                text=np.round(stressed_corr, 2),
                texttemplate='%{text}',
                textfont={"size": 9},
                colorbar=dict(x=1.02, title='ρ', len=0.8)
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            title='Correlation Matrices: Baseline vs Crash',
            height=height,
            showlegend=False
        )
        
        fig.update_xaxes(tickangle=45)
        
        return {
            "id": "correlation_heatmap",
            "title": "Correlation Matrices",
            "plotly": fig.to_dict()
        }
        
    except Exception as e:
        logger.warning(f"Failed to build correlation heatmap: {e}")
        return None
















