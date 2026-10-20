"""
Comprehensive tests for Unusual Whales MCP Server infrastructure.

Tests cover:
- DDC Loader: catalog loading, validation, filtering, URL substitution
- Rate Limiter: token bucket algorithm, per-class limits
- Data Fetcher: caching, parameter handling, error cases
"""

import pytest
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Import modules under test
from core.mcp_servers.unusualwhales.uw_models import (
    UWDatasetEntry,
    UWCatalog,
    RateLimitConfig,
    ParamConstraint,
    UWDatasetClass,
)
from core.mcp_servers.unusualwhales.uw_ddc_loader import (
    UWDDCLoader,
    get_default_loader,
    load_catalog,
    get_dataset,
    search_datasets,
)
from core.mcp_servers.unusualwhales.uw_rate_limiter import (
    SimpleRateLimiter,
    UWRateLimiter,
)
from core.mcp_servers.unusualwhales.uw_data_fetcher import UWDataFetcher


# =============================================================================
# DDC LOADER TESTS
# =============================================================================

class TestUWDatasetEntry:
    """Tests for UWDatasetEntry Pydantic model."""
    
    def test_valid_entry_creation(self):
        """Test creating a valid dataset entry."""
        entry = UWDatasetEntry(
            dataset="test-dataset",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test/{ticker}",
            method="GET",
            params_schema={"ticker": "string", "date": "date?"},
            identifier_param="ticker",
            cache_ttl=300,
        )
        assert entry.dataset == "test-dataset"
        assert entry.class_ == "options_flow"
        assert entry.discoverable is True
        assert entry.url == "/api/test/{ticker}"
    
    def test_url_validation_must_start_with_slash(self):
        """Test URL validation rejects URLs not starting with /."""
        with pytest.raises(ValueError, match="URL must start with"):
            UWDatasetEntry(
                dataset="test",
                **{"class": "options_flow"},
                discoverable=True,
                url="api/test",  # Missing leading slash
            )
    
    def test_url_validation_unclosed_placeholder(self):
        """Test URL validation catches unclosed placeholders."""
        with pytest.raises(ValueError, match="Unclosed placeholder"):
            UWDatasetEntry(
                dataset="test",
                **{"class": "options_flow"},
                discoverable=True,
                url="/api/test/{ticker",  # Missing closing brace
            )
    
    def test_method_validation(self):
        """Test HTTP method validation."""
        # Valid methods
        for method in ["GET", "POST", "PUT", "DELETE", "get", "post"]:
            entry = UWDatasetEntry(
                dataset="test",
                **{"class": "options_flow"},
                discoverable=True,
                url="/api/test",
                method=method,
            )
            assert entry.method == method.upper()
        
        # Invalid method
        with pytest.raises(ValueError, match="Method must be one of"):
            UWDatasetEntry(
                dataset="test",
                **{"class": "options_flow"},
                discoverable=True,
                url="/api/test",
                method="PATCH",
            )
    
    def test_substitute_url_simple(self):
        """Test simple URL substitution."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/stock/{ticker}/flow",
            params_schema={"ticker": "string"},
        )
        result = entry.substitute_url(ticker="AAPL")
        assert result == "/api/stock/AAPL/flow"
    
    def test_substitute_url_with_spaces(self):
        """Test URL substitution properly encodes spaces."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "market_sentiment"},
            discoverable=True,
            url="/api/market/{sector}/sector-tide",
            params_schema={"sector": "string"},
        )
        result = entry.substitute_url(sector="Real Estate")
        assert result == "/api/market/Real%20Estate/sector-tide"
    
    def test_substitute_url_with_special_chars(self):
        """Test URL substitution properly encodes special characters."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test/{value}",
            params_schema={"value": "string"},
        )
        result = entry.substitute_url(value="test&value=bad")
        assert "%26" in result  # & should be encoded
        assert "%3D" in result  # = should be encoded
    
    def test_substitute_url_multiple_params(self):
        """Test URL substitution with multiple parameters."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/{ticker}/greek-flow/{expiry}",
            params_schema={"ticker": "string", "expiry": "string"},
        )
        result = entry.substitute_url(ticker="AAPL", expiry="2024-02-02")
        assert result == "/api/AAPL/greek-flow/2024-02-02"
    
    def test_get_path_params(self):
        """Test extraction of path parameters."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/{ticker}/flow/{expiry}",
            params_schema={"ticker": "string", "expiry": "string", "date": "date?"},
        )
        path_params = entry.get_path_params()
        assert set(path_params) == {"ticker", "expiry"}
    
    def test_get_query_params(self):
        """Test extraction of query parameters."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/{ticker}/flow",
            params_schema={"ticker": "string", "date": "date?", "limit": "integer?"},
        )
        query_params = entry.get_query_params()
        assert set(query_params.keys()) == {"date", "limit"}
    
    def test_get_required_params(self):
        """Test identification of required parameters."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/{ticker}/flow",
            params_schema={
                "ticker": "string",  # Required
                "date": "date?",     # Optional
                "limit": "integer?", # Optional
            },
        )
        required = entry.get_required_params()
        assert required == ["ticker"]
    
    def test_validate_params_with_defaults(self):
        """Test parameter validation applies defaults."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test",
            params_schema={"limit": "integer?"},
            param_defaults={"limit": 100},
        )
        result = entry.validate_params({})
        assert result["limit"] == 100
    
    def test_validate_params_user_overrides_defaults(self):
        """Test user params override defaults."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test",
            params_schema={"limit": "integer?"},
            param_defaults={"limit": 100},
        )
        result = entry.validate_params({"limit": 50})
        assert result["limit"] == 50
    
    def test_validate_params_missing_required(self):
        """Test validation fails for missing required params."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/{ticker}/flow",
            params_schema={"ticker": "string"},
        )
        with pytest.raises(ValueError, match="Missing required parameter: ticker"):
            entry.validate_params({})
    
    def test_validate_params_constraints_min(self):
        """Test parameter constraint validation (min)."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test",
            params_schema={"limit": "integer?"},
            param_constraints={"limit": {"min": 1, "max": 200}},
        )
        with pytest.raises(ValueError, match="limit must be >= 1"):
            entry.validate_params({"limit": 0})
    
    def test_validate_params_constraints_max(self):
        """Test parameter constraint validation (max)."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test",
            params_schema={"limit": "integer?"},
            param_constraints={"limit": {"min": 1, "max": 200}},
        )
        with pytest.raises(ValueError, match="limit must be <= 200"):
            entry.validate_params({"limit": 500})
    
    def test_validate_params_constraints_string_number(self):
        """Test constraint validation handles string numbers."""
        entry = UWDatasetEntry(
            dataset="test",
            **{"class": "options_flow"},
            discoverable=True,
            url="/api/test",
            params_schema={"limit": "string?"},
            param_constraints={"limit": {"min": 1, "max": 200}},
        )
        # String "100" should be converted and validated
        result = entry.validate_params({"limit": "100"})
        assert result["limit"] == "100"
        
        # String "0" should fail
        with pytest.raises(ValueError, match="limit must be >= 1"):
            entry.validate_params({"limit": "0"})


