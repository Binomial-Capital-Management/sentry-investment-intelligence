#!/usr/bin/env python3
"""
Audit endpoint parameter mappings to identify potential issues.

This script compares:
1. Catalog definitions (identifier_param, params_schema)
2. Field mappings (cardinality)
3. Backend routing logic expectations

Flags potential mismatches that could cause "No data returned" errors.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.canvas.field_mappings import (
    ENDPOINT_TO_CARDINALITY,
    ENDPOINT_TO_STRUCTURE_TYPE,
)

# Catalog paths
CATALOG_PATHS = [
    "core/mcp_servers/fmp/ddc_catalog.json",
    "core/mcp_servers/fmp/alternatives_catalog.json",
    "core/mcp_servers/fmp/valuation_catalog.json",
    "core/mcp_servers/fmp/tradeflow_catalog.json",
    "core/mcp_servers/polygon/polygon_ddc_catalog.json",
    "core/mcp_servers/unusualwhales/uw_market_catalog.json",
    "core/mcp_servers/unusualwhales/uw_options_catalog.json",
    "core/mcp_servers/unusualwhales/uw_institutional_catalog.json",
]

# Known identifier param names in our routing logic
KNOWN_IDENTIFIER_PARAMS = {
    "symbol", "symbols", "ticker", "tickers",
    "options_ticker", "fx_ticker", "crypto_ticker",
    "name", "cik"
}


def load_catalogs() -> Dict[str, Dict[str, Any]]:
    """Load all catalogs and return endpoint -> config mapping."""
    endpoints = {}
    root = Path(__file__).parent.parent
    
    for path in CATALOG_PATHS:
        full_path = root / path
        if not full_path.exists():
            continue
        
        try:
            with open(full_path) as f:
                catalog = json.load(f)
            
            source = catalog.get("source", Path(path).stem)
            for ds in catalog.get("datasets", []):
                name = ds.get("dataset")
                if name:
                    endpoints[name] = {
                        "source": source,
                        "identifier_param": ds.get("identifier_param"),
                        "params_schema": ds.get("params_schema", {}),
                        "url": ds.get("url"),
                        "notes": ds.get("notes"),
                    }
        except Exception as e:
            print(f"Error loading {path}: {e}")
    
    return endpoints


def audit_endpoints():
    """Audit all endpoints and flag potential issues."""
    catalogs = load_catalogs()
    issues: List[Dict[str, Any]] = []
    
    print("=" * 80)
    print("ENDPOINT PARAMETER AUDIT")
    print("=" * 80)
    print()
    
    # Check each endpoint
    for endpoint, config in sorted(catalogs.items()):
        cardinality = ENDPOINT_TO_CARDINALITY.get(endpoint, "unknown")
        identifier_param = config.get("identifier_param")
        params_schema = config.get("params_schema", {})
        
        endpoint_issues = []
        
        # Issue 1: Has identifier_param but cardinality=none
        if identifier_param and cardinality == "none":
            endpoint_issues.append(
                f"Has identifier_param='{identifier_param}' but cardinality='none' - symbol won't be passed!"
            )
        
        # Issue 2: No identifier_param but cardinality=single/multi
        if not identifier_param and cardinality in ("single", "multi"):
            # Check if any known identifier is in params_schema
            schema_params = set(params_schema.keys())
            has_known_id = schema_params & KNOWN_IDENTIFIER_PARAMS
            if has_known_id:
                endpoint_issues.append(
                    f"Missing identifier_param in catalog but has {has_known_id} in schema"
                )
        
        # Issue 3: identifier_param not in our routing logic
        if identifier_param and identifier_param not in KNOWN_IDENTIFIER_PARAMS:
            endpoint_issues.append(
                f"Identifier '{identifier_param}' not in known routing params - needs backend update"
            )
        
        # Issue 4: Cardinality not defined
        if cardinality == "unknown":
            endpoint_issues.append("Missing cardinality mapping")
        
        # Issue 5: 'name' or 'cik' identifier but not symbol-based
        if identifier_param in ("name", "cik") and cardinality != "none":
            # These typically need special handling
            pass  # Just informational
        
        if endpoint_issues:
            issues.append({
                "endpoint": endpoint,
                "source": config.get("source"),
                "identifier_param": identifier_param,
                "cardinality": cardinality,
                "issues": endpoint_issues,
            })
    
    # Print issues by severity
    critical = [i for i in issues if any("won't be passed" in iss for iss in i["issues"])]
    warnings = [i for i in issues if i not in critical]
    
    print(f"Found {len(critical)} CRITICAL issues (data won't be returned):")
    print("-" * 60)
    for item in critical:
        print(f"\n📛 {item['endpoint']} ({item['source']})")
        print(f"   identifier_param: {item['identifier_param']}")
        print(f"   cardinality: {item['cardinality']}")
        for iss in item["issues"]:
            print(f"   ⚠️  {iss}")
    
    print(f"\n\nFound {len(warnings)} warnings:")
    print("-" * 60)
    for item in warnings[:20]:  # Show first 20
        print(f"\n⚠️  {item['endpoint']} ({item['source']})")
        for iss in item["issues"]:
            print(f"   → {iss}")
    
    if len(warnings) > 20:
        print(f"\n... and {len(warnings) - 20} more warnings")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total endpoints checked: {len(catalogs)}")
    print(f"Critical issues: {len(critical)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Healthy: {len(catalogs) - len(issues)}")
    
    # Return critical issues for programmatic use
    return critical


if __name__ == "__main__":
    critical = audit_endpoints()
    sys.exit(1 if critical else 0)






