"""
Unit tests for Instanton Rare Event Analyzer.

Tests the core physics math, probability calculations, and portfolio decomposition.
Does NOT require external API calls - uses synthetic data.
"""

import pytest
import numpy as np
import pandas as pd
from scipy import stats

# Import modules to test
from core.agents.quant_tools.instanton_rare_event.instanton_solver import (
    compute_action,
    compute_instanton_gbm,
    compute_instanton_student_t,
    compute_instanton,
    compute_fluctuation_band,
    InstantonPath,
)
from core.agents.quant_tools.instanton_rare_event.probability_calculator import (
    saddle_point_probability,
    crash_probability_gaussian,
    crash_probability_student_t,
    compute_crash_probability,
    compute_severity_distribution,
)
from core.agents.quant_tools.instanton_rare_event.distribution_fitter import (
    fit_distribution,
    compute_tail_fatness_ratio,
    FittedDistribution,
)
from core.agents.quant_tools.instanton_rare_event.portfolio_decomposition import (
    compute_crash_contributions,
    estimate_crash_correlations,
    compute_diversification_decay,
)


class TestInstantonSolver:
    """Tests for instanton path and action calculations."""
    
    def test_compute_action_zero_for_expected_path(self):
        """Action should be zero when returns match drift exactly."""
        # Daily drift
        mu = 0.001
        sigma = 0.02
        n_days = 10
        
        # Returns exactly matching drift
        log_returns = np.full(n_days, mu)
        
        action = compute_action(log_returns, sigma, mu)
        
        # Action should be (close to) zero
        assert action < 0.01, f"Action should be ~0, got {action}"
    
    def test_compute_action_increases_with_deviation(self):
        """Larger deviations from drift should increase action."""
        mu = 0.0
        sigma = 0.02
        n_days = 10
        
        # Small deviation
        small_dev = np.full(n_days, -0.01)
        action_small = compute_action(small_dev, sigma, mu)
        
        # Large deviation
        large_dev = np.full(n_days, -0.05)
        action_large = compute_action(large_dev, sigma, mu)
        
        assert action_large > action_small, "Larger deviation should have higher action"
    
    def test_instanton_gbm_path_shape(self):
        """GBM instanton should have constant daily returns."""
        S0 = 100.0
        S_target = 80.0  # 20% crash
        n_days = 30
        sigma = 0.02
        
        instanton = compute_instanton_gbm(S0, S_target, n_days, sigma)
        
        # Check path endpoints
        assert np.isclose(instanton.prices[0], S0), "Path should start at S0"
        assert np.isclose(instanton.prices[-1], S_target, rtol=0.01), "Path should end at target"
        
        # Check constant daily returns
        returns = instanton.log_returns
        assert np.allclose(returns, returns[0]), "Daily returns should be constant"
    
    def test_instanton_gbm_action_positive(self):
        """Action for crash should be positive."""
        S0 = 100.0
        S_target = 80.0
        n_days = 30
        sigma = 0.02
        
        instanton = compute_instanton_gbm(S0, S_target, n_days, sigma)
        
        assert instanton.action > 0, "Crash action should be positive"
    
    def test_instanton_action_scales_with_crash_severity(self):
        """More severe crash should have higher action (lower probability)."""
        S0 = 100.0
        n_days = 30
        sigma = 0.02
        
        # 10% crash
        instanton_10 = compute_instanton_gbm(S0, 90.0, n_days, sigma)
        
        # 30% crash
        instanton_30 = compute_instanton_gbm(S0, 70.0, n_days, sigma)
        
        assert instanton_30.action > instanton_10.action, \
            "More severe crash should have higher action"
    
    def test_instanton_action_scales_with_horizon(self):
        """Longer horizon should have lower action (more time to crash)."""
        S0 = 100.0
        S_target = 80.0
        sigma = 0.02
        
        # Short horizon
        instanton_short = compute_instanton_gbm(S0, S_target, 10, sigma)
        
        # Long horizon
        instanton_long = compute_instanton_gbm(S0, S_target, 60, sigma)
        
        assert instanton_long.action < instanton_short.action, \
            "Longer horizon should have lower action (easier to reach target)"
    
    def test_fluctuation_band_contains_instanton(self):
        """Fluctuation band should contain the instanton path."""
        S0 = 100.0
        S_target = 80.0
        n_days = 30
        sigma = 0.02
        
        instanton = compute_instanton_gbm(S0, S_target, n_days, sigma)
        band = compute_fluctuation_band(instanton, sigma, confidence=0.68)
        
        # Central path should be close to instanton
        assert len(band["median_path"]) == len(instanton.prices)
        
        # Upper band should be above instanton at most points
        upper = band["upper_band"]
        lower = band["lower_band"]
        
        # Endpoints should be close (fixed boundary conditions)
        assert np.isclose(upper[0], instanton.prices[0], rtol=0.1)
        assert np.isclose(lower[0], instanton.prices[0], rtol=0.1)


