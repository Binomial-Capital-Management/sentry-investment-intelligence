"""
029_email_lists

Revision ID: 3f5b05c0522a
Revises: b2ce93173212
Create Date: 2025-12-31T16:05:17.193382

Original SQL file: 029_email_lists.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3f5b05c0522a"
down_revision = "b2ce93173212"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 029_email_lists.sql."""
    op.execute("""
-- Migration: Email Lists for Reusable Recipients
-- Description: Add email_lists table for users to save reusable recipient groups
-- Author: Claude
-- Date: 2025-11-05

-- Create email_lists table
CREATE TABLE IF NOT EXISTS email_lists (
    id UUID PRIMARY KEY DEFAULT generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    recipients JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT email_lists_name_length CHECK (char_length(name) >= 1 AND char_length(name) <= 100),
    CONSTRAINT email_lists_desc_length CHECK (description IS NULL OR char_length(description) <= 500),
    CONSTRAINT email_lists_unique_name UNIQUE (user_id, name)
);

-- Enable Row Level Security
ALTER TABLE email_lists ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their own email lists
CREATE POLICY email_lists_isolation ON email_lists
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Create indexes for performance
CREATE INDEX idx_email_lists_user_id ON email_lists(user_id);
CREATE INDEX idx_email_lists_name ON email_lists(user_id, name);
CREATE INDEX idx_email_lists_created_at ON email_lists(created_at DESC);

-- Add updated_at trigger
CREATE TRIGGER update_email_lists_updated_at
    BEFORE UPDATE ON email_lists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (RLS enforces access control)
GRANT SELECT, INSERT, UPDATE, DELETE ON email_lists TO PUBLIC;

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
