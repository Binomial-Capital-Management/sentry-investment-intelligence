"""
Unit tests for Quiver Quant MCP server live routing.
"""

import json
import json as jsonlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.mcp_servers.quiver import QuiverDataFetcher, QuiverQuantServer, QuiverTierError
from core.mcp_servers.quiver.quiver_fetcher import normalize_quiver_payload
from core.mcp_servers.quiver.quiver_registry import implemented_quiver_paths


def _content_text(result) -> str:
    item = result.content[0]
    return item["text"] if isinstance(item, dict) else item.text


class TestQuiverDataFetcher:
    def test_parse_response_text_json_array(self):
        payload = QuiverDataFetcher.parse_response_text('[{"Ticker":"AAPL"}]', 200)
        assert isinstance(payload, list)
        assert payload[0]["Ticker"] == "AAPL"

    def test_parse_response_text_empty_body(self):
        payload = QuiverDataFetcher.parse_response_text("", 200)
        assert payload == []

    def test_parse_response_text_tier_error(self):
        with pytest.raises(QuiverTierError, match="Upgrade your subscription plan"):
            QuiverDataFetcher.parse_response_text("Upgrade your subscription plan to access this dataset.", 200)

    def test_normalize_congress_payload_coerces_numbers_and_dates(self):
        payload = [{
            "Representative": "Tina Smith",
            "ReportDate": "2026-04-02",
            "TransactionDate": "2026-03-31",
            "Amount": "50001.0",
            "ExcessReturn": "-1.43369192478229",
            "PriceChange": "-0.523307856503471",
            "SPYChange": "0.910384068278814",
        }]
        normalized = normalize_quiver_payload("congresstrading", payload)
        row = normalized[0]
        assert isinstance(row["Amount"], float)
        assert isinstance(row["ExcessReturn"], float)
        assert row["ReportDate"] == "2026-04-02"
        assert row["TransactionDate"] == "2026-03-31"

    def test_normalize_insider_payload_coerces_datetime_and_numbers(self):
        payload = [{
            "Ticker": "UBFO",
            "Date": "2026-04-01T00:00:00.000",
            "Shares": 95733.0,
            "PricePerShare": 10.51,
            "SharesOwnedFollowing": 0.0,
            "fileDate": "2026-04-04T01:40:32.000",
            "uploaded": "2026-04-05T03:30:48.843",
        }]
        normalized = normalize_quiver_payload("insiders", payload)
        row = normalized[0]
        assert row["Date"] == "2026-04-01T00:00:00"
        assert row["fileDate"] == "2026-04-04T01:40:32"
        assert row["uploaded"] == "2026-04-05T03:30:48"
        assert isinstance(row["Shares"], float)

    def test_normalize_offexchange_payload_coerces_integer_fields(self):
        payload = [{
            "Ticker": "GV",
            "Date": "2026-04-02",
            "OTC_Short": 162477415,
            "OTC_Total": "318924146",
            "DPI": "0.509454731663685",
        }]
        normalized = normalize_quiver_payload("offexchange", payload)
        row = normalized[0]
        assert isinstance(row["OTC_Short"], int)
        assert isinstance(row["OTC_Total"], int)
        assert isinstance(row["DPI"], float)
        assert row["Date"] == "2026-04-02"


