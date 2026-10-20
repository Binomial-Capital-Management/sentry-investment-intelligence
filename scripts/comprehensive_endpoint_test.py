#!/usr/bin/env python3
"""
Comprehensive endpoint test - validates all data pathways are working.
Tests: object registry, catalog loading, data sources, and endpoint accessibility.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.canvas.object_registry import get_object_type, get_all_object_types, get_all_data_sources, list_object_types

def load_catalog(catalog_path: str) -> Dict[str, Any]:
    """Load a catalog JSON file."""
    full_path = Path(__file__).parent.parent / "core" / "mcp_servers" / catalog_path
    if not full_path.exists():
        return {"datasets": [], "error": f"Not found: {full_path}"}
    with open(full_path) as f:
        return json.load(f)

def get_catalog_datasets(catalog_path: str, class_filter: str = None, asset_class_filter: str = None) -> Set[str]:
    """Get dataset names from a catalog, optionally filtered."""
    catalog = load_catalog(catalog_path)
    datasets = set()
    for entry in catalog.get("datasets", []):
        if not entry.get("discoverable", False):
            continue
        if class_filter and entry.get("class") != class_filter:
            continue
        if asset_class_filter:
            asset_classes = entry.get("asset_classes", [])
            if asset_class_filter not in asset_classes:
                continue
        ds_name = entry.get("dataset")
        if ds_name:
            datasets.add(ds_name)
    return datasets

def check_server_has_get_fields(server_name: str) -> bool:
    """Check if a server implementation has get_fields tool (or alias)."""
    servers_with_get_fields = {
        "FMPMarketDataServer",  # Has get_fields
        "FMPAlternativesServer",  # Has get_fields alias
        "PolygonOptionsFuturesServer",  # Has get_fields alias
        "PolygonCryptoFXServer",  # Has get_fields alias (but NOT used for crypto/forex)
        "UWOptionsServer",  # Has get_fields alias (added)
        "UWMarketServer",  # Has get_fields alias (added)
        "UWInstitutionalServer",  # Has get_fields alias (added)
    }
    servers_without_get_fields = {
        "FMPAdvancedValuationServer",  # Uses specialized tools
        "FMPTradeFlowServer",  # Uses specialized tools
        "SECFilingServer",  # Uses specialized tools
        "EconomicDataServer",  # Uses specialized tools
    }
    if server_name in servers_with_get_fields:
        return True
    if server_name in servers_without_get_fields:
        return False
    # Unknown - assume no
    return False

def run_tests():
    print("=" * 80)
    print("COMPREHENSIVE ENDPOINT & DATA SOURCE TEST")
    print("=" * 80)
    
    issues = []
    warnings = []
    
    # 1. Test all object types
    print("\n[1] OBJECT TYPE REGISTRY")
    print("-" * 40)
    
    object_type_names = list_object_types()
    print(f"Found {len(object_type_names)} object types: {object_type_names}")
    
    for obj_name in object_type_names:
        obj = get_object_type(obj_name)
        if not obj:
            issues.append(f"Object type '{obj_name}' listed but not found!")
            continue
        print(f"\n  📦 {obj_name} ({obj.display_name})")
        print(f"     Provides: {len(obj.provides)} datasets")
        print(f"     Data sources: {len(obj.data_sources)}")
        
        # Check if at least one data source has get_fields
        has_get_fields_source = False
        for src in obj.data_sources:
            if check_server_has_get_fields(src.server):
                has_get_fields_source = True
                break
        
        if not has_get_fields_source and obj.provides:
            issues.append(f"{obj_name}: No data source with get_fields tool!")
            print(f"     ❌ NO DATA SOURCE HAS get_fields!")
        else:
            print(f"     ✓ Has get_fields source")
        
        # Check if provides are actually available in catalogs
        for src in obj.data_sources:
            catalog_path = src.catalog_path
            if not catalog_path:
                continue
            
            catalog_datasets = get_catalog_datasets(
                catalog_path, 
                class_filter=src.class_filter,
                asset_class_filter=src.asset_class_filter
            )
            
            # Find provides not in this source's catalog
            missing_in_catalog = obj.provides - catalog_datasets
            
            # Only report if this is the primary source (has matching filter)
            if src.class_filter or src.asset_class_filter:
                # This is a filtered source - check what's missing that matches the filter
                pass
            
            print(f"     Source: {src.server}")
            print(f"       Catalog: {catalog_path}")
            print(f"       Discoverable: {len(catalog_datasets)} datasets")
            if src.class_filter:
                print(f"       Filter: class={src.class_filter}")
            if src.asset_class_filter:
                print(f"       Filter: asset_class={src.asset_class_filter}")

    # 2. Check news endpoints specifically
    print("\n\n[2] NEWS ENDPOINT COVERAGE")
    print("-" * 40)
    
    news_endpoints = {
        "equity": ["stock-news", "stock-news-latest", "press-releases", "press-releases-latest", "general-news-latest", "fmp-articles"],
        "crypto": ["crypto-news", "crypto-news-latest"],
        "forex": ["forex-news", "forex-news-latest"],
    }
    
    for obj_type, expected_news in news_endpoints.items():
        obj = get_object_type(obj_type)
        if not obj:
            issues.append(f"Object type '{obj_type}' not found!")
            continue
        
        print(f"\n  📰 {obj_type} news:")
        for news_ep in expected_news:
            if news_ep in obj.provides:
                print(f"     ✓ {news_ep}")
            else:
                issues.append(f"{obj_type}: Missing news endpoint '{news_ep}' in provides")
                print(f"     ❌ {news_ep} NOT IN PROVIDES")
    
    # 3. Check ddc_catalog.json has news endpoints
    print("\n\n[3] DDC_CATALOG NEWS ENDPOINTS")
    print("-" * 40)
    
    ddc_catalog = load_catalog("fmp/ddc_catalog.json")
    ddc_news = [d for d in ddc_catalog.get("datasets", []) if d.get("class") == "news"]
    print(f"Found {len(ddc_news)} news endpoints in ddc_catalog.json:")
    for news in ddc_news:
        print(f"  • {news.get('dataset')}")
        if news.get('identifier_param'):
            print(f"    identifier_param: {news.get('identifier_param')}")
    
    expected_in_ddc = ["crypto-news", "crypto-news-latest", "forex-news", "forex-news-latest"]
    for ep in expected_in_ddc:
        found = any(d.get("dataset") == ep for d in ddc_news)
        if not found:
            issues.append(f"ddc_catalog.json missing: {ep}")
            print(f"  ❌ MISSING: {ep}")
    
    # 4. Check alternatives_catalog.json
    print("\n\n[4] ALTERNATIVES_CATALOG ASSET COVERAGE")
    print("-" * 40)
    
    alt_catalog = load_catalog("fmp/alternatives_catalog.json")
    alt_by_class = {}
    for d in alt_catalog.get("datasets", []):
        cls = d.get("class", "unknown")
        alt_by_class.setdefault(cls, []).append(d.get("dataset"))
    
    for cls, datasets in alt_by_class.items():
        print(f"  {cls}: {len(datasets)} datasets")
        for ds in datasets[:5]:
            print(f"    • {ds}")
        if len(datasets) > 5:
            print(f"    ... and {len(datasets) - 5} more")
    
    # 5. Check Polygon catalog
    print("\n\n[5] POLYGON CATALOG ASSET COVERAGE")
    print("-" * 40)
    
    polygon_catalog = load_catalog("polygon/polygon_ddc_catalog.json")
    polygon_by_class = {}
    for d in polygon_catalog.get("datasets", []):
        for ac in d.get("asset_classes", ["unknown"]):
            polygon_by_class.setdefault(ac, []).append(d.get("dataset"))
    
    for cls, datasets in polygon_by_class.items():
        print(f"  {cls}: {len(datasets)} datasets")
    
    # 6. Check Unusual Whales catalogs
    print("\n\n[6] UNUSUAL WHALES CATALOG COVERAGE")
    print("-" * 40)
    
    uw_catalogs = [
        "unusualwhales/uw_options_catalog.json",
        "unusualwhales/uw_market_catalog.json", 
        "unusualwhales/uw_institutional_catalog.json",
    ]
    
    for cat_path in uw_catalogs:
        cat = load_catalog(cat_path)
        datasets = [d.get("dataset") for d in cat.get("datasets", [])]
        print(f"  {cat_path.split('/')[-1]}: {len(datasets)} datasets")
    
    # 7. Identifier param coverage
    print("\n\n[7] IDENTIFIER PARAM PATTERNS")
    print("-" * 40)
    
    all_catalogs = [
        ("fmp/ddc_catalog.json", "FMP DDC"),
        ("fmp/alternatives_catalog.json", "FMP Alternatives"),
        ("fmp/tradeflow_catalog.json", "FMP Tradeflow"),
        ("fmp/valuation_catalog.json", "FMP Valuation"),
        ("polygon/polygon_ddc_catalog.json", "Polygon"),
    ]
    
    identifier_params = {}
    for cat_path, cat_name in all_catalogs:
        cat = load_catalog(cat_path)
        for d in cat.get("datasets", []):
            id_param = d.get("identifier_param")
            if id_param:
                identifier_params.setdefault(id_param, []).append(f"{cat_name}:{d.get('dataset')}")
    
    print("Identifier params used:")
    for param, endpoints in sorted(identifier_params.items()):
        print(f"  {param}: {len(endpoints)} endpoints")
        # Check if this param is handled in object_data_service
        known_params = {"symbol", "ticker", "options_ticker", "fx_ticker", "crypto_ticker", 
                       "symbols", "name", "cik", "id", "tickers"}
        if param not in known_params:
            warnings.append(f"Identifier param '{param}' may not be handled in object_data_service.py")
            print(f"    ⚠️  May not be handled in backend!")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if issues:
        print(f"\n❌ ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"   • {issue}")
    else:
        print("\n✅ No critical issues found!")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   • {warning}")
    
    print("\n" + "=" * 80)
    
    return len(issues)

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)

