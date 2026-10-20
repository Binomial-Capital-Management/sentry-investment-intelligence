"""
003_portfolios_chats_ext

Revision ID: 1bdda4ace4ac
Revises: beea6bc04481
Create Date: 2025-12-31T16:05:17.178857

Original SQL file: 003_portfolios_chats_ext.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1bdda4ace4ac"
down_revision = "beea6bc04481"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 003_portfolios_chats_ext.sql."""
    op.execute("""
-- Migration 003: Portfolio defaults, chat titles, message metadata
-- Adds missing columns and indexes to support Portfolio CRUD and Chat threading

-- Portfolios: add is_default flag
ALTER TABLE IF EXISTS portfolios
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE;

-- Index to quickly fetch default per user
CREATE INDEX IF NOT EXISTS idx_portfolios_default
    ON portfolios(user_id)
    WHERE is_default = TRUE;

-- Chat sessions: add optional title
ALTER TABLE IF EXISTS chat_sessions
    ADD COLUMN IF NOT EXISTS title VARCHAR(255);

-- Chat messages: add metadata JSONB for portfolio references and others
ALTER TABLE IF EXISTS chat_messages
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Ensure created_at/updated_at columns exist where referenced in code
-- (chat_sessions.updated_at is already created in 001; triggers exist)

-- No RLS policy changes required; existing policies apply to new columns.

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
