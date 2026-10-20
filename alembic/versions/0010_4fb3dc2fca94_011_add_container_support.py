"""
011_add_container_support

Revision ID: 4fb3dc2fca94
Revises: 110e66f72e0b
Create Date: 2025-12-31T16:05:17.184166

Original SQL file: 011_add_container_support.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4fb3dc2fca94"
down_revision = "110e66f72e0b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 011_add_container_support.sql."""
    op.execute("""
-- Migration 011: Add container persistence for Code Interpreter
-- Adds container_id column to chat_sessions for OpenAI container persistence

-- Add container_id to chat_sessions for Code Interpreter persistence
ALTER TABLE IF EXISTS chat_sessions
    ADD COLUMN IF NOT EXISTS container_id VARCHAR(255);

-- Index for container lookups
CREATE INDEX IF NOT EXISTS idx_chat_sessions_container
    ON chat_sessions(container_id);
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
