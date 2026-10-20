"""
Path Optimizer - Dijkstra-based multi-objective hedge path finding.

Uses modified Dijkstra/A* algorithm to find minimum-cost paths from
current portfolio state to target factor exposures.

Supports k-best path tracking for alternatives.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import heapq
import math
import logging
from copy import deepcopy

from .factor_calculator import PortfolioFactors, FactorTarget
from .gap_to_screener import HedgeCandidate, FactorGap

logger = logging.getLogger(__name__)

# Option multiplier (shares per contract)
OPTION_MULTIPLIER = 100


@dataclass
class FactorImpact:
    """Impact of a hedge action on portfolio factors.
    
    Uses dollar-based tracking for proper portfolio math:
    - notional_change: Dollar value of position added (negative for shorts)
    - beta_dollar_change: beta * notional (for weighted average calculation)
    - sector_dollar_change: Dollar exposure change per sector
    """
    
    delta_change: float = 0.0
    gamma_change: float = 0.0
    vega_change: float = 0.0
    
    # Dollar-weighted changes for proper portfolio math
    notional_change: float = 0.0
    beta_dollar_change: float = 0.0  # beta * notional_change
    sector_dollar_changes: Dict[str, float] = field(default_factory=dict)


@dataclass
class HedgeAction:
    """A single hedging action (buy/sell an instrument)."""
    
    instrument: str               # Human-readable description
    ticker: str
    action_type: str              # "buy" | "sell" | "short"
    quantity: int                 # Contracts or shares
    cost: float                   # Total cost (premium + slippage)
    factor_impact: FactorImpact
    
    # Details for options
    option_symbol: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    option_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for output."""
        result = {
            "action": self.instrument,
            "ticker": self.ticker,
            "type": self.action_type,
            "quantity": self.quantity,
            "cost": round(self.cost, 2),
            "delta_impact": round(self.factor_impact.delta_change, 2),
            "gamma_impact": round(self.factor_impact.gamma_change, 4),
            "vega_impact": round(self.factor_impact.vega_change, 2),
            "notional_impact": round(self.factor_impact.notional_change, 2),
            "beta_dollar_impact": round(self.factor_impact.beta_dollar_change, 2),
        }
        
        if self.factor_impact.sector_dollar_changes:
            result["sector_dollar_impact"] = {
                k: round(v, 2) for k, v in self.factor_impact.sector_dollar_changes.items()
            }
        
        if self.strike:
            result["strike"] = self.strike
        if self.expiry:
            result["expiry"] = self.expiry
        
        return result


@dataclass
class HedgeState:
    """Current state in the search space.
    
    Uses dollar-weighted tracking for proper portfolio math:
    - beta_dollar = sum(position_beta * position_notional)
    - portfolio_beta = beta_dollar / total_notional
    """
    
    # Current factor levels after actions
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    
    # Dollar-weighted factor tracking (for proper portfolio math)
    total_notional: float = 0.0
    beta_dollar: float = 0.0  # sum(beta_i * notional_i)
    sector_dollars: Dict[str, float] = field(default_factory=dict)
    
    # Cumulative cost
    cost: float = 0.0
    
    # Path taken to reach this state
    path: List[HedgeAction] = field(default_factory=list)
    
    @property
    def beta(self) -> float:
        """Portfolio beta = dollar-weighted average."""
        if abs(self.total_notional) < 1:
            return 1.0
        return self.beta_dollar / self.total_notional
    
    @property
    def sector_weights(self) -> Dict[str, float]:
        """Sector weights = dollar exposure / total notional."""
        if abs(self.total_notional) < 1:
            return {}
        return {s: d / self.total_notional for s, d in self.sector_dollars.items()}
    
    def __lt__(self, other: "HedgeState") -> bool:
        """For heap comparison."""
        return self.cost < other.cost
    
    def clone(self) -> "HedgeState":
        """Create a deep copy."""
        return HedgeState(
            delta=self.delta,
            gamma=self.gamma,
            vega=self.vega,
            total_notional=self.total_notional,
            beta_dollar=self.beta_dollar,
            sector_dollars=dict(self.sector_dollars),
            cost=self.cost,
            path=list(self.path),
        )


@dataclass
class HedgePath:
    """A complete hedging path with all details."""
    
    rank: int
    total_cost: float
    efficiency: float           # gap_closed / cost
    steps: List[HedgeAction]
    final_factors: Dict[str, Any]
    
    # Gap closure metrics
    delta_closure_pct: float = 0.0
    gamma_closure_pct: float = 0.0
    vega_closure_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for output."""
        return {
            "rank": self.rank,
            "total_cost": round(self.total_cost, 2),
            "efficiency": round(self.efficiency, 4),
            "steps": [s.to_dict() for s in self.steps],
            "final_factors": self.final_factors,
            "gap_closure": {
                "delta_pct": round(self.delta_closure_pct * 100, 1),
                "gamma_pct": round(self.gamma_closure_pct * 100, 1),
                "vega_pct": round(self.vega_closure_pct * 100, 1),
            }
        }


def _calculate_distance_to_target(
    state: HedgeState,
    target: FactorTarget,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Calculate weighted Euclidean distance from state to target.
    
    Uses normalized gaps to make different factors comparable.
    
    IMPORTANT: Equal weighting for delta, beta, and sectors to ensure
    the algorithm optimizes for ALL targets simultaneously.
    """
    if weights is None:
        weights = {
            "delta": 1.0,   # Delta - equal weight
            "gamma": 0.3,
            "vega": 0.3,
            "beta": 1.0,    # Beta - equal weight (was 0.1, too low!)
            "sector": 1.0,  # Sectors - equal weight
        }
    
    distance = 0.0
    
    # Delta distance (normalize by 10,000 shares equivalent)
    if target.delta is not None:
        delta_gap = abs(state.delta - target.delta) / 10000
        distance += weights.get("delta", 1.0) * (delta_gap ** 2)
    
    # Gamma distance (normalize by 100)
    if target.gamma is not None:
        gamma_gap = abs(state.gamma - target.gamma) / 100
        distance += weights.get("gamma", 0.3) * (gamma_gap ** 2)
    
    # Vega distance (normalize by 1000)
    if target.vega is not None:
        vega_gap = abs(state.vega - target.vega) / 1000
        distance += weights.get("vega", 0.3) * (vega_gap ** 2)
    
    # Beta distance - IMPORTANT: high weight
    if target.beta is not None:
        beta_gap = abs(state.beta - target.beta)
        distance += weights.get("beta", 1.0) * (beta_gap ** 2)
    
    # Sector distances - IMPORTANT for neutralization
    for sector, target_weight in target.sector_targets.items():
        current_weight = state.sector_weights.get(sector, 0)
        sector_gap = abs(current_weight - target_weight)
        distance += weights.get("sector", 1.0) * (sector_gap ** 2)
    
    return math.sqrt(distance)


