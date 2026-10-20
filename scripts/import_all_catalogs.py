#!/usr/bin/env python3
"""
Import all endpoint catalogs into canvas_fields.db

This script reads all catalog JSON files and populates the canvas_fields database
with endpoints from FMP, Polygon, and Unusual Whales.
"""

import json
import sqlite3
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import field_mappings directly to avoid aiohttp dependency
import importlib.util
spec = importlib.util.spec_from_file_location(
    "field_mappings", 
    PROJECT_ROOT / "core" / "canvas" / "field_mappings.py"
)
field_mappings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(field_mappings)

get_structure_type_for_endpoint = field_mappings.get_structure_type_for_endpoint
get_compatibility_group_for_endpoint = field_mappings.get_compatibility_group_for_endpoint
get_time_key_for_endpoint = field_mappings.get_time_key_for_endpoint
get_cardinality_for_endpoint = field_mappings.get_cardinality_for_endpoint
ENDPOINT_TO_OBJECT_TYPES = field_mappings.ENDPOINT_TO_OBJECT_TYPES
ENDPOINT_TO_CATEGORY = field_mappings.ENDPOINT_TO_CATEGORY

DB_PATH = PROJECT_ROOT / "core" / "canvas" / "data" / "canvas_fields.db"

CATALOGS = [
    # FMP catalogs
    ("fmp", PROJECT_ROOT / "core" / "mcp_servers" / "fmp" / "ddc_catalog.json"),
    ("fmp", PROJECT_ROOT / "core" / "mcp_servers" / "fmp" / "valuation_catalog.json"),
    ("fmp", PROJECT_ROOT / "core" / "mcp_servers" / "fmp" / "tradeflow_catalog.json"),
    ("fmp", PROJECT_ROOT / "core" / "mcp_servers" / "fmp" / "alternatives_catalog.json"),
    # Polygon
    ("polygon", PROJECT_ROOT / "core" / "mcp_servers" / "polygon" / "polygon_ddc_catalog.json"),
    # Unusual Whales
    ("unusualwhales", PROJECT_ROOT / "core" / "mcp_servers" / "unusualwhales" / "uw_market_catalog.json"),
    ("unusualwhales", PROJECT_ROOT / "core" / "mcp_servers" / "unusualwhales" / "uw_options_catalog.json"),
    ("unusualwhales", PROJECT_ROOT / "core" / "mcp_servers" / "unusualwhales" / "uw_institutional_catalog.json"),
]

# Category mappings for non-FMP sources
POLYGON_CATEGORIES = {
    "options": "Options",
    "forex": "Forex",
    "crypto": "Crypto",
    "reference": "Reference",
    "snapshot": "Price & Volume",
}

UW_CATEGORIES = {
    "earnings": "Earnings",
    "market_analytics": "Market Analytics",
    "options": "Options",
    "flow": "Options Flow",
    "greek": "Options Greeks",
    "institutional": "Ownership",
    "congress": "Political Trading",
    "darkpool": "Dark Pool",
    "insider": "Insider Trading",
    "screener": "Screener",
}


def get_category(source: str, endpoint: str, dataset_class: str) -> str:
    """Determine category for an endpoint."""
    # Check FMP mappings first
    if endpoint in ENDPOINT_TO_CATEGORY:
        return ENDPOINT_TO_CATEGORY[endpoint]
    
    # Polygon categories
    if source == "polygon":
        for key, cat in POLYGON_CATEGORIES.items():
            if key in endpoint.lower():
                return cat
        return "Market Data"
    
    # Unusual Whales categories
    if source == "unusualwhales":
        for key, cat in UW_CATEGORIES.items():
            if key in dataset_class.lower() or key in endpoint.lower():
                return cat
        return "Options Flow"
    
    return "Other"


