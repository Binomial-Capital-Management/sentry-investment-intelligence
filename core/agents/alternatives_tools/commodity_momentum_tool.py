"""
Commodity Momentum Screener Tool

Screens and ranks commodities by momentum across multiple timeframes.
NO hardcoded symbol lists - user provides symbols to screen.

Calculates:
- Rate of change (1W, 1M, 3M)
- Price vs moving averages
- Trend strength and momentum acceleration
- Cross-commodity relative strength via z-scores

HMM Regime Detection (optional):
- Fits Hidden Markov Model on the fetched price data
- Detects market regime: TRENDING, CHOPPY, or MEAN_REVERTING
- Adjusts momentum signals based on regime reliability
- No external data sources - uses only the commodity prices provided
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from agents import function_tool

from core.mcp_servers.fmp.FMPAlternativesServer import FMPAlternativesServer
from core.utils.mcp_result_parser import safe_parse_json
from core.agents.quant_tools.chart_helpers import wrap_plotly_charts
from core.utils.context_utils import get_cancel_event

logger = logging.getLogger(__name__)


def _check_cancellation(context: str = ""):
    """Check if cancellation was requested and raise CancelledError if so."""
    cancel_event = get_cancel_event()
    if cancel_event and cancel_event.is_set():
        logger.info(f"[CANCEL] commodity_momentum cancelled{' during ' + context if context else ''}")
        raise asyncio.CancelledError(f"commodity_momentum cancelled{' during ' + context if context else ''}")


# =============================================================================
# HMM REGIME DETECTOR (integrated, uses fetched data only)
# =============================================================================

class MomentumRegimeDetector:
    """
    Hidden Markov Model regime detector for momentum strategies.
    
    Detects three states from price data:
    - TRENDING: Positive autocorrelation, momentum works
    - CHOPPY: Near-zero autocorrelation, signals unreliable
    - MEAN_REVERTING: Negative autocorrelation, fade extremes
    
    Features are derived from the price data itself - no external sources.
    Signal multipliers are calculated from the data (momentum performance per regime)
    or can be user-specified.
    """
    
    STATES = ["MEAN_REVERTING", "CHOPPY", "TRENDING"]
    N_STATES = 3
    
    def __init__(self, n_states: int = 3, user_multipliers: Optional[Dict[str, float]] = None):
        """
        Initialize detector.
        
        Args:
            n_states: Number of hidden states (default 3)
            user_multipliers: Optional user-specified multipliers per regime.
                             Example: {"TRENDING": 1.5, "CHOPPY": 0.3, "MEAN_REVERTING": 0.2}
                             If not provided, multipliers are calculated from the data.
        """
        self.n_states = n_states
        self.model = None
        self._fitted = False
        self.user_multipliers = user_multipliers
        self.calculated_multipliers = None
    
    def _compute_features(self, prices_dict: Dict[str, pd.DataFrame], window: int = 21) -> Optional[np.ndarray]:
        """
        Compute HMM features from price data.
        
        Features derived (per time step):
        1. Average return across commodities
        2. Average autocorrelation (trend indicator)
        3. Average volatility
        4. Cross-correlation (dispersion)
        
        Args:
            prices_dict: {symbol: DataFrame with 'close' column}
            window: Rolling window for calculations
        
        Returns:
            Array of shape (T, n_features) or None if insufficient data
        """
        if len(prices_dict) < 2:
            logger.warning("[HMM] Need at least 2 symbols for regime detection")
            return None
        
        # Log what we're working with
        logger.info(f"[HMM] Processing {len(prices_dict)} symbols for regime detection")
        for sym, df in prices_dict.items():
            logger.debug(f"[HMM] {sym}: {len(df)} rows, columns: {list(df.columns)}")
        
        # Align all price series - handle both indexed and column date formats
        price_series = {}
        for sym, df in prices_dict.items():
            if 'date' in df.columns:
                # Set date as index if it's a column
                series = df.set_index('date')['close']
            elif df.index.name == 'date' or isinstance(df.index, pd.DatetimeIndex):
                # Date is already the index
                series = df['close']
            else:
                # Try to use first column as index
                series = df.set_index(df.columns[0])['close'] if 'close' in df.columns else df.iloc[:, 1]
            price_series[sym] = series
        
        all_prices = pd.DataFrame(price_series)
        
        # Forward fill small gaps (up to 3 days) then drop remaining NaN
        all_prices = all_prices.ffill(limit=3).dropna()
        
        logger.info(f"[HMM] Aligned data: {len(all_prices)} rows after dropna")
        
        min_required = window * 2 + 10  # More relaxed: need window*2 + some buffer
        if len(all_prices) < min_required:
            logger.warning(f"[HMM] Insufficient aligned data: {len(all_prices)} points (need {min_required})")
            return None
        
        # Calculate returns
        returns = all_prices.pct_change().dropna()
        
        # Feature 1: Average return (market direction)
        avg_return = returns.mean(axis=1)
        
        # Feature 2: Rolling autocorrelation (trend vs mean-reversion)
        def rolling_autocorr(series, lag=1):
            return series.rolling(window).apply(
                lambda x: pd.Series(x).autocorr(lag=lag) if len(x) > lag else 0,
                raw=False
            )
        
        autocorr = returns.apply(lambda col: rolling_autocorr(col, lag=1)).mean(axis=1)
        
        # Feature 3: Rolling volatility
        volatility = returns.rolling(window).std().mean(axis=1)
        
        # Feature 4: Cross-commodity correlation (dispersion)
        def rolling_cross_corr(df, w):
            result = []
            for i in range(len(df)):
                if i < w:
                    result.append(np.nan)
                else:
                    window_df = df.iloc[i-w:i]
                    corr_matrix = window_df.corr()
                    # Average off-diagonal correlation
                    mask = ~np.eye(corr_matrix.shape[0], dtype=bool)
                    avg_corr = corr_matrix.values[mask].mean()
                    result.append(avg_corr)
            return pd.Series(result, index=df.index)
        
        cross_corr = rolling_cross_corr(returns, window)
        
        # Combine features
        features = pd.DataFrame({
            'avg_return': avg_return,
            'autocorr': autocorr,
            'volatility': volatility,
            'cross_corr': cross_corr
        }).dropna()
        
        min_feature_obs = self.n_states * 10  # Relaxed from 20 to 10
        if len(features) < min_feature_obs:
            logger.warning(f"[HMM] Insufficient feature data: {len(features)} points (need {min_feature_obs})")
            return None
        
        logger.info(f"[HMM] Computed {len(features)} feature observations")
        return features.values, features.index
    
    def fit_predict(self, prices_dict: Dict[str, pd.DataFrame], window: int = 21) -> Optional[Dict[str, Any]]:
        """
        Fit HMM and predict current regime.
        
        Signal multipliers are either:
        1. User-specified (if passed to __init__)
        2. Calculated from the data: average forward return in each regime
        
        Args:
            prices_dict: {symbol: DataFrame with 'date' and 'close' columns}
            window: Rolling window for feature calculation
        
        Returns:
            Dict with regime info or None if fitting fails
        """
        try:
            from hmmlearn import hmm
        except ImportError:
            logger.warning("[HMM] hmmlearn not installed, skipping regime detection")
            return None
        
        result = self._compute_features(prices_dict, window)
        if result is None:
            return None
        
        observations, dates = result
        
        # Standardize features
        means = np.nanmean(observations, axis=0)
        stds = np.nanstd(observations, axis=0) + 1e-9
        standardized = (observations - means) / stds
        
        # Handle any remaining NaN
        valid_mask = ~np.isnan(standardized).any(axis=1)
        clean_obs = standardized[valid_mask]
        clean_dates = dates[valid_mask]
        
        min_clean_obs = self.n_states * 8  # Relaxed from 15 to 8 (24 minimum for 3 states)
        if len(clean_obs) < min_clean_obs:
            logger.warning(f"[HMM] Not enough clean observations: {len(clean_obs)} (need {min_clean_obs})")
            return None
        
        logger.info(f"[HMM] Fitting HMM with {len(clean_obs)} observations")
        
        # Fit HMM
        try:
            self.model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="diag",
                n_iter=100,
                random_state=42
            )
            self.model.fit(clean_obs)
            self._fitted = True
        except Exception as e:
            logger.warning(f"[HMM] Fitting failed: {e}")
            return None
        
        # Get state sequence and probabilities
        state_sequence = self.model.predict(clean_obs)
        state_probs = self.model.predict_proba(clean_obs)
        current_probs = state_probs[-1]
        current_state_idx = int(np.argmax(current_probs))
        
        # Map state index to name based on emission means
        # State with highest autocorr mean = TRENDING
        # State with lowest autocorr mean = MEAN_REVERTING
        # Middle = CHOPPY
        autocorr_means = self.model.means_[:, 1]  # autocorr is feature index 1
        sorted_indices = np.argsort(autocorr_means)
        
        state_mapping = {
            sorted_indices[0]: "MEAN_REVERTING",
            sorted_indices[1]: "CHOPPY",
            sorted_indices[2]: "TRENDING"
        }
        
        current_state = state_mapping.get(current_state_idx, f"STATE_{current_state_idx}")
        
        # Build probability dict with proper names
        all_probs = {
            state_mapping.get(i, f"STATE_{i}"): float(p)
            for i, p in enumerate(current_probs)
        }
        
        # =================================================================
        # CALCULATE MULTIPLIERS FROM DATA (if not user-specified)
        # Multiplier = how well did momentum perform in each regime?
        # =================================================================
        
        if self.user_multipliers:
            # Use user-specified multipliers
            multipliers = self.user_multipliers
            multiplier_source = "user_specified"
        else:
            # Calculate from data: average forward return per regime
            multipliers = self._calculate_multipliers_from_data(
                prices_dict, state_sequence, state_mapping, clean_dates
            )
            multiplier_source = "calculated_from_data"
        
        self.calculated_multipliers = multipliers
        multiplier = multipliers.get(current_state, 1.0)
        
        # Transition matrix
        trans_matrix = self.model.transmat_
        persistence = float(trans_matrix[current_state_idx, current_state_idx])
        
        # Next period forecast
        next_probs_raw = current_probs @ trans_matrix
        next_probs = {
            state_mapping.get(i, f"STATE_{i}"): float(p)
            for i, p in enumerate(next_probs_raw)
        }
        
        # Stability assessment
        if persistence > 0.85:
            stability = "STABLE"
        elif persistence > 0.7:
            stability = "MODERATE"
        else:
            stability = "UNSTABLE"
        
        return {
            "current_regime": current_state,
            "current_probability": float(current_probs[current_state_idx]),
            "all_probabilities": all_probs,
            "transition_forecast": next_probs,
            "regime_persistence": persistence,
            "regime_stability": stability,
            "signal_multiplier": multiplier,
            "all_multipliers": multipliers,
            "multiplier_source": multiplier_source,
            "n_observations_used": len(clean_obs),
            "interpretation": self._interpret_regime(current_state, persistence, multiplier)
        }
    
    def _calculate_multipliers_from_data(
        self,
        prices_dict: Dict[str, pd.DataFrame],
        state_sequence: np.ndarray,
        state_mapping: Dict[int, str],
        dates: pd.DatetimeIndex
    ) -> Dict[str, float]:
        """
        Calculate signal multipliers from historical regime performance.
        
        Logic: In each regime, what was the average forward return of a 
        momentum strategy (going long winners, short losers)?
        
        Multiplier = regime_sharpe / overall_sharpe (normalized)
        If momentum worked well in that regime, multiplier > 1.
        If poorly, multiplier < 1.
        """
        try:
            # Align all prices to dates
            all_prices = pd.DataFrame({
                sym: df.set_index('date')['close'] if 'date' in df.columns else df['close']
                for sym, df in prices_dict.items()
            })
            all_prices = all_prices.reindex(dates).dropna()
            
            if len(all_prices) != len(state_sequence):
                # Align lengths
                min_len = min(len(all_prices), len(state_sequence))
                all_prices = all_prices.iloc[-min_len:]
                state_sequence = state_sequence[-min_len:]
            
            # Calculate returns
            returns = all_prices.pct_change().dropna()
            
            # Calculate momentum signal: previous period return
            momentum_signal = returns.shift(1)  # Yesterday's return predicts today
            
            # Momentum strategy return: sum of (signal * return) across assets
            # Positive if winners kept winning, negative if they reversed
            strategy_returns = (momentum_signal * returns).mean(axis=1).dropna()
            
            # Align with state sequence
            min_len = min(len(strategy_returns), len(state_sequence))
            strategy_returns = strategy_returns.iloc[-min_len:]
            states_aligned = state_sequence[-min_len:]
            
            # Calculate performance by regime
            regime_performance = {}
            overall_mean = strategy_returns.mean()
            overall_std = strategy_returns.std() + 1e-9
            
            for state_idx, state_name in state_mapping.items():
                mask = states_aligned == state_idx
                if mask.sum() > 10:  # Need enough observations
                    regime_returns = strategy_returns[mask]
                    regime_mean = regime_returns.mean()
                    
                    # Multiplier: how much better/worse than overall?
                    # Centered around 1.0
                    if overall_mean != 0:
                        raw_mult = regime_mean / (overall_mean + 1e-9)
                        # Clip to reasonable range [0.2, 2.0]
                        multiplier = np.clip(raw_mult, 0.2, 2.0)
                    else:
                        multiplier = 1.0
                    
                    regime_performance[state_name] = round(float(multiplier), 3)
                else:
                    regime_performance[state_name] = 1.0  # Default if not enough data
            
            logger.info(f"[HMM] Calculated multipliers from data: {regime_performance}")
            return regime_performance
            
        except Exception as e:
            logger.warning(f"[HMM] Multiplier calculation failed: {e}, using defaults")
            # Fallback: return neutral multipliers
            return {name: 1.0 for name in state_mapping.values()}
    
    def _interpret_regime(self, regime: str, persistence: float, multiplier: float) -> str:
        """Generate human-readable interpretation based on calculated multiplier."""
        # Interpretation based on actual multiplier from data, not hardcoded
        if multiplier > 1.1:
            effectiveness = "Momentum signals are RELIABLE in this regime (historically profitable)."
        elif multiplier > 0.8:
            effectiveness = "Momentum signals are MODERATE in this regime (mixed results)."
        elif multiplier > 0.5:
            effectiveness = "Momentum signals are WEAK in this regime (often unprofitable)."
        else:
            effectiveness = "Momentum signals FAIL in this regime (consider fading)."
        
        base = f"Market is {regime}. {effectiveness} Multiplier: {multiplier:.2f}x"
        
        if persistence < 0.7:
            base += f" WARNING: Regime unstable ({persistence:.0%} persistence)—transition likely."
        
        return base


async def _fetch_data(server: FMPAlternativesServer, symbol: str, days: int = 120) -> Optional[pd.DataFrame]:
    """Fetch historical commodity data for momentum calculation using EOD (daily) data."""
    from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        result = await server.call_tool("get_commodities_data", {
            "symbol": symbol,
            "data_type": "historical",
            "timeframe": "eod",  # Daily data - much more efficient
            "from": from_date,
            "to": to_date
        })
        
        if not result or not hasattr(result, 'content'):
            return None
        
        data = safe_parse_json(result)
        if not data:
            return None
        
        historical_data = data.get('historical_data', data)
        
        if isinstance(historical_data, list) and len(historical_data) > 0:
            df = pd.DataFrame(historical_data)
            
            # Dynamic column detection
            date_col = next((c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()), df.columns[0])
            price_col = next((c for c in df.columns if c.lower() == 'close'),
                            next((c for c in df.columns if c.lower() in ['price', 'c']), None))
            if not price_col:
                price_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            
            df['date'] = pd.to_datetime(df[date_col])
            df['close'] = pd.to_numeric(df[price_col], errors='coerce')
            df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)
            return df[['date', 'close']]
        
        return None
    except Exception as e:
        logger.warning(f"Error fetching {symbol}: {e}")
        return None


def _calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate momentum metrics for a single commodity."""
    if len(df) < 20:
        return {}
    
    current = df['close'].iloc[-1]
    metrics = {'price': current}
    
    # ROC at different periods
    periods = {'1w': 5, '1m': 21, '3m': 63}
    for name, days in periods.items():
        if len(df) > days:
            past = df['close'].iloc[-days-1]
            metrics[f'roc_{name}'] = (current / past - 1) * 100
    
    # Moving averages
    if len(df) >= 20:
        sma20 = df['close'].rolling(20).mean().iloc[-1]
        metrics['vs_sma20'] = (current / sma20 - 1) * 100
    
    if len(df) >= 50:
        sma50 = df['close'].rolling(50).mean().iloc[-1]
        metrics['vs_sma50'] = (current / sma50 - 1) * 100
    
    # Trend strength: count MAs below price (0-2)
    ma_score = 0
    if 'vs_sma20' in metrics and metrics['vs_sma20'] > 0:
        ma_score += 1
    if 'vs_sma50' in metrics and metrics['vs_sma50'] > 0:
        ma_score += 1
    metrics['ma_trend'] = ma_score
    
    # Momentum acceleration
    if 'roc_1m' in metrics and 'roc_3m' in metrics:
        monthly_avg = metrics['roc_3m'] / 3
        metrics['acceleration'] = metrics['roc_1m'] - monthly_avg
    
    # Volatility
    if len(df) >= 21:
        returns = df['close'].pct_change().dropna()
        metrics['vol_1m'] = returns.tail(21).std() * np.sqrt(252) * 100
    
    return metrics