def _is_within_tolerance(
    state: HedgeState,
    target: FactorTarget,
    tolerance: float = 0.05  # Tighter default: 5%
) -> bool:
    """Check if state is within tolerance of ALL targets.
    
    IMPORTANT: All factors must be within tolerance for the path to be "complete".
    This prevents single-instrument paths that only partially achieve targets.
    """
    
    # Delta tolerance: tolerance% of target (use absolute, minimum 500 to avoid noise)
    if target.delta is not None:
        delta_tol = max(abs(target.delta) * tolerance, 500)
        if abs(state.delta - target.delta) > delta_tol:
            logger.debug(f"Delta not within tolerance: {state.delta:.0f} vs target {target.delta:.0f} (tol={delta_tol:.0f})")
            return False
    
    # Gamma tolerance: tolerance% of target or 25
    if target.gamma is not None:
        gamma_tol = max(abs(target.gamma) * tolerance, 25)
        if abs(state.gamma - target.gamma) > gamma_tol:
            return False
    
    # Vega tolerance: tolerance% of target or 250
    if target.vega is not None:
        vega_tol = max(abs(target.vega) * tolerance, 250)
        if abs(state.vega - target.vega) > vega_tol:
            return False
    
    # Beta tolerance: TIGHT - tolerance% of target or 0.05 (important!)
    if target.beta is not None:
        beta_tol = max(abs(target.beta) * tolerance, 0.05)
        if abs(state.beta - target.beta) > beta_tol:
            logger.debug(f"Beta not within tolerance: {state.beta:.3f} vs target {target.beta:.3f} (tol={beta_tol:.3f})")
            return False
    
    # Sector tolerances - TIGHT for neutralization
    for sector, target_weight in target.sector_targets.items():
        current_weight = state.sector_weights.get(sector, 0)
        # If target is 0 (neutralize), use absolute 1% tolerance
        if abs(target_weight) < 0.01:
            sector_tol = 0.01
        else:
            sector_tol = max(abs(target_weight) * tolerance, 0.01)
        if abs(current_weight - target_weight) > sector_tol:
            logger.debug(f"Sector {sector} not within tolerance: {current_weight:.3f} vs target {target_weight:.3f}")
            return False
    
    return True


def _compute_factor_gap_vector(
    current_state: HedgeState,
    target: FactorTarget
) -> Dict[str, float]:
    """
    Compute the full multi-factor gap vector.
    
    Returns dict with gaps for all factors that have targets.
    Note: Beta and sector gaps are scaled to dollars (using current total_notional)
    so they are comparable to delta when solving quantities.
    """
    gaps = {}
    total_notional = max(abs(current_state.total_notional), 1.0)
    
    if target.delta is not None:
        gaps["delta"] = target.delta - current_state.delta
    
    if target.gamma is not None:
        gaps["gamma"] = target.gamma - current_state.gamma
    
    if target.vega is not None:
        gaps["vega"] = target.vega - current_state.vega
    
    if target.beta is not None:
        # Scale beta gap to dollar terms so it influences sizing meaningfully
        gaps["beta"] = (target.beta - current_state.beta) * total_notional
    
    # Sector gaps
    for sector, target_weight in target.sector_targets.items():
        current_weight = current_state.sector_weights.get(sector, 0)
        # Sector weight gap scaled to dollars
        gaps[f"sector_{sector}"] = (target_weight - current_weight) * total_notional
    
    return gaps


def _compute_candidate_impact_vector(
    candidate: HedgeCandidate,
    unit_qty: float,
    is_short: bool = False
) -> Dict[str, float]:
    """
    Compute the factor impact vector for a candidate at unit quantity.
    
    This is the "column" in the factor impact matrix for this candidate.
    """
    sign = -1 if is_short else 1
    impacts = {}
    
    if candidate.instrument_type == "option":
        # Options: Greeks per contract * 100
        impacts["delta"] = candidate.delta * unit_qty * OPTION_MULTIPLIER * sign
        impacts["gamma"] = candidate.gamma * unit_qty * OPTION_MULTIPLIER * sign
        impacts["vega"] = candidate.vega * unit_qty * OPTION_MULTIPLIER * sign
        # Options are leveraged - minimal beta/notional impact
        impacts["beta"] = 0
    else:
        # Stocks/ETFs: impact is notional-based
        notional = unit_qty * candidate.mid_price * sign
        impacts["delta"] = notional  # Stock delta = notional
        impacts["gamma"] = 0
        impacts["vega"] = 0
        # Beta contribution (dollar-weighted to align with delta scale)
        if candidate.mid_price > 0:
            impacts["beta"] = candidate.beta * candidate.mid_price * sign
        # Sector contribution (dollar impact; will be normalized via weights)
        if candidate.sector:
            impacts[f"sector_{candidate.sector}"] = candidate.mid_price * sign
    
    return impacts


