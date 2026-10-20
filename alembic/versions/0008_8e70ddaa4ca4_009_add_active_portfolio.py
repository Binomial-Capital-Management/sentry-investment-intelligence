"""
009_add_active_portfolio

Revision ID: 8e70ddaa4ca4
Revises: 711e1be3c96d
Create Date: 2025-12-31T16:05:17.183169

Original SQL file: 009_add_active_portfolio.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8e70ddaa4ca4"
down_revision = "711e1be3c96d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 009_add_active_portfolio.sql."""
    op.execute("""
-- Add active_portfolio_id to chat_sessions for persistent portfolio selection
-- This allows portfolio selection to survive server restarts
-- Idempotent migration with proper transaction handling

BEGIN;

-- Add nullable column for active portfolio (if not exists)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_sessions' 
        AND column_name = 'active_portfolio_id'
    ) THEN
        ALTER TABLE chat_sessions 
        ADD COLUMN active_portfolio_id UUID;
        
        -- Add foreign key constraint
        ALTER TABLE chat_sessions
        ADD CONSTRAINT fk_chat_sessions_active_portfolio
        FOREIGN KEY (active_portfolio_id)
        REFERENCES portfolios(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- Create index for efficient lookups (if not exists)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_active
ON chat_sessions(user_id, active_portfolio_id)
WHERE active_portfolio_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN chat_sessions.active_portfolio_id IS 'Currently active portfolio for this chat session';
""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
