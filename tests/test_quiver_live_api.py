"""
Live Quiver Quant API smoke tests.

These are intentionally separate from the mocked unit suite. Run them manually:

    PYTHONPATH=. pytest tests/test_quiver_live_api.py -q -s
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from core.mcp_servers.quiver.quiver_fetcher import QuiverDataFetcher


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _print_preview(title: str, payload):
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)
    print(f"type: {type(payload).__name__}")
    if isinstance(payload, list):
        print(f"rows: {len(payload)}")
        if payload:
            first = payload[0]
            print(f"first keys: {sorted(first.keys())[:15]}")
            print(f"first row: {first}")
    else:
        print(payload)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("QUIVER_API_KEY"), reason="QUIVER_API_KEY not set")
async def test_live_congress_trading():
    fetcher = QuiverDataFetcher(os.environ["QUIVER_API_KEY"])
    try:
        await fetcher.connect()
        payload = await fetcher.fetch("/beta/live/congresstrading", {"page_size": 5})
        _print_preview("Live Congress Trading", payload)
        assert isinstance(payload, list)
        assert len(payload) > 0
    finally:
        await fetcher.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("QUIVER_API_KEY"), reason="QUIVER_API_KEY not set")
async def test_live_insiders():
    fetcher = QuiverDataFetcher(os.environ["QUIVER_API_KEY"])
    try:
        await fetcher.connect()
        payload = await fetcher.fetch("/beta/live/insiders", {"page_size": 5})
        _print_preview("Live Insider Trading", payload)
        assert isinstance(payload, list)
        assert len(payload) > 0
    finally:
        await fetcher.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("QUIVER_API_KEY"), reason="QUIVER_API_KEY not set")
async def test_live_offexchange():
    fetcher = QuiverDataFetcher(os.environ["QUIVER_API_KEY"])
    try:
        await fetcher.connect()
        payload = await fetcher.fetch("/beta/live/offexchange", {"page_size": 5})
        _print_preview("Live Off-Exchange", payload)
        assert isinstance(payload, list)
        assert len(payload) > 0
    finally:
        await fetcher.cleanup()