def _solve_optimal_quantity(
    candidate: HedgeCandidate,
    gaps: Dict[str, float],
    current_state: HedgeState,
    weights: Optional[Dict[str, float]] = None
) -> Tuple[float, bool]:
    """
    Solve for optimal quantity using least-squares projection.
    
    Finds quantity q that minimizes weighted ||gaps - impact(q)||²
    
    This is the core MATRIX OPERATION:
    - gaps = target vector (what we need to close)
    - impact = candidate's factor impact per unit
    - q* = (impact · gaps) / (impact · impact)  [projection formula]
    
    Returns (optimal_qty, is_short)
    """
    if weights is None:
        # Default weights for different factors (normalizes their scales)
        weights = {
            "delta": 1.0 / 10000,      # Delta in $10K units
            "gamma": 1.0 / 100,        # Gamma normalized
            "vega": 1.0 / 1000,        # Vega normalized
            "beta": 1.0 / 10000,       # Beta impact scaled like delta (dollar-weighted)
        }
        # Sector weights (they're already 0-1 range)
        for key in gaps:
            if key.startswith("sector_"):
                weights[key] = 1.0 / 10000  # dollar impact scaled like delta
    
    # Try both long and short
    best_qty = 0
    best_is_short = False
    best_score = float('inf')
    
    for is_short in [False, True]:
        # Get impact vector for unit quantity
        impact = _compute_candidate_impact_vector(candidate, 1.0, is_short)
        
        # Compute weighted dot products for least-squares
        # q* = (w·impact · w·gaps) / (w·impact · w·impact)
        numerator = 0.0
        denominator = 0.0
        
        for factor, gap in gaps.items():
            w = weights.get(factor, 1.0)
            imp = impact.get(factor, 0)
            
            numerator += w * imp * w * gap
            denominator += w * imp * w * imp
        
        if denominator < 1e-10:
            continue  # This candidate can't help with these gaps
        
        # Optimal quantity (can be negative if wrong direction)
        q_opt = numerator / denominator
        
        # Must be positive (we handle direction via is_short)
        if q_opt <= 0:
            continue
        
        # Calculate residual (how much gap remains after this hedge)
        residual = 0.0
        for factor, gap in gaps.items():
            w = weights.get(factor, 1.0)
            imp = impact.get(factor, 0)
            remaining = gap - imp * q_opt
            residual += (w * remaining) ** 2
        
        if residual < best_score:
            best_score = residual
            best_qty = q_opt
            best_is_short = is_short
    
    return best_qty, best_is_short


def _generate_candidate_actions(
    candidate: HedgeCandidate,
    current_state: HedgeState,
    target: FactorTarget,
    max_contracts: int = 100,
    max_shares: int = 5000,
    max_gap_pct_per_instrument: float = 0.10,  # Each instrument can close max 10% of remaining gap
    target_num_instruments: int = 15  # Target number of instruments for the hedge
) -> List[Tuple[HedgeAction, float]]:
    """
    Generate possible actions for a hedge candidate with OPTIMAL quantities.
    
    Uses MATRIX OPTIMIZATION to find quantities that best close ALL factor gaps,
    not just delta. This is proper multi-factor portfolio optimization.
    
    CRITICAL: Each instrument is capped to ensure we need target_num_instruments
    to close the gap without overshooting.
    
    Returns list of (action, priority_score) tuples.
    """
    actions = []
    
    # Compute full gap vector (REMAINING gap, not original)
    gaps = _compute_factor_gap_vector(current_state, target)
    delta_gap_abs = abs(gaps.get("delta", 0))
    beta_gap_abs = abs(gaps.get("beta", 0))
    
    if not gaps:
        return actions
    
    # SMART CAP: Ensure gap is large enough for multiple instruments
    # If gap is small, we need to allow more % per instrument or skip expensive instruments
    min_delta_per_instrument = delta_gap_abs / max(target_num_instruments, 1)
    
    # For stocks, check if this instrument is "too expensive" for the remaining gap
    if candidate.instrument_type != "option" and candidate.mid_price > 0:
        # 1 share contributes mid_price delta
        if candidate.mid_price > delta_gap_abs * 0.5:
            # Even 1 share would close >50% of remaining gap - too much
            logger.debug(f"[{candidate.ticker}] Skipping: price ${candidate.mid_price:.0f} > 50% of gap ${delta_gap_abs:.0f}")
            return actions
    
    # Log remaining gaps for debugging
    logger.debug(f"[{candidate.ticker}] Gaps: delta={gaps.get('delta', 0):.0f}, beta=${gaps.get('beta', 0):.0f}, target_per_inst=${min_delta_per_instrument:.0f}")
    
    # Solve for optimal quantity using least-squares projection
    optimal_qty, is_short = _solve_optimal_quantity(candidate, gaps, current_state)
    
    if optimal_qty <= 0:
        return actions
    
    if candidate.instrument_type == "option":
        # Round to integer contracts
        base_qty = int(optimal_qty)
        if base_qty <= 0:
            base_qty = 1
        
        # Generate actions at optimal and nearby quantities
        quantities = set()
        quantities.add(max(1, int(base_qty * 0.5)))
        quantities.add(max(1, base_qty))
        quantities.add(max(1, min(int(base_qty * 1.5), max_contracts)))
        
        for qty in quantities:
            if qty <= 0 or qty > max_contracts:
                continue
            
            # Cap per-instrument delta to max_gap_pct_per_instrument of REMAINING gap
            # This ensures we need multiple instruments to close the gap (no single instrument dominance)
            per_contract_delta = candidate.delta * OPTION_MULTIPLIER
            delta_cap = delta_gap_abs * max_gap_pct_per_instrument if delta_gap_abs > 0 else abs(per_contract_delta) * 10
            if abs(per_contract_delta * qty) > delta_cap and per_contract_delta != 0:
                qty = max(1, int(delta_cap / abs(per_contract_delta)))
            if qty <= 0:
                continue

            # Calculate cost (premium)
            cost = candidate.cost_for_quantity(qty, OPTION_MULTIPLIER)
            
            # Full factor impact
            impact = FactorImpact(
                delta_change=candidate.delta * qty * OPTION_MULTIPLIER,
                gamma_change=candidate.gamma * qty * OPTION_MULTIPLIER,
                vega_change=candidate.vega * qty * OPTION_MULTIPLIER,
                notional_change=0,
                beta_dollar_change=0,
            )
            
            # Create action description
            opt_type = (candidate.option_type or "").upper()[0] if candidate.option_type else "?"
            action_str = f"buy {candidate.ticker} {candidate.strike}{opt_type}"
            if candidate.expiry:
                action_str += f" {candidate.expiry}"
            
            action = HedgeAction(
                instrument=action_str,
                ticker=candidate.ticker,
                action_type="buy",
                quantity=qty,
                cost=cost,
                factor_impact=impact,
                option_symbol=candidate.option_symbol,
                strike=candidate.strike,
                expiry=candidate.expiry,
                option_type=candidate.option_type,
            )
            
            # Priority: total gap reduction per dollar (multi-factor efficiency)
            gap_reduction = _compute_gap_reduction(gaps, impact, current_state)
            efficiency = gap_reduction / max(cost, 1)
            actions.append((action, efficiency))
    
    elif candidate.instrument_type in ["etf", "stock"]:
        if candidate.mid_price <= 0:
            return actions
        
        # Round to integer shares
        base_qty = int(optimal_qty)
        if base_qty < 10:
            base_qty = 10
        
        # Generate actions at optimal and nearby quantities
        quantities = set()
        quantities.add(max(10, int(base_qty * 0.5)))
        quantities.add(max(10, base_qty))
        quantities.add(max(10, min(int(base_qty * 1.5), max_shares)))
        
        for qty in quantities:
            if qty <= 0:
                continue
            
            # Calculate notional value
            position_notional = qty * candidate.mid_price
            
            # Cap per-instrument contribution to ensure we need multiple instruments
            # Use the SMALLER of: percentage cap OR target per instrument
            # This prevents overshooting when gap is small
            
            # Cap by delta gap (notional = delta for stocks)
            pct_cap = delta_gap_abs * max_gap_pct_per_instrument if delta_gap_abs > 0 else position_notional * 2
            target_cap = min_delta_per_instrument * 1.5  # Allow 50% buffer
            delta_cap = min(pct_cap, target_cap) if target_cap > 0 else pct_cap
            
            if abs(position_notional) > delta_cap and candidate.mid_price > 0:
                capped_qty = int(delta_cap / candidate.mid_price)
                if capped_qty < 1:
                    # Skip this candidate - even 1 share exceeds the cap
                    logger.debug(f"[{candidate.ticker}] Skipping: 1 share (${candidate.mid_price:.0f}) exceeds delta cap ${delta_cap:.0f}")
                    continue
                qty = capped_qty
                position_notional = qty * candidate.mid_price
            
            # Also cap by beta gap (ensure we don't overshoot beta)
            if beta_gap_abs > 0 and candidate.beta != 0:
                beta_contribution = abs(candidate.beta * position_notional)
                beta_cap = beta_gap_abs * max_gap_pct_per_instrument
                if beta_contribution > beta_cap:
                    max_notional_by_beta = beta_cap / abs(candidate.beta)
                    max_qty_by_beta = int(max_notional_by_beta / candidate.mid_price)
                    if max_qty_by_beta < 1:
                        # Skip - even 1 share exceeds beta cap
                        logger.debug(f"[{candidate.ticker}] Skipping: 1 share exceeds beta cap")
                        continue
                    if max_qty_by_beta < qty:
                        logger.debug(f"[{candidate.ticker}] Beta cap: qty {qty} -> {max_qty_by_beta}")
                        qty = max_qty_by_beta
                        position_notional = qty * candidate.mid_price
            
            logger.debug(f"[{candidate.ticker}] Final qty={qty}, notional=${position_notional:.0f}, delta_cap=${delta_cap:.0f}")
            
            action_type = "short" if is_short else "buy"
            sign = -1 if is_short else 1
            
            notional_change = position_notional * sign
            delta_change = position_notional * sign
            
            # Calculate cost
            slippage = candidate.mid_price * qty * max(candidate.spread_pct, 0.001)
            borrow_cost = position_notional * 0.005 if is_short else 0
            cost = slippage + borrow_cost
            
            # Full factor impact
            impact = FactorImpact(
                delta_change=delta_change,
                notional_change=notional_change,
                beta_dollar_change=candidate.beta * notional_change,
            )
            
            if candidate.sector:
                impact.sector_dollar_changes[candidate.sector] = notional_change
            
            action_str = f"{action_type} {qty} shares {candidate.ticker} @ ${candidate.mid_price:.2f}"
            
            action = HedgeAction(
                instrument=action_str,
                ticker=candidate.ticker,
                action_type=action_type,
                quantity=qty,
                cost=cost,
                factor_impact=impact,
            )
            
            # Priority: total gap reduction per dollar (multi-factor efficiency)
            gap_reduction = _compute_gap_reduction(gaps, impact, current_state)
            efficiency = gap_reduction / max(cost, 1)
            actions.append((action, efficiency))
    
    return actions


