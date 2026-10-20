"""
028_task_saved_outputs

Revision ID: b2ce93173212
Revises: 50f8c335bf4a
Create Date: 2025-12-31T16:05:17.192166

Original SQL file: 028_task_saved_outputs.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2ce93173212"
down_revision = "50f8c335bf4a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 028_task_saved_outputs.sql."""
    op.execute("""
-- Saved task outputs for history view
CREATE TABLE IF NOT EXISTS task_saved_outputs (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    task_run_id UUID NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    output JSONB,
    artifacts JSONB,
    delivery_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_saved_outputs_task_id
    ON task_saved_outputs(task_id, created_at DESC);

ALTER TABLE task_saved_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_saved_outputs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS task_saved_outputs_isolation ON task_saved_outputs;
CREATE POLICY task_saved_outputs_isolation ON task_saved_outputs
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

DROP TRIGGER IF EXISTS update_task_saved_outputs_updated_at ON task_saved_outputs;
CREATE TRIGGER update_task_saved_outputs_updated_at
    BEFORE UPDATE ON task_saved_outputs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