def _composite_score(metrics: Dict[str, float]) -> float:
    """
    Calculate composite momentum score using equal-weighted z-score normalization.
    No hardcoded weights - each available metric contributes equally.
    """
    components = []
    
    # Collect all available momentum signals
    if 'roc_1w' in metrics:
        components.append(metrics['roc_1w'])
    if 'roc_1m' in metrics:
        components.append(metrics['roc_1m'])
    if 'roc_3m' in metrics:
        components.append(metrics['roc_3m'])
    if 'vs_sma20' in metrics:
        components.append(metrics['vs_sma20'])
    if 'vs_sma50' in metrics:
        components.append(metrics['vs_sma50'])
    if 'acceleration' in metrics:
        components.append(metrics['acceleration'])
    
    # Equal-weighted average of available components
    return np.mean(components) if components else 0


def _classify_regime(score: float, all_scores: List[float]) -> Dict[str, Any]:
    """Classify momentum regime using z-score relative to universe."""
    if not all_scores:
        return {'regime': 'UNKNOWN', 'z_score': 0, 'percentile': 50}
    
    mean_s = np.mean(all_scores)
    std_s = np.std(all_scores) + 1e-9
    z = (score - mean_s) / std_s
    
    if z > 1.5:
        regime, signal = "STRONG_UPTREND", "BULLISH"
    elif z > 0.5:
        regime, signal = "UPTREND", "BULLISH"
    elif z > -0.5:
        regime, signal = "NEUTRAL", "NEUTRAL"
    elif z > -1.5:
        regime, signal = "DOWNTREND", "BEARISH"
    else:
        regime, signal = "STRONG_DOWNTREND", "BEARISH"
    
    pct = (sum(1 for s in all_scores if s < score) / len(all_scores)) * 100
    
    return {'regime': regime, 'signal': signal, 'z_score': round(z, 2), 'percentile': round(pct, 0)}


def _build_chart(rankings: List[Dict[str, Any]], chart_id: str = "commodity_momentum") -> Dict[str, Any]:
    """Build horizontal bar chart of momentum rankings."""
    import plotly.graph_objects as go
    
    rankings = sorted(rankings, key=lambda x: x.get('score', 0), reverse=True)
    
    symbols = [r['symbol'] for r in rankings]
    scores = [r.get('score', 0) for r in rankings]
    colors = ['#22c55e' if s > 0 else '#ef4444' for s in scores]
    
    fig = go.Figure(go.Bar(
        y=symbols, x=scores, orientation='h',
        marker_color=colors,
        text=[f'{s:+.1f}' for s in scores],
        textposition='outside'
    ))
    
    fig.add_vline(x=0, line_dash="dash", line_color="#9ca3af")
    
    fig.update_layout(
        title=dict(text="<b>Commodity Momentum Rankings</b>", font=dict(size=14)),
        xaxis_title="Momentum Score",
        yaxis=dict(autorange="reversed"),
        height=max(300, len(rankings) * 35),
        template='plotly_white',
        margin=dict(l=80, r=60, t=50, b=40)
    )
    
    # Return proper chart dict format for wrap_plotly_charts
    return {
        'id': chart_id,
        'title': 'Commodity Momentum Rankings',
        'plotly': fig.to_dict()
    }