def _compute_gap_reduction(
    gaps: Dict[str, float],
    impact: FactorImpact,
    current_state: HedgeState
) -> float:
    """
    Compute total weighted gap reduction from an action.
    
    This measures how much the action helps close ALL factor gaps.
    IMPORTANT: Sectors weighted heavily to ensure neutralization is prioritized.
    """
    # Weight factors for gap reduction scoring (dollar scaled)
    weights = {
        "delta": 1.0,
        "gamma": 0.3,
        "vega": 0.3,
        "beta": 1.0,  # beta gap already dollar-scaled
        "sector": 1.5,  # Sectors weighted MORE to prioritize neutralization
    }
    
    total_reduction = 0.0
    
    # Delta
    if "delta" in gaps and gaps["delta"] != 0:
        reduction = min(abs(impact.delta_change), abs(gaps["delta"]))
        if (gaps["delta"] > 0) == (impact.delta_change > 0):
            total_reduction += weights["delta"] * reduction
    
    # Gamma
    if "gamma" in gaps and gaps["gamma"] != 0:
        reduction = min(abs(impact.gamma_change), abs(gaps["gamma"]))
        if (gaps["gamma"] > 0) == (impact.gamma_change > 0):
            total_reduction += weights["gamma"] * reduction
    
    # Vega
    if "vega" in gaps and gaps["vega"] != 0:
        reduction = min(abs(impact.vega_change), abs(gaps["vega"]))
        if (gaps["vega"] > 0) == (impact.vega_change > 0):
            total_reduction += weights["vega"] * reduction
    
    # Beta (via beta_dollar) - gaps and impacts already dollar scaled
    if "beta" in gaps and current_state.total_notional > 0:
        beta_dollar_change = impact.beta_dollar_change
        reduction = min(abs(beta_dollar_change), abs(gaps["beta"]))
        if (gaps["beta"] > 0) == (beta_dollar_change > 0):
            total_reduction += weights["beta"] * reduction
    
    # Sectors - use higher "sector" weight for neutralization priority
    for factor, gap in gaps.items():
        if factor.startswith("sector_") and gap != 0:
            sector = factor.replace("sector_", "")
            sector_change = impact.sector_dollar_changes.get(sector, 0)
            reduction = min(abs(sector_change), abs(gap))
            if (gap > 0) == (sector_change > 0):
                total_reduction += weights.get("sector", 1.5) * reduction
    
    return total_reduction