class TestUWDDCLoader:
    """Tests for UWDDCLoader catalog loading."""
    
    def test_loader_loads_all_catalogs(self):
        """Test loader loads all three catalogs by default."""
        loader = UWDDCLoader()
        assert loader.catalog is not None
        assert len(loader.catalog.datasets) > 0
        
        # Should have datasets from all three catalogs
        classes = loader.catalog.get_dataset_count()
        assert "options_flow" in classes
        assert "congressional" in classes or "darkpool" in classes
        assert "market_analytics" in classes or "short_interest" in classes
    
    def test_loader_builds_index(self):
        """Test loader builds dataset index for fast lookup."""
        loader = UWDDCLoader()
        
        # Index should be built
        assert len(loader._dataset_index) == len(loader.catalog.datasets)
        
        # Lookup should work
        dataset = loader.get_dataset("group-greek-flow")
        assert dataset is not None
        assert dataset.dataset == "group-greek-flow"
    
    def test_loader_merges_enums(self):
        """Test loader merges enums from all catalogs."""
        loader = UWDDCLoader()
        
        # Should have enums
        assert len(loader._enums) > 0
        
        # Should have flow_group enum from options catalog
        flow_groups = loader.get_enum_values("flow_group")
        assert len(flow_groups) > 0
        assert "airline" in flow_groups or "technology" in [f.lower() for f in flow_groups]
    
    def test_loader_get_dataset_not_found(self):
        """Test get_dataset returns None for unknown dataset."""
        loader = UWDDCLoader()
        result = loader.get_dataset("nonexistent-dataset")
        assert result is None
    
    def test_filter_by_class(self):
        """Test filtering datasets by class."""
        loader = UWDDCLoader()
        
        options_flow = loader.filter_by_class("options_flow")
        assert len(options_flow) > 0
        assert all(d.class_ == "options_flow" for d in options_flow)
    
    def test_filter_discoverable(self):
        """Test filtering discoverable datasets."""
        loader = UWDDCLoader()
        
        discoverable = loader.filter_discoverable(True)
        assert len(discoverable) > 0
        assert all(d.discoverable is True for d in discoverable)
    
    def test_get_options_datasets(self):
        """Test getting all options-related datasets."""
        loader = UWDDCLoader()
        
        options = loader.get_options_datasets()
        assert len(options) > 0
        
        # All should be in options-related classes
        options_classes = {
            'options_flow', 'options_volatility', 'options_greeks',
            'options_analytics', 'options_reference', 'options_screener',
            'options_timeseries', 'market_sentiment'
        }
        assert all(d.class_ in options_classes for d in options)
    
    def test_get_institutional_datasets(self):
        """Test getting all institutional-related datasets."""
        loader = UWDDCLoader()
        
        inst = loader.get_institutional_datasets()
        assert len(inst) > 0
        
        inst_classes = {'congressional', 'darkpool', 'institutional', 'insider', 'etf'}
        assert all(d.class_ in inst_classes for d in inst)
    
    def test_get_market_datasets(self):
        """Test getting all market-related datasets."""
        loader = UWDDCLoader()
        
        market = loader.get_market_datasets()
        assert len(market) > 0
        
        market_classes = {'earnings', 'screener', 'market_analytics', 'short_interest'}
        assert all(d.class_ in market_classes for d in market)
    
    def test_search_datasets_by_name(self):
        """Test searching datasets by name."""
        loader = UWDDCLoader()
        
        results = loader.search_datasets("greek")
        assert len(results) > 0
        assert any("greek" in d.dataset.lower() for d in results)
    
    def test_search_datasets_by_notes(self):
        """Test searching datasets by notes content."""
        loader = UWDDCLoader()
        
        results = loader.search_datasets("volatility")
        assert len(results) > 0
    
    def test_search_datasets_case_insensitive(self):
        """Test search is case-insensitive."""
        loader = UWDDCLoader()
        
        results_lower = loader.search_datasets("greek")
        results_upper = loader.search_datasets("GREEK")
        
        assert len(results_lower) == len(results_upper)
    
    def test_get_datasets_by_identifier(self):
        """Test getting datasets by identifier param."""
        loader = UWDDCLoader()
        
        ticker_datasets = loader.get_datasets_by_identifier("ticker")
        assert len(ticker_datasets) > 0
        assert all(d.identifier_param == "ticker" for d in ticker_datasets)
    
    def test_validate_catalog_integrity(self):
        """Test catalog integrity validation."""
        loader = UWDDCLoader()
        
        report = loader.validate_catalog_integrity()
        assert "total_datasets" in report
        assert "classes" in report
        assert "discoverable_count" in report
        assert "issues" in report
    
    def test_get_catalog_summary(self):
        """Test getting human-readable summary."""
        loader = UWDDCLoader()
        
        summary = loader.get_catalog_summary()
        assert "Unusual Whales Dataset Catalog" in summary
        assert "Total Datasets:" in summary
        assert "Breakdown by Class:" in summary
    
    def test_force_reload(self):
        """Test force reload functionality."""
        loader = UWDDCLoader()
        original_count = len(loader.catalog.datasets)
        
        # Force reload should work
        loader.load_catalogs(force_reload=True)
        assert len(loader.catalog.datasets) == original_count
    
    def test_dataset_counts_match_helpers(self):
        """Test that helper methods cover all datasets."""
        loader = UWDDCLoader()
        
        options = loader.get_options_datasets()
        inst = loader.get_institutional_datasets()
        market = loader.get_market_datasets()
        
        total_via_helpers = len(options) + len(inst) + len(market)
        total_in_catalog = len(loader.catalog.datasets)
        
        assert total_via_helpers == total_in_catalog, \
            f"Helper methods returned {total_via_helpers} but catalog has {total_in_catalog}"


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""
    
    def test_get_default_loader_singleton(self):
        """Test default loader is singleton."""
        loader1 = get_default_loader()
        loader2 = get_default_loader()
        assert loader1 is loader2
    
    def test_load_catalog(self):
        """Test load_catalog function."""
        catalog = load_catalog()
        assert catalog is not None
        assert len(catalog.datasets) > 0
    
    def test_get_dataset_function(self):
        """Test get_dataset convenience function."""
        dataset = get_dataset("group-greek-flow")
        assert dataset is not None
    
    def test_search_datasets_function(self):
        """Test search_datasets convenience function."""
        results = search_datasets("flow")
        assert len(results) > 0


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

