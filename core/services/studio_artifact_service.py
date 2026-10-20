"""
Studio Artifact Service Layer

Handles persistence of studio-generated artifacts (mindmaps, reports, data tables).
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import json
import logging

logger = logging.getLogger(__name__)


def _parse_uuid_or_none(value: str) -> Optional[UUID]:
    """Parse string to UUID or return None for legacy IDs."""
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return None


class StudioArtifactService:
    """Service layer for studio artifact operations with RLS enforcement."""

    def __init__(self):
        pass

    async def save_artifact(
        self,
        user_id: str,
        session_id: str,
        artifact_type: str,
        content: Dict[str, Any],
        title: Optional[str] = None,
        description: Optional[str] = None,
        format: Optional[str] = None,
        source_note_ids: Optional[List[str]] = None,
        org_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a generated artifact.

        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID
            artifact_type: 'mindmap', 'report', or 'datatable'
            content: The artifact content (JSON for mindmap/datatable, dict with markdown for report)
            title: Optional title
            description: Original generation prompt
            format: Generation format (e.g., 'detailed', 'executive')
            source_note_ids: List of memory note IDs used as context
            org_id: Optional organization ID

        Returns:
            Dict with saved artifact info
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict

        config = get_config()

        if not user_id:
            return {"status": "error", "message": "User ID required"}

        if not config.enable_postgres:
            return {"status": "skipped", "message": "Postgres disabled", "id": None}

        session_uuid = _parse_uuid_or_none(session_id)
        if session_uuid is None:
            return {"status": "error", "message": "Invalid session ID format"}

        try:
            pg = await get_postgres_rls_client()

            # Parse source note IDs to UUIDs
            source_uuids = None
            if source_note_ids:
                source_uuids = [
                    _parse_uuid_or_none(sid) for sid in source_note_ids if _parse_uuid_or_none(sid)
                ]

            async with pg.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO studio_artifacts (
                        session_id, user_id, org_id, type, title, content,
                        description, format, source_note_ids
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING *
                """,
                    session_uuid,
                    user_id,
                    org_id,
                    artifact_type,
                    title,
                    json.dumps(content),
                    description,
                    format,
                    source_uuids,
                )

            return {"status": "success", "artifact": record_to_dict(row)}

        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
            return {"status": "error", "message": str(e)}

    async def get_session_artifacts(
        self, user_id: str, session_id: str, artifact_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get all artifacts for a session.

        Args:
            user_id: User ID for RLS context
            session_id: Chat session UUID
            artifact_type: Optional filter by type

        Returns:
            Dict with artifacts list
        """
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict

        config = get_config()

        if not user_id:
            return {"status": "error", "message": "User ID required"}

        if not config.enable_postgres:
            return {"status": "success", "artifacts": [], "session_id": session_id}

        session_uuid = _parse_uuid_or_none(session_id)
        if session_uuid is None:
            return {"status": "success", "artifacts": [], "session_id": session_id}

        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_user_context(user_id) as conn:
                if artifact_type:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM studio_artifacts
                        WHERE session_id = $1 AND type = $2
                        ORDER BY created_at DESC
                    """,
                        session_uuid,
                        artifact_type,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM studio_artifacts
                        WHERE session_id = $1
                        ORDER BY created_at DESC
                    """,
                        session_uuid,
                    )

            artifacts = [record_to_dict(row) for row in rows]

            return {
                "status": "success",
                "session_id": session_id,
                "artifacts": artifacts,
                "total_count": len(artifacts),
            }

        except Exception as e:
            logger.error(f"Failed to get artifacts: {e}")
            return {"status": "error", "message": str(e)}

    async def get_artifact(self, user_id: str, artifact_id: str) -> Dict[str, Any]:
        """Get a single artifact by ID."""
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict

        config = get_config()

        if not config.enable_postgres:
            return {"status": "error", "message": "Postgres disabled"}

        artifact_uuid = _parse_uuid_or_none(artifact_id)
        if artifact_uuid is None:
            return {"status": "error", "message": "Invalid artifact ID"}

        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_user_context(user_id) as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM studio_artifacts WHERE id = $1
                """,
                    artifact_uuid,
                )

            if not row:
                return {"status": "error", "message": "Artifact not found"}

            return {"status": "success", "artifact": record_to_dict(row)}

        except Exception as e:
            logger.error(f"Failed to get artifact: {e}")
            return {"status": "error", "message": str(e)}

    async def delete_artifact(self, user_id: str, artifact_id: str) -> Dict[str, Any]:
        """Delete an artifact by ID."""
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config

        config = get_config()

        if not config.enable_postgres:
            return {"status": "error", "message": "Postgres disabled"}

        artifact_uuid = _parse_uuid_or_none(artifact_id)
        if artifact_uuid is None:
            return {"status": "error", "message": "Invalid artifact ID"}

        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_user_context(user_id) as conn:
                result = await conn.execute(
                    """
                    DELETE FROM studio_artifacts WHERE id = $1
                """,
                    artifact_uuid,
                )

            deleted = result.split()[-1] != "0"

            return {"status": "success" if deleted else "not_found", "deleted": deleted}

        except Exception as e:
            logger.error(f"Failed to delete artifact: {e}")
            return {"status": "error", "message": str(e)}

    async def update_artifact(
        self,
        user_id: str,
        artifact_id: str,
        title: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update an artifact's title or content."""
        from core.database.postgres_client import get_postgres_rls_client
        from core.config import get_config
        from core.utils.dto_utils import record_to_dict

        config = get_config()

        if not config.enable_postgres:
            return {"status": "error", "message": "Postgres disabled"}

        artifact_uuid = _parse_uuid_or_none(artifact_id)
        if artifact_uuid is None:
            return {"status": "error", "message": "Invalid artifact ID"}

        try:
            pg = await get_postgres_rls_client()

            async with pg.acquire_with_user_context(user_id) as conn:
                if title is not None and content is not None:
                    row = await conn.fetchrow(
                        """
                        UPDATE studio_artifacts
                        SET title = $2, content = $3
                        WHERE id = $1
                        RETURNING *
                    """,
                        artifact_uuid,
                        title,
                        json.dumps(content),
                    )
                elif title is not None:
                    row = await conn.fetchrow(
                        """
                        UPDATE studio_artifacts SET title = $2 WHERE id = $1 RETURNING *
                    """,
                        artifact_uuid,
                        title,
                    )
                elif content is not None:
                    row = await conn.fetchrow(
                        """
                        UPDATE studio_artifacts SET content = $2 WHERE id = $1 RETURNING *
                    """,
                        artifact_uuid,
                        json.dumps(content),
                    )
                else:
                    return {"status": "error", "message": "Nothing to update"}

            if not row:
                return {"status": "error", "message": "Artifact not found"}

            return {"status": "success", "artifact": record_to_dict(row)}

        except Exception as e:
            logger.error(f"Failed to update artifact: {e}")
            return {"status": "error", "message": str(e)}


# Singleton instance
_service_instance: Optional[StudioArtifactService] = None


def get_studio_artifact_service() -> StudioArtifactService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = StudioArtifactService()
    return _service_instance
