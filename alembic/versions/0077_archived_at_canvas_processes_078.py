"""
078_archived_at_canvas_processes

Add archived_at column for soft-delete support on canvas_processes.
NULL = active, non-null = archived timestamp.
"""

from alembic import op
import sqlalchemy as sa

revision = "archived_at_canvas_001"
down_revision = "bloomberg_fields_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canvas_processes",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_canvas_processes_archived_at",
        "canvas_processes",
        ["archived_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_canvas_processes_archived_at", table_name="canvas_processes")
    op.drop_column("canvas_processes", "archived_at")