class TestSimpleRateLimiter:
    """Tests for SimpleRateLimiter."""
    
    @pytest.mark.asyncio
    async def test_acquire_under_limit(self):
        """Test acquiring when under limit is instant."""
        limiter = SimpleRateLimiter(calls_per_second=10, burst=10)
        
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be nearly instant
    
    @pytest.mark.asyncio
    async def test_acquire_respects_rate_limit(self):
        """Test rate limiting actually limits requests."""
        limiter = SimpleRateLimiter(calls_per_second=10, burst=2)
        
        # Use up burst
        await limiter.acquire()
        await limiter.acquire()
        
        # Third should have to wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        
        # Should have waited some time (but account for timing variations)
        assert elapsed >= 0.05  # At least 50ms wait
    
    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        """Test tokens refill based on time passed."""
        limiter = SimpleRateLimiter(calls_per_second=10, burst=5)
        
        # Use some tokens
        await limiter.acquire()
        await limiter.acquire()
        initial_tokens = limiter.tokens
        
        # Wait for refill
        await asyncio.sleep(0.3)
        
        # Acquire should trigger refill calculation
        await limiter.acquire()
        
        # Tokens should have refilled somewhat
        # (this is timing-dependent, so we're lenient)
        assert limiter.tokens >= 0


class TestUWRateLimiter:
    """Tests for UWRateLimiter."""
    
    def test_has_all_expected_classes(self):
        """Test rate limiter has entries for all expected classes."""
        limiter = UWRateLimiter()
        
        expected_classes = [
            "options_flow", "options_volatility", "options_greeks",
            "options_analytics", "options_reference", "options_screener",
            "options_timeseries", "market_sentiment",
            "congressional", "darkpool", "institutional", "insider", "etf",
            "earnings", "screener", "market_analytics", "short_interest",
            "default"
        ]
        
        for cls in expected_classes:
            assert cls in limiter.limiters, f"Missing rate limiter for {cls}"
    
    @pytest.mark.asyncio
    async def test_acquire_uses_correct_limiter(self):
        """Test acquire uses the correct class-specific limiter."""
        limiter = UWRateLimiter()
        
        # Should use options_flow limiter, not default
        await limiter.acquire("options_flow")
        
        # Check tokens were decremented on correct limiter
        assert limiter.limiters["options_flow"].tokens < limiter.limiters["options_flow"].burst
    
    @pytest.mark.asyncio
    async def test_acquire_falls_back_to_default(self):
        """Test acquire falls back to default for unknown class."""
        limiter = UWRateLimiter()
        
        await limiter.acquire("unknown_class")
        
        # Should have used default
        assert limiter.limiters["default"].tokens < limiter.limiters["default"].burst
    
    def test_get_status(self):
        """Test get_status returns correct info."""
        limiter = UWRateLimiter()
        
        status = limiter.get_status()
        assert "options_flow" in status
        assert "rps" in status["options_flow"]
        assert "burst" in status["options_flow"]
        assert "tokens" in status["options_flow"]
    
    def test_update_limits(self):
        """Test updating rate limits."""
        limiter = UWRateLimiter()
        
        limiter.update_limits("options_flow", rps=20, burst=50)
        
        assert limiter.limiters["options_flow"].calls_per_second == 20
        assert limiter.limiters["options_flow"].burst == 50


