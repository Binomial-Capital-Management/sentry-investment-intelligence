"""
Dynamic Hedge Chart Builders

Creates visualizations for multi-Greek monitoring and backtesting.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def build_greeks_evolution_chart(daily_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build 4-subplot chart showing delta/gamma/vega/theta evolution."""
    try:
        if not daily_results:
            return None
        
        dates = [r['date'] for r in daily_results]
        
        # Extract Greeks time series
        portfolio_delta = [r['portfolio_greeks']['delta'] for r in daily_results]
        portfolio_gamma = [r['portfolio_greeks']['gamma'] for r in daily_results]
        portfolio_vega = [r['portfolio_greeks']['vega'] for r in daily_results]
        portfolio_theta = [r['portfolio_greeks']['theta'] for r in daily_results]
        
        residual_delta = [r['residual_greeks']['delta'] for r in daily_results]
        
        # Create 2x2 subplot
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=["Delta Evolution", "Gamma Evolution", "Vega Evolution", "Theta Evolution"],
            vertical_spacing=0.15,
            horizontal_spacing=0.12
        )
        
        # Delta (row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_delta, name="Portfolio Delta",
            line=dict(color='#2E86AB', width=2),
            hovertemplate='%{x}<br>Portfolio: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=residual_delta, name="Residual Delta",
            line=dict(color='#C62828', width=2, dash='dash'),
            hovertemplate='%{x}<br>Residual: %{y:.2f}<extra></extra>'
        ), row=1, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color="green", row=1, col=1)
        
        # Gamma (row=1, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_gamma, name="Gamma",
            line=dict(color='#9C27B0', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Gamma: %{y:.4f}<extra></extra>'
        ), row=1, col=2)
        
        # Vega (row=2, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_vega, name="Vega",
            line=dict(color='#FF9800', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Vega: %{y:.2f}<extra></extra>'
        ), row=2, col=1)
        
        # Theta (row=2, col=2)
        fig.add_trace(go.Scatter(
            x=dates, y=portfolio_theta, name="Theta",
            line=dict(color='#4CAF50', width=2),
            showlegend=False,
            hovertemplate='%{x}<br>Theta: %{y:.2f}<extra></extra>'
        ), row=2, col=2)
        
        fig.update_layout(
            title="Greeks Evolution Over Time",
            template="plotly_white",
            height=600,
            showlegend=True,
            legend=dict(x=0.7, y=1.12, orientation='h'),
            hovermode='x unified'
        )
        
        fig.update_yaxes(title_text="Delta", row=1, col=1)
        fig.update_yaxes(title_text="Gamma", row=1, col=2)
        fig.update_yaxes(title_text="Vega", row=2, col=1)
        fig.update_yaxes(title_text="Theta", row=2, col=2)
        
        return {
            "id": "greeks_evolution",
            "title": "Greeks Evolution",
            "plotly": fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Greeks evolution chart failed: {e}")
        return None


def build_drift_score_chart(
    daily_results: List[Dict[str, Any]],
    threshold: float = 0.1
) -> Dict[str, Any]:
    """Build drift score chart with rebalancing markers."""
    try:
        if not daily_results:
            return None
        
        dates = [r['date'] for r in daily_results]
        drift_scores = [r['drift_score'] for r in daily_results]
        
        # Find rebalancing dates
        rebalancing_dates = [r['date'] for r in daily_results if r.get('rebalancing_triggered')]
        rebalancing_scores = [r['drift_score'] for r in daily_results if r.get('rebalancing_triggered')]
        
        fig = go.Figure()
        
        # Drift score line
        fig.add_trace(go.Scatter(
            x=dates,
            y=drift_scores,
            name="Drift Score",
            mode='lines',
            line=dict(color='#2E86AB', width=2),
            fill='tozeroy',
            fillcolor='rgba(46, 134, 171, 0.2)',
            hovertemplate='%{x}<br>Drift: %{y:.4f}<extra></extra>'
        ))
        
        # Rebalancing markers
        if rebalancing_dates:
            fig.add_trace(go.Scatter(
                x=rebalancing_dates,
                y=rebalancing_scores,
                name=f"Rebalance ({len(rebalancing_dates)})",
                mode='markers',
                marker=dict(
                    color='#C62828',
                    size=10,
                    symbol='triangle-up',
                    line=dict(color='darkred', width=1)
                ),
                hovertemplate='%{x}<br>Rebalance<br>Score: %{y:.4f}<extra></extra>'
            ))
        
        # Threshold line
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Threshold: {threshold}",
            annotation_position="right"
        )
        
        fig.update_layout(
            title="Multi-Greek Drift Score & Rebalancing Events",
            xaxis_title="Date",
            yaxis_title="Drift Score",
            template="plotly_white",
            height=400,
            hovermode='x unified',
            showlegend=True
        )
        
        return {
            "id": "drift_score",
            "title": "Drift Score & Rebalancing",
            "plotly": fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Drift score chart failed: {e}")
        return None


def build_pnl_comparison_chart(daily_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build cumulative P&L comparison chart."""
    try:
        if not daily_results:
            return None
        
        dates = [r['date'] for r in daily_results]
        hedged_pnl = [r.get('hedged_pnl', 0) for r in daily_results]
        unhedged_pnl = [r.get('unhedged_pnl', 0) for r in daily_results]
        
        fig = go.Figure()
        
        # Hedged P&L
        fig.add_trace(go.Scatter(
            x=dates,
            y=hedged_pnl,
            name="Hedged P&L",
            mode='lines',
            line=dict(color='#2E7D32', width=3),
            hovertemplate='%{x}<br>Hedged: $%{y:,.2f}<extra></extra>'
        ))
        
        # Unhedged P&L
        fig.add_trace(go.Scatter(
            x=dates,
            y=unhedged_pnl,
            name="Unhedged P&L",
            mode='lines',
            line=dict(color='#C62828', width=3),
            hovertemplate='%{x}<br>Unhedged: $%{y:,.2f}<extra></extra>'
        ))
        
        # Fill between
        fig.add_trace(go.Scatter(
            x=dates + dates[::-1],
            y=hedged_pnl + unhedged_pnl[::-1],
            fill='toself',
            fillcolor='rgba(46, 125, 50, 0.15)',
            line=dict(color='rgba(0,0,0,0)'),
            hoverinfo='skip',
            showlegend=False
        ))
        
        # Zero line
        fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)
        
        fig.update_layout(
            title="Cumulative P&L: Hedged vs Unhedged",
            xaxis_title="Date",
            yaxis_title="Cumulative P&L ($)",
            template="plotly_white",
            height=400,
            hovermode='x unified',
            showlegend=True,
            legend=dict(x=0.02, y=0.98)
        )
        
        return {
            "id": "pnl_comparison",
            "title": "P&L Comparison",
            "plotly": fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"P&L comparison chart failed: {e}")
        return None


def build_scenario_heatmap(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build heatmap of residual delta across price/vol scenarios."""
    try:
        if not scenarios:
            return None
        
        # Extract unique price moves and vol changes
        price_moves = sorted(list(set(s['price_move_pct'] for s in scenarios)))
        vol_changes = sorted(list(set(s['vol_change_pct'] for s in scenarios)))
        
        # Build matrix
        z_matrix = []
        for vol in vol_changes:
            row = []
            for price in price_moves:
                # Find matching scenario
                for s in scenarios:
                    if s['price_move_pct'] == price and s['vol_change_pct'] == vol:
                        row.append(s.get('residual_delta', 0))
                        break
                else:
                    row.append(0)
            z_matrix.append(row)
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z_matrix,
            x=[f"{p:+.0f}%" for p in price_moves],
            y=[f"Vol {v:+.0f}%" for v in vol_changes],
            colorscale='RdYlGn_r',
            colorbar=dict(title="Residual Δ"),
            hovertemplate='Price: %{x}<br>Vol: %{y}<br>Residual Δ: %{z:.2f}<extra></extra>'
        ))
        
        # Add residual delta values as text annotations
        for i, vol in enumerate(vol_changes):
            for j, price in enumerate(price_moves):
                for s in scenarios:
                    if s['price_move_pct'] == price and s['vol_change_pct'] == vol:
                        residual = s.get('residual_delta', 0)
                        # Format: use K for thousands
                        if abs(residual) >= 1000:
                            text = f"{residual/1000:.1f}K"
                        else:
                            text = f"{residual:.0f}"
                        
                        fig.add_annotation(
                            x=f"{price:+.0f}%",
                            y=f"Vol {vol:+.0f}%",
                            text=text,
                            showarrow=False,
                            font=dict(size=11, color="white", family="Arial Black"),
                            bgcolor="rgba(0,0,0,0.7)",
                            borderpad=3
                        )
                        break
        
        fig.update_layout(
            title="Scenario Analysis: Residual Delta",
            xaxis_title="Price Move",
            yaxis_title="Volatility Change",
            template="plotly_white",
            height=400
        )
        
        return {
            "id": "scenario_heatmap",
            "title": "Scenario Analysis",
            "plotly": fig.to_dict()
        }
    except Exception as e:
        logger.warning(f"Scenario heatmap failed: {e}")
        return None
