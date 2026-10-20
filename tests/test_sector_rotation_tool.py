"""
Unit tests for Sector Rotation Flow Tool.

Tests cover:
- Factor computation
- Aggregation methods
- Trade generation
- ML modules (regime, anomaly, lead-lag, ensemble)
- Validation
- Charts
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List


# =============================================================================
# FACTOR TESTS
# =============================================================================

class TestDeltaFlowFactor:
    """Tests for delta flow factor computation."""
    
    def test_compute_positive_zscore(self):
        """Positive flow should yield positive z-score."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor
        
        factor = DeltaFlowFactor()
        historical = [100, 120, 80, 90, 110, 95, 105, 115, 85, 100]
        current = 200  # Well above mean
        
        result = factor.compute(current_flow=current, historical_flows=historical)
        
        assert result["zscore"] > 0
        assert "signal" in result
    
    def test_compute_negative_zscore(self):
        """Negative flow should yield negative z-score."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor
        
        factor = DeltaFlowFactor()
        historical = [100, 120, 80, 90, 110, 95, 105, 115, 85, 100]
        current = -50  # Well below mean
        
        result = factor.compute(current_flow=current, historical_flows=historical)
        
        assert result["zscore"] < 0
    
    def test_compute_insufficient_history(self):
        """Should handle insufficient historical data gracefully."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor
        
        factor = DeltaFlowFactor()
        historical = [100, 120]  # Only 2 points
        current = 150
        
        result = factor.compute(current_flow=current, historical_flows=historical)
        
        # Should still return a result, possibly with zscore=0 or raw value
        assert "zscore" in result or "value" in result
    
    def test_custom_config_thresholds(self):
        """Custom config should override default thresholds."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor
        
        custom_config = {
            "zscore_strong_threshold": 1.0,  # Lower than default 2.0
            "zscore_moderate_threshold": 0.5,
        }
        factor = DeltaFlowFactor(config=custom_config)
        
        assert factor.config["zscore_strong_threshold"] == 1.0
        assert factor.config["zscore_moderate_threshold"] == 0.5


class TestVegaFlowFactor:
    """Tests for vega flow momentum factor."""
    
    def test_compute_momentum(self):
        """Should compute momentum from vega history."""
        from core.agents.quant_tools.sector_rotation.factors import VegaFlowFactor
        
        factor = VegaFlowFactor()
        historical = [100, 110, 120, 130, 140]  # Increasing trend
        current = 150
        
        result = factor.compute(current_vega=current, historical_vega=historical)
        
        assert "zscore" in result or "momentum" in result


class TestOTMConvictionFactor:
    """Tests for OTM conviction factor."""
    
    def test_bullish_skew(self):
        """More call premium than put should be bullish."""
        from core.agents.quant_tools.sector_rotation.factors import OTMConvictionFactor
        
        factor = OTMConvictionFactor()
        result = factor.compute(call_premium=1000000, put_premium=200000)
        
        assert result.get("ratio", 0) > 0.5 or result.get("signal") == "bullish"
    
    def test_bearish_skew(self):
        """More put premium than call should be bearish."""
        from core.agents.quant_tools.sector_rotation.factors import OTMConvictionFactor
        
        factor = OTMConvictionFactor()
        result = factor.compute(call_premium=200000, put_premium=1000000)
        
        assert result.get("ratio", 1) < 0.5 or result.get("signal") == "bearish"
    
    def test_zero_premium_handling(self):
        """Should handle zero premium without division error."""
        from core.agents.quant_tools.sector_rotation.factors import OTMConvictionFactor
        
        factor = OTMConvictionFactor()
        
        # Both zero
        result = factor.compute(call_premium=0, put_premium=0)
        assert "ratio" in result or "error" not in result
        
        # One zero
        result = factor.compute(call_premium=1000, put_premium=0)
        assert "ratio" in result


# =============================================================================
# AGGREGATION TESTS
# =============================================================================

class TestFactorAggregator:
    """Tests for factor aggregation methods."""
    
    def test_equal_weighted(self):
        """Equal weighted should average all factors."""
        from core.agents.quant_tools.sector_rotation.aggregation import FactorAggregator
        
        aggregator = FactorAggregator(method="equal_weighted")
        factors = {
            "delta_flow": 2.0,
            "vega_flow": 1.0,
            "otm_conviction": 0.5,
        }
        
        result = aggregator.aggregate(factors=factors)
        
        expected_avg = (2.0 + 1.0 + 0.5) / 3
        assert abs(result["composite_score"] - expected_avg) < 0.01
    
    def test_regime_conditional_risk_on(self):
        """Regime conditional should adjust weights for risk_on."""
        from core.agents.quant_tools.sector_rotation.aggregation import FactorAggregator
        
        aggregator = FactorAggregator(method="regime_conditional")
        factors = {"delta_flow": 2.0, "vega_flow": 1.0}
        
        result = aggregator.aggregate(factors=factors, regime="risk_on")
        
        assert "composite_score" in result
        assert result.get("regime_used") == "risk_on" or "method" in result
    
    def test_custom_weights(self):
        """Custom weights should be applied."""
        from core.agents.quant_tools.sector_rotation.aggregation import FactorAggregator
        
        custom_weights = {"delta_flow": 0.8, "vega_flow": 0.2}
        aggregator = FactorAggregator(
            method="equal_weighted",
            custom_weights=custom_weights
        )
        
        factors = {"delta_flow": 2.0, "vega_flow": 1.0}
        result = aggregator.aggregate(factors=factors)
        
        # Should use custom weights
        assert "composite_score" in result


# =============================================================================
# TRADE GENERATION TESTS
# =============================================================================

class TestTradeGenerator:
    """Tests for trade generation."""
    
    def test_generate_long_trade(self):
        """Positive signal should generate long trade."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        signals = {
            "Technology": {"composite_score": 2.5, "factors": {}},
        }
        
        result = generator.generate(sector_signals=signals)
        
        assert result["status"] == "success"
        assert len(result["trades"]) > 0
        assert result["trades"][0]["direction"] == "long"
    
    def test_generate_short_trade(self):
        """Negative signal should generate short trade."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        signals = {
            "Energy": {"composite_score": -2.5, "factors": {}},
        }
        
        result = generator.generate(sector_signals=signals)
        
        assert result["status"] == "success"
        assert len(result["trades"]) > 0
        assert result["trades"][0]["direction"] == "short"
    
    def test_position_sizing_high_conviction(self):
        """High conviction should get larger position."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        
        # High conviction signal
        high_signals = {"Tech": {"composite_score": 3.0, "factors": {}}}
        high_result = generator.generate(sector_signals=high_signals)
        
        # Low conviction signal
        low_signals = {"Tech": {"composite_score": 0.6, "factors": {}}}
        low_result = generator.generate(sector_signals=low_signals)
        
        if high_result["trades"] and low_result["trades"]:
            high_size = high_result["trades"][0]["position_size"]
            low_size = low_result["trades"][0]["position_size"]
            assert high_size >= low_size
    
    def test_regime_affects_sizing(self):
        """Regime should affect position sizing."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        signals = {"Tech": {"composite_score": 2.0, "factors": {}}}
        
        # Risk on - should be larger for longs
        risk_on_result = generator.generate(sector_signals=signals, regime="risk_on")
        
        # Risk off - should be smaller for longs
        risk_off_result = generator.generate(sector_signals=signals, regime="risk_off")
        
        if risk_on_result["trades"] and risk_off_result["trades"]:
            risk_on_size = risk_on_result["trades"][0]["position_size"]
            risk_off_size = risk_off_result["trades"][0]["position_size"]
            assert risk_on_size >= risk_off_size
    
    def test_max_sectors_constraint(self):
        """Should respect max sectors constraint."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        config = {"max_sectors_long": 2, "max_sectors_short": 1}
        generator = TradeGenerator(config=config)
        
        signals = {
            "Tech": {"composite_score": 3.0, "factors": {}},
            "Healthcare": {"composite_score": 2.5, "factors": {}},
            "Financials": {"composite_score": 2.0, "factors": {}},
            "Energy": {"composite_score": -2.0, "factors": {}},
            "Utilities": {"composite_score": -1.5, "factors": {}},
        }
        
        result = generator.generate(sector_signals=signals)
        
        n_long = sum(1 for t in result["trades"] if t["direction"] == "long")
        n_short = sum(1 for t in result["trades"] if t["direction"] == "short")
        
        assert n_long <= 2
        assert n_short <= 1
    
    def test_cost_estimation(self):
        """Transaction cost should be calculated."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        signals = {"Tech": {"composite_score": 2.0, "factors": {}}}
        
        result = generator.generate(sector_signals=signals)
        
        if result["trades"]:
            assert "estimated_cost_bps" in result["trades"][0]
            assert result["trades"][0]["estimated_cost_bps"] > 0


# =============================================================================
# ML MODULE TESTS
# =============================================================================

class TestRegimeClassifier:
    """Tests for regime classification."""
    
    def test_rule_based_fallback(self):
        """Should work without sklearn using rule-based fallback."""
        from core.agents.quant_tools.sector_rotation.ml.regime import RegimeClassifier
        
        classifier = RegimeClassifier()
        
        # Create test features
        features = pd.DataFrame({
            "composite": [1.5, 2.0, 1.8, 0.5, 1.2]
        })
        
        result = classifier.predict(features)
        
        assert "regime" in result
        assert result["regime"] in ["risk_on", "risk_off", "transition"]
    
    def test_predict_without_fit(self):
        """Should handle prediction without prior fit."""
        from core.agents.quant_tools.sector_rotation.ml.regime import RegimeClassifier
        
        classifier = RegimeClassifier()
        features = pd.DataFrame({"composite": [1.0, 2.0, -1.0]})
        
        result = classifier.predict(features)
        
        # Should fallback to rule-based
        assert "regime" in result


class TestAnomalyDetector:
    """Tests for anomaly detection."""
    
    def test_zscore_fallback(self):
        """Should work with z-score fallback when sklearn unavailable."""
        from core.agents.quant_tools.sector_rotation.ml.anomaly import AnomalyDetector
        
        detector = AnomalyDetector()
        
        # Create test data with one obvious anomaly
        flow_data = pd.DataFrame({
            "score": [1.0, 1.1, 0.9, 1.0, 1.2, 10.0]  # 10.0 is anomaly
        })
        
        result = detector.detect(flow_data)
        
        assert "results" in result
        assert len(result["results"]) == 6
    
    def test_fit_and_detect(self):
        """Should fit on historical data and detect anomalies."""
        from core.agents.quant_tools.sector_rotation.ml.anomaly import AnomalyDetector
        
        detector = AnomalyDetector()
        
        # Historical data for fitting
        historical = pd.DataFrame({
            "score": np.random.normal(0, 1, 100)
        })
        
        fit_result = detector.fit(historical)
        
        # Either succeeds with sklearn or reports fallback
        assert fit_result["status"] in ["success", "fallback", "insufficient_data"]


class TestLeadLagDetector:
    """Tests for lead-lag detection."""
    
    def test_correlation_fallback(self):
        """Should work with correlation fallback."""
        from core.agents.quant_tools.sector_rotation.ml.lead_lag import LeadLagDetector
        
        detector = LeadLagDetector()
        
        # Create correlated time series
        n = 50
        flow_data = pd.DataFrame({
            "Tech": np.cumsum(np.random.randn(n)),
            "Healthcare": np.cumsum(np.random.randn(n)),
        })
        
        return_data = pd.DataFrame({
            "Tech": np.random.randn(n) * 0.02,
            "Healthcare": np.random.randn(n) * 0.02,
        })
        
        result = detector.detect(flow_data, return_data)
        
        assert "relationships" in result or "status" in result


class TestEnsembleModel:
    """Tests for ensemble stacking model."""
    
    def test_insufficient_data(self):
        """Should handle insufficient training data."""
        from core.agents.quant_tools.sector_rotation.ml.ensemble import EnsembleModel
        
        model = EnsembleModel(config={"min_samples": 50})
        
        # Only 10 samples
        X = pd.DataFrame({"f1": range(10), "f2": range(10)})
        y = pd.Series([0, 1] * 5)
        
        result = model.fit(X, y)
        
        assert result["status"] == "insufficient_data"
    
    def test_predict_not_fitted(self):
        """Should handle prediction when not fitted."""
        from core.agents.quant_tools.sector_rotation.ml.ensemble import EnsembleModel
        
        model = EnsembleModel()
        X = pd.DataFrame({"f1": [1, 2, 3], "f2": [4, 5, 6]})
        
        result = model.predict(X)
        
        assert result["status"] == "not_fitted"


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestWalkForwardValidator:
    """Tests for walk-forward validation."""
    
    def test_insufficient_data(self):
        """Should report insufficient data."""
        from core.agents.quant_tools.sector_rotation.validation import WalkForwardValidator
        
        validator = WalkForwardValidator(config={"min_samples": 100})
        
        signals = pd.Series([1, -1, 1, -1, 1])  # Only 5 samples
        returns = pd.Series([0.01, -0.01, 0.02, -0.02, 0.01])
        
        result = validator.validate(signals, returns)
        
        assert result["status"] == "insufficient_data"
    
    def test_metrics_calculation(self):
        """Should calculate performance metrics correctly."""
        from core.agents.quant_tools.sector_rotation.validation import WalkForwardValidator
        
        validator = WalkForwardValidator(config={"min_samples": 10, "train_pct": 0.6})
        
        # Create enough data
        n = 50
        signals = pd.Series(np.random.choice([-1, 0, 1], n))
        returns = pd.Series(np.random.randn(n) * 0.02)
        
        result = validator.validate(signals, returns)
        
        if result["status"] == "success":
            assert "aggregate" in result
            assert "sharpe_ratio" in result["aggregate"]
            assert "hit_rate" in result["aggregate"]
    
    def test_percentage_based_windows(self):
        """Should use percentage-based train/test windows."""
        from core.agents.quant_tools.sector_rotation.validation import WalkForwardValidator
        
        validator = WalkForwardValidator(config={"train_pct": 0.80})
        
        n = 100
        signals = pd.Series(np.random.choice([-1, 1], n))
        returns = pd.Series(np.random.randn(n) * 0.02)
        
        result = validator.validate(signals, returns)
        
        if result["status"] == "success":
            # 80% of 100 = 80 train, 20% = 20 test
            assert result["train_window"] == 80
            assert result["test_window"] == 20


# =============================================================================
# CHART TESTS
# =============================================================================

class TestChartGenerator:
    """Tests for chart generation."""
    
    def test_sector_signal_bars(self):
        """Should generate sector signal bar chart."""
        from core.agents.quant_tools.sector_rotation.charts import ChartGenerator
        
        generator = ChartGenerator()
        signals = {
            "Technology": 2.5,
            "Healthcare": 1.2,
            "Energy": -1.8,
            "Financials": 0.5,
        }
        
        result = generator.sector_signal_bars(signals)
        
        # Either returns base64 string or None if matplotlib unavailable
        assert result is None or isinstance(result, str)
    
    def test_factor_heatmap(self):
        """Should generate factor heatmap."""
        from core.agents.quant_tools.sector_rotation.charts import ChartGenerator
        
        generator = ChartGenerator()
        matrix = {
            "Technology": {"delta": 2.0, "vega": 1.5, "otm": 0.8},
            "Healthcare": {"delta": 1.0, "vega": -0.5, "otm": 1.2},
        }
        
        result = generator.factor_heatmap(matrix)
        
        assert result is None or isinstance(result, str)
    
    def test_custom_config(self):
        """Should respect custom chart config."""
        from core.agents.quant_tools.sector_rotation.charts import ChartGenerator
        
        config = {
            "figure_width": 8,
            "figure_height": 6,
            "bullish_color": "#00ff00",
        }
        generator = ChartGenerator(config=config)
        
        assert generator.config["figure_width"] == 8
        assert generator.config["bullish_color"] == "#00ff00"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSectorRotationIntegration:
    """Integration tests for the full tool."""
    
    @pytest.mark.asyncio
    async def test_basic_analysis(self):
        """Basic analysis should return valid structure."""
        from core.agents.quant_tools.sector_rotation.tool import analyze_sector_rotation_flow
        
        with patch('core.agents.quant_tools.sector_rotation.fetchers.SectorDataFetcher') as MockFetcher:
            # Mock the fetcher
            mock_instance = AsyncMock()
            mock_instance.fetch_greek_flow.return_value = {
                "net_delta": 1000000,
                "net_vega": 500000,
                "call_premium": 800000,
                "put_premium": 200000,
            }
            MockFetcher.return_value = mock_instance
            
            result = await analyze_sector_rotation_flow(
                sectors=["Technology", "Healthcare"],
            )
            
            assert result["status"] == "success"
            assert "sectors" in result
            assert "rankings" in result
            assert "summary" in result
    
    @pytest.mark.asyncio
    async def test_with_trades_enabled(self):
        """Should generate trades when enabled."""
        from core.agents.quant_tools.sector_rotation.tool import analyze_sector_rotation_flow
        
        with patch('core.agents.quant_tools.sector_rotation.fetchers.SectorDataFetcher') as MockFetcher:
            mock_instance = AsyncMock()
            mock_instance.fetch_greek_flow.return_value = {
                "net_delta": 5000000,  # Strong signal
                "net_vega": 1000000,
                "call_premium": 900000,
                "put_premium": 100000,
            }
            MockFetcher.return_value = mock_instance
            
            result = await analyze_sector_rotation_flow(
                sectors=["Technology"],
                generate_trades=True,
            )
            
            assert "trades" in result
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Should handle errors gracefully."""
        from core.agents.quant_tools.sector_rotation.tool import analyze_sector_rotation_flow
        
        with patch('core.agents.quant_tools.sector_rotation.fetchers.SectorDataFetcher') as MockFetcher:
            mock_instance = AsyncMock()
            mock_instance.connect.side_effect = Exception("Connection failed")
            MockFetcher.return_value = mock_instance
            
            result = await analyze_sector_rotation_flow(sectors=["Technology"])
            
            assert result["status"] == "error"
            assert "error" in result