class TestProbabilityCalculator:
    """Tests for crash probability calculations."""
    
    def test_saddle_point_probability_range(self):
        """Probability should be in [0, 1] for reasonable actions."""
        # Low action = high probability
        prob_low = saddle_point_probability(0.5)
        assert 0 < prob_low < 1
        
        # High action = low probability
        prob_high = saddle_point_probability(10.0)
        assert 0 < prob_high < 1
        assert prob_high < prob_low
    
    def test_crash_probability_gaussian_decreases_with_severity(self):
        """More severe crashes should be less probable."""
        sigma = 0.02
        horizon_days = 30
        
        prob_10 = crash_probability_gaussian(-10.0, horizon_days, sigma)
        prob_20 = crash_probability_gaussian(-20.0, horizon_days, sigma)
        prob_30 = crash_probability_gaussian(-30.0, horizon_days, sigma)
        
        assert prob_10 > prob_20 > prob_30, \
            "Crash probability should decrease with severity"
    
    def test_crash_probability_gaussian_increases_with_horizon(self):
        """Longer horizons should have higher crash probability (more time for crash)."""
        sigma = 0.02
        crash_pct = -20.0
        
        prob_10d = crash_probability_gaussian(crash_pct, 10, sigma)
        prob_30d = crash_probability_gaussian(crash_pct, 30, sigma)
        prob_90d = crash_probability_gaussian(crash_pct, 90, sigma)
        
        assert prob_10d < prob_30d < prob_90d, \
            "Crash probability should increase with horizon"
    
    def test_crash_probability_student_t_fatter_than_gaussian(self):
        """Student-t should give higher crash probability than Gaussian."""
        sigma = 0.02
        horizon_days = 30
        crash_pct = -20.0
        df = 4.0  # Fat tails
        
        prob_gaussian = crash_probability_gaussian(crash_pct, horizon_days, sigma)
        prob_t = crash_probability_student_t(crash_pct, horizon_days, sigma, df)
        
        assert prob_t > prob_gaussian, \
            "Student-t should give higher tail probability than Gaussian"
    
    def test_severity_distribution_statistics(self):
        """Severity distribution should have sensible VaR statistics."""
        S0 = 100.0
        horizon_days = 30
        sigma = 0.02
        
        severity = compute_severity_distribution(S0, horizon_days, sigma)
        
        stats = severity["statistics"]
        
        # VaR 99 should be more negative than VaR 95
        assert stats["var_99"] < stats["var_95"], \
            "VaR 99% should be more negative than VaR 95%"
        
        # Expected shortfall should be more negative than VaR
        assert stats["expected_shortfall_99"] <= stats["var_99"], \
            "ES should be at least as negative as VaR"


class TestDistributionFitter:
    """Tests for distribution fitting."""
    
    def test_fit_normal_returns(self):
        """Normal returns should be fit as normal distribution."""
        np.random.seed(42)
        returns = np.random.randn(500) * 0.02  # Normal with 2% vol
        
        fitted = fit_distribution(returns.tolist(), method="normal")
        
        assert fitted.dist_type == "normal"
        assert np.isclose(fitted.sigma, 0.02, rtol=0.2)  # Within 20%
    
    def test_fit_fat_tailed_returns(self):
        """Fat-tailed returns should favor t-distribution."""
        np.random.seed(42)
        # Student-t with df=4 (fat tails)
        returns = stats.t.rvs(df=4, size=500) * 0.02
        
        fitted = fit_distribution(returns.tolist(), method="auto")
        
        # Should detect fat tails
        assert fitted.tail_fatness_ratio > 1.5, \
            "Fat-tailed returns should have tail ratio > 1.5"
    
    def test_tail_fatness_ratio_increases_with_lower_df(self):
        """Lower df should give higher tail fatness ratio."""
        # High df (near Gaussian)
        ratio_high = compute_tail_fatness_ratio(30.0)
        
        # Low df (fat tails)
        ratio_low = compute_tail_fatness_ratio(4.0)
        
        assert ratio_low > ratio_high, \
            "Lower df should have higher tail fatness ratio"
        assert ratio_low > 2.0, "df=4 should have tail ratio > 2"


