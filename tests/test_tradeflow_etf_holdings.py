import pytest

from core.mcp_servers.fmp.FMPTradeFlowServer import FMPTradeFlowServer


class DummyFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.params_seen = []

    async def fetch_dataset(self, symbol, dataset, historical_params=None):
        page = historical_params.get("page", 0) if historical_params else 0
        self.calls.append(page)
        self.params_seen.append(historical_params)
        return self.pages.get(page, [])


@pytest.mark.asyncio
async def test_get_etf_holdings_auto_paginates(monkeypatch):
    server = FMPTradeFlowServer(api_key="test-key")
    fetcher = DummyFetcher(
        {
            0: [{"symbol": "AAA"}, {"symbol": "BBB"}],
            1: [{"symbol": "CCC"}],
        }
    )
    server.data_fetcher = fetcher

    result = await server._handle_get_etf_holdings(
        {
            "symbol": "SPY",
            "limit": 2,
        }
    )

    assert result["etf_symbol"] == "SPY"
    assert len(result["holdings"]) == 3
    assert result["pagination"]["pages_fetched"] == 2
    assert fetcher.calls == [0, 1]
    assert fetcher.params_seen[0]["size"] == 2


@pytest.mark.asyncio
async def test_get_etf_holdings_respects_max_results(monkeypatch):
    server = FMPTradeFlowServer(api_key="test-key")
    fetcher = DummyFetcher(
        {
            0: [{"symbol": "AAA"}, {"symbol": "BBB"}],
            1: [{"symbol": "CCC"}, {"symbol": "DDD"}],
        }
    )
    server.data_fetcher = fetcher

    result = await server._handle_get_etf_holdings(
        {
            "symbol": "QQQ",
            "limit": 2,
            "max_results": 3,
        }
    )

    assert len(result["holdings"]) == 3
    assert result["pagination"]["returned"] == 3
    assert result["pagination"]["pages_fetched"] == 2
