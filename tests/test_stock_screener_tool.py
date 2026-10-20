import pytest

from core.mcp_servers.fmp.FMPMarketDataServer import FMPMarketDataServer


class DummyFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def fetch_dataset(self, symbol, dataset, historical_params=None):
        self.calls.append(
            {
                "symbol": symbol,
                "dataset": dataset.dataset if hasattr(dataset, "dataset") else dataset,
                "params": historical_params or {},
            }
        )
        return self.payload


@pytest.mark.asyncio
async def test_run_stock_screener_passes_additional_filters(monkeypatch):
    server = FMPMarketDataServer(api_key="test-key")
    fetcher = DummyFetcher(
        [
            {"symbol": "AAA", "marketCap": 5_000_000_000},
            {"symbol": "BBB", "marketCap": 4_000_000_000},
        ]
    )
    server.data_fetcher = fetcher

    result = await server._handle_run_stock_screener(
        {
            "limit": 1,
            "sort_by": "marketCap",
            "order": "desc",
            "filters": {
                "sector": "Energy",
                "volumeLowerThan": 1_000_000,
                "isEtf": False,
            },
        }
    )

    assert result["result_count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["symbol"] == "AAA"
    assert result["raw"] == fetcher.payload

    call = fetcher.calls[0]
    assert call["symbol"] == ""
    assert call["dataset"] == "stock-screener"
    # Should include every filter we set, even ones missing from params_schema
    assert call["params"]["sector"] == "Energy"
    assert call["params"]["volumeLowerThan"] == 1_000_000
    assert call["params"]["isEtf"] == "false"  # booleans lowercased
    assert call["params"]["sort"] == "marketCap"
    assert call["params"]["order"] == "desc"


@pytest.mark.asyncio
async def test_run_stock_screener_can_skip_raw_payload(monkeypatch):
    server = FMPMarketDataServer(api_key="test-key")
    fetcher = DummyFetcher({"data": [{"symbol": "XYZ"}, {"symbol": "QWE"}]})
    server.data_fetcher = fetcher

    result = await server._handle_run_stock_screener(
        {
            "filters": {"industry": "Utilities"},
            "limit": 2,
            "include_raw": False,
        }
    )

    assert "raw" not in result
    assert result["result_count"] == 2
    assert result["results"] == fetcher.payload["data"]
    assert fetcher.calls[0]["params"]["industry"] == "Utilities"


@pytest.mark.asyncio
async def test_run_stock_screener_ignores_reserved_filters(monkeypatch):
    server = FMPMarketDataServer(api_key="primary-key")
    fetcher = DummyFetcher([{"symbol": "AAA"}])
    server.data_fetcher = fetcher

    await server._handle_run_stock_screener(
        {
            "filters": {
                "apikey": "malicious",
                "sector": "Energy",
            }
        }
    )

    params = fetcher.calls[0]["params"]
    assert "apikey" not in params  # stripped in handler


@pytest.mark.asyncio
async def test_run_stock_screener_supports_comparison_dict(monkeypatch):
    server = FMPMarketDataServer(api_key="test-key")
    fetcher = DummyFetcher([{"symbol": "AAA"}])
    server.data_fetcher = fetcher

    await server._handle_run_stock_screener(
        {
            "filters": {
                "marketCap": {"isLessThan": 10_000_000_000},
                "pe": {"isGreaterThan": 5},
                "beta": {"equals": 1},
            }
        }
    )

    params = fetcher.calls[0]["params"]
    assert params["marketCapIsLessThan"] == 10_000_000_000
    assert params["peIsGreaterThan"] == 5
    assert params["betaEquals"] == 1
