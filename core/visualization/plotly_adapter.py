"""Simple bridge between existing data structures and Plotly charts."""
from .plotly_charts import RiskCharts
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


class PlotlyAdapter:
    """Adapter to create Plotly charts from risk analysis results."""
    
    def __init__(self, color_scheme='binomial_blue'):
        self.charts = RiskCharts(color_scheme=color_scheme)
    
    def create_charts(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Create all relevant charts from analysis results."""
        charts = {}
        
        # Portfolio allocation - this should always work if we have weights
        if 'weights' in results:
            try:
                charts['allocation'] = self.charts.plot_portfolio_allocation(
                    weights=results['weights'],
                    title="Portfolio Allocation"
                )
            except Exception as e:
                print(f"Allocation chart error: {e}")
        
        # VaR comparison - we have this data
        if 'risk_metrics' in results:
            try:
                var_data = self._extract_var_data(results['risk_metrics'])
                if var_data:
                    # Extract just the VaR values for comparison
                    var_values = {method: data.get('var_95', 0) for method, data in var_data.items()}
                    charts['var_comparison'] = self.charts.plot_var_comparison(var_values)
            except Exception as e:
                print(f"VaR comparison error: {e}")
        
        # Risk decomposition if available
        if 'risk_decomposition' in results:
            try:
                # Check if it's already in the right format
                risk_data = results['risk_decomposition']
                if isinstance(risk_data, dict):
                    # Ensure we have numeric values
                    if 'systematic_risk' in risk_data and 'idiosyncratic_risk' in risk_data:
                        risk_data = {
                            'Systematic Risk': float(risk_data.get('systematic_risk', 0.5)),
                            'Idiosyncratic Risk': float(risk_data.get('idiosyncratic_risk', 0.5))
                        }
                    charts['risk_decomposition'] = self.charts.plot_risk_decomposition(risk_data)
            except Exception as e:
                print(f"Risk decomposition error: {e}")
        
        # Module-specific charts
        
        # Barra Factor Analysis
        if 'factor_results' in results and results.get('factor_results'):
            factor_results = results['factor_results']
            if 'factor_exposures' in factor_results:
                try:
                    charts['factor_exposures'] = self.charts.plot_factor_exposures_heatmap(
                        factor_exposures=factor_results['factor_exposures'],
                        title="Factor Exposures (Barra Model)"
                    )
                except Exception as e:
                    print(f"Factor exposures chart error: {e}")
        
        # Monte Carlo Simulation
        if 'risk_metrics' in results and 'monte_carlo' in results['risk_metrics']:
            mc_data = results['risk_metrics']['monte_carlo']
            if 'simulation_paths' in mc_data or 'simulated_returns' in mc_data:
                try:
                    charts['monte_carlo_simulation'] = self.charts.plot_monte_carlo_simulation(
                        simulation_data=mc_data,
                        title="Monte Carlo Risk Simulation"
                    )
                except Exception as e:
                    print(f"Monte Carlo simulation chart error: {e}")
        
        # Efficient Frontier (for optimization results)
        if 'optimization' in results:
            # Check if we have frontier data
            if 'frontier' in results:
                try:
                    charts['efficient_frontier'] = self.charts.plot_efficient_frontier(
                        frontier_data=results['frontier'],
                        current_portfolio=results.get('current_portfolio'),
                        optimized_portfolio=results.get('optimization')
                    )
                except Exception as e:
                    print(f"Efficient frontier chart error: {e}")
        
        # Correlation Matrix (if available)
        if 'returns_data' in results and 'returns' in results['returns_data']:
            try:
                returns_df = results['returns_data']['returns']
                if isinstance(returns_df, pd.DataFrame) and len(returns_df.columns) > 1:
                    charts['correlation_matrix'] = self.charts.plot_correlation_matrix(
                        returns=returns_df,
                        title="Asset Correlation Matrix"
                    )
            except Exception as e:
                print(f"Correlation matrix chart error: {e}")
        
        # Returns Distribution (if we have portfolio returns)
        if 'returns_data' in results and 'returns' in results['returns_data'] and 'weights' in results:
            try:
                returns_df = results['returns_data']['returns']
                weights = list(results['weights'].values())
                portfolio_returns = returns_df @ weights
                
                charts['returns_distribution'] = self.charts.plot_returns_distribution(
                    returns=portfolio_returns,
                    title="Portfolio Returns Distribution"
                )
            except Exception as e:
                print(f"Returns distribution chart error: {e}")
        
        return charts
    
    def _extract_var_data(self, risk_metrics: Dict) -> Optional[Dict]:
        """Extract VaR data from different calculation methods."""
        var_data = {}
        
        for method in ['parametric', 'historical', 'monte_carlo']:
            if method in risk_metrics:
                var_data[method] = {
                    'var_95': risk_metrics[method].get('VaR_0.95', 0),
                    'var_99': risk_metrics[method].get('VaR_0.99', 0),
                    'cvar_95': risk_metrics[method].get('CVaR_0.95', 0),
                    'cvar_99': risk_metrics[method].get('CVaR_0.99', 0)
                }
        
        return var_data if var_data else None