def _format_table(rankings: List[Dict[str, Any]]) -> str:
    """Format rankings as markdown table."""
    # Check if we have regime-adjusted scores
    has_raw = any('raw_score' in r for r in rankings)
    
    if has_raw:
        rows = ["| Symbol | Score | Raw | 1W | 1M | 3M | Regime |",
                "|--------|-------|-----|-----|-----|-----|--------|"]
        
        for r in rankings:
            sym = r['symbol']
            score = r.get('score', 0)
            raw = r.get('raw_score', score)
            roc_1w = r.get('roc_1w', 0)
            roc_1m = r.get('roc_1m', 0)
            roc_3m = r.get('roc_3m', 0)
            regime = r.get('relative_regime', r.get('regime', 'N/A'))
            
            rows.append(f"| {sym} | {score:+.1f} | {raw:+.1f} | {roc_1w:+.1f}% | {roc_1m:+.1f}% | {roc_3m:+.1f}% | {regime} |")
    else:
        rows = ["| Symbol | Score | 1W | 1M | 3M | vs SMA50 | Regime |",
                "|--------|-------|-----|-----|-----|----------|--------|"]
        
        for r in rankings:
            sym = r['symbol']
            score = r.get('score', 0)
            roc_1w = r.get('roc_1w', 0)
            roc_1m = r.get('roc_1m', 0)
            roc_3m = r.get('roc_3m', 0)
            vs50 = r.get('vs_sma50', 0)
            regime = r.get('regime', 'N/A')
            
            rows.append(f"| {sym} | {score:+.1f} | {roc_1w:+.1f}% | {roc_1m:+.1f}% | {roc_3m:+.1f}% | {vs50:+.1f}% | {regime} |")
    
    return "\n".join(rows)


