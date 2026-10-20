"""
Hedge Portfolio Optimizer - Automatically construct portfolios to neutralize factor exposures.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.optimize import minimize
from core.visualization.risk_templates.hedge_visualizations import HedgePortfolioVisualizations
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class HedgePortfolioOptimizer:
    """
    Constructs hedge portfolios to neutralize unwanted factor exposures.
    Can create market-neutral, sector-neutral, or custom factor-neutral portfolios.
    """
    
    def __init__(self, barra_model):
        """
        Initialize with a fitted BarraFactorModel.
        
        Parameters:
        -----------
        barra_model : BarraFactorModel
            Fitted factor model with calculated exposures
        """
        self.barra_model = barra_model
        if barra_model.factor_exposures is None:
            raise ValueError("Barra model must be fitted before creating hedges")
            
    def calculate_hedge_weights(self, 
                              portfolio_weights: Dict[str, float],
                              target_betas: Optional[Dict[str, float]] = None,
                              hedge_universe: Optional[List[str]] = None,
                              constraints: str = 'long_short',
                              max_position_size: float = 0.5) -> Dict[str, float]:
        """
        Calculate optimal hedge portfolio weights to achieve target factor exposures.
        
        Parameters:
        -----------
        portfolio_weights : Dict[str, float]
            Current portfolio weights by ticker
        target_betas : Dict[str, float], optional
            Target factor exposures (default: 0 for all factors)
        hedge_universe : List[str], optional
            Tickers available for hedging (default: factor ETFs)
        constraints : str
            'long_only' or 'long_short' constraints
        max_position_size : float
            Maximum weight for any single position
            
        Returns:
        --------
        Dict[str, float] : Hedge portfolio weights
        """
        # Convert portfolio weights to array
        tickers = list(portfolio_weights.keys())
        weights = np.array([portfolio_weights[t] for t in tickers])
        
        # Get current portfolio betas
        exposures = self.barra_model.factor_exposures.loc[tickers]
        portfolio_betas = exposures.T @ weights
        
        # Set default target betas (0 = market neutral)
        if target_betas is None:
            target_betas = {factor: 0.0 for factor in portfolio_betas.index}
        
        # Determine hedge universe (default to factor ETFs)
        if hedge_universe is None:
            hedge_universe = list(self.barra_model.FACTOR_ETFS.keys())
            
        # Get hedge instrument exposures
        hedge_exposures = self._get_hedge_exposures(hedge_universe)
        
        # Calculate required hedge to achieve target betas
        hedge_weights = self._optimize_hedge(
            portfolio_betas=portfolio_betas,
            target_betas=target_betas,
            hedge_exposures=hedge_exposures,
            constraints=constraints,
            max_position_size=max_position_size
        )
        
        return hedge_weights
    
    def _get_hedge_exposures(self, hedge_universe: List[str]) -> pd.DataFrame:
        """Get or estimate factor exposures for hedge instruments."""
        etf_exposures = {}
        
        for etf in hedge_universe:
            # First check if we have calculated exposures for this ETF
            if etf in self.barra_model.factor_exposures.index:
                etf_exposures[etf] = self.barra_model.factor_exposures.loc[etf]
            elif etf in self.barra_model.FACTOR_ETFS:
                # If not calculated but it's a factor ETF, use simplified assumption
                # This is a fallback - ideally all ETFs should be in factor_exposures
                factor_name = self.barra_model.FACTOR_ETFS[etf]
                exposures = pd.Series(0.0, index=self.barra_model.factor_exposures.columns)
                if factor_name in exposures.index:
                    exposures[factor_name] = 1.0
                    # Add small market beta for sector ETFs
                    if 'Market' in exposures.index and factor_name != 'Market':
                        exposures['Market'] = 0.3
                etf_exposures[etf] = exposures
                logger.warning(f"Using simplified exposures for {etf}. Consider including it in portfolio analysis for accurate exposures.")
                    
        if not etf_exposures:
            raise ValueError("No valid hedge instruments found in hedge universe")
            
        return pd.DataFrame(etf_exposures).T
    
    def _optimize_hedge(self,
                       portfolio_betas: pd.Series,
                       target_betas: Dict[str, float],
                       hedge_exposures: pd.DataFrame,
                       constraints: str,
                       max_position_size: float) -> Dict[str, float]:
        """Solve optimization problem to find hedge weights."""
        n_assets = len(hedge_exposures)
        
        # Convert target betas to array
        target_beta_array = np.array([
            target_betas.get(factor, 0.0) 
            for factor in portfolio_betas.index
        ])
        
        # Calculate required beta change
        beta_change_needed = target_beta_array - portfolio_betas.values
        
        # Objective: minimize sum of absolute hedge weights (transaction cost proxy)
        def objective(weights):
            return np.sum(np.abs(weights))
        
        # Constraint: hedge achieves desired beta change (equality constraint)
        # For SLSQP, equality constraints should equal 0 when satisfied
        optimization_constraints = []
        for i, factor in enumerate(portfolio_betas.index):
            def make_constraint(idx):
                def constraint_func(weights):
                    hedge_betas = hedge_exposures.T @ weights
                    return hedge_betas.iloc[idx] - beta_change_needed[idx]
                return constraint_func
            
            optimization_constraints.append({
                'type': 'eq',
                'fun': make_constraint(i)
            })
        
        # Set bounds based on constraint type
        if constraints == 'long_only':
            bounds = [(0, max_position_size) for _ in range(n_assets)]
        else:  # long_short
            bounds = [(-max_position_size, max_position_size) for _ in range(n_assets)]
        
        # Initial guess
        x0 = np.zeros(n_assets)
        
        # Optimize
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=optimization_constraints,
            options={'ftol': 1e-8}
        )
        
        if not result.success:
            logger.warning(f"Hedge optimization did not converge: {result.message}")
            
        # Convert to dictionary
        hedge_weights = {
            ticker: weight 
            for ticker, weight in zip(hedge_exposures.index, result.x)
            if abs(weight) > 0.001  # Filter out tiny positions
        }
        
        return hedge_weights
    
    def evaluate_hedge_effectiveness(self,
                                   portfolio_weights: Dict[str, float],
                                   hedge_weights: Dict[str, float]) -> Dict:
        """
        Evaluate how well the hedge neutralizes factor exposures.
        
        Returns:
        --------
        Dict containing:
            - original_betas: Factor exposures before hedge
            - hedged_betas: Factor exposures after hedge
            - beta_reduction: Percentage reduction in each beta
            - tracking_error: Expected tracking error vs hedged portfolio
        """
        # Calculate original portfolio betas
        tickers = list(portfolio_weights.keys())
        weights = np.array([portfolio_weights[t] for t in tickers])
        exposures = self.barra_model.factor_exposures.loc[tickers]
        original_betas = exposures.T @ weights
        
        # Calculate hedge portfolio betas
        hedge_exposures = self._get_hedge_exposures(list(hedge_weights.keys()))
        hedge_weight_array = np.array([hedge_weights[t] for t in hedge_exposures.index])
        hedge_betas = hedge_exposures.T @ hedge_weight_array
        
        # Combined portfolio betas
        hedged_betas = original_betas + hedge_betas
        
        # Calculate beta reduction
        beta_reduction = {}
        for factor in original_betas.index:
            if abs(original_betas[factor]) > 0.01:
                reduction = 1 - abs(hedged_betas[factor]) / abs(original_betas[factor])
                beta_reduction[factor] = reduction
            else:
                beta_reduction[factor] = 0.0
                
        # Estimate tracking error
        # This is simplified - actual tracking error depends on factor volatilities
        try:
            # Calculate tracking error using full covariance matrix
            # TE = sqrt(beta' * Cov * beta) where beta is hedged portfolio betas
            hedged_beta_array = hedged_betas.reindex(self.barra_model.factor_covariance.index).fillna(0)
            tracking_variance = hedged_beta_array.T @ self.barra_model.factor_covariance @ hedged_beta_array
            # Factor covariance is daily, so annualize by sqrt(252)
            tracking_error = np.sqrt(tracking_variance * 252)
        except Exception as e:
            logger.warning(f"Error calculating tracking error: {e}")
            # Fallback: simple calculation
            tracking_error = np.sqrt(np.sum(hedged_betas.values ** 2)) * 0.15 * np.sqrt(252)
        
        return {
            'original_betas': original_betas.to_dict(),
            'hedged_betas': hedged_betas.to_dict(),
            'beta_reduction': beta_reduction,
            'tracking_error': tracking_error
        }
    
    def calculate_hedge_cost(self,
                           hedge_weights: Dict[str, float],
                           transaction_cost_bps: float = 10,
                           borrow_cost_bps: float = 50) -> Dict[str, float]:
        """
        Estimate the cost of implementing the hedge.
        
        Parameters:
        -----------
        hedge_weights : Dict[str, float]
            Hedge portfolio weights
        transaction_cost_bps : float
            Transaction cost in basis points
        borrow_cost_bps : float
            Annual borrow cost for shorts in basis points
            
        Returns:
        --------
        Dict with cost components
        """
        total_turnover = sum(abs(w) for w in hedge_weights.values())
        short_exposure = sum(abs(w) for w in hedge_weights.values() if w < 0)
        
        # One-time transaction cost
        transaction_cost = total_turnover * transaction_cost_bps / 10000
        
        # Annual borrow cost for shorts
        annual_borrow_cost = short_exposure * borrow_cost_bps / 10000
        
        return {
            'transaction_cost_pct': transaction_cost * 100,
            'annual_borrow_cost_pct': annual_borrow_cost * 100,
            'total_turnover': total_turnover,
            'short_exposure': short_exposure
        }
    
    def generate_hedge_report(self,
                            portfolio_weights: Dict[str, float],
                            target_betas: Optional[Dict[str, float]] = None,
                            constraints: str = 'long_short',
                            max_position_size: float = 0.5) -> Dict:
        """
        Generate comprehensive hedge analysis report.
        
        Returns:
        --------
        Dict containing:
            - hedge_weights: Recommended hedge positions
            - effectiveness: Hedge effectiveness metrics
            - costs: Implementation costs
            - summary: Text summary of recommendations
        """
        # Calculate optimal hedge
        hedge_weights = self.calculate_hedge_weights(
            portfolio_weights=portfolio_weights,
            target_betas=target_betas,
            constraints=constraints,
            max_position_size=max_position_size
        )
        
        # Evaluate effectiveness
        effectiveness = self.evaluate_hedge_effectiveness(
            portfolio_weights=portfolio_weights,
            hedge_weights=hedge_weights
        )
        
        # Calculate costs
        costs = self.calculate_hedge_cost(hedge_weights)
        
        # Generate summary
        summary = self._generate_hedge_summary(
            hedge_weights=hedge_weights,
            effectiveness=effectiveness,
            costs=costs
        )
        
        return {
            'hedge_weights': hedge_weights,
            'effectiveness': effectiveness,
            'costs': costs,
            'summary': summary,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def _generate_hedge_summary(self,
                              hedge_weights: Dict[str, float],
                              effectiveness: Dict,
                              costs: Dict) -> str:
        """Generate human-readable hedge summary."""
        lines = ["Hedge Portfolio Recommendation", "=" * 40]
        
        # Hedge positions
        lines.append("\nHedge Positions:")
        for ticker, weight in sorted(hedge_weights.items(), key=lambda x: abs(x[1]), reverse=True):
            position = "Long" if weight > 0 else "Short"
            lines.append(f"  {position} {abs(weight)*100:.1f}% {ticker}")
            
        # Effectiveness
        lines.append("\nFactor Exposure Changes:")
        orig_betas = effectiveness['original_betas']
        hedged_betas = effectiveness['hedged_betas']
        
        for factor in orig_betas:
            if abs(orig_betas[factor]) > 0.05:  # Only show significant exposures
                lines.append(f"  {factor}: {orig_betas[factor]:.2f} → {hedged_betas[factor]:.2f}")
                
        # Costs
        lines.append("\nImplementation Costs:")
        lines.append(f"  Transaction Cost: {costs['transaction_cost_pct']:.2f}%")
        lines.append(f"  Annual Borrow Cost: {costs['annual_borrow_cost_pct']:.2f}%")
        
        # Risk reduction
        lines.append(f"\nExpected Tracking Error: {effectiveness['tracking_error']:.2%} annualized")
        
        return "\n".join(lines)
    
    def plot_hedge_analysis(self,
                          portfolio_weights: Dict[str, float],
                          hedge_weights: Dict[str, float],
                          save_path: Optional[str] = None):
        """
        Create visualization of hedge effectiveness using plotly.
        Returns interactive plotly figure.
        """
        effectiveness = self.evaluate_hedge_effectiveness(portfolio_weights, hedge_weights)
        
        # Extract data for visualization
        original_betas = effectiveness['original_betas']
        hedged_betas = effectiveness['hedged_betas']
        
        # Use the plotly visualization
        fig = HedgePortfolioVisualizations.plot_hedge_analysis(
            original_betas=original_betas,
            hedged_betas=hedged_betas,
            hedge_weights=hedge_weights,
            figsize=(15, 12)
        )
        
        # Save if path provided
        if save_path:
            if save_path.endswith('.html'):
                HedgePortfolioVisualizations.save_plotly_figure(fig, save_path, format='html')
            else:
                HedgePortfolioVisualizations.save_plotly_figure(fig, save_path, format='png')
            logger.info(f"Saved hedge analysis visualization to {save_path}")
        
        return fig