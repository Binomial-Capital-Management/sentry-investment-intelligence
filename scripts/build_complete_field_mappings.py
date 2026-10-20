#!/usr/bin/env python3
"""
Build Complete FMP Field Mappings

Probes ALL endpoints from ALL catalogs to build a comprehensive field_mappings.db.
This should be run locally, then the resulting DB committed to the repo for production use.

Usage:
  python scripts/build_complete_field_mappings.py
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.mcp_servers.fmp.field_map_manager import FieldMapManager
from core.mcp_servers.fmp.field_discovery import (
    FMPFieldDiscovery,
    build_probe_params,
    resolve_probe_identifier,
)
from core.mcp_servers.fmp.data_fetcher import FMPDataFetcher
from core.mcp_servers.fmp.ddc_loader import DDCLoader


async def build_complete_mappings():
    """Build comprehensive field mappings from all catalogs"""
    print("=" * 80)
    print("🚀 Building Complete FMP Field Mappings")
    print("=" * 80)
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Resolve API key strictly from environment so Docker builds do not require full config
    fmp_api_key = os.getenv("FMP_API_KEY")

    if not fmp_api_key:
        print("❌ ERROR: FMP_API_KEY not found in environment")
        sys.exit(1)

    # Database path (in repo, will be committed)
    db_path = project_root / "core/mcp_servers/fmp/data/field_mappings.db"
    print(f"📂 Database: {db_path}\n")

    # Initialize field manager and clear existing mappings
    field_manager = FieldMapManager(db_path=str(db_path))
    print("🗑️  Clearing existing mappings...")
    field_manager.clear_mappings()
    print("   ✅ Cleared\n")

    # Catalog paths
    catalogs = [
        ("DDC (Market Data)", project_root / "core/mcp_servers/fmp/ddc_catalog.json"),
        ("Valuation", project_root / "core/mcp_servers/fmp/valuation_catalog.json"),
        ("Alternatives", project_root / "core/mcp_servers/fmp/alternatives_catalog.json"),
        ("TradeFlow", project_root / "core/mcp_servers/fmp/tradeflow_catalog.json"),
    ]

    all_endpoints = set()

    # Process each catalog
    for catalog_name, catalog_path in catalogs:
        if not catalog_path.exists():
            print(f"⚠️  Skipping {catalog_name}: {catalog_path.name} not found")
            continue

        print(f"📚 Processing {catalog_name} catalog ({catalog_path.name})")
        print("-" * 80)

        # Load catalog
        ddc_loader = DDCLoader(str(catalog_path))
        discoverable_count = len([ds for ds in ddc_loader.catalog.datasets if ds.discoverable])
        print(f"   - Total datasets: {len(ddc_loader.catalog.datasets)}")
        print(f"   - Discoverable datasets: {discoverable_count}")

        # Initialize components
        data_fetcher = FMPDataFetcher(api_key=fmp_api_key)
        discovery = FMPFieldDiscovery(
            api_key=fmp_api_key,
            data_fetcher=data_fetcher,
            ddc_loader=ddc_loader,
            field_manager=field_manager
        )

        print("   🔍 Discovering fields...")
        discoverable = [
            ds for ds in ddc_loader.catalog.datasets
            if ds.discoverable
        ]
        await data_fetcher.connect()
        endpoint_urls = {}
        endpoint_classes = {}
        datasets_probed = 0

        try:
            for dataset in discoverable:
                identifier = resolve_probe_identifier(dataset, "AAPL") or ""
                probe_params = build_probe_params(dataset)

                try:
                    data = await data_fetcher.fetch_dataset(identifier, dataset, historical_params=probe_params)
                except Exception as fetch_error:
                    print(f"Failed to probe {dataset.dataset}: {fetch_error}")
                    continue

                if not data:
                    continue

                endpoint_urls[dataset.dataset] = dataset.url
                endpoint_classes[dataset.dataset] = dataset.class_.value
                fields = discovery._extract_fields(data, dataset.dataset)
                if not fields:
                    continue

                field_manager.save_discovered_fields(fields, endpoint_urls, endpoint_classes)
                datasets_probed += 1
        finally:
            await data_fetcher.cleanup()

        catalog_endpoints = set(endpoint_urls.keys())
        all_endpoints.update(catalog_endpoints)

        print(f"   ✅ Probed {datasets_probed} datasets from this catalog")
        print(f"   📝 Endpoints probed: {len(catalog_endpoints)}")

        if 'valuation' in catalog_name.lower():
            dcf_endpoints = [ep for ep in catalog_endpoints if 'dcf' in ep.lower()]
            if dcf_endpoints:
                print(f"   💰 DCF endpoints found: {', '.join(dcf_endpoints)}")

        print()

    # Final stats
    print("=" * 80)
    print("✅ COMPLETE - Field Mappings Built Successfully")
    print("=" * 80)

    final_stats = field_manager.get_statistics()
    print(f"\n📊 Final Statistics:")
    print(f"   - Total fields: {final_stats['total_fields']}")
    print(f"   - Total endpoints: {len(all_endpoints)}")
    print(f"   - Database size: {db_path.stat().st_size / 1024:.1f} KB")
    print(f"   - Last update: {final_stats['last_update']}")

    # Show endpoint breakdown
    print(f"\n📋 Fields by endpoint (top 20):")
    endpoint_counts = sorted(final_stats['by_endpoint'].items(), key=lambda x: x[1], reverse=True)
    for endpoint, count in endpoint_counts[:20]:
        print(f"   - {endpoint}: {count} fields")

    # Verify custom DCF endpoints are present
    print(f"\n🔍 Verifying critical endpoints:")
    critical_endpoints = ['custom-discounted-cash-flow', 'custom-levered-discounted-cash-flow', 'revenue', 'netIncome']
    for endpoint_name in critical_endpoints:
        if endpoint_name in final_stats['by_endpoint']:
            print(f"   ✅ {endpoint_name}: {final_stats['by_endpoint'][endpoint_name]} fields")
        else:
            # Check if it's a field, not an endpoint
            field_info = field_manager.get_field_endpoint(endpoint_name)
            if field_info:
                print(f"   ✅ {endpoint_name}: found in {field_info['endpoint']}")
            else:
                print(f"   ⚠️  {endpoint_name}: NOT FOUND")

    field_manager.close()

    print(f"\n💡 Next steps:")
    print(f"   1. Verify the mappings look correct above")
    print(f"   2. Commit the updated field_mappings.db:")
    print(f"      git add core/mcp_servers/fmp/data/field_mappings.db")
    print(f"      git commit -m 'Update field mappings with all endpoints including custom DCF'")
    print(f"   3. Deploy to production")
    print(f"   4. Test with DCF query in production\n")


if __name__ == "__main__":
    asyncio.run(build_complete_mappings())
