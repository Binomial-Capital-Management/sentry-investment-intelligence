"""
Synthetic order-book stress-test tool for BinomialHash + manifold pipeline.

Generates ~25,000 L2 order-book snapshots across 8 liquid tickers with
5 hidden tradeable signals planted structurally in future_mid_move_5s.

Temporary tool: gated behind the HOTSAUCE activation phrase.

Planted signals (what the agent should discover):
  1. Imbalance alpha — imbalance > 0.68 AND book_pressure > 0.60 → positive drift
  2. Spread compression breakout — spread < 0.02 AND volume spike → directional move
  3. Toxic venue — EDGX fills during high activity mean-revert (adverse selection)
  4. Cross-asset lead-lag — SPY imbalance leads QQQ by ~200ms
  5. Volatility regime break — signals flip sign when realized_vol_1m > 0.035
"""

import json
import math
import random
from typing import Dict, List

from agents import function_tool

from core.agents.binomial_hash import bh_ingest


_TICKERS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "META", "MSFT"]
_VENUES = ["ARCA", "BATS", "EDGX", "NYSE", "NSDQ", "IEX"]
_SIDES = ["buy", "sell"]

_BASE_PRICES = {
    "SPY": 520.0, "QQQ": 440.0, "AAPL": 195.0, "TSLA": 260.0,
    "NVDA": 880.0, "AMZN": 185.0, "META": 500.0, "MSFT": 420.0,
}

_SNAPSHOTS_PER_TICKER = 3000


def _generate_orderbook_rows(seed: int = 42) -> List[Dict]:
    rng = random.Random(seed)
    rows: List[Dict] = []

    spy_imbalance_history: List[float] = []

    for ticker in _TICKERS:
        base = _BASE_PRICES[ticker]
        for snap_i in range(_SNAPSHOTS_PER_TICKER):
            ts_ms = 1_700_000_000_000 + snap_i * 100 + _TICKERS.index(ticker) * 50

            drift = math.sin(snap_i * 0.002) * 0.3
            noise = rng.gauss(0, 0.15)
            mid = round(base + drift + noise, 4)

            raw_spread = abs(rng.gauss(0.03, 0.015))
            spread = round(max(0.01, raw_spread), 4)
            bid = round(mid - spread / 2, 4)
            ask = round(mid + spread / 2, 4)

            bid_size_l1 = max(10, int(rng.gauss(300, 120)))
            ask_size_l1 = max(10, int(rng.gauss(300, 120)))
            bid_depth_5 = bid_size_l1 + max(0, int(rng.gauss(800, 300)))
            ask_depth_5 = ask_size_l1 + max(0, int(rng.gauss(800, 300)))

            total_l1 = bid_size_l1 + ask_size_l1
            imbalance = round(bid_size_l1 / total_l1, 6) if total_l1 > 0 else 0.5
            total_d5 = bid_depth_5 + ask_depth_5
            book_pressure = round(bid_depth_5 / total_d5, 6) if total_d5 > 0 else 0.5

            trade_vol = max(0, int(rng.gauss(400, 250)))
            trade_count = max(0, int(rng.gauss(8, 5)))
            venue = rng.choice(_VENUES)
            last_side = rng.choice(_SIDES)
            vwap_dev = round(rng.gauss(0, 0.04), 6)
            rvol = round(abs(rng.gauss(0.022, 0.012)), 6)

            # ── base random future move ──
            future_move = rng.gauss(0, 0.008)

            # ── SIGNAL 1: imbalance alpha ──
            if imbalance > 0.68 and book_pressure > 0.60:
                future_move += 0.015

            # ── SIGNAL 2: spread compression breakout ──
            if spread < 0.02 and trade_vol > 800:
                direction = 1.0 if last_side == "buy" else -1.0
                future_move += 0.025 * direction

            # ── SIGNAL 3: toxic venue (EDGX adverse selection) ──
            if venue == "EDGX" and trade_count > 15:
                revert = -1.0 if last_side == "buy" else 1.0
                future_move += 0.012 * revert

            # ── SIGNAL 4: cross-asset lead-lag (SPY → QQQ) ──
            if ticker == "SPY":
                spy_imbalance_history.append(imbalance)
            if ticker == "QQQ" and len(spy_imbalance_history) > 2:
                lagged_spy_imb = spy_imbalance_history[
                    min(snap_i, len(spy_imbalance_history) - 1)
                ]
                if lagged_spy_imb > 0.65:
                    future_move += 0.010

            # ── SIGNAL 5: volatility regime break ──
            high_vol = rvol > 0.035
            if high_vol:
                future_move *= -1.2

            future_move = round(future_move, 6)

            rows.append({
                "ticker": ticker,
                "timestamp_ms": ts_ms,
                "bid_price": bid,
                "ask_price": ask,
                "mid_price": mid,
                "spread": spread,
                "bid_size_l1": bid_size_l1,
                "ask_size_l1": ask_size_l1,
                "bid_depth_5": bid_depth_5,
                "ask_depth_5": ask_depth_5,
                "imbalance": imbalance,
                "book_pressure": book_pressure,
                "trade_volume_last_1s": trade_vol,
                "trade_count_last_1s": trade_count,
                "venue": venue,
                "last_trade_side": last_side,
                "vwap_deviation": vwap_dev,
                "realized_vol_1m": rvol,
                "future_mid_move_5s": future_move,
            })

    return rows


@function_tool
async def hotsauce_test_bh(activation_phrase: str) -> str:
    """Generate a synthetic L2 order-book dataset and ingest into BinomialHash.

    This tool is gated and should only run when activation_phrase is exactly
    "HOTSAUCE".

    Output:
      - Returns the BH compact summary string for the generated dataset.
      - Dataset contains ~24,000 order-book snapshots across 8 liquid tickers.
      - 5 tradeable signals are hidden in the future_mid_move_5s column.

    Args:
        activation_phrase: Must be "HOTSAUCE".
    """
    if activation_phrase != "HOTSAUCE":
        return json.dumps(
            {"error": "Tool disabled unless activation phrase is exactly 'HOTSAUCE'."}
        )

    rows = _generate_orderbook_rows(seed=20260223)
    payload = json.dumps({"orderbook_snapshots": rows})
    summary = bh_ingest(payload, "hotsauce_test_bh")
    return summary
