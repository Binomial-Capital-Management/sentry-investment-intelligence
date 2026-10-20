"""
Unit tests for the Canvas Object Registry.

These tests verify that:
1. All object types load correctly from MCP catalogs
2. Dataset counts match expectations
3. Composition (contains/parent) relationships work
4. Helper functions return correct results
"""

import pytest
from typing import Set

from core.canvas import (
    ObjectType,
    DataSource,
    OBJECT_REGISTRY,
    get_object_type,
    get_all_object_types,
    list_object_types,
    get_combined_capabilities,
    get_object_with_parent_capabilities,
    get_nested_types,
    get_objects_providing,
    get_expanded_capabilities,
    get_all_data_sources,
)


class TestObjectRegistryLoading:
    """Tests for registry initialization and catalog loading."""
    
    def test_registry_loads_successfully(self):
        """Registry should load without errors."""
        assert OBJECT_REGISTRY is not None
        assert len(OBJECT_REGISTRY) > 0
    
    def test_expected_object_types_exist(self):
        """All expected object types should be registered."""
        expected_types = [
            "portfolio",
            "equity",
            "equity_options",
            "etf",
            "crypto",
            "commodity",
            "forex",
            "macro_series",
        ]
        
        registered = list_object_types()
        for obj_type in expected_types:
            assert obj_type in registered, f"Missing object type: {obj_type}"
    
    def test_object_types_have_required_fields(self):
        """Each object type should have all required fields."""
        for obj in get_all_object_types():
            assert obj.name, f"Object missing name"
            assert obj.display_name, f"Object {obj.name} missing display_name"
            assert isinstance(obj.provides, set), f"Object {obj.name} provides should be a set"
            assert isinstance(obj.data_sources, list), f"Object {obj.name} data_sources should be a list"
            assert len(obj.data_sources) > 0, f"Object {obj.name} should have at least one data source"


class TestDatasetCounts:
    """Tests for dataset loading from MCP catalogs."""
    
    def test_equity_has_substantial_datasets(self):
        """Equity should have 100+ datasets from multiple MCP servers."""
        equity = get_object_type("equity")
        assert equity is not None
        assert len(equity.provides) >= 100, f"Equity has {len(equity.provides)} datasets, expected >= 100"
    
    def test_equity_options_has_datasets(self):
        """Equity options should have datasets from Polygon and UW."""
        options = get_object_type("equity_options")
        assert options is not None
        assert len(options.provides) >= 50, f"Options has {len(options.provides)} datasets, expected >= 50"
    
    def test_crypto_has_datasets_from_multiple_sources(self):
        """Crypto should have datasets from FMP and Polygon."""
        crypto = get_object_type("crypto")
        assert crypto is not None
        assert len(crypto.provides) >= 15, f"Crypto has {len(crypto.provides)} datasets, expected >= 15"
        
        # Should have multiple data sources
        assert len(crypto.data_sources) >= 2, "Crypto should have at least 2 data sources"
    
    def test_forex_has_datasets_from_multiple_sources(self):
        """Forex should have datasets from FMP and Polygon."""
        forex = get_object_type("forex")
        assert forex is not None
        assert len(forex.provides) >= 15, f"Forex has {len(forex.provides)} datasets, expected >= 15"
    
    def test_etf_has_holdings_datasets(self):
        """ETF should include holdings-related datasets."""
        etf = get_object_type("etf")
        assert etf is not None
        
        holdings_datasets = [d for d in etf.provides if "holdings" in d or "etf" in d]
        assert len(holdings_datasets) >= 3, f"ETF should have holdings datasets, found: {holdings_datasets}"
    
    def test_macro_series_has_economic_datasets(self):
        """Macro series should have FRED-related datasets."""
        macro = get_object_type("macro_series")
        assert macro is not None
        assert "get-series" in macro.provides
        assert "search-series" in macro.provides


class TestDataSources:
    """Tests for MCP data source configuration."""
    
    def test_equity_has_multiple_data_sources(self):
        """Equity should pull from multiple MCP servers."""
        equity = get_object_type("equity")
        server_names = [src.server for src in equity.data_sources]
        
        assert "FMPMarketDataServer" in server_names
        assert "UWMarketServer" in server_names or "UWInstitutionalServer" in server_names
    
    def test_options_uses_polygon_and_uw(self):
        """Options should use Polygon for contracts and UW for flow."""
        options = get_object_type("equity_options")
        server_names = [src.server for src in options.data_sources]
        
        assert "PolygonOptionsFuturesServer" in server_names
        assert "UWOptionsServer" in server_names
    
    def test_data_sources_have_catalog_paths(self):
        """Data sources from catalogs should have catalog_path set."""
        equity = get_object_type("equity")
        
        catalog_sources = [src for src in equity.data_sources if src.catalog_path]
        assert len(catalog_sources) >= 2, "Equity should have multiple catalog-based sources"


class TestComposition:
    """Tests for contains/parent relationships."""
    
    def test_portfolio_contains_asset_types(self):
        """Portfolio should declare it contains equity, etf, crypto, etc."""
        portfolio = get_object_type("portfolio")
        assert portfolio.contains is not None
        
        assert "equity" in portfolio.contains
        assert "etf" in portfolio.contains
        assert "crypto" in portfolio.contains
    
    def test_equity_options_has_equity_parent(self):
        """Equity options should be nested under equity."""
        options = get_object_type("equity_options")
        assert options.parent == "equity"
    
    def test_get_nested_types_returns_options(self):
        """get_nested_types('equity') should return equity_options."""
        nested = get_nested_types("equity")
        nested_names = [n.name for n in nested]
        
        assert "equity_options" in nested_names


