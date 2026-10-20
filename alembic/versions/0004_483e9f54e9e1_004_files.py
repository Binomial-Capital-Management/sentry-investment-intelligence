"""
004_files

Revision ID: 483e9f54e9e1
Revises: 1bdda4ace4ac
Create Date: 2025-12-31T16:05:17.180160

Original SQL file: 004_files.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "483e9f54e9e1"
down_revision = "1bdda4ace4ac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 004_files.sql."""
    op.execute("""
-- File uploads table with RLS for user separation
-- NO HARDCODING - dynamic schema for any file type

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    original_name TEXT NOT NULL,
    stored_key TEXT NOT NULL, -- S3 key or local path
    content_type TEXT,
    size_bytes BIGINT NOT NULL,
    metadata JSONB DEFAULT '{}', -- Dynamic metadata, no hardcoded fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for user queries
CREATE INDEX idx_files_user_id ON files(user_id);
CREATE INDEX idx_files_created_at ON files(created_at DESC);

-- Enable RLS
ALTER TABLE files ENABLE ROW LEVEL SECURITY;

-- RLS Policies - users can only see their own files
CREATE POLICY files_select_own ON files
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY files_insert_own ON files
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

CREATE POLICY files_update_own ON files
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true))
    WITH CHECK (user_id = current_setting('app.current_user_id', true));

CREATE POLICY files_delete_own ON files
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true));

-- File references in chat messages
CREATE TABLE IF NOT EXISTS message_files (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id, file_id)
);

-- Index for message lookups
CREATE INDEX idx_message_files_message_id ON message_files(message_id);
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
