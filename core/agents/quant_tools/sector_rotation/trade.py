"""
Trade generation for sector rotation signals.

Converts signals into actionable trades with sizing.
All thresholds configurable.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_TRADE_CONFIG = {
    # Signal thresholds
    "strong_signal_threshold": 2.0,
    "moderate_signal_threshold": 1.0,
    
    # Position sizing
    "max_position_pct": 0.20,
    "base_position_pct": 0.10,
    "conviction_multiplier": 1.5,
    
    # Regime adjustments
    "regime_transition_multiplier": 0.7,
    "regime_risk_off_long_multiplier": 0.6,
    "regime_risk_off_short_multiplier": 1.1,
    "regime_risk_on_long_multiplier": 1.1,
    "regime_risk_on_short_multiplier": 0.7,
    
    # Anomaly boost
    "anomaly_boost_multiplier": 1.2,
    
    # Risk limits
    "max_sectors_long": 3,
    "max_sectors_short": 2,
    "min_signal_for_trade": 0.5,
    
    # Transaction costs (bps)
    "transaction_cost_bps": 10,
    "slippage_bps": 5,
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Trade:
    """Represents a single trade recommendation."""
    sector: str
    direction: TradeDirection
    signal_strength: float
    position_size: float
    conviction: str
    rationale: List[str]
    estimated_cost_bps: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector,
            "direction": self.direction.value,
            "signal_strength": round(self.signal_strength, 4),
            "position_size": round(self.position_size, 4),
            "conviction": self.conviction,
            "rationale": self.rationale,
            "estimated_cost_bps": round(self.estimated_cost_bps, 2)
        }


# =============================================================================
# TRADE GENERATOR
# =============================================================================

class TradeGenerator:
    """
    Generates trade recommendations from sector signals.
    
    Applies position sizing, risk limits, and cost estimates.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_TRADE_CONFIG, **(config or {})}
    
    def generate(
        self,
        sector_signals: Dict[str, Dict[str, Any]],
        regime: Optional[str] = None,
        anomalies: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Generate trades from sector signals.
        
        Args:
            sector_signals: Dict mapping sector -> signal info
            regime: Current market regime (risk_on, risk_off, transition)
            anomalies: Dict mapping sector -> is_anomaly flag
        
        Returns:
            Dict with trade recommendations
        """
        if not sector_signals:
            return {"status": "no_signals", "trades": []}
        
        trades = []
        
        for sector, signal_info in sector_signals.items():
            trade = self._generate_single(
                sector=sector,
                signal_info=signal_info,
                regime=regime,
                is_anomaly=anomalies.get(sector, False) if anomalies else False
            )
            
            if trade is not None:
                trades.append(trade)
        
        # Apply portfolio-level constraints
        trades = self._apply_constraints(trades)
        
        # Sort by conviction
        trades.sort(key=lambda t: abs(t.signal_strength), reverse=True)
        
        # Summary
        n_long = sum(1 for t in trades if t.direction == TradeDirection.LONG)
        n_short = sum(1 for t in trades if t.direction == TradeDirection.SHORT)
        total_cost = sum(t.estimated_cost_bps for t in trades)
        
        return {
            "status": "success",
            "trades": [t.to_dict() for t in trades],
            "summary": {
                "n_long": n_long,
                "n_short": n_short,
                "total_trades": len(trades),
                "total_cost_bps": round(total_cost, 2),
                "regime": regime
            }
        }
    
    def _generate_single(
        self,
        sector: str,
        signal_info: Dict[str, Any],
        regime: Optional[str],
        is_anomaly: bool
    ) -> Optional[Trade]:
        """Generate trade for a single sector."""
        # Extract signal strength
        signal = signal_info.get("composite_score", signal_info.get("zscore", 0))
        
        min_signal = self.config.get("min_signal_for_trade", 0.5)
        if abs(signal) < min_signal:
            return None
        
        # Determine direction
        if signal > 0:
            direction = TradeDirection.LONG
        elif signal < 0:
            direction = TradeDirection.SHORT
        else:
            return None
        
        # Determine conviction
        strong_thresh = self.config.get("strong_signal_threshold", 2.0)
        moderate_thresh = self.config.get("moderate_signal_threshold", 1.0)
        
        if abs(signal) >= strong_thresh:
            conviction = "high"
        elif abs(signal) >= moderate_thresh:
            conviction = "medium"
        else:
            conviction = "low"
        
        # Calculate position size
        position_size = self._calculate_size(
            signal_strength=abs(signal),
            conviction=conviction,
            regime=regime,
            is_anomaly=is_anomaly,
            direction=direction
        )
        
        # Build rationale
        rationale = self._build_rationale(
            signal_info=signal_info,
            regime=regime,
            is_anomaly=is_anomaly
        )
        
        # Estimate costs
        cost_bps = self._estimate_cost()
        
        return Trade(
            sector=sector,
            direction=direction,
            signal_strength=signal,
            position_size=position_size,
            conviction=conviction,
            rationale=rationale,
            estimated_cost_bps=cost_bps
        )
    
    def _calculate_size(
        self,
        signal_strength: float,
        conviction: str,
        regime: Optional[str],
        is_anomaly: bool,
        direction: TradeDirection
    ) -> float:
        """Calculate position size based on signal and context."""
        base = self.config.get("base_position_pct", 0.10)
        max_size = self.config.get("max_position_pct", 0.20)
        multiplier = self.config.get("conviction_multiplier", 1.5)
        
        # Start with base
        size = base
        
        # Scale by conviction
        if conviction == "high":
            size *= multiplier
        elif conviction == "medium":
            size *= (1 + multiplier) / 2
        
        # Boost for anomalies (potential informed flow)
        if is_anomaly:
            size *= self.config.get("anomaly_boost_multiplier", 1.2)
        
        # Regime adjustments - direction-aware, all from config
        if regime == "transition":
            size *= self.config.get("regime_transition_multiplier", 0.7)
        elif regime == "risk_off":
            if direction == TradeDirection.LONG:
                size *= self.config.get("regime_risk_off_long_multiplier", 0.6)
            else:
                size *= self.config.get("regime_risk_off_short_multiplier", 1.1)
        elif regime == "risk_on":
            if direction == TradeDirection.LONG:
                size *= self.config.get("regime_risk_on_long_multiplier", 1.1)
            else:
                size *= self.config.get("regime_risk_on_short_multiplier", 0.7)
        
        # Cap at max
        return min(size, max_size)
    
    def _build_rationale(
        self,
        signal_info: Dict[str, Any],
        regime: Optional[str],
        is_anomaly: bool
    ) -> List[str]:
        """Build human-readable rationale for trade."""
        rationale = []
        
        # Factor contributions
        factors = signal_info.get("factors", {})
        for factor_name, factor_value in factors.items():
            if isinstance(factor_value, dict):
                zscore = factor_value.get("zscore", 0)
                if abs(zscore) >= 1.0:
                    direction = "bullish" if zscore > 0 else "bearish"
                    rationale.append(f"{factor_name}: {direction} ({zscore:.2f}σ)")
            elif isinstance(factor_value, (int, float)) and abs(factor_value) >= 1.0:
                direction = "bullish" if factor_value > 0 else "bearish"
                rationale.append(f"{factor_name}: {direction} ({factor_value:.2f}σ)")
        
        # Regime context
        if regime:
            rationale.append(f"Regime: {regime}")
        
        # Anomaly flag
        if is_anomaly:
            rationale.append("⚠️ Unusual flow detected (potential informed activity)")
        
        return rationale if rationale else ["Composite signal threshold met"]
    
    def _estimate_cost(self) -> float:
        """Estimate transaction cost in bps (round-trip)."""
        txn_cost = self.config.get("transaction_cost_bps", 10)
        slippage = self.config.get("slippage_bps", 5)
        
        # Round-trip cost in bps (constant regardless of size)
        return (txn_cost + slippage) * 2
    
    def _apply_constraints(self, trades: List[Trade]) -> List[Trade]:
        """Apply portfolio-level constraints."""
        max_long = self.config.get("max_sectors_long", 3)
        max_short = self.config.get("max_sectors_short", 2)
        
        # Sort by signal strength - strongest first
        longs = sorted(
            [t for t in trades if t.direction == TradeDirection.LONG],
            key=lambda t: t.signal_strength,
            reverse=True
        )[:max_long]
        
        # For shorts, most negative = strongest
        shorts = sorted(
            [t for t in trades if t.direction == TradeDirection.SHORT],
            key=lambda t: t.signal_strength
        )[:max_short]
        
        return longs + shorts