def _apply_action(state: HedgeState, action: HedgeAction) -> HedgeState:
    """Apply an action to a state and return new state.
    
    Uses proper dollar-weighted portfolio math:
    - total_notional += notional_change
    - beta_dollar += beta_dollar_change
    - sector_dollars += sector_dollar_changes
    """
    new_state = state.clone()
    
    # Update Greeks directly
    new_state.delta += action.factor_impact.delta_change
    new_state.gamma += action.factor_impact.gamma_change
    new_state.vega += action.factor_impact.vega_change
    
    # Update dollar-weighted factors (proper portfolio math)
    new_state.total_notional += action.factor_impact.notional_change
    new_state.beta_dollar += action.factor_impact.beta_dollar_change
    
    # Update sector exposures in dollars
    for sector, dollar_change in action.factor_impact.sector_dollar_changes.items():
        new_state.sector_dollars[sector] = (
            new_state.sector_dollars.get(sector, 0) + dollar_change
        )
    
    new_state.cost += action.cost
    new_state.path.append(action)
    
    return new_state


def dijkstra_multi_objective(
    start_factors: PortfolioFactors,
    target: FactorTarget,
    candidates: List[HedgeCandidate],
    max_steps: int = 5,
    k_paths: int = 3,
    max_iterations: int = 1000,
    tolerance: float = 0.1,
    min_instruments: int = 1
) -> List[HedgePath]:
    """
    Find k-best minimum-cost paths from current factors to target.
    
    Uses A* with heuristic = distance to target.
    
    Args:
        start_factors: Current portfolio factors
        target: Target factor exposures
        candidates: Available hedge instruments
        max_steps: Maximum actions in a path
        k_paths: Number of paths to return
        max_iterations: Maximum search iterations
        tolerance: Tolerance for reaching target
        min_instruments: Minimum number of instruments in hedge (to avoid concentration risk)
    
    Returns:
        List of HedgePath objects, ranked by cost
    """
    if not candidates:
        return []
    
    # Initialize start state
    # Initialize start state with proper dollar-weighted tracking
    # total_notional = portfolio value (or delta for stock portfolios)
    total_notional = getattr(start_factors, 'total_notional', 0) or abs(start_factors.delta) or 100000
    
    # Convert sector weights to dollar values
    sector_dollars = {}
    for sector, weight in start_factors.sector_weights.items():
        sector_dollars[sector] = weight * total_notional
    
    start_state = HedgeState(
        delta=start_factors.delta,
        gamma=start_factors.gamma,
        vega=start_factors.vega,
        total_notional=total_notional,
        beta_dollar=start_factors.beta * total_notional,  # Weighted beta
        sector_dollars=sector_dollars,
        cost=0.0,
        path=[],
    )
    
    # Calculate initial gap for closure metrics
    initial_gap = FactorGap(
        delta_gap=(target.delta or start_factors.delta) - start_factors.delta,
        gamma_gap=(target.gamma or start_factors.gamma) - start_factors.gamma,
        vega_gap=(target.vega or start_factors.vega) - start_factors.vega,
    )
    
    # Priority queue: (priority, iteration, state)
    # Priority = cost + heuristic (A* style)
    heap: List[Tuple[float, int, HedgeState]] = []
    
    initial_heuristic = _calculate_distance_to_target(start_state, target)
    heapq.heappush(heap, (initial_heuristic, 0, start_state))
    
    # Track completed paths
    completed_paths: List[HedgePath] = []
    
    # Track primary instruments used in completed paths (for diversity)
    used_primary_instruments: set = set()
    
    # Track visited states to avoid cycles
    visited: set = set()
    
    iteration = 0
    
    while heap and iteration < max_iterations and len(completed_paths) < k_paths:
        iteration += 1
        
        _, _, current_state = heapq.heappop(heap)
        
        # Create state key for cycle detection
        # Use unique tickers (no duplicates) and path length
        unique_tickers = tuple(sorted(set(a.ticker for a in current_state.path)))
        state_key = (
            unique_tickers,
            len(current_state.path),
        )
        
        if state_key in visited:
            continue
        visited.add(state_key)
        
        # Get primary instrument for this path (first instrument used)
        primary_instrument = current_state.path[0].ticker if current_state.path else None
        
        # Count unique instruments in path
        num_instruments = len(set(a.ticker for a in current_state.path))
        
        # Check if target reached AND minimum instruments requirement met
        # This prevents single-instrument hedges that create concentration risk
        if _is_within_tolerance(current_state, target, tolerance) and num_instruments >= min_instruments:
            # DIVERSITY CHECK: Skip if primary instrument already used in completed path
            if primary_instrument and primary_instrument in used_primary_instruments:
                continue  # Find a different path with different instruments
            
            # Mark this primary instrument as used
            if primary_instrument:
                used_primary_instruments.add(primary_instrument)
            
            logger.info(f"Found complete path with {num_instruments} instruments (min={min_instruments})")
            
            # Calculate efficiency and closure metrics
            gap_closed = abs(initial_gap.delta_gap) - abs(
                (target.delta or 0) - current_state.delta
            )
            efficiency = gap_closed / max(current_state.cost, 1) if current_state.cost > 0 else 0
            
            delta_closure = 1.0
            if initial_gap.delta_gap != 0:
                remaining = (target.delta or 0) - current_state.delta
                delta_closure = 1 - abs(remaining / initial_gap.delta_gap)
            
            gamma_closure = 1.0
            if initial_gap.gamma_gap != 0:
                remaining = (target.gamma or 0) - current_state.gamma
                gamma_closure = 1 - abs(remaining / initial_gap.gamma_gap)
            
            vega_closure = 1.0
            if initial_gap.vega_gap != 0:
                remaining = (target.vega or 0) - current_state.vega
                vega_closure = 1 - abs(remaining / initial_gap.vega_gap)
            
            path = HedgePath(
                rank=len(completed_paths) + 1,
                total_cost=current_state.cost,
                efficiency=efficiency,
                steps=current_state.path,
                final_factors={
                    "delta": round(current_state.delta, 2),
                    "gamma": round(current_state.gamma, 4),
                    "vega": round(current_state.vega, 2),
                    "beta": round(current_state.beta, 3),
                    "sector_weights": dict(current_state.sector_weights),
                },
                delta_closure_pct=delta_closure,
                gamma_closure_pct=gamma_closure,
                vega_closure_pct=vega_closure,
            )
            completed_paths.append(path)
            continue
        
        # Don't explore further if max steps reached
        if len(current_state.path) >= max_steps:
            continue
        
        # Get tickers already used in this path
        used_tickers = {a.ticker for a in current_state.path}
        
        # Generate successor states
        for candidate in candidates:
            # DIVERSITY: Skip candidates already used in this path
            # This ensures each path step uses a different instrument
            if candidate.ticker in used_tickers:
                continue
            
            actions = _generate_candidate_actions(
                candidate, current_state, target,
                target_num_instruments=min_instruments
            )
            
            for action, _ in actions:
                new_state = _apply_action(current_state, action)
                
                # Calculate priority for PORTFOLIO BUILDING (not just pathfinding)
                # Key insight: We want to explore portfolios that:
                # 1. Have enough instruments (min_instruments)
                # 2. Close factor gaps effectively
                # 3. Cost is secondary to effectiveness
                
                heuristic = _calculate_distance_to_target(new_state, target)
                num_instruments = len(set(a.ticker for a in new_state.path))
                
                # PORTFOLIO BUILDING PRIORITY:
                # - Phase 1 (under min_instruments): STRONGLY favor adding more instruments
                # - Phase 2 (at min_instruments): Optimize for gap closure
                
                if num_instruments < min_instruments:
                    # Phase 1: Building the portfolio
                    # Priority = how far from min_instruments + small heuristic adjustment
                    # Lower num_instruments = MUCH higher priority (worse)
                    instruments_deficit = min_instruments - num_instruments
                    priority = instruments_deficit * 1000 + heuristic * 10  # Cost barely matters here
                else:
                    # Phase 2: Portfolio is big enough, now optimize for targets
                    # Priority = heuristic (distance to target) + small cost factor
                    priority = heuristic * 100 + new_state.cost * 0.01  # Cost is minor factor
                
                heapq.heappush(heap, (priority, iteration, new_state))
    
    # If no complete paths found, return best DIVERSE partial paths
    # IMPORTANT: Partial paths must ALSO respect min_instruments requirement
    if not completed_paths and heap:
        logger.warning(f"No complete paths found meeting all constraints. Returning best partial paths with min {min_instruments} instruments.")
        
        # Get best incomplete states with minimum instruments requirement
        best_states = []
        partial_used_tickers: set = set()
        
        # First pass: find paths with at least min_instruments
        candidates_with_min = []
        temp_heap = list(heap)
        for _, _, state in sorted(temp_heap, key=lambda x: x[0]):
            num_instruments = len(set(a.ticker for a in state.path))
            if num_instruments >= min_instruments:
                candidates_with_min.append(state)
        
        # If we have paths with min_instruments, use those
        if candidates_with_min:
            logger.info(f"Found {len(candidates_with_min)} partial paths with >= {min_instruments} instruments")
            for state in candidates_with_min[:k_paths]:
                # Check for diversity
                tickers_in_path = frozenset(a.ticker for a in state.path)
                if tickers_in_path not in partial_used_tickers:
                    partial_used_tickers.add(tickers_in_path)
                    best_states.append(state)
        else:
            # Fallback: return the paths with MOST instruments (even if < min)
            logger.warning(f"No partial paths found with {min_instruments} instruments. Returning paths with most instruments available.")
            sorted_by_instruments = sorted(
                [(state, len(set(a.ticker for a in state.path))) for _, _, state in temp_heap if state.path],
                key=lambda x: (-x[1], sum(a.cost for a in x[0].path))  # Most instruments, lowest cost
            )
            for state, num_inst in sorted_by_instruments[:k_paths]:
                tickers_in_path = frozenset(a.ticker for a in state.path)
                if tickers_in_path not in partial_used_tickers:
                    partial_used_tickers.add(tickers_in_path)
                    best_states.append(state)
                    logger.info(f"Returning partial path with {num_inst} instruments (wanted {min_instruments})")
        
        for i, state in enumerate(best_states):
            delta_closure = 0.0
            if initial_gap.delta_gap != 0:
                remaining = (target.delta or 0) - state.delta
                delta_closure = 1 - abs(remaining / initial_gap.delta_gap)
            
            path = HedgePath(
                rank=i + 1,
                total_cost=state.cost,
                efficiency=delta_closure / max(state.cost, 1) * 10000,
                steps=state.path,
                final_factors={
                    "delta": round(state.delta, 2),
                    "gamma": round(state.gamma, 4),
                    "vega": round(state.vega, 2),
                    "beta": round(state.beta, 3),
                    "sector_weights": dict(state.sector_weights),
                },
                delta_closure_pct=delta_closure,
            )
            completed_paths.append(path)
    
    # Sort by cost
    completed_paths.sort(key=lambda p: p.total_cost)
    
    # Re-rank
    for i, path in enumerate(completed_paths):
        path.rank = i + 1
    
    return completed_paths[:k_paths]


