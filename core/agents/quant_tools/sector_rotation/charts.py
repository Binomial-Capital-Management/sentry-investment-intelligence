"""
Visualization for sector rotation analysis.

Uses Plotly + register_chart_handle for proper caching.
All styling configurable.
"""

from typing import Dict, List, Optional, Any, Tuple
import logging

from core.agents.risk_tools.shared import register_chart_handle

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_CHART_CONFIG = {
    # Figure sizing
    "figure_width": 900,
    "figure_height": 600,
    "heatmap_height": 500,
    
    # Colors
    "bullish_color": "#22c55e",
    "bearish_color": "#ef4444",
    "neutral_color": "#6b7280",
    "background_color": "#1f2937",
    "text_color": "#f3f4f6",
    
    # Cache TTL
    "chart_ttl_seconds": 900,
}


# =============================================================================
# CHART GENERATOR
# =============================================================================

class ChartGenerator:
    """
    Generates visualizations for sector rotation analysis.
    
    Uses Plotly for charts and register_chart_handle for caching.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_CHART_CONFIG, **(config or {})}
        self._go = None
    
    def _lazy_import(self):
        """Lazy import plotly."""
        if self._go is None:
            try:
                import plotly.graph_objects as go
                self._go = go
            except ImportError:
                logger.warning("plotly not installed")
                return False
        return True
    
    def sector_signal_bars(
        self,
        sector_signals: Dict[str, float],
        title: str = "Sector Rotation Signals"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate bar chart of sector signals.
        
        Returns cached chart handle, not the full chart data.
        """
        if not self._lazy_import():
            return None
        
        go = self._go
        
        try:
            # Sort by signal strength
            sorted_sectors = sorted(
                sector_signals.items(),
                key=lambda x: x[1],
                reverse=True
            )
            sectors = [s[0] for s in sorted_sectors]
            signals = [s[1] for s in sorted_sectors]
            
            # Color based on direction
            colors = [
                self.config.get("bullish_color", "#22c55e") if s > 0
                else self.config.get("bearish_color", "#ef4444")
                for s in signals
            ]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=sectors,
                x=signals,
                orientation='h',
                marker_color=colors,
                text=[f'{s:.2f}σ' for s in signals],
                textposition='outside',
            ))
            
            fig.update_layout(
                title=title,
                xaxis_title="Signal Strength (σ)",
                height=self.config.get("figure_height", 600),
                width=self.config.get("figure_width", 900),
                template="plotly_dark",
            )
            
            # Add zero line
            fig.add_vline(
                x=0, 
                line_dash="dash", 
                line_color=self.config.get("neutral_color", "#6b7280")
            )
            
            # Convert to dict for caching
            plotly_payload = fig.to_dict()
            
            # Register with chart cache and return handle
            return register_chart_handle(
                plotly_payload,
                chart_type="sector_rotation_signals",
                title=title,
                alt_text=f"Bar chart showing sector rotation signals for {len(sectors)} sectors",
                ttl_seconds=self.config.get("chart_ttl_seconds", 900),
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate sector signal bars: {e}")
            return None
    
    def factor_heatmap(
        self,
        factor_matrix: Dict[str, Dict[str, float]],
        title: str = "Factor Scores by Sector"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate heatmap of factor scores across sectors.
        
        Returns cached chart handle.
        """
        if not self._lazy_import():
            return None
        
        go = self._go
        
        try:
            # Convert to lists for Plotly
            sectors = list(factor_matrix.keys())
            if not sectors:
                return None
            
            factors = list(factor_matrix[sectors[0]].keys())
            
            z_values = [
                [factor_matrix[sector].get(factor, 0) for factor in factors]
                for sector in sectors
            ]
            
            fig = go.Figure(data=go.Heatmap(
                z=z_values,
                x=factors,
                y=sectors,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f'{v:.2f}' for v in row] for row in z_values],
                texttemplate='%{text}',
                textfont={"size": 10},
                hoverongaps=False,
            ))
            
            fig.update_layout(
                title=title,
                height=self.config.get("heatmap_height", 500),
                width=self.config.get("figure_width", 900),
                template="plotly_dark",
            )
            
            plotly_payload = fig.to_dict()
            
            return register_chart_handle(
                plotly_payload,
                chart_type="sector_factor_heatmap",
                title=title,
                alt_text=f"Heatmap showing factor scores across {len(sectors)} sectors",
                ttl_seconds=self.config.get("chart_ttl_seconds", 900),
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate factor heatmap: {e}")
            return None
    
    def rotation_flow_chart(
        self,
        flow_history: List[Dict[str, float]],
        sectors: List[str],
        title: str = "Sector Flow Over Time"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate line chart showing flow evolution.
        
        Returns cached chart handle.
        """
        if not self._lazy_import():
            return None
        
        go = self._go
        
        try:
            fig = go.Figure()
            
            for sector in sectors:
                values = [h.get(sector, 0) for h in flow_history]
                fig.add_trace(go.Scatter(
                    y=values,
                    mode='lines',
                    name=sector,
                    line=dict(width=2),
                ))
            
            fig.update_layout(
                title=title,
                xaxis_title="Time Period",
                yaxis_title="Flow Z-Score",
                height=self.config.get("figure_height", 600),
                width=self.config.get("figure_width", 900),
                template="plotly_dark",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            
            # Add zero line
            fig.add_hline(
                y=0, 
                line_dash="dash", 
                line_color=self.config.get("neutral_color", "#6b7280")
            )
            
            plotly_payload = fig.to_dict()
            
            return register_chart_handle(
                plotly_payload,
                chart_type="sector_rotation_flow",
                title=title,
                alt_text=f"Line chart showing flow over time for {len(sectors)} sectors",
                ttl_seconds=self.config.get("chart_ttl_seconds", 900),
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate rotation flow chart: {e}")
            return None
    
    def regime_timeline(
        self,
        regimes: List[Tuple[str, str]],
        title: str = "Market Regime Timeline"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate timeline showing regime changes.
        
        Returns cached chart handle.
        """
        if not self._lazy_import():
            return None
        
        go = self._go
        
        try:
            regime_colors = {
                "risk_on": self.config.get("bullish_color", "#22c55e"),
                "risk_off": self.config.get("bearish_color", "#ef4444"),
                "transition": self.config.get("neutral_color", "#6b7280"),
            }
            
            colors = [
                regime_colors.get(regime, self.config.get("neutral_color", "#6b7280"))
                for _, regime in regimes
            ]
            
            dates = [date for date, _ in regimes]
            
            fig = go.Figure(data=go.Bar(
                x=dates,
                y=[1] * len(regimes),
                marker_color=colors,
                hovertext=[regime for _, regime in regimes],
            ))
            
            fig.update_layout(
                title=title,
                xaxis_title="Time Period",
                height=200,
                width=self.config.get("figure_width", 900),
                template="plotly_dark",
                showlegend=False,
                yaxis=dict(showticklabels=False),
            )
            
            plotly_payload = fig.to_dict()
            
            return register_chart_handle(
                plotly_payload,
                chart_type="regime_timeline",
                title=title,
                alt_text=f"Timeline showing {len(regimes)} regime periods",
                ttl_seconds=self.config.get("chart_ttl_seconds", 900),
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate regime timeline: {e}")
            return None
