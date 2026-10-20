"""
033_broker_connections

Revision ID: 1c061000fab8
Revises: 172ddcabbede
Create Date: 2025-12-31T16:05:17.195388

Original SQL file: 033_broker_connections.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c061000fab8"
down_revision = "172ddcabbede"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 033_broker_connections.sql."""
    op.execute("""
-- IBKR Broker Connections Table with RLS
-- Stores encrypted IBKR Flex Query credentials per user

CREATE TABLE IF NOT EXISTS broker_connections (
    id UUID PRIMARY KEY DEFAULT public.generate_uuid_v4_safe(),
    user_id TEXT NOT NULL,
    broker_type TEXT NOT NULL DEFAULT 'ibkr',
    flex_token_encrypted TEXT NOT NULL,
    flex_query_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
    last_sync_at TIMESTAMPTZ,
    token_expires_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure one broker connection per user per broker type
CREATE UNIQUE INDEX IF NOT EXISTS idx_broker_connections_user_broker
    ON broker_connections(user_id, broker_type);

-- Index for efficient sync queries
CREATE INDEX IF NOT EXISTS idx_broker_connections_last_sync
    ON broker_connections(last_sync_at) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_broker_connections_user_id
    ON broker_connections(user_id);

-- Enable RLS and force it for all roles
ALTER TABLE broker_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_connections FORCE ROW LEVEL SECURITY;

-- Isolation policy: users only see their own broker connections
DROP POLICY IF EXISTS broker_connections_isolation ON broker_connections;
CREATE POLICY broker_connections_isolation ON broker_connections
    FOR ALL
    USING (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    )
    WITH CHECK (
        current_setting('app.current_user_id', true) IS NOT NULL
        AND user_id = current_setting('app.current_user_id', true)
    );

-- Maintain updated_at column automatically
CREATE OR REPLACE FUNCTION update_broker_connections_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_broker_connections_updated_at ON broker_connections;
CREATE TRIGGER trg_broker_connections_updated_at
    BEFORE UPDATE ON broker_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_broker_connections_updated_at();

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