async def screen_commodity_momentum_internal(
    symbols_csv: str,
    lookback_days: int = 120,
    generate_chart: bool = True,
    detect_regime: bool = True,
    regime_window: int = 21,
    regime_multipliers: Optional[dict] = None
) -> dict:
    """
    Internal function for commodity momentum screening. Used by Canvas executor.
    
    Args:
        symbols_csv: Comma-separated FMP commodity symbols
        lookback_days: Days of history (default 120, max 365)
        generate_chart: Generate ranking chart
        detect_regime: Enable HMM regime detection
        regime_window: Rolling window for regime features
        regime_multipliers: Optional user-specified multipliers per regime
    
    Returns:
        Dict with rankings, leaders, laggards, market_breadth, regime_analysis, charts.
    """
    server = FMPAlternativesServer()
    
    try:
        await server.connect()
        
        # Parse symbols
        symbols = [s.strip().upper() for s in symbols_csv.split(',') if s.strip()]
        if not symbols:
            return {"error": "No symbols provided. Pass comma-separated symbols like GCUSD,SIUSD,CLUSD"}
        
        lookback_days = min(max(lookback_days, 30), 365)
        
        logger.info(f"[MOMENTUM] Screening {len(symbols)} commodities")
        
        results = []
        all_scores = []
        prices_dict = {}  # Store for regime detection
        
        for symbol in symbols:
            # ✅ CHECK CANCELLATION at each symbol iteration
            _check_cancellation(f"processing symbol {symbol}")
            
            df = await _fetch_data(server, symbol, lookback_days)
            
            # ✅ CHECK CANCELLATION after data fetch
            _check_cancellation(f"after fetching {symbol} data")
            
            if df is None or len(df) < 20:
                logger.warning(f"[MOMENTUM] Skipping {symbol} - insufficient data")
                continue
            
            # Store for regime detection
            prices_dict[symbol] = df.copy()
            
            metrics = _calculate_metrics(df)
            score = _composite_score(metrics)
            all_scores.append(score)
            
            results.append({
                'symbol': symbol,
                'price': round(metrics.get('price', 0), 2),
                'roc_1w': round(metrics.get('roc_1w', 0), 2),
                'roc_1m': round(metrics.get('roc_1m', 0), 2),
                'roc_3m': round(metrics.get('roc_3m', 0), 2),
                'vs_sma50': round(metrics.get('vs_sma50', 0), 2) if 'vs_sma50' in metrics else None,
                'ma_trend': metrics.get('ma_trend', 0),
                'acceleration': round(metrics.get('acceleration', 0), 2) if 'acceleration' in metrics else None,
                'vol_1m': round(metrics.get('vol_1m', 0), 1) if 'vol_1m' in metrics else None,
                'raw_score': round(score, 2),
                'score': round(score, 2)  # Will be adjusted if regime detection enabled
            })
        
        if not results:
            return {"error": "No valid data for any symbols", "symbols_attempted": symbols}
        
        # =================================================================
        # HMM REGIME DETECTION
        # =================================================================
        regime_analysis = None
        signal_multiplier = 1.0
        
        if detect_regime and len(prices_dict) >= 2:
            logger.info(f"[MOMENTUM] Running HMM regime detection on {len(prices_dict)} symbols")
            
            detector = MomentumRegimeDetector(n_states=3, user_multipliers=regime_multipliers)
            regime_result = detector.fit_predict(prices_dict, window=regime_window)
            
            if regime_result:
                regime_analysis = regime_result
                signal_multiplier = regime_result.get("signal_multiplier", 1.0)
                
                # Adjust all scores by regime multiplier
                for r in results:
                    r['score'] = round(r['raw_score'] * signal_multiplier, 2)
                
                # Re-sort by adjusted score
                all_scores = [r['score'] for r in results]
                
                logger.info(f"[MOMENTUM] Regime: {regime_result['current_regime']} "
                           f"(multiplier: {signal_multiplier})")
            else:
                logger.warning("[MOMENTUM] Regime detection failed, using raw scores")
        elif detect_regime and len(prices_dict) < 2:
            logger.warning("[MOMENTUM] Need at least 2 symbols for regime detection")
        
        # Add individual regime classification (relative to universe)
        for r in results:
            regime = _classify_regime(r['score'], all_scores)
            r['relative_regime'] = regime['regime']
            r['signal'] = regime['signal']
            r['z_score'] = regime['z_score']
            r['percentile'] = regime['percentile']
        
        # Sort by adjusted score
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Market breadth
        uptrend_count = sum(1 for r in results if r['score'] > 0)
        breadth_pct = (uptrend_count / len(results)) * 100
        
        if breadth_pct > 70:
            breadth_signal = "BROAD_BULLISH"
        elif breadth_pct > 50:
            breadth_signal = "LEAN_BULLISH"
        elif breadth_pct > 30:
            breadth_signal = "LEAN_BEARISH"
        else:
            breadth_signal = "BROAD_BEARISH"
        
        response = {
            "timestamp": datetime.now().isoformat(),
            "symbols_screened": len(results),
            "lookback_days": lookback_days,
            "rankings_table": _format_table(results),
            "rankings": results,
            "leaders": results[:3],
            "laggards": results[-3:] if len(results) >= 3 else results,
            "market_breadth": {
                "uptrend": uptrend_count,
                "downtrend": len(results) - uptrend_count,
                "breadth_pct": round(breadth_pct, 1),
                "signal": breadth_signal
            }
        }
        
        # Add regime analysis if available
        if regime_analysis:
            response["regime_analysis"] = {
                "enabled": True,
                "market_regime": regime_analysis["current_regime"],
                "regime_probability": round(regime_analysis["current_probability"], 3),
                "all_probabilities": {k: round(v, 3) for k, v in regime_analysis["all_probabilities"].items()},
                "regime_stability": regime_analysis["regime_stability"],
                "regime_persistence": round(regime_analysis["regime_persistence"], 3),
                "signal_multiplier": round(signal_multiplier, 3),
                "all_multipliers": regime_analysis.get("all_multipliers", {}),
                "multiplier_source": regime_analysis.get("multiplier_source", "unknown"),
                "transition_forecast": {k: round(v, 3) for k, v in regime_analysis["transition_forecast"].items()},
                "interpretation": regime_analysis["interpretation"],
                "scores_adjusted": True
            }
        else:
            response["regime_analysis"] = {
                "enabled": detect_regime,
                "market_regime": None,
                "reason": "Insufficient data or hmmlearn not installed" if detect_regime else "Disabled",
                "scores_adjusted": False
            }
        
        if generate_chart:
            chart = _build_chart(results, chart_id="commodity_momentum_screener")
            response["charts"] = wrap_plotly_charts([chart], default_type="momentum")
        
        return response
    
    except asyncio.CancelledError:
        logger.info("[CANCEL] Commodity momentum screening cancelled by user")
        raise  # Re-raise to propagate cancellation
    except Exception as e:
        logger.error(f"Momentum screening failed: {e}", exc_info=True)
        return {"error": str(e), "error_type": type(e).__name__}
    finally:
        await server.cleanup()