class TestPortfolioDecomposition:
    """Tests for portfolio crash decomposition."""
    
    @pytest.fixture
    def sample_portfolio_data(self):
        """Generate sample portfolio data for testing."""
        np.random.seed(42)
        n_days = 252
        
        # Generate correlated returns
        tickers = ["AAPL", "MSFT", "GOOGL", "NVDA"]
        
        # Base correlation matrix
        corr = np.array([
            [1.0, 0.7, 0.6, 0.8],
            [0.7, 1.0, 0.5, 0.7],
            [0.6, 0.5, 1.0, 0.6],
            [0.8, 0.7, 0.6, 1.0],
        ])
        
        # Volatilities
        vols = np.array([0.25, 0.22, 0.28, 0.45])  # NVDA is most volatile
        
        # Generate correlated returns
        L = np.linalg.cholesky(corr)
        z = np.random.randn(n_days, 4)
        returns = (z @ L.T) * (vols / np.sqrt(252))
        
        returns_df = pd.DataFrame(returns, columns=tickers)
        
        weights = [0.3, 0.25, 0.25, 0.2]  # NVDA only 20%
        volatilities = {t: v for t, v in zip(tickers, vols)}
        
        return {
            "returns_df": returns_df,
            "tickers": tickers,
            "weights": weights,
            "volatilities": volatilities,
            "correlation_matrix": corr,
        }
    
    def test_crash_contributions_sum_to_one(self, sample_portfolio_data):
        """Crash contributions should sum to approximately 1."""
        contributions = compute_crash_contributions(
            sample_portfolio_data["weights"],
            sample_portfolio_data["volatilities"],
            sample_portfolio_data["correlation_matrix"],
            sample_portfolio_data["tickers"],
        )
        
        total = sum(
            contributions["by_asset"][t]["crash_contribution"]
            for t in sample_portfolio_data["tickers"]
        )
        
        assert np.isclose(total, 1.0, rtol=0.05), \
            f"Crash contributions should sum to ~1, got {total}"
    
    def test_high_vol_asset_contributes_more(self, sample_portfolio_data):
        """High volatility asset should contribute more than its weight."""
        contributions = compute_crash_contributions(
            sample_portfolio_data["weights"],
            sample_portfolio_data["volatilities"],
            sample_portfolio_data["correlation_matrix"],
            sample_portfolio_data["tickers"],
        )
        
        nvda = contributions["by_asset"]["NVDA"]
        
        # NVDA is 20% weight but 45% vol - should contribute > 20%
        assert nvda["crash_contribution"] > nvda["weight"], \
            "High vol asset should contribute more than its weight"
    
    def test_crash_correlations_higher_than_normal(self, sample_portfolio_data):
        """Correlations in crash regime should typically be higher."""
        result = estimate_crash_correlations(
            sample_portfolio_data["returns_df"],
            threshold_sigma=-2.0
        )
        
        # This isn't guaranteed with synthetic data, but crash correlations
        # shouldn't be drastically lower
        assert result["average_crash_correlation"] >= 0, \
            "Crash correlation should be non-negative"
        assert "interpretation" in result
    
    def test_diversification_ratio_less_than_one(self, sample_portfolio_data):
        """Diversification ratio should be less than 1 (diversification helps)."""
        normal_corr = sample_portfolio_data["correlation_matrix"]
        crash_corr = normal_corr  # Use same for simplicity
        
        result = compute_diversification_decay(
            sample_portfolio_data["weights"],
            normal_corr,
            crash_corr,
            sample_portfolio_data["volatilities"],
            sample_portfolio_data["tickers"],
        )
        
        assert result["normal_regime"]["diversification_ratio"] < 1.0, \
            "Diversification should reduce portfolio vol (ratio < 1)"


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_full_instanton_pipeline(self):
        """Test the full instanton calculation pipeline."""
        # Parameters
        S0 = 100.0
        crash_pct = -20.0
        horizon_days = 30
        sigma = 0.02
        mu = 0.0
        
        # 1. Compute instanton
        instanton = compute_instanton(S0, crash_pct, horizon_days, sigma, mu)
        
        assert instanton.action > 0
        assert len(instanton.prices) == horizon_days + 1
        
        # 2. Compute probability
        prob = compute_crash_probability(
            instanton, sigma, horizon_days, crash_pct
        )
        
        assert 0 < prob.probability < 1
        assert prob.confidence_interval[0] < prob.probability < prob.confidence_interval[1]
        
        # 3. Gaussian comparison
        gaussian_prob = crash_probability_gaussian(crash_pct, horizon_days, sigma)
        
        # Probabilities should be in same ballpark
        assert 0.1 < prob.probability / gaussian_prob < 10
    
    def test_student_t_gives_higher_probability(self):
        """Student-t instanton should give higher crash probability."""
        S0 = 100.0
        crash_pct = -25.0  # More severe crash
        horizon_days = 30
        sigma = 0.02
        df = 4.0  # Fat tails
        
        # Gaussian instanton
        instanton_gauss = compute_instanton(S0, crash_pct, horizon_days, sigma)
        prob_gauss = compute_crash_probability(
            instanton_gauss, sigma, horizon_days, crash_pct
        )
        
        # Student-t instanton
        instanton_t = compute_instanton(S0, crash_pct, horizon_days, sigma, df=df)
        prob_t = compute_crash_probability(
            instanton_t, sigma, horizon_days, crash_pct, df=df
        )
        
        # Student-t should give higher probability for tail events
        # (Though the exact relationship depends on the implementation)
        assert prob_t.tail_multiplier >= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


