# =============================================================================
# PORTFOLIO OPTIMIZATION APPROACH (Alternative to Dijkstra)
# =============================================================================

@dataclass
class HedgePortfolio:
    """A portfolio of hedge instruments (not a sequential path)."""
    
    instruments: List[HedgeAction]
    total_cost: float
    total_notional: float
    final_factors: Dict[str, Any]
    gap_closure: Dict[str, float]  # How much of each gap was closed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_instruments": len(self.instruments),
            "total_cost": round(self.total_cost, 2),
            "total_notional": round(self.total_notional, 2),
            "instruments": [i.to_dict() for i in self.instruments],
            "final_factors": self.final_factors,
            "gap_closure": {k: round(v * 100, 1) for k, v in self.gap_closure.items()},
        }


def _score_candidate_efficiency(
    candidate: HedgeCandidate,
    gaps: Dict[str, float],
    weights: Optional[Dict[str, float]] = None
) -> Tuple[float, float, bool]:
    """
    Score a candidate by how efficiently it closes the multi-factor gap.
    
    Returns (efficiency_score, optimal_qty, is_short)
    
    Higher score = better candidate for the hedge portfolio.
    """
    if weights is None:
        weights = {
            "delta": 1.0,
            "gamma": 0.3,
            "vega": 0.3,
            "beta": 1.0,
        }
        for key in gaps:
            if key.startswith("sector_"):
                weights[key] = 1.0
    
    best_score = 0.0
    best_qty = 0.0
    best_is_short = False
    
    for is_short in [False, True]:
        impact = _compute_candidate_impact_vector(candidate, 1.0, is_short)
        
        # Calculate gap closure per unit
        gap_closure = 0.0
        total_gap_magnitude = 0.0
        
        for factor, gap in gaps.items():
            if abs(gap) < 1e-10:
                continue
            w = weights.get(factor, 1.0)
            imp = impact.get(factor, 0)
            
            # How much of this gap can this candidate close (normalized)?
            if gap != 0:
                closure_fraction = (imp / gap) if abs(gap) > 1e-10 else 0
                # Clamp to [0, 1] - we want candidates that close gaps, not overshoot
                closure_fraction = max(0, min(1, closure_fraction))
                gap_closure += w * closure_fraction
                total_gap_magnitude += w
        
        if total_gap_magnitude < 1e-10:
            continue
        
        # Normalize by total gap magnitude
        efficiency = gap_closure / total_gap_magnitude
        
        # Penalize expensive candidates
        cost_per_unit = candidate.mid_price * (0.001 + 0.01)  # spread + slippage estimate
        if cost_per_unit > 0:
            efficiency /= (1 + cost_per_unit / 1000)
        
        if efficiency > best_score:
            best_score = efficiency
            # Estimate optimal quantity
            # Find qty that closes ~10-15% of delta gap (to leave room for other instruments)
            delta_gap = abs(gaps.get("delta", 0))
            delta_impact = abs(impact.get("delta", 0))
            if delta_impact > 0 and delta_gap > 0:
                target_closure = 0.12  # Each instrument closes ~12% of gap on average
                best_qty = (delta_gap * target_closure) / delta_impact
            else:
                best_qty = 10  # Default
            best_is_short = is_short
    
    return best_score, best_qty, best_is_short


