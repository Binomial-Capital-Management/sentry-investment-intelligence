"""
Field Map Manager - Efficient field discovery caching
Following KISS principle - simple SQLite database for field mappings
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional, List, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# Class-based priority from DDC catalog
# Scale: 50-100, more homogenous distribution
CLASS_PRIORITY = {
    "market": 100,           # Core market data (income statement, balance sheet, cash flow)
    "market-data": 100,      # Alias for market
    "analyst": 90,           # Analyst estimates and ratings
    "forecast": 85,          # Forward-looking forecasts
    "ownership": 80,         # Institutional ownership
    "institutional": 80,     # Institutional activity
    "insider": 75,           # Insider transactions
    "etf": 75,               # ETF data
    "technical": 70,         # Technical indicators
    "corporate_actions": 70, # Dividends, splits, etc
    "economics": 65,         # Economic indicators
    "crypto": 65,            # Crypto data
    "forex": 65,             # Forex data
    "commodities": 65,       # Commodities data
    "market_wide": 60,       # Market-wide metrics
    "valuation": 60,         # Derived valuations (DCF models, multiples)
    "esg": 55,               # ESG metrics
    "documents": 55,         # SEC filings and reports
    "congressional": 50,     # Congressional trades
    "political": 50,         # Political data
    "news": 50,              # News and sentiment
}


# Static aliases for commonly requested field names that don't match FMP naming.
# Maps alias -> (dataset_name, actual_field_name).
# Prevents expensive 80-endpoint discovery when the agent uses common shorthand.
FIELD_ALIASES: Dict[str, tuple] = {
    # P/E ratio variants
    "peRatio": ("company-quote", "pe"),
    "peRatioTTM": ("ratios-ttm", "peRatioTTM"),
    "pe": ("company-quote", "pe"),
    "pe_ratio": ("company-quote", "pe"),
    "priceEarningsRatio": ("company-quote", "pe"),
    # EV/EBITDA variants
    "evToEbitda": ("key-metrics-ttm", "evToEBITDATTM"),
    "evToEbitdaTTM": ("key-metrics-ttm", "evToEBITDATTM"),
    "ev_to_ebitda": ("key-metrics-ttm", "evToEBITDATTM"),
    "evEbitda": ("key-metrics-ttm", "evToEBITDATTM"),
    # Common shorthand
    "ps": ("key-metrics-ttm", "evToSalesTTM"),
    "pb": ("ratios-ttm", "priceToBookRatioTTM"),
    "priceToBook": ("ratios-ttm", "priceToBookRatioTTM"),
    "priceToSales": ("ratios-ttm", "priceToSalesRatioTTM"),
    "dividendYield": ("ratios-ttm", "dividendYieldTTM"),
    "dividend_yield": ("ratios-ttm", "dividendYieldTTM"),
    # Market data
    "market_cap": ("company-quote", "marketCap"),
    "marketCap": ("company-quote", "marketCap"),
    "price": ("company-quote", "price"),
    "volume": ("company-quote", "volume"),
    "beta": ("company-profile", "beta"),
    # Per-share metrics → TTM (no period/limit required)
    "bookValuePerShare": ("ratios-ttm", "bookValuePerShareTTM"),
    "book_value_per_share": ("ratios-ttm", "bookValuePerShareTTM"),
    "revenuePerShare": ("ratios-ttm", "revenuePerShareTTM"),
    "netIncomePerShare": ("ratios-ttm", "netIncomePerShareTTM"),
    "cashPerShare": ("ratios-ttm", "cashPerShareTTM"),
    "freeCashFlowPerShare": ("ratios-ttm", "freeCashFlowPerShareTTM"),
    "tangibleBookValuePerShare": ("ratios-ttm", "tangibleBookValuePerShareTTM"),
    # Profitability ratios → TTM
    "returnOnEquity": ("key-metrics-ttm", "returnOnEquityTTM"),
    "roe": ("key-metrics-ttm", "returnOnEquityTTM"),
    "returnOnAssets": ("key-metrics-ttm", "returnOnAssetsTTM"),
    "roa": ("key-metrics-ttm", "returnOnAssetsTTM"),
    "returnOnCapitalEmployed": ("key-metrics-ttm", "returnOnCapitalEmployedTTM"),
    "roce": ("key-metrics-ttm", "returnOnCapitalEmployedTTM"),
    "returnOnInvestedCapital": ("key-metrics-ttm", "returnOnInvestedCapitalTTM"),
    "roic": ("key-metrics-ttm", "returnOnInvestedCapitalTTM"),
    # Margins → TTM
    "grossProfitMargin": ("ratios-ttm", "grossProfitMarginTTM"),
    "operatingProfitMargin": ("ratios-ttm", "operatingProfitMarginTTM"),
    "netProfitMargin": ("ratios-ttm", "netProfitMarginTTM"),
    "ebitdaMargin": ("ratios-ttm", "ebitdaMarginTTM"),
    # Leverage & liquidity → TTM
    "currentRatio": ("key-metrics-ttm", "currentRatioTTM"),
    "debtToEquity": ("ratios-ttm", "debtToEquityRatioTTM"),
    "debtEquityRatio": ("ratios-ttm", "debtToEquityRatioTTM"),
    "debtToAssets": ("ratios-ttm", "debtToAssetsRatioTTM"),
    "interestCoverage": ("ratios-ttm", "interestCoverageRatioTTM"),
    # Enterprise value
    "enterpriseValue": ("key-metrics-ttm", "enterpriseValueTTM"),
    "enterprise_value": ("key-metrics-ttm", "enterpriseValueTTM"),
    "evToSales": ("key-metrics-ttm", "evToSalesTTM"),
    "evToFreeCashFlow": ("key-metrics-ttm", "evToFreeCashFlowTTM"),
    # Yield & payout
    "freeCashFlowYield": ("key-metrics-ttm", "freeCashFlowYieldTTM"),
    "earningsYield": ("key-metrics-ttm", "earningsYieldTTM"),
    "dividendPayoutRatio": ("ratios-ttm", "dividendPayoutRatioTTM"),
}

# Dataset name aliases for commonly mis-requested dataset names.
# Maps alias -> canonical dataset name in the DDC catalog.
DATASET_ALIASES: Dict[str, str] = {
    "company-key-metrics": "key-metrics-ttm",
    "company-ratios": "ratios-ttm",
    "key-metrics": "key-metrics-ttm",
    "ratios": "ratios-ttm",
    "company-financials": "income-statement",
    "financials": "income-statement",
}


class FieldMapManager:
    """
    Manages field mappings to avoid redundant API calls.
    Simple SQLite database that remembers where each field lives.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize field map manager with SQLite database"""
        if db_path is None:
            # Default to data directory
            data_dir = Path(__file__).parent / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "field_mappings.db")
        
        self.db_path = db_path
        # Use check_same_thread=False to allow multi-threaded access
        # And set timeout to handle concurrent access better
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self._init_database()
        
        logger.info(f"FieldMapManager initialized with database: {db_path}")
    
    def _init_database(self):
        """Create tables if they don't exist"""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS field_mappings (
                field_name TEXT PRIMARY KEY,
                endpoint_name TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                field_type TEXT,
                endpoint_priority INTEGER DEFAULT 50,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 0
            )
        """)

        # Legacy schema migration: add columns if missing
        try:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN sample_value TEXT")
        except Exception:
            pass

        try:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN endpoint_priority INTEGER DEFAULT 50")
        except Exception:
            pass

        # Ensure required_params and notes columns exist (backwards compatible)
        cursor.execute("PRAGMA table_info(field_mappings)")
        columns = {row[1] for row in cursor.fetchall()}
        if "required_params" not in columns:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN required_params TEXT")
        if "notes" not in columns:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN notes TEXT")

        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_endpoint
            ON field_mappings(endpoint_name)
        """)

        self.conn.commit()
    
    def save_discovered_fields(self, fields: Dict[str, Any], endpoint_urls: Dict[str, str] = None, endpoint_classes: Dict[str, str] = None) -> int:
        """
        Save discovered fields with priority-based replacement.
        Only replaces existing mappings if new endpoint has higher priority.

        Args:
            fields: Dict of field_name -> {value, source, type}
            endpoint_urls: Optional dict of endpoint_name -> url_pattern
            endpoint_classes: Optional dict of endpoint_name -> class (for priority)

        Returns:
            Number of fields saved (new + updated)
        """
        cursor = self.conn.cursor()
        new_fields = 0
        updated_fields = 0

        for field_name, info in fields.items():
            # Extract endpoint from source
            endpoint = info.get("source", "unknown")
            field_type = info.get("type", "unknown")
            required_params = info.get("required_params")
            required_params_json = json.dumps(required_params) if required_params else None
            notes = info.get("notes")

            # Get URL pattern
            if endpoint_urls and endpoint in endpoint_urls:
                url_pattern = endpoint_urls[endpoint]
            else:
                url_pattern = f"unknown_pattern_for_{endpoint}"

            # Get endpoint class and priority
            endpoint_class = endpoint_classes.get(endpoint, "unknown") if endpoint_classes else "unknown"
            priority = CLASS_PRIORITY.get(endpoint_class, 50)  # Default priority = 50

            # Check if field already exists
            cursor.execute("""
                SELECT endpoint_priority, endpoint_name
                FROM field_mappings
                WHERE field_name = ?
            """, (field_name,))

            existing = cursor.fetchone()

            if existing:
                existing_priority = existing["endpoint_priority"]
                existing_endpoint = existing["endpoint_name"]

                # Only update if new priority is HIGHER
                if priority > existing_priority:
                    cursor.execute("""
                        UPDATE field_mappings
                        SET endpoint_name = ?, endpoint_url = ?, field_type = ?,
                            endpoint_priority = ?, last_verified = ?, required_params = ?, notes = ?
                        WHERE field_name = ?
                    """, (
                        endpoint,
                        url_pattern,
                        field_type,
                        priority,
                        datetime.now(),
                        required_params_json,
                        notes,
                        field_name,
                    ))
                    updated_fields += 1
                    logger.debug(f"Updated {field_name}: {existing_endpoint} (pri={existing_priority}) → {endpoint} (pri={priority})")
                else:
                    # Keep existing higher-priority mapping
                    logger.debug(f"Kept {field_name}: {existing_endpoint} (pri={existing_priority}) > {endpoint} (pri={priority})")
                    if required_params_json or notes:
                        cursor.execute("""
                            UPDATE field_mappings
                            SET required_params = COALESCE(?, required_params),
                                notes = COALESCE(?, notes),
                                last_verified = ?
                            WHERE field_name = ?
                        """, (required_params_json, notes, datetime.now(), field_name))
            else:
                # New field - insert
                cursor.execute("""
                    INSERT INTO field_mappings
                    (field_name, endpoint_name, endpoint_url, field_type, endpoint_priority, last_verified, required_params, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    field_name,
                    endpoint,
                    url_pattern,
                    field_type,
                    priority,
                    datetime.now(),
                    required_params_json,
                    notes,
                ))
                new_fields += 1

        self.conn.commit()
        logger.debug(f"Saved field mappings: {new_fields} new, {updated_fields} updated with higher priority")
        return new_fields + updated_fields
    
    def get_field_endpoint(self, field_name: str) -> Optional[Dict[str, str]]:
        """
        Get endpoint information for a specific field.
        Returns None if field not found.
        """
        try:
            cursor = self.conn.cursor()
            
            # Get field info first (read-only)
            cursor.execute("""
                SELECT endpoint_name, endpoint_url, field_type, required_params, notes
                FROM field_mappings 
                WHERE field_name = ?
            """, (field_name,))
            
            row = cursor.fetchone()
            result = None
            if row:
                result = {
                    "endpoint": row["endpoint_name"],
                    "url": row["endpoint_url"],
                    "type": row["field_type"]
                }
                raw_params = row["required_params"]
                if raw_params:
                    try:
                        result["required_params"] = json.loads(raw_params)
                    except json.JSONDecodeError:
                        result["required_params"] = []
                if row["notes"]:
                    result["notes"] = row["notes"]
                
                # Update hit count separately to avoid lock contention
                try:
                    cursor.execute("""
                        UPDATE field_mappings 
                        SET hit_count = hit_count + 1 
                        WHERE field_name = ?
                    """, (field_name,))
                    self.conn.commit()
                except:
                    # Ignore hit count update failures
                    pass
            
            return result
        except Exception as e:
            logger.warning(f"Error getting field endpoint: {e}")
            return None
    
    def get_fields_by_endpoint(self, endpoint_name: str) -> List[str]:
        """Get all fields available in a specific endpoint"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT field_name 
            FROM field_mappings 
            WHERE endpoint_name = ?
        """, (endpoint_name,))
        
        return [row["field_name"] for row in cursor.fetchall()]
    
    def get_endpoints_for_fields(self, field_names: List[str]) -> Dict[str, List[str]]:
        """
        Get minimal set of endpoints needed to fetch given fields.
        Returns dict of endpoint -> [fields] to minimize API calls.
        Resolves FIELD_ALIASES before DB lookup to avoid unnecessary discovery.
        """
        endpoints = {}

        for field_name in field_names:
            # Check static alias first — avoids expensive discovery for common names
            alias = FIELD_ALIASES.get(field_name)
            if alias:
                dataset_name, actual_field = alias
                if dataset_name not in endpoints:
                    endpoints[dataset_name] = []
                # Store original requested name so caller can map back
                endpoints[dataset_name].append(actual_field)
                continue

            info = self.get_field_endpoint(field_name)
            if info:
                endpoint = info["endpoint"]
                if endpoint not in endpoints:
                    endpoints[endpoint] = []
                endpoints[endpoint].append(field_name)

        return endpoints
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about field mappings"""
        cursor = self.conn.cursor()
        
        # Total fields
        cursor.execute("SELECT COUNT(*) as total FROM field_mappings")
        total = cursor.fetchone()["total"]
        
        # Fields per endpoint
        cursor.execute("""
            SELECT endpoint_name, COUNT(*) as count 
            FROM field_mappings 
            GROUP BY endpoint_name
        """)
        by_endpoint = {row["endpoint_name"]: row["count"] for row in cursor.fetchall()}
        
        # Most accessed fields
        cursor.execute("""
            SELECT field_name, hit_count 
            FROM field_mappings 
            ORDER BY hit_count DESC 
            LIMIT 10
        """)
        top_fields = [(row["field_name"], row["hit_count"]) for row in cursor.fetchall()]
        
        # Last update
        cursor.execute("SELECT MAX(last_verified) as last FROM field_mappings")
        last_update = cursor.fetchone()["last"]
        
        return {
            "total_fields": total,
            "by_endpoint": by_endpoint,
            "top_fields": top_fields,
            "last_update": last_update
        }
    
    def get_all_field_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached field mappings with their metadata"""
        cursor = self.conn.cursor()
        # Older databases may not have 'sample_value' column. Select only existing columns.
        cursor.execute("""
            SELECT field_name, endpoint_name, endpoint_url, field_type, required_params, notes
            FROM field_mappings
            ORDER BY field_name
        """)
        
        mappings = {}
        for row in cursor.fetchall():
            entry = {
                "endpoint": row["endpoint_name"],
                "url": row["endpoint_url"],
                "type": row["field_type"],
                # 'sample' is optional; legacy DBs won't have it
            }
            raw_params = row["required_params"]
            if raw_params:
                try:
                    entry["required_params"] = json.loads(raw_params)
                except json.JSONDecodeError:
                    entry["required_params"] = []
            if row["notes"]:
                entry["notes"] = row["notes"]
            mappings[row["field_name"]] = entry
        
        return mappings
    
    def needs_refresh(self, days: int = 365) -> bool:
        """Check if field mappings need refresh (older than N days)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MIN(last_verified) as oldest 
            FROM field_mappings
        """)
        
        oldest = cursor.fetchone()["oldest"]
        if not oldest:
            return True
        
        oldest_date = datetime.fromisoformat(oldest)
        age_days = (datetime.now() - oldest_date).days
        
        return age_days > days
    
    def clear_mappings(self):
        """Clear all field mappings (for fresh discovery)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM field_mappings")
        self.conn.commit()
        logger.info("Cleared all field mappings")
    
    def close(self):
        """Close database connection"""
        self.conn.close()