def get_object_type(source: str, endpoint: str, identifier_param: str) -> str:
    """Determine object type for an endpoint."""
    if endpoint in ENDPOINT_TO_OBJECT_TYPES:
        types = ENDPOINT_TO_OBJECT_TYPES[endpoint]
        return types[0] if types else "market"
    
    # Infer from identifier param
    if identifier_param in ["symbol", "ticker", "tickers"]:
        return "equity"
    if "options" in endpoint.lower() or identifier_param == "options_ticker":
        return "option"
    if "forex" in endpoint.lower() or identifier_param == "fx_ticker":
        return "forex"
    if "crypto" in endpoint.lower() or identifier_param == "crypto_ticker":
        return "crypto"
    if "commodity" in endpoint.lower():
        return "commodity"
    
    return "market"


def import_catalog(conn: sqlite3.Connection, source: str, catalog_path: Path) -> int:
    """Import a single catalog file into the database."""
    if not catalog_path.exists():
        print(f"  ⚠ Catalog not found: {catalog_path}")
        return 0
    
    with open(catalog_path) as f:
        data = json.load(f)
    
    datasets = data.get("datasets", [])
    if not datasets:
        print(f"  ⚠ No datasets in: {catalog_path.name}")
        return 0
    
    cursor = conn.cursor()
    imported = 0
    
    for ds in datasets:
        endpoint = ds.get("dataset", "")
        if not endpoint:
            continue
        
        # Get params
        params_schema = ds.get("params_schema", {})
        required_params = list(params_schema.keys())
        identifier_param = ds.get("identifier_param", "")
        dataset_class = ds.get("class", "")
        
        # Get metadata
        category = get_category(source, endpoint, dataset_class)
        object_type = get_object_type(source, endpoint, identifier_param)
        structure_type = get_structure_type_for_endpoint(endpoint)
        compat_group = get_compatibility_group_for_endpoint(endpoint)
        time_key = get_time_key_for_endpoint(endpoint)
        cardinality = get_cardinality_for_endpoint(endpoint)
        
        # For non-FMP, infer structure type from endpoint name if unknown
        if structure_type == "unknown":
            if "historical" in endpoint or "aggregates" in endpoint:
                structure_type = "daily_trading"
                compat_group = "daily_trading"
                time_key = "date"
            elif "snapshot" in endpoint or "quote" in endpoint:
                structure_type = "snapshot"
                compat_group = "point_in_time"
                time_key = None
            elif "flow" in endpoint or "greek" in endpoint:
                structure_type = "options_flow"
                compat_group = "options"
                time_key = "date"
            elif "indicator" in endpoint:
                structure_type = "technical_series"
                compat_group = "daily_trading"
                time_key = "timestamp"
        
        # Generate field entries (we don't have actual fields, so create placeholder)
        # In reality, fields should be discovered by calling the API
        cursor.execute("""
            INSERT OR REPLACE INTO fields 
            (field_name, endpoint, source, field_type, required_params, object_type, category,
             structure_type, compatibility_group, time_key, cardinality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{endpoint}_data",  # Placeholder field name
            endpoint,
            source,
            "object",
            json.dumps(required_params),
            object_type,
            category,
            structure_type,
            compat_group,
            time_key,
            cardinality,
        ))
        imported += 1
    
    conn.commit()
    return imported


def main():
    print("=" * 60)
    print("Importing all catalogs into canvas_fields.db")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Ensure table has all required columns
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(fields)")
    columns = {row[1] for row in cursor.fetchall()}
    
    new_columns = [
        ("structure_type", "TEXT"),
        ("compatibility_group", "TEXT"),
        ("time_key", "TEXT"),
        ("cardinality", "TEXT"),
    ]
    
    for col_name, col_type in new_columns:
        if col_name not in columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE fields ADD COLUMN {col_name} {col_type}")
    
    conn.commit()
    
    # Import each catalog
    total = 0
    for source, path in CATALOGS:
        print(f"\n📁 {source}: {path.name}")
        count = import_catalog(conn, source, path)
        print(f"   ✓ Imported {count} endpoints")
        total += count
    
    # Show summary
    print("\n" + "=" * 60)
    print("Summary by source:")
    cursor.execute("""
        SELECT source, COUNT(DISTINCT endpoint) as cnt 
        FROM fields 
        GROUP BY source 
        ORDER BY cnt DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} endpoints")
    
    print(f"\nTotal: {total} endpoints imported")
    print("=" * 60)
    
    conn.close()


if __name__ == "__main__":
    main()

