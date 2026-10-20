"""
037_cascade_delete_orphaned_broker_connections

Revision ID: b9e44963a742
Revises: b4c1eee58910
Create Date: 2025-12-31T16:05:17.196388

Original SQL file: 037_cascade_delete_orphaned_broker_connections.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b9e44963a742"
down_revision = "b4c1eee58910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 037_cascade_delete_orphaned_broker_connections.sql."""
    op.execute("""
-- Migration 037: Cascade delete orphaned broker connections
-- Purpose: When IBKR portfolio is deleted, delete broker connection if no other portfolios reference it
-- Date: 2025-11-12

-- Create function to delete orphaned broker connections
CREATE OR REPLACE FUNCTION delete_orphaned_broker_connection()
RETURNS TRIGGER AS $$
BEGIN
    -- Only proceed if the deleted portfolio had a broker connection
    IF OLD.broker_connection_id IS NOT NULL THEN
        -- Check if any other portfolios reference this broker connection
        IF NOT EXISTS (
            SELECT 1 FROM portfolios
            WHERE broker_connection_id = OLD.broker_connection_id
            AND id != OLD.id
        ) THEN
            -- No other portfolios reference this connection - delete it
            DELETE FROM broker_connections
            WHERE id = OLD.broker_connection_id;

            RAISE NOTICE 'Deleted orphaned broker connection %', OLD.broker_connection_id;
        END IF;
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to run after portfolio deletion
CREATE TRIGGER cleanup_orphaned_broker_connections
AFTER DELETE ON portfolios
FOR EACH ROW
EXECUTE FUNCTION delete_orphaned_broker_connection();

-- Add comment for documentation
COMMENT ON FUNCTION delete_orphaned_broker_connection IS 'Automatically deletes broker_connections when their last portfolio is deleted';
COMMENT ON TRIGGER cleanup_orphaned_broker_connections ON portfolios IS 'Cascade deletes broker connection when last portfolio is deleted';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