class TestQuiverQuantServer:
    def test_server_import(self):
        assert QuiverQuantServer is not None

    def test_server_tool_names(self):
        server = QuiverQuantServer.__new__(QuiverQuantServer)
        tools = server._get_tools()
        tool_names = {tool.name for tool in tools}
        expected = {
            "get_congress_trading",
            "get_political_activity",
            "get_government_contracts",
            "get_quiver_insider_trading",
            "get_institutional_holdings",
            "get_social_sentiment",
            "get_alternative_signals",
            "get_quiver_strategies",
            "get_quiver_reference_data",
            "get_quiver_mobile_data",
            "list_quiver_datasets",
        }
        assert tool_names == expected

    def test_tools_have_object_input_schemas(self):
        server = QuiverQuantServer.__new__(QuiverQuantServer)
        for tool in server._get_tools():
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema

    def test_tools_have_detailed_descriptions(self):
        server = QuiverQuantServer.__new__(QuiverQuantServer)
        for tool in server._get_tools():
            assert tool.description
            assert len(tool.description) > 120

    def test_registry_covers_all_documented_get_data_paths(self):
        spec_path = Path("docs/quiver_openapi_schema.json")
        if not spec_path.exists():
            pytest.skip("Quiver OpenAPI spec not bundled (vendor ToS); export it from api.quiverquant.com/docs to run")
        spec = jsonlib.loads(spec_path.read_text())
        documented = set()
        for path, item in spec.get("paths", {}).items():
            if not path.startswith("/beta/"):
                continue
            if path.startswith("/beta/token/"):
                continue
            if path.startswith("/beta/auth/"):
                continue
            if path.startswith("/beta/api/v1/"):
                continue
            if "get" not in item:
                continue
            documented.add(path)

        missing = documented - implemented_quiver_paths()
        assert not missing, f"Missing Quiver paths from registry: {sorted(missing)}"

    def test_server_name_property(self):
        server = QuiverQuantServer.__new__(QuiverQuantServer)
        server._name = "QuiverQuantServer"
        assert server.name == "QuiverQuantServer"

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        server = QuiverQuantServer.__new__(QuiverQuantServer)
        result = await server.call_tool("unknown_tool", {})
        assert result.isError is True
        assert "unknown_tool" in _content_text(result)

    @pytest.mark.asyncio
    async def test_get_congress_trading_live_routes_to_congresstrading(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "AAPL"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            result = await server.call_tool("get_congress_trading", {})

        assert result.isError is False
        server.data_fetcher.fetch.assert_awaited_once_with("/beta/live/congresstrading", params={})
        payload = json.loads(_content_text(result))
        assert payload["dataset"] == "congresstrading"
        assert payload["mode"] == "live"

    @pytest.mark.asyncio
    async def test_get_congress_trading_live_routes_to_senate(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "AAPL"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_congress_trading", {"chamber": "senate"})

        server.data_fetcher.fetch.assert_awaited_once_with("/beta/live/senatetrading", params={})

    @pytest.mark.asyncio
    async def test_get_congress_politicians_live_routes_correctly(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Name": "Jane Doe"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_congress_trading", {"dataset": "politicians", "party": "Republican"})

        server.data_fetcher.fetch.assert_awaited_once_with(
            "/beta/live/congress/politicians",
            params={"party": "Republican"},
        )

    @pytest.mark.asyncio
    async def test_get_government_contracts_live_routes_all_contracts(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "LMT"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_government_contracts", {"include_modifications": True, "date": "20260405"})

        server.data_fetcher.fetch.assert_awaited_once_with(
            "/beta/live/govcontractsall",
            params={"date": "20260405"},
        )

    @pytest.mark.asyncio
    async def test_get_quiver_insider_trading_live_routes_with_filters(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "NVDA"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_quiver_insider_trading", {"ticker": "NVDA", "uploaded": "20260404"})

        server.data_fetcher.fetch.assert_awaited_once_with(
            "/beta/live/insiders",
            params={"ticker": "NVDA", "uploaded": "20260404"},
        )

    @pytest.mark.asyncio
    async def test_get_social_sentiment_live_routes_wsb_comments(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "TSLA"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_social_sentiment", {"source": "wsb", "detail_level": "comments"})

        server.data_fetcher.fetch.assert_awaited_once_with("/beta/live/wsbcomments", params={})

    @pytest.mark.asyncio
    async def test_get_social_sentiment_routes_spaccomments(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "DWAC"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_social_sentiment", {"source": "spacs", "detail_level": "comments"})

        server.data_fetcher.fetch.assert_awaited_once_with("/beta/live/spaccomments", params={})

    @pytest.mark.asyncio
    async def test_get_alternative_signals_live_routes_offexchange(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "AMD"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_alternative_signals", {"signal": "off_exchange", "date": "20260404"})

        server.data_fetcher.fetch.assert_awaited_once_with(
            "/beta/live/offexchange",
            params={"date": "20260404"},
        )

    @pytest.mark.asyncio
    async def test_get_quiver_strategies_live_routes_infrequent(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Strategy": "alpha"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_quiver_strategies", {"rebalance_frequency": "infrequent"})

        server.data_fetcher.fetch.assert_awaited_once_with("/beta/strategies/holdings_infrequent", params={})

    @pytest.mark.asyncio
    async def test_get_quiver_reference_data_live_routes_tickerdata(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value=[{"Ticker": "META"}])

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool("get_quiver_reference_data", {"dataset": "tickerdata"})

        server.data_fetcher.fetch.assert_awaited_once_with("/beta/tickerdata", params={})

    @pytest.mark.asyncio
    async def test_get_quiver_mobile_data_routes_profile_endpoint(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(return_value={"name": "Jane Doe"})

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            await server.call_tool(
                "get_quiver_mobile_data",
                {"dataset": "congress_politician_profile", "bioguide_id": "P000197"},
            )

        server.data_fetcher.fetch.assert_awaited_once_with(
            "/beta/mobile/congress/politicians/P000197",
            params={},
        )

    @pytest.mark.asyncio
    async def test_list_quiver_datasets_succeeds(self):
        server = QuiverQuantServer(api_key="test")

        with patch("core.agents.binomial_hash.bh_ingest", side_effect=lambda raw, label: raw):
            result = await server.call_tool("list_quiver_datasets", {})

        assert result.isError is False
        payload = json.loads(_content_text(result))
        assert "datasets" in payload
        assert any(entry["dataset"] == "congresstrading" for entry in payload["datasets"])

    @pytest.mark.asyncio
    async def test_tier_error_returns_mcp_error(self):
        server = QuiverQuantServer(api_key="test")
        server.data_fetcher.fetch = AsyncMock(side_effect=QuiverTierError("Upgrade your subscription plan to access this dataset."))

        result = await server.call_tool("get_quiver_strategies", {})

        assert result.isError is True
        error_payload = json.loads(_content_text(result))
        assert error_payload["error"] == "tier_error"
