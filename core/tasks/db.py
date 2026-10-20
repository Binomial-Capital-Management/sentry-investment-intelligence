"""
Database access layer for tasks.
Provides RLS-safe CRUD operations and run lifecycle helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from asyncpg import Record

from core.database.postgres_client import get_postgres_rls_client
from core.tasks.types import (
    TaskDefinition,
    TaskRecord,
    TaskRunRecord,
    TaskRunStatus,
    TaskScheduleConfig,
    TaskDeliveryConfig,
    CanvasData,
    TaskStatus,
    TaskTriggerType,
    TaskRunHistoryItem,
    TaskSavedOutputRecord,
)
from core.workflows.engine import truncate_output


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str)


class TasksRepository:
    """RLS-aware helper for tasks and task runs."""

    def __init__(self):
        self.pg = None

    async def _pg(self):
        if not self.pg:
            self.pg = await get_postgres_rls_client()
        return self.pg

    # ===== Task CRUD =====

    async def create_task(self, user_id: str, payload: Dict[str, Any], org_id: Optional[str] = None) -> TaskRecord:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (
                    user_id, org_id, name, description, status,
                    schedule_config, delivery_config, metadata,
                    canvas_data, agent_config, next_run_at, last_run_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6::jsonb, $7::jsonb, $8::jsonb,
                    $9::jsonb, $10::jsonb, $11, $12
                )
                RETURNING *
                """,
                user_id,
                org_id,
                payload["name"],
                payload.get("description"),
                payload.get("status", TaskStatus.DRAFT.value),
                _json(payload["schedule_config"]),
                _json(payload["delivery_config"]),
                _json(payload.get("metadata", {})),
                _json(payload["canvas_data"]),
                _json(payload["agent_config"]),
                payload.get("next_run_at"),
                payload.get("last_run_at"),
            )
        return self._record_from_row(row)

    async def update_task(
        self,
        user_id: str,
        task_id: str,
        payload: Dict[str, Any],
        org_id: Optional[str] = None
    ) -> TaskRecord:
        if not payload:
            raise ValueError("No fields to update")

        pg = await self._pg()
        fields = []
        values = []
        for key, value in payload.items():
            if key in {"schedule_config", "delivery_config", "metadata", "canvas_data", "agent_config"}:
                fields.append(f"{key} = ${len(values) + 1}::jsonb")
                values.append(_json(value))
            else:
                fields.append(f"{key} = ${len(values) + 1}")
                values.append(value)

        query = f"""
            UPDATE tasks
            SET {', '.join(fields)}, updated_at = NOW()
            WHERE id = ${len(values) + 1}
              AND (org_id IS NOT DISTINCT FROM ${len(values) + 2})
            RETURNING *
        """
        values.append(task_id)
        values.append(org_id)

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(query, *values)
            if not row:
                raise ValueError("Task not found or not owned by user")
        return self._record_from_row(row)

    async def list_tasks(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        org_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> List[TaskRecord]:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            params = [limit, offset]
            where_clauses = ["1=1"]

            if status:
                where_clauses.append(f"status = ${len(params) + 1}")
                params.append(status.value)
            if org_id is not None:
                where_clauses.append(f"org_id IS NOT DISTINCT FROM ${len(params) + 1}")
                params.append(org_id)

            query = f"""
                SELECT *
                FROM tasks
                WHERE {' AND '.join(where_clauses)}
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """

            rows = await conn.fetch(query, *params)
        return [self._record_from_row(row) for row in rows]

    async def get_task(self, user_id: str, task_id: str, org_id: Optional[str] = None) -> TaskRecord:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM tasks
                WHERE id = $1
                  AND (org_id IS NOT DISTINCT FROM $2)
                """,
                task_id,
                org_id,
            )
            if not row:
                raise ValueError("Task not found or not owned by user")
        return self._record_from_row(row)

    async def delete_task(self, user_id: str, task_id: str, org_id: Optional[str] = None) -> None:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            result = await conn.execute(
                """
                DELETE FROM tasks
                WHERE id = $1
                  AND (org_id IS NOT DISTINCT FROM $2)
                """,
                task_id,
                org_id,
            )
        if result == "DELETE 0":
            raise ValueError("Task not found or not owned by user")

    async def toggle_task_status(self, user_id: str, task_id: str, org_id: Optional[str] = None) -> TaskRecord:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                UPDATE tasks
                SET status = CASE
                    WHEN status = 'active' THEN 'paused'
                    WHEN status = 'paused' THEN 'active'
                    ELSE status
                END,
                updated_at = NOW()
                WHERE id = $1
                  AND (org_id IS NOT DISTINCT FROM $2)
                RETURNING *
                """,
                task_id,
                org_id,
            )
            if not row:
                raise ValueError("Task not found or not owned by user")
        return self._record_from_row(row)

    async def update_next_run(self, user_id: str, task_id: str, next_run_at, last_run_at, org_id: Optional[str] = None) -> None:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET next_run_at = $1,
                    last_run_at = $2,
                    updated_at = NOW()
                WHERE id = $3
                  AND (org_id IS NOT DISTINCT FROM $4)
                """,
                next_run_at,
                last_run_at,
                task_id,
                org_id,
            )

    # ===== Task Runs =====

    async def create_run(
        self,
        task_id: str,
        user_id: str,
        trigger_type: TaskTriggerType,
        org_id: Optional[str] = None
    ) -> TaskRunRecord:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO task_runs (
                    task_id, user_id, org_id, status, trigger_type,
                    input_snapshot, result, delivery_results
                ) VALUES (
                    $1, $2, $3, 'queued', $4, '{}'::jsonb, NULL, NULL
                )
                RETURNING *
                """,
                task_id,
                user_id,
                org_id,
                trigger_type.value,
            )
        return self._run_from_row(row)

    async def mark_run_status(
        self,
        run_id: str,
        user_id: str,
        status: TaskRunStatus,
        *,
        result: Optional[Dict[str, Any]] = None,
        delivery_results: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> None:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute(
                """
                UPDATE task_runs
                SET status = $1,
                    result = $2::jsonb,
                    delivery_results = $3::jsonb,
                    error_message = $4,
                    updated_at = NOW(),
                    started_at = COALESCE(started_at, NOW()),
                    completed_at = CASE
                        WHEN $1 IN ('completed', 'failed', 'cancelled') THEN NOW()
                        ELSE completed_at
                    END
                WHERE id = $5
                  AND (org_id IS NOT DISTINCT FROM $6)
                """,
                status.value,
                _json(result) if result is not None else None,
                _json(delivery_results) if delivery_results is not None else None,
                error_message,
                run_id,
                org_id,
            )

    async def list_runs(self, user_id: str, task_id: str, limit: int = 50, org_id: Optional[str] = None) -> List[TaskRunRecord]:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM task_runs
                WHERE task_id = $1
                  AND (org_id IS NOT DISTINCT FROM $3)
                ORDER BY created_at DESC
                LIMIT $2
                """,
                task_id,
                limit,
                org_id,
            )
        return [self._run_from_row(row) for row in rows]

    async def get_run(self, user_id: str, run_id: str, org_id: Optional[str] = None) -> TaskRunRecord:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM task_runs
                WHERE id = $1
                  AND (org_id IS NOT DISTINCT FROM $2)
                """,
                run_id,
                org_id,
            )
            if not row:
                raise ValueError("Task run not found or not owned by user")
        return self._run_from_row(row)

    async def save_run_output(
        self,
        user_id: str,
        task_id: str,
        run_id: str,
        *,
        output: Any = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        delivery_metadata: Optional[Dict[str, Any]] = None,
        org_id: Optional[str] = None
    ) -> None:
        """
        Persist the final output of a task run so the history tab can display it.
        Stores a single row per run_id (later inserts replace existing data).
        """
        pg = await self._pg()
        sanitized_output = truncate_output(output)
        artifacts_payload = artifacts or []
        metadata_payload = delivery_metadata or {}

        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            await conn.execute(
                "DELETE FROM task_saved_outputs WHERE task_run_id = $1",
                run_id,
            )
            await conn.execute(
                """
                INSERT INTO task_saved_outputs (
                    task_run_id,
                    task_id,
                    user_id,
                    output,
                    artifacts,
                    delivery_metadata
                ) VALUES (
                    $1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb
                )
                """,
                run_id,
                task_id,
                user_id,
                _json(sanitized_output) if sanitized_output is not None else None,
                _json(artifacts_payload),
                _json(metadata_payload),
            )

    async def list_run_history(
        self,
        user_id: str,
        task_id: str,
        limit: int = 50,
        org_id: Optional[str] = None
    ) -> List[TaskRunHistoryItem]:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            run_rows = await conn.fetch(
                """
                SELECT *
                FROM task_runs
                WHERE task_id = $1 AND user_id = $2
                  AND (org_id IS NOT DISTINCT FROM $4)
                ORDER BY created_at DESC
                LIMIT $3
                """,
                task_id,
                user_id,
                limit,
                org_id,
            )
            runs = [self._run_from_row(row) for row in run_rows]
            if not runs:
                return []

            run_ids = [str(row["id"]) for row in run_rows]
            saved_rows = []
            if run_ids:
                saved_rows = await conn.fetch(
                    """
                    SELECT tso.*
                    FROM task_saved_outputs tso
                    JOIN tasks t ON t.id = tso.task_id
                    WHERE task_run_id = ANY($1::uuid[])
                      AND tso.user_id = $2
                      AND ($3::text IS NULL OR t.org_id IS NOT DISTINCT FROM $3)
                    """,
                    run_ids,
                    user_id,
                    org_id,
                )

        saved_map = {
            str(row["task_run_id"]): self._saved_output_from_row(row)
            for row in saved_rows
        }
        return [
            TaskRunHistoryItem(
                run=run,
                saved_output=saved_map.get(run.id),
            )
            for run in runs
        ]

    async def get_run_history_entry(
        self,
        user_id: str,
        run_id: str,
        org_id: Optional[str] = None
    ) -> TaskRunHistoryItem:
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            run_row = await conn.fetchrow(
                """
                SELECT *
                FROM task_runs
                WHERE id = $1
                  AND (org_id IS NOT DISTINCT FROM $2)
                """,
                run_id,
                org_id,
            )
            if not run_row:
                raise ValueError("Task run not found or not owned by user")

            saved_row = await conn.fetchrow(
                """
                SELECT tso.*
                FROM task_saved_outputs tso
                JOIN tasks t ON t.id = tso.task_id
                WHERE task_run_id = $1
                  AND ($2::text IS NULL OR t.org_id IS NOT DISTINCT FROM $2)
                """,
                run_id,
                org_id,
            )

        return TaskRunHistoryItem(
            run=self._run_from_row(run_row),
            saved_output=self._saved_output_from_row(saved_row) if saved_row else None,
        )

    async def find_artifact_by_filename(
        self,
        user_id: str,
        filename: str,
        org_id: Optional[str] = None,
    ) -> bool:
        """
        Verify that an artifact filename belongs to the requesting user/org.
        """
        pg = await self._pg()
        async with pg.acquire_with_org_context(user_id, org_id) as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM task_saved_outputs tso
                JOIN tasks t ON t.id = tso.task_id
                WHERE tso.user_id = $1
                  AND ($2::text IS NULL OR t.org_id IS NOT DISTINCT FROM $2)
                  AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(COALESCE(tso.artifacts, '[]'::jsonb)) elem
                    WHERE elem ->> 'filename' = $3
                  )
                LIMIT 1
                """,
                user_id,
                org_id,
                filename,
            )
            return row is not None

    # ===== Row Parsing =====

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        """Handle JSONB columns - parse if string, use directly if dict/list"""
        if isinstance(value, str):
            return json.loads(value)
        return value

    def _record_from_row(self, row: Record) -> TaskRecord:
        return TaskRecord(
            id=str(row["id"]),
            user_id=row["user_id"],
            org_id=row.get("org_id", None) if hasattr(row, "get") else row["org_id"] if "org_id" in row else None,
            name=row["name"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            schedule_config=TaskScheduleConfig.model_validate(self._parse_json_field(row["schedule_config"])),
            delivery_config=TaskDeliveryConfig.model_validate(self._parse_json_field(row["delivery_config"])),
            metadata=self._parse_json_field(row["metadata"]) if row["metadata"] else {},
            canvas_data=CanvasData.model_validate(self._parse_json_field(row["canvas_data"])),
            agent_config=TaskDefinition.model_validate(self._parse_json_field(row["agent_config"])),
            next_run_at=row["next_run_at"],
            last_run_at=row["last_run_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _run_from_row(self, row: Record) -> TaskRunRecord:
        return TaskRunRecord(
            id=str(row["id"]),
            task_id=str(row["task_id"]),
            user_id=row["user_id"],
            org_id=row.get("org_id", None) if hasattr(row, "get") else row["org_id"] if "org_id" in row else None,
            status=TaskRunStatus(row["status"]),
            trigger_type=TaskTriggerType(row["trigger_type"]),
            input_snapshot=self._parse_json_field(row["input_snapshot"]) if row["input_snapshot"] else {},
            result=self._parse_json_field(row["result"]) if row["result"] else None,
            delivery_results=self._parse_json_field(row["delivery_results"]) if row["delivery_results"] else None,
            error_message=row["error_message"],
            execution_time_ms=row["execution_time_ms"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _saved_output_from_row(self, row: Record) -> TaskSavedOutputRecord:
        return TaskSavedOutputRecord(
            id=str(row["id"]),
            task_run_id=str(row["task_run_id"]),
            task_id=str(row["task_id"]),
            user_id=row["user_id"],
            output=self._parse_json_field(row["output"]) if row["output"] else None,
            artifacts=self._parse_json_field(row["artifacts"]) if row["artifacts"] else [],
            delivery_metadata=self._parse_json_field(row["delivery_metadata"]) if row["delivery_metadata"] else {},
            created_at=row["created_at"],
        )