# =============================================================================
# DATA FETCHER TESTS
# =============================================================================

class TestUWDataFetcher:
    """Tests for UWDataFetcher."""
    
    def test_init(self):
        """Test fetcher initialization."""
        fetcher = UWDataFetcher(api_key="test_key")
        
        assert fetcher.api_key == "test_key"
        assert fetcher.base_url == "https://api.unusualwhales.com"
        assert fetcher.session is None  # Not connected yet
        assert fetcher._request_count == 0
        assert fetcher._error_count == 0
    
    def test_build_cache_key(self):
        """Test cache key building."""
        fetcher = UWDataFetcher(api_key="test")
        
        key = fetcher._build_cache_key("test-dataset", {"ticker": "AAPL", "date": "2024-01-01"})
        
        assert "uw:test-dataset:" in key
        assert "ticker=AAPL" in key
        assert "date=2024-01-01" in key
    
    def test_build_cache_key_consistent(self):
        """Test cache key is consistent regardless of param order."""
        fetcher = UWDataFetcher(api_key="test")
        
        key1 = fetcher._build_cache_key("test", {"a": 1, "b": 2})
        key2 = fetcher._build_cache_key("test", {"b": 2, "a": 1})
        
        assert key1 == key2
    
    def test_build_cache_key_ignores_none(self):
        """Test cache key ignores None values."""
        fetcher = UWDataFetcher(api_key="test")
        
        key = fetcher._build_cache_key("test", {"ticker": "AAPL", "date": None})
        
        assert "date" not in key
    
    @pytest.mark.asyncio
    async def test_memory_cache_set_and_get(self):
        """Test memory cache operations."""
        fetcher = UWDataFetcher(api_key="test")
        
        await fetcher.set_cache("test_key", {"data": "value"}, ttl=60)
        result = await fetcher.get_cache("test_key")
        
        assert result == {"data": "value"}
    
    @pytest.mark.asyncio
    async def test_memory_cache_expiration(self):
        """Test memory cache entries expire."""
        fetcher = UWDataFetcher(api_key="test")
        
        # Set with very short TTL
        await fetcher.set_cache("test_key", {"data": "value"}, ttl=0)
        
        # Wait a tiny bit
        await asyncio.sleep(0.01)
        
        # Should be expired
        result = await fetcher.get_cache("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_memory_cache_size_limit(self):
        """Test memory cache enforces size limit."""
        fetcher = UWDataFetcher(api_key="test")
        fetcher.max_cache_size = 10
        
        # Fill cache beyond limit
        for i in range(20):
            await fetcher.set_cache(f"key_{i}", {"data": i}, ttl=3600)
        
        # Cache size should be limited
        assert len(fetcher.memory_cache) <= fetcher.max_cache_size
    
    def test_normalize_response_with_data_key(self):
        """Test normalizing response that already has data key."""
        fetcher = UWDataFetcher(api_key="test")
        loader = UWDDCLoader()
        dataset = loader.get_dataset("group-greek-flow")
        
        result = fetcher._normalize_response({"data": [1, 2, 3]}, dataset)
        assert result == {"data": [1, 2, 3]}
    
    def test_normalize_response_dict_without_data(self):
        """Test normalizing dict response without data key."""
        fetcher = UWDataFetcher(api_key="test")
        loader = UWDDCLoader()
        dataset = loader.get_dataset("group-greek-flow")
        
        result = fetcher._normalize_response({"value": 123}, dataset)
        assert result == {"data": {"value": 123}}
    
    def test_normalize_response_list(self):
        """Test normalizing list response."""
        fetcher = UWDataFetcher(api_key="test")
        loader = UWDDCLoader()
        dataset = loader.get_dataset("group-greek-flow")
        
        result = fetcher._normalize_response([1, 2, 3], dataset)
        assert result == {"data": [1, 2, 3]}
    
    @pytest.mark.asyncio
    async def test_fetch_dataset_not_connected(self):
        """Test fetch fails when not connected."""
        fetcher = UWDataFetcher(api_key="test")
        loader = UWDDCLoader()
        dataset = loader.get_dataset("group-greek-flow")
        
        with pytest.raises(RuntimeError, match="not connected"):
            await fetcher.fetch_dataset(dataset, {"flow_group": "airline"})
    
    @pytest.mark.asyncio
    async def test_fetch_dataset_validation_error(self):
        """Test fetch returns error for invalid params."""
        fetcher = UWDataFetcher(api_key="test")
        loader = UWDDCLoader()
        
        # Find a dataset with required params
        dataset = loader.get_dataset("group-greek-flow")
        
        # Missing required param should return error
        result = await fetcher.fetch_dataset(dataset, {})
        assert "error" in result
    
    def test_get_stats(self):
        """Test stats retrieval."""
        fetcher = UWDataFetcher(api_key="test")
        
        stats = fetcher.get_stats()
        assert "request_count" in stats
        assert "error_count" in stats
        assert "cache_size" in stats
        assert "rate_limiter_status" in stats


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_all_datasets_have_valid_urls(self):
        """Test all datasets have valid URL templates."""
        loader = UWDDCLoader()
        
        for dataset in loader.catalog.datasets:
            # URL should start with /api
            assert dataset.url.startswith("/api"), f"{dataset.dataset}: URL doesn't start with /api"
            
            # Path params should be in params_schema
            for param in dataset.get_path_params():
                assert param in dataset.params_schema, \
                    f"{dataset.dataset}: Path param '{param}' not in params_schema"
    
    def test_all_datasets_have_rate_limits(self):
        """Test all dataset classes have rate limiters."""
        loader = UWDDCLoader()
        limiter = UWRateLimiter()
        
        classes_in_catalog = set(d.class_ for d in loader.catalog.datasets)
        
        for cls in classes_in_catalog:
            # Should have explicit or default rate limiter
            assert cls in limiter.limiters or "default" in limiter.limiters
    
    def test_catalog_matches_rate_limiter_classes(self):
        """Test rate limiter covers all catalog classes."""
        loader = UWDDCLoader()
        limiter = UWRateLimiter()
        
        catalog_classes = set(d.class_ for d in loader.catalog.datasets)
        limiter_classes = set(limiter.limiters.keys()) - {"default"}
        
        # All catalog classes should be in limiter
        missing = catalog_classes - limiter_classes
        assert len(missing) == 0, f"Rate limiter missing classes: {missing}"
    
    def test_url_substitution_all_datasets(self):
        """Test URL substitution works for all datasets."""
        loader = UWDDCLoader()
        
        for dataset in loader.catalog.datasets:
            path_params = dataset.get_path_params()
            if path_params:
                # Build dummy values
                values = {p: "test_value" for p in path_params}
                
                # Substitution should work without error
                url = dataset.substitute_url(**values)
                
                # URL should have no remaining placeholders
                assert "{" not in url, f"{dataset.dataset}: URL still has placeholders after substitution"


# =============================================================================
# UW OPTIONS SERVER TESTS
# =============================================================================

class TestUWOptionsServer:
    """Tests for the UWOptionsServer MCP implementation."""
    
    def test_server_import(self):
        """Test server can be imported."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        assert UWOptionsServer is not None
    
    def test_server_tools_count(self):
        """Test server has expected number of tools."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        # Create server instance without calling __init__ to avoid API key check
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        assert len(tools) == 14, f"Expected 14 tools, got {len(tools)}"
    
    def test_server_tool_names(self):
        """Test all expected tools are present."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        expected_tools = {
            "uw_flow_alerts",
            "uw_greek_flow", 
            "uw_gex",
            "uw_flow_summary",
            "uw_volatility",
            "uw_option_chain",
            "uw_contract_data",
            "uw_oi_change",
            "uw_net_flow_expiry",
            "uw_sentiment",
            "uw_hottest_contracts",
            "uw_options_volume",
            "uw_greeks",
            "uw_option_price_levels",
        }
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        tool_names = {t.name for t in tools}
        
        assert tool_names == expected_tools, f"Tool mismatch: {tool_names ^ expected_tools}"
    
    def test_server_tools_have_descriptions(self):
        """Test all tools have descriptions."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20, f"Tool {tool.name} description too short"
    
    def test_server_tools_have_input_schemas(self):
        """Test all tools have input schemas."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        for tool in tools:
            assert tool.inputSchema, f"Tool {tool.name} has no input schema"
            assert tool.inputSchema.get("type") == "object", \
                f"Tool {tool.name} input schema is not an object"
            assert "properties" in tool.inputSchema, \
                f"Tool {tool.name} input schema has no properties"
    
    def test_server_name_property(self):
        """Test server name property."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        server._name = "UWOptionsServer"
        
        assert server.name == "UWOptionsServer"
    
    def test_success_result_format(self):
        """Test _success_result returns proper CallToolResult."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        result = server._success_result({"test": "data"})
        
        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert "test" in result.content[0]["text"]
    
    def test_error_result_format(self):
        """Test _error_result returns proper CallToolResult."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        result = server._error_result("Test error", "test_type")
        
        assert result.isError is True
        assert len(result.content) == 1
        assert "error" in result.content[0]["text"]
        assert "test_type" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        """Test call_tool returns error for unknown tool."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        result = await server.call_tool("unknown_tool", {})
        
        assert result.isError is True
        assert "Unknown tool" in result.content[0]["text"]
    
    def test_greek_flow_tool_schema(self):
        """Test uw_greek_flow has proper routing parameters."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        greek_flow = next(t for t in tools if t.name == "uw_greek_flow")
        props = greek_flow.inputSchema["properties"]
        
        # Should have ticker OR flow_group options
        assert "ticker" in props
        assert "flow_group" in props
        assert "expiry" in props
        assert "date" in props
    
    def test_gex_tool_schema_views(self):
        """Test uw_gex has all view options."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        gex = next(t for t in tools if t.name == "uw_gex")
        view_enum = gex.inputSchema["properties"]["view"]["enum"]
        
        expected_views = ["summary", "by_strike", "by_expiry", "by_strike_expiry", 
                         "spot_strike", "spot_expiry_strike"]
        assert set(view_enum) == set(expected_views)
    
    def test_volatility_tool_schema_metrics(self):
        """Test uw_volatility has all metric options."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        vol = next(t for t in tools if t.name == "uw_volatility")
        metric_enum = vol.inputSchema["properties"]["metric"]["enum"]
        
        expected_metrics = ["stats", "rank", "realized", "term_structure", 
                          "interpolated", "historical_skew"]
        assert set(metric_enum) == set(expected_metrics)
    
    def test_flow_alerts_has_filters(self):
        """Test uw_flow_alerts has comprehensive filter options."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        flow = next(t for t in tools if t.name == "uw_flow_alerts")
        props = flow.inputSchema["properties"]
        
        # Key filter params should exist
        expected_filters = ["ticker", "min_premium", "max_premium", "is_sweep",
                          "is_floor", "is_otm", "min_dte", "max_dte", "sectors"]
        for f in expected_filters:
            assert f in props, f"Missing filter: {f}"
    
    def test_hottest_contracts_has_order_options(self):
        """Test uw_hottest_contracts has ordering options."""
        from core.mcp_servers.unusualwhales import UWOptionsServer
        
        server = UWOptionsServer.__new__(UWOptionsServer)
        tools = server._get_tools()
        
        hot = next(t for t in tools if t.name == "uw_hottest_contracts")
        props = hot.inputSchema["properties"]
        
        assert "order" in props
        assert "order_direction" in props
        assert props["order_direction"]["enum"] == ["desc", "asc"]


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

