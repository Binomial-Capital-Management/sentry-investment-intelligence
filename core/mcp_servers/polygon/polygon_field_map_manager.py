"""
SQLite-backed cache for Polygon field discovery results.

We store discovered field paths along with the dataset and asset metadata to
avoid repeat probing across sessions. The schema is intentionally simple to
remain aligned with the KISS guidance in CODING_RULES.md.
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .polygon_ddc_loader import (
    PolygonAssetClass,
    PolygonAssetGroup,
    PolygonDatasetEntry,
)

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "polygon_field_mappings.db"


class PolygonFieldMapManager:
    """Maintain discovered field metadata in SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        path = db_path or DEFAULT_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS field_mappings (
                field_path TEXT NOT NULL,
                dataset TEXT NOT NULL,
                asset_group TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                sample_type TEXT,
                sample_value TEXT,
                discovered_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                PRIMARY KEY (field_path, dataset, asset_group, asset_class)
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_dataset ON field_mappings(dataset)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_group ON field_mappings(asset_group)"
        )
        cursor.execute("PRAGMA table_info(field_mappings)")
        columns = {row[1] for row in cursor.fetchall()}
        if "required_params" not in columns:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN required_params TEXT")
        if "notes" not in columns:
            cursor.execute("ALTER TABLE field_mappings ADD COLUMN notes TEXT")
        self._conn.commit()

    def save_discovered_fields(
        self,
        dataset: PolygonDatasetEntry,
        fields: Dict[str, Dict[str, Optional[str]]],
    ) -> int:
        """
        Persist newly discovered fields.

        Args:
            dataset: Dataset entry associated with the discovery.
            fields: Mapping of field path to metadata (type/value).

        Returns:
            Number of rows inserted or updated.
        """

        cursor = self._conn.cursor()
        now = datetime.utcnow().isoformat()
        affected = 0

        for path, metadata in fields.items():
            metadata = metadata or {}
            sample_type = metadata.get("type")
            sample_value = metadata.get("value")
            required_params = metadata.get("required_params")
            notes = metadata.get("notes")
            required_json = json.dumps(required_params) if required_params else None

            for group in dataset.asset_group:
                for asset_class in dataset.asset_classes:
                    cursor.execute(
                        """
                        INSERT INTO field_mappings (
                            field_path, dataset, asset_group, asset_class,
                            sample_type, sample_value, required_params, notes,
                            discovered_at, last_seen, hit_count
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(field_path, dataset, asset_group, asset_class)
                        DO UPDATE SET
                            sample_type = COALESCE(excluded.sample_type, field_mappings.sample_type),
                            sample_value = COALESCE(excluded.sample_value, field_mappings.sample_value),
                            required_params = COALESCE(excluded.required_params, field_mappings.required_params),
                            notes = COALESCE(excluded.notes, field_mappings.notes),
                            last_seen = excluded.last_seen,
                            hit_count = field_mappings.hit_count + 1
                        """,
                        (
                            path,
                            dataset.dataset,
                            group.value,
                            asset_class.value,
                            sample_type,
                            sample_value,
                            required_json,
                            notes,
                            now,
                            now,
                        ),
                    )
                    affected += cursor.rowcount

        self._conn.commit()
        return affected

    def list_fields_for_dataset(
        self,
        dataset_name: str,
        asset_group: PolygonAssetGroup,
    ) -> List[Dict[str, str]]:
        """Return cached fields for a specific dataset."""

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT field_path, sample_type, sample_value, required_params, notes, hit_count
            FROM field_mappings
            WHERE dataset = ? AND asset_group = ?
            ORDER BY hit_count DESC, field_path
            """,
            (dataset_name, asset_group.value),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def list_fields_for_asset_class(
        self,
        asset_group: PolygonAssetGroup,
        asset_class: PolygonAssetClass,
    ) -> List[Dict[str, str]]:
        """Return all cached fields for an asset class within an asset group."""

        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT field_path, dataset, sample_type, sample_value, required_params, notes, hit_count
            FROM field_mappings
            WHERE asset_group = ? AND asset_class = ?
            ORDER BY dataset, field_path
            """,
            (asset_group.value, asset_class.value),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def touch_fields(
        self,
        dataset: PolygonDatasetEntry,
        field_paths: Iterable[str],
    ) -> None:
        """Increment hit counts for the provided field paths."""

        cursor = self._conn.cursor()
        now = datetime.utcnow().isoformat()
        for path in field_paths:
            for group in dataset.asset_group:
                cursor.execute(
                    """
                    UPDATE field_mappings
                    SET hit_count = hit_count + 1, last_seen = ?
                    WHERE field_path = ? AND dataset = ? AND asset_group = ?
                    """,
                    (
                        now,
                        path,
                        dataset.dataset,
                        group.value,
                    ),
                )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""

        self._conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        raw_params = result.get("required_params")
        if raw_params:
            try:
                result["required_params"] = json.loads(raw_params)
            except json.JSONDecodeError:
                result["required_params"] = []
        else:
            result["required_params"] = []
        if "notes" not in result:
            result["notes"] = None
        return result


__all__ = ["PolygonFieldMapManager", "DEFAULT_DB_PATH"]
