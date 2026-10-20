"""
Canvas Field Registry - Read-only access to discovered fields.

Queries the canvas_fields.db populated by scripts/discover_canvas_fields.py.
NO HARDCODING - all fields come from the database.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

# Database path - configurable via env var for EFS in production
DB_PATH = Path(os.getenv('CANVAS_FIELDS_DB_PATH', str(Path(__file__).parent / "data" / "canvas_fields.db")))


class CanvasFieldRegistry:
    """Read-only registry for querying discovered fields."""
    
    # Alias mapping for backward compatibility
    # 'market' is the canonical name, but database may contain 'macro' from older field_mappings
    OBJECT_TYPE_ALIASES = {
        "market": ["macro"],  # 'market' should also match 'macro' in DB
    }

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Canvas fields database not found at {self.db_path}. "
                "Run scripts/discover_canvas_fields.py to populate it."
            )
    
    def _get_object_type_variants(self, object_type: str) -> List[str]:
        """Get all variants of an object_type including aliases for backward compatibility."""
        variants = [object_type]
        # Add any aliases (e.g., 'market' -> also search 'macro')
        if object_type in self.OBJECT_TYPE_ALIASES:
            variants.extend(self.OBJECT_TYPE_ALIASES[object_type])
        return variants

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def list_fields(
        self,
        source: Optional[str] = None,
        endpoint: Optional[str] = None,
        object_type: Optional[str] = None,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List available fields with optional filtering.

        Args:
            source: Filter by source (fmp, polygon, uw)
            endpoint: Filter by endpoint name
            object_type: Filter by object type (equity, etf, crypto, forex, etc.)
            category: Filter by category (Valuation, Fundamentals, etc.)
            query: Search field names (case-insensitive)
            limit: Max results
            offset: Pagination offset

        Returns:
            List of field dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = "SELECT field_name, endpoint, source, field_type, required_params, object_type, category FROM fields WHERE 1=1"
        params: List[Any] = []

        if source:
            sql += " AND source = ?"
            params.append(source)

        if endpoint:
            sql += " AND endpoint = ?"
            params.append(endpoint)

        if object_type:
            # object_type can be comma-separated (e.g., "equity,etf")
            # We need to find rows where the object_type column contains this type
            # Also handle aliases (e.g., 'market' should match 'macro' for backward compatibility)
            variants = self._get_object_type_variants(object_type)
            conditions = []
            for variant in variants:
                conditions.append("(object_type = ? OR object_type LIKE ? OR object_type LIKE ? OR object_type LIKE ?)")
                params.extend([
                    variant,                      # exact match
                    f"{variant},%",               # starts with
                    f"%,{variant},%",             # in middle
                    f"%,{variant}",               # ends with
                ])
            sql += f" AND ({' OR '.join(conditions)})"

        if category:
            sql += " AND category = ?"
            params.append(category)

        if query:
            sql += " AND LOWER(field_name) LIKE ?"
            params.append(f"%{query.lower()}%")

        sql += " ORDER BY category, endpoint, field_name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, tuple(params))

        results = []
        for row in cursor.fetchall():
            req_params = None
            if row["required_params"]:
                try:
                    req_params = json.loads(row["required_params"])
                    # Filter out apikey from displayed params
                    if isinstance(req_params, list):
                        req_params = [p for p in req_params if p.lower() != "apikey"]
                except json.JSONDecodeError:
                    pass

            results.append({
                "field": row["field_name"],
                "endpoint": row["endpoint"],
                "source": row["source"],
                "type": row["field_type"],
                "required_params": req_params,
                "object_type": row["object_type"],
                "category": row["category"],
            })

        conn.close()
        return results

    def search_fields(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search fields by name.

        Args:
            query: Search string
            sources: Optional list of sources to filter (fmp, polygon, uw)
            limit: Max results

        Returns:
            List of matching fields
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = "SELECT field_name, endpoint, source, field_type FROM fields WHERE LOWER(field_name) LIKE ?"
        params: List[Any] = [f"%{query.lower()}%"]

        if sources:
            placeholders = ",".join(["?"] * len(sources))
            sql += f" AND source IN ({placeholders})"
            params.extend(sources)

        sql += " ORDER BY field_name ASC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, tuple(params))

        results = []
        for row in cursor.fetchall():
            results.append({
                "field": row["field_name"],
                "endpoint": row["endpoint"],
                "source": row["source"],
                "type": row["field_type"],
            })

        conn.close()
        return results

    def get_endpoints(self, source: Optional[str] = None) -> List[str]:
        """Get list of unique endpoints."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if source:
            cursor.execute(
                "SELECT DISTINCT endpoint FROM fields WHERE source = ? ORDER BY endpoint",
                (source,),
            )
        else:
            cursor.execute("SELECT DISTINCT endpoint FROM fields ORDER BY endpoint")

        endpoints = [row["endpoint"] for row in cursor.fetchall()]
        conn.close()
        return endpoints

    def get_fields_for_endpoint(self, endpoint: str) -> List[str]:
        """Get all field names for a specific endpoint."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT field_name FROM fields WHERE endpoint = ? ORDER BY field_name",
            (endpoint,),
        )

        fields = [row["field_name"] for row in cursor.fetchall()]
        conn.close()
        return fields

    def get_categories_for_object_type(self, object_type: str) -> List[Dict[str, Any]]:
        """
        Get all available categories for an object type with field counts.

        Args:
            object_type: The object type (equity, etf, crypto, etc.)

        Returns:
            List of categories with name and field count
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Find categories where the object_type matches (including aliases)
        variants = self._get_object_type_variants(object_type)
        conditions = []
        params: List[Any] = []
        for variant in variants:
            conditions.append("(object_type = ? OR object_type LIKE ? OR object_type LIKE ? OR object_type LIKE ?)")
            params.extend([
                variant,
                f"{variant},%",
                f"%,{variant},%",
                f"%,{variant}",
            ])
        
        cursor.execute(f"""
            SELECT category, COUNT(*) as field_count, COUNT(DISTINCT endpoint) as endpoint_count
            FROM fields 
            WHERE {' OR '.join(conditions)}
            GROUP BY category
            ORDER BY field_count DESC
        """, tuple(params))

        results = []
        for row in cursor.fetchall():
            results.append({
                "category": row["category"],
                "field_count": row["field_count"],
                "endpoint_count": row["endpoint_count"],
            })

        conn.close()
        return results

    def get_fields_grouped(
        self,
        object_type: str,
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Get all fields for an object type grouped by category -> endpoint.

        Returns structure:
        {
            "Valuation": {
                "ratios-ttm": [
                    {"field": "pe", "type": "float", "required_params": ["date"]},
                    ...
                ],
                "key-metrics": [...],
            },
            "Fundamentals": {...},
            ...
        }
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Handle aliases (e.g., 'market' should also match 'macro' for backward compatibility)
        variants = self._get_object_type_variants(object_type)
        conditions = []
        params: List[Any] = []
        for variant in variants:
            conditions.append("(object_type = ? OR object_type LIKE ? OR object_type LIKE ? OR object_type LIKE ?)")
            params.extend([
                variant,
                f"{variant},%",
                f"%,{variant},%",
                f"%,{variant}",
            ])

        cursor.execute(f"""
            SELECT field_name, endpoint, source, field_type, required_params, category, structure_type
            FROM fields 
            WHERE {' OR '.join(conditions)}
            ORDER BY category, endpoint, field_name
        """, tuple(params))

        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        for row in cursor.fetchall():
            category = row["category"] or "Other"
            endpoint = row["endpoint"]

            if category not in grouped:
                grouped[category] = {}
            if endpoint not in grouped[category]:
                grouped[category][endpoint] = []

            req_params = None
            if row["required_params"]:
                try:
                    req_params = json.loads(row["required_params"])
                    if isinstance(req_params, list):
                        req_params = [p for p in req_params if p.lower() != "apikey"]
                except json.JSONDecodeError:
                    pass

            grouped[category][endpoint].append({
                "field": row["field_name"],
                "type": row["field_type"],
                "source": row["source"],
                "required_params": req_params,
                "structure_type": row["structure_type"],
            })

        conn.close()
        return grouped

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the field registry."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total fields
        cursor.execute("SELECT COUNT(*) as total FROM fields")
        total = cursor.fetchone()["total"]

        # By source
        cursor.execute(
            "SELECT source, COUNT(*) as count FROM fields GROUP BY source ORDER BY count DESC"
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        # By object type
        cursor.execute(
            "SELECT object_type, COUNT(*) as count FROM fields GROUP BY object_type ORDER BY count DESC"
        )
        by_object_type = {row["object_type"]: row["count"] for row in cursor.fetchall()}

        # By category
        cursor.execute(
            "SELECT category, COUNT(*) as count FROM fields GROUP BY category ORDER BY count DESC"
        )
        by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

        # Unique endpoints
        cursor.execute("SELECT COUNT(DISTINCT endpoint) as count FROM fields")
        unique_endpoints = cursor.fetchone()["count"]

        conn.close()

        return {
            "total_fields": total,
            "by_source": by_source,
            "by_object_type": by_object_type,
            "by_category": by_category,
            "unique_endpoints": unique_endpoints,
        }

    def get_endpoints_by_compatibility_group(self, group: str) -> List[str]:
        """Get all endpoints in a compatibility group."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT endpoint FROM fields WHERE compatibility_group = ? ORDER BY endpoint",
            (group,)
        )
        endpoints = [row["endpoint"] for row in cursor.fetchall()]
        conn.close()
        return endpoints

    def check_compatibility(self, endpoints: List[str]) -> Dict[str, Any]:
        """
        Check if a list of endpoints are compatible for merging.
        
        Returns:
            {
                "compatible": bool,
                "group": str (if all same group),
                "groups": list (if multiple groups),
                "reason": str (if not compatible)
            }
        """
        if len(endpoints) <= 1:
            return {"compatible": True, "group": None}
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        groups = {}
        for ep in endpoints:
            cursor.execute(
                "SELECT DISTINCT compatibility_group FROM fields WHERE endpoint = ?",
                (ep,)
            )
            row = cursor.fetchone()
            if row and row["compatibility_group"]:
                groups[ep] = row["compatibility_group"]
            else:
                groups[ep] = "unknown"
        
        conn.close()
        
        unique_groups = set(groups.values())
        
        if len(unique_groups) == 1:
            return {"compatible": True, "group": list(unique_groups)[0]}
        else:
            return {
                "compatible": False,
                "groups": list(unique_groups),
                "endpoints_by_group": {
                    g: [ep for ep, grp in groups.items() if grp == g]
                    for g in unique_groups
                },
                "reason": f"Endpoints span {len(unique_groups)} incompatible groups: {unique_groups}"
            }

    def get_endpoint_metadata(self, endpoint: str) -> Dict[str, Any]:
        """
        Get compatibility metadata for an endpoint.
        
        Returns:
            {
                "endpoint": str,
                "structure_type": str,
                "compatibility_group": str,
                "time_key": str or None,
                "cardinality": str,
                "required_params": list
            }
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT DISTINCT endpoint, structure_type, compatibility_group, time_key, cardinality, required_params, source
               FROM fields WHERE endpoint = ? LIMIT 1""",
            (endpoint,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {
                "endpoint": endpoint,
                "structure_type": "unknown",
                "compatibility_group": "unknown",
                "time_key": None,
                "cardinality": "single",
                "required_params": [],
                "source": "unknown",
            }
        
        # Parse required_params from JSON string
        required_params = []
        if row["required_params"]:
            try:
                required_params = json.loads(row["required_params"])
                if isinstance(required_params, list):
                    required_params = [p.lower() for p in required_params if p.lower() != "apikey"]
            except json.JSONDecodeError:
                pass
        
        return {
            "endpoint": row["endpoint"],
            "structure_type": row["structure_type"],
            "required_params": required_params,
            "source": row["source"],
            "compatibility_group": row["compatibility_group"],
            "time_key": row["time_key"],
            "cardinality": row["cardinality"],
        }

    def get_endpoints_metadata(self, endpoints: List[str]) -> List[Dict[str, Any]]:
        """Get compatibility metadata for multiple endpoints."""
        return [self.get_endpoint_metadata(ep) for ep in endpoints]


# Singleton instance
_registry: Optional[CanvasFieldRegistry] = None


def get_field_registry() -> CanvasFieldRegistry:
    """Get or create the singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = CanvasFieldRegistry()
    return _registry

