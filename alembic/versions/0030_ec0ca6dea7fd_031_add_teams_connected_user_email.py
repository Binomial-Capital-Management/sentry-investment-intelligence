"""
031_add_teams_connected_user_email

Revision ID: ec0ca6dea7fd
Revises: 2ab6a94fdc66
Create Date: 2025-12-31T16:05:17.194388

Original SQL file: 031_add_teams_connected_user_email.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ec0ca6dea7fd"
down_revision = "2ab6a94fdc66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 031_add_teams_connected_user_email.sql."""
    op.execute("""
-- Migration: Add connected_user_email to teams_integrations table
-- Description: Store Microsoft 365 user email from OAuth id_token
-- Date: 2025-01-09

-- Add connected_user_email column
ALTER TABLE teams_integrations
ADD COLUMN IF NOT EXISTS connected_user_email TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_teams_integrations_user_email
    ON teams_integrations(user_id, connected_user_email)
    WHERE connected_user_email IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN teams_integrations.connected_user_email IS 'Microsoft 365 user email from OAuth id_token';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