@function_tool(strict_mode=False)  # Uses Optional[dict] for regime_multipliers
async def screen_commodity_momentum(
    symbols_csv: str,
    lookback_days: int = 120,
    generate_chart: bool = True,
    detect_regime: bool = True,
    regime_window: int = 21,
    regime_multipliers: Optional[dict] = None
) -> dict:
    """
    Screen and rank commodities by momentum with optional HMM regime detection.
    
    The regime detector uses a Hidden Markov Model to identify whether the
    market is TRENDING (momentum works), CHOPPY (signals unreliable), or
    MEAN_REVERTING (fade signals). It uses ONLY the price data you provide—
    no external data sources or hardcoded values.
    
    When regime detection is enabled:
    - Scores are adjusted by a regime multiplier
    - Multipliers are CALCULATED FROM THE DATA: how well did momentum 
      actually perform in each detected regime historically?
    - Or you can specify your own multipliers via regime_multipliers param.
    
    Args:
        symbols_csv: Comma-separated FMP commodity symbols 
                     (e.g., "GCUSD,SIUSD,CLUSD,NGUSD,HGUSD,BZUSD")
        lookback_days: Days of history (default 120, max 365)
        generate_chart: Generate ranking chart
        detect_regime: Enable HMM regime detection (default True)
                      Requires hmmlearn package and at least 2 symbols.
        regime_window: Rolling window for regime feature calculation (default 21 days)
        regime_multipliers: Optional user-specified multipliers per regime.
                           If not provided, calculated from historical performance.
                           Example: {"TRENDING": 1.5, "CHOPPY": 0.5, "MEAN_REVERTING": 0.3}
    
    Returns:
        - rankings_table: Markdown table sorted by momentum score
        - rankings: Full ranking details with raw and regime-adjusted scores
        - leaders: Top performers
        - laggards: Bottom performers
        - market_breadth: % in uptrend
        - regime_analysis: HMM regime detection results (if enabled)
          - includes calculated multipliers and their source
        - chart: Momentum ranking visualization
    
    Example:
        # Basic momentum screening (multipliers calculated from data)
        screen_commodity_momentum(symbols_csv="GCUSD,SIUSD,CLUSD,NGUSD,HGUSD")
        
        # With custom multipliers
        screen_commodity_momentum(
            symbols_csv="GCUSD,SIUSD,CLUSD,NGUSD,HGUSD",
            regime_multipliers={"TRENDING": 1.3, "CHOPPY": 0.4, "MEAN_REVERTING": 0.2}
        )
        
        # Disable regime detection for simple screening
        screen_commodity_momentum(
            symbols_csv="GCUSD,SIUSD",
            detect_regime=False
        )
    """
    return await screen_commodity_momentum_internal(
        symbols_csv=symbols_csv,
        lookback_days=lookback_days,
        generate_chart=generate_chart,
        detect_regime=detect_regime,
        regime_window=regime_window,
        regime_multipliers=regime_multipliers
    )