class TestExpandedCapabilities:
    """Tests for capability expansion through composition."""
    
    def test_portfolio_expands_to_contained_types(self):
        """Portfolio expanded capabilities should include all contained types."""
        portfolio = get_object_type("portfolio")
        expanded = get_expanded_capabilities("portfolio")
        
        # Should be much larger than own capabilities
        assert len(expanded) > len(portfolio.provides) * 10
        
        # Should include equity datasets
        equity = get_object_type("equity")
        for ds in list(equity.provides)[:5]:  # Check first 5
            assert ds in expanded, f"Portfolio should expand to include equity dataset: {ds}"
    
    def test_options_expands_to_include_parent(self):
        """Equity options expanded should include parent equity capabilities."""
        options = get_object_type("equity_options")
        expanded = get_expanded_capabilities("equity_options")
        
        # Should include own + parent
        assert len(expanded) > len(options.provides)
        
        # Should include equity datasets
        equity = get_object_type("equity")
        assert len(expanded) >= len(options.provides) + len(equity.provides) - 10  # Allow some overlap
    
    def test_standalone_type_expands_to_self(self):
        """A type without contains/parent should just return own capabilities."""
        commodity = get_object_type("commodity")
        expanded = get_expanded_capabilities("commodity")
        
        # Should be same as own (commodity has no contains or parent)
        assert expanded == commodity.provides


class TestHelperFunctions:
    """Tests for utility functions."""
    
    def test_get_object_type_returns_correct_type(self):
        """get_object_type should return the correct object."""
        equity = get_object_type("equity")
        assert equity.name == "equity"
        assert equity.display_name == "Equity"
    
    def test_get_object_type_returns_none_for_invalid(self):
        """get_object_type should return None for unknown types."""
        result = get_object_type("nonexistent_type")
        assert result is None
    
    def test_list_object_types_returns_all(self):
        """list_object_types should return all registered names."""
        names = list_object_types()
        assert len(names) == len(OBJECT_REGISTRY)
        
        for name in names:
            assert name in OBJECT_REGISTRY
    
    def test_get_all_object_types_returns_objects(self):
        """get_all_object_types should return ObjectType instances."""
        objects = get_all_object_types()
        
        for obj in objects:
            assert isinstance(obj, ObjectType)
    
    def test_get_combined_capabilities(self):
        """get_combined_capabilities should union multiple types."""
        combined = get_combined_capabilities(["equity", "crypto"])
        
        equity = get_object_type("equity")
        crypto = get_object_type("crypto")
        
        # Should contain all from both
        assert equity.provides.issubset(combined)
        assert crypto.provides.issubset(combined)
    
    def test_get_objects_providing_finds_correct_types(self):
        """get_objects_providing should find types with a specific dataset."""
        # company-quote should be in equity
        providers = get_objects_providing("company-quote")
        provider_names = [p.name for p in providers]
        
        assert "equity" in provider_names
    
    def test_get_all_data_sources_aggregates(self):
        """get_all_data_sources should aggregate from contained types."""
        portfolio_sources = get_all_data_sources("portfolio")
        portfolio = get_object_type("portfolio")
        
        # Should have more than just PortfolioService
        assert len(portfolio_sources) > len(portfolio.data_sources)
        
        # Should include sources from contained equity
        server_names = [src.server for src in portfolio_sources]
        assert "FMPMarketDataServer" in server_names


class TestSpecificDatasets:
    """Tests for specific important datasets."""
    
    def test_equity_has_fundamental_datasets(self):
        """Equity should have financial statement datasets."""
        equity = get_object_type("equity")
        
        fundamental_datasets = [
            "income-statement",
            "balance-sheet-statement", 
            "cash-flow-statement",
            "company-quote",
            "company-profile",
        ]
        
        for ds in fundamental_datasets:
            assert ds in equity.provides, f"Equity missing fundamental dataset: {ds}"
    
    def test_equity_has_institutional_datasets(self):
        """Equity should have insider/institutional datasets."""
        equity = get_object_type("equity")
        
        # Check for institutional-related datasets
        institutional = [d for d in equity.provides if "insider" in d or "institution" in d]
        assert len(institutional) >= 2, f"Equity should have institutional datasets, found: {institutional}"
    
    def test_options_has_flow_datasets(self):
        """Options should have flow and greek datasets."""
        options = get_object_type("equity_options")
        
        flow_datasets = [d for d in options.provides if "flow" in d or "greek" in d]
        assert len(flow_datasets) >= 5, f"Options should have flow datasets, found: {flow_datasets}"
    
    def test_options_has_iv_datasets(self):
        """Options should have implied volatility datasets."""
        options = get_object_type("equity_options")
        
        iv_datasets = [d for d in options.provides if "iv" in d.lower() or "volatility" in d.lower()]
        assert len(iv_datasets) >= 2, f"Options should have IV datasets, found: {iv_datasets}"


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_list_combined_capabilities(self):
        """get_combined_capabilities with empty list should return empty set."""
        result = get_combined_capabilities([])
        assert result == set()
    
    def test_invalid_type_in_combined_capabilities(self):
        """get_combined_capabilities should handle invalid types gracefully."""
        result = get_combined_capabilities(["equity", "nonexistent"])
        equity = get_object_type("equity")
        
        # Should still include equity's capabilities
        assert equity.provides.issubset(result)
    
    def test_get_expanded_capabilities_invalid_type(self):
        """get_expanded_capabilities should return empty set for invalid type."""
        result = get_expanded_capabilities("nonexistent")
        assert result == set()
    
    def test_get_nested_types_no_children(self):
        """get_nested_types for type with no children should return empty list."""
        result = get_nested_types("commodity")
        assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])











