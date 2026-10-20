"""
064_fix_canvas_processes_fk

Revision ID: e462aa469f11
Revises: 7f5022a80271
Create Date: 2025-12-31T16:05:17.209389

Original SQL file: 064_fix_canvas_processes_fk.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e462aa469f11"
down_revision = "7f5022a80271"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 064_fix_canvas_processes_fk.sql."""
    op.execute("""
-- Migration 064: Remove foreign key constraint from canvas_processes
-- The FK to users(id) was incorrect - users.id is UUID, user_id is TEXT
-- Following the same pattern as portfolio_postmortems (no FK on user_id)

ALTER TABLE canvas_processes 
DROP CONSTRAINT IF EXISTS canvas_processes_user_id_fkey;

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