def optimize_hedge_portfolio(
    start_factors: PortfolioFactors,
    target: FactorTarget,
    candidates: List[HedgeCandidate],
    num_instruments: int = 15,
    max_notional_per_instrument: float = 50000,
    max_iterations: int = 3,
) -> Optional[HedgePortfolio]:
    """
    Optimize a hedge PORTFOLIO of N instruments simultaneously.
    
    Unlike Dijkstra (sequential path), this approach:
    1. Scores all candidates by multi-factor efficiency
    2. Selects top N candidates
    3. Iteratively optimizes quantities to close all gaps
    4. Returns a single optimal hedge portfolio
    
    This is TRUE PORTFOLIO OPTIMIZATION, not pathfinding.
    
    Args:
        start_factors: Current portfolio factor exposures
        target: Target factor exposures
        candidates: List of hedge candidates (ETFs, stocks, options)
        num_instruments: Target number of instruments in hedge portfolio (10-20)
        max_notional_per_instrument: Cap per instrument to ensure diversification
        max_iterations: Iterations for quantity refinement
    
    Returns:
        HedgePortfolio with optimized instruments and quantities
    """
    if not candidates:
        logger.warning("No candidates provided for portfolio optimization")
        return None
    
    logger.info(f"Optimizing hedge portfolio with {len(candidates)} candidates, targeting {num_instruments} instruments")
    
    # Initialize state tracking
    total_notional = getattr(start_factors, 'total_notional', 0) or abs(start_factors.delta) or 100000
    
    # Compute initial gaps
    current_delta = start_factors.delta
    current_gamma = start_factors.gamma
    current_vega = start_factors.vega
    current_beta = start_factors.beta
    current_sectors = dict(start_factors.sector_weights)
    
    gaps = {
        "delta": (target.delta or current_delta) - current_delta,
        "gamma": (target.gamma or current_gamma) - current_gamma,
        "vega": (target.vega or current_vega) - current_vega,
        "beta": ((target.beta or current_beta) - current_beta) * total_notional,
    }
    for sector, target_weight in target.sector_targets.items():
        current_weight = current_sectors.get(sector, 0)
        gaps[f"sector_{sector}"] = (target_weight - current_weight) * total_notional
    
    initial_gaps = dict(gaps)
    logger.info(f"Initial gaps: delta={gaps['delta']:.0f}, beta_gap=${gaps.get('beta', 0):.0f}")
    
    # Score all candidates
    scored_candidates = []
    for cand in candidates:
        score, qty, is_short = _score_candidate_efficiency(cand, gaps)
        if score > 0.01:  # Minimum efficiency threshold
            scored_candidates.append((score, qty, is_short, cand))
    
    # Sort by efficiency (descending)
    scored_candidates.sort(key=lambda x: -x[0])
    
    if not scored_candidates:
        logger.warning("No candidates passed efficiency threshold")
        return None
    
    # Select top N candidates (diverse by ticker)
    selected = []
    used_tickers = set()
    for score, qty, is_short, cand in scored_candidates:
        if cand.ticker in used_tickers:
            continue
        selected.append((score, qty, is_short, cand))
        used_tickers.add(cand.ticker)
        if len(selected) >= num_instruments:
            break
    
    logger.info(f"Selected {len(selected)} instruments for hedge portfolio")
    
    # Iteratively optimize quantities
    # Start with initial estimates, then refine
    portfolio_actions: List[HedgeAction] = []
    remaining_gaps = dict(gaps)
    
    for iteration in range(max_iterations):
        portfolio_actions = []
        running_delta = current_delta
        running_gamma = current_gamma
        running_vega = current_vega
        running_beta_dollar = current_beta * total_notional
        running_sector_dollars = {s: w * total_notional for s, w in current_sectors.items()}
        running_notional = total_notional
        total_cost = 0.0
        
        # Recalculate gaps
        remaining_gaps = dict(gaps)
        
        for idx, (score, est_qty, is_short, cand) in enumerate(selected):
            # Solve for optimal quantity given remaining gaps
            impact = _compute_candidate_impact_vector(cand, 1.0, is_short)
            
            # Use weighted least squares to find qty
            # But also respect max_notional_per_instrument
            numerator = 0.0
            denominator = 0.0
            weight_map = {
                "delta": 1.0 / max(abs(initial_gaps.get("delta", 1)), 1),
                "beta": 1.0 / max(abs(initial_gaps.get("beta", 1)), 1),
            }
            for key in remaining_gaps:
                if key.startswith("sector_"):
                    weight_map[key] = 1.0 / max(abs(initial_gaps.get(key, 1)), 1)
            
            for factor, gap in remaining_gaps.items():
                w = weight_map.get(factor, 0.1)
                imp = impact.get(factor, 0)
                numerator += w * imp * gap
                denominator += w * imp * imp
            
            if denominator < 1e-10:
                continue
            
            optimal_qty = numerator / denominator
            
            # Sanity checks
            if optimal_qty <= 0:
                continue
            
            # Cap by max notional
            if cand.instrument_type != "option":
                max_qty_by_notional = max_notional_per_instrument / max(cand.mid_price, 1)
                optimal_qty = min(optimal_qty, max_qty_by_notional)
            
            # Cap by reasonable limits
            if cand.instrument_type == "option":
                optimal_qty = min(optimal_qty, 50)  # Max 50 contracts
            else:
                optimal_qty = min(optimal_qty, 5000)  # Max 5000 shares
            
            # Round to int
            qty = max(1, int(round(optimal_qty)))
            
            # Calculate actual impact
            actual_impact = _compute_candidate_impact_vector(cand, qty, is_short)
            
            # Update running totals
            delta_change = actual_impact.get("delta", 0)
            gamma_change = actual_impact.get("gamma", 0)
            vega_change = actual_impact.get("vega", 0)
            beta_dollar_change = actual_impact.get("beta", 0) * qty
            
            running_delta += delta_change
            running_gamma += gamma_change
            running_vega += vega_change
            
            # Update remaining gaps
            for factor in remaining_gaps:
                remaining_gaps[factor] -= actual_impact.get(factor, 0)
            
            # Compute cost
            spread = cand.mid_price * 0.001  # 0.1% spread
            slippage = cand.mid_price * 0.005  # 0.5% slippage
            cost = qty * (spread + slippage)
            total_cost += cost
            
            # Notional for position
            if cand.instrument_type == "option":
                position_notional = qty * OPTION_MULTIPLIER * cand.mid_price
            else:
                position_notional = qty * cand.mid_price
            
            if is_short:
                position_notional = -position_notional
                beta_dollar_change = -beta_dollar_change
            
            running_notional += position_notional
            running_beta_dollar += beta_dollar_change
            
            # Build action
            action_type = "short" if is_short else "buy"
            instrument_desc = f"{action_type.upper()} {qty} {cand.ticker} @ ${cand.mid_price:.2f}"
            
            factor_impact = FactorImpact(
                delta_change=delta_change,
                gamma_change=gamma_change,
                vega_change=vega_change,
                notional_change=position_notional,
                beta_dollar_change=beta_dollar_change,
            )
            
            action = HedgeAction(
                instrument=instrument_desc,
                ticker=cand.ticker,
                action_type=action_type,
                quantity=qty,
                cost=cost,
                factor_impact=factor_impact,
                strike=cand.strike,
                expiry=cand.expiry,
                option_type=cand.option_type,
            )
            
            portfolio_actions.append(action)
    
    if not portfolio_actions:
        logger.warning("Failed to build hedge portfolio")
        return None
    
    # Calculate final factors
    final_delta = current_delta + sum(a.factor_impact.delta_change for a in portfolio_actions)
    final_gamma = current_gamma + sum(a.factor_impact.gamma_change for a in portfolio_actions)
    final_vega = current_vega + sum(a.factor_impact.vega_change for a in portfolio_actions)
    final_notional = running_notional
    final_beta_dollar = running_beta_dollar
    final_beta = final_beta_dollar / final_notional if final_notional != 0 else current_beta
    
    # Calculate gap closures
    gap_closure = {}
    if abs(initial_gaps.get("delta", 0)) > 0:
        delta_closed = initial_gaps["delta"] - remaining_gaps.get("delta", 0)
        gap_closure["delta"] = delta_closed / initial_gaps["delta"]
    if abs(initial_gaps.get("beta", 0)) > 0:
        beta_closed = initial_gaps["beta"] - remaining_gaps.get("beta", 0)
        gap_closure["beta"] = beta_closed / initial_gaps["beta"]
    for sector in target.sector_targets:
        key = f"sector_{sector}"
        if abs(initial_gaps.get(key, 0)) > 0:
            closed = initial_gaps[key] - remaining_gaps.get(key, 0)
            gap_closure[sector] = closed / initial_gaps[key]
    
    total_hedge_cost = sum(a.cost for a in portfolio_actions)
    total_hedge_notional = sum(abs(a.factor_impact.notional_change) for a in portfolio_actions)
    
    logger.info(f"Hedge portfolio: {len(portfolio_actions)} instruments, cost=${total_hedge_cost:.2f}, notional=${total_hedge_notional:.0f}")
    logger.info(f"Final factors: delta={final_delta:.0f}, beta={final_beta:.3f}")
    logger.info(f"Gap closure: {gap_closure}")
    
    return HedgePortfolio(
        instruments=portfolio_actions,
        total_cost=total_hedge_cost,
        total_notional=total_hedge_notional,
        final_factors={
            "delta": round(final_delta, 2),
            "gamma": round(final_gamma, 4),
            "vega": round(final_vega, 2),
            "beta": round(final_beta, 3),
        },
        gap_closure=gap_closure,
    )