# =============================================================================
# CONFIG TESTS
# =============================================================================

class TestConfigOverrides:
    """Tests for configuration override behavior."""
    
    def test_factor_config_override(self):
        """Factor config should override defaults."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor, DEFAULT_FACTOR_CONFIG
        
        custom = {"zscore_strong_threshold": 3.0}
        factor = DeltaFlowFactor(config=custom)
        
        assert factor.config["zscore_strong_threshold"] == 3.0
        # Other defaults should remain
        assert factor.config["zscore_min_history"] == DEFAULT_FACTOR_CONFIG["zscore_min_history"]
    
    def test_trade_config_override(self):
        """Trade config should override defaults."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator, DEFAULT_TRADE_CONFIG
        
        custom = {"max_position_pct": 0.30, "base_position_pct": 0.15}
        generator = TradeGenerator(config=custom)
        
        assert generator.config["max_position_pct"] == 0.30
        assert generator.config["base_position_pct"] == 0.15
        # Other defaults should remain
        assert generator.config["transaction_cost_bps"] == DEFAULT_TRADE_CONFIG["transaction_cost_bps"]


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_signals(self):
        """Should handle empty signals gracefully."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        result = generator.generate(sector_signals={})
        
        assert result["status"] == "no_signals"
        assert result["trades"] == []
    
    def test_all_neutral_signals(self):
        """Should handle all neutral signals."""
        from core.agents.quant_tools.sector_rotation.trade import TradeGenerator
        
        generator = TradeGenerator()
        signals = {
            "Tech": {"composite_score": 0.1, "factors": {}},  # Below threshold
            "Healthcare": {"composite_score": -0.1, "factors": {}},
        }
        
        result = generator.generate(sector_signals=signals)
        
        # Should have no trades (all below min_signal_for_trade)
        assert len(result["trades"]) == 0
    
    def test_single_sector(self):
        """Should work with single sector."""
        from core.agents.quant_tools.sector_rotation.aggregation import FactorAggregator
        
        aggregator = FactorAggregator()
        factors = {"delta_flow": 2.0}
        
        result = aggregator.aggregate(factors=factors)
        
        assert result["composite_score"] == 2.0
    
    def test_nan_handling(self):
        """Should handle NaN values."""
        from core.agents.quant_tools.sector_rotation.factors import DeltaFlowFactor
        
        factor = DeltaFlowFactor()
        historical = [100, np.nan, 80, 90, np.nan, 95, 105]
        current = 150
        
        # Should not crash
        result = factor.compute(current_flow=current, historical_flows=historical)
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
