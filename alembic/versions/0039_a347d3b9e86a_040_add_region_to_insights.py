"""
040_add_region_to_insights

Revision ID: a347d3b9e86a
Revises: 70bce92dbf1b
Create Date: 2025-12-31T16:05:17.198393

Original SQL file: 040_add_region_to_insights.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a347d3b9e86a"
down_revision = "70bce92dbf1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 040_add_region_to_insights.sql."""
    op.execute("""
-- Add Region Support to User Insights
-- Following CODING_RULES.md: KISS, MVP first, no hardcoding
-- Supports market region segmentation (us, eu, china, korea, japan)
-- January 2025

-- Add region column to user_insights table
ALTER TABLE user_insights ADD COLUMN IF NOT EXISTS region VARCHAR(20);

-- Add check constraint for valid regions
-- Only markets page can have regions; crypto and macro have NULL region
ALTER TABLE user_insights ADD CONSTRAINT valid_region
  CHECK (
    region IS NULL
    OR (page_type = 'markets' AND region IN ('us', 'eu', 'china', 'korea', 'japan'))
  );

-- Update composite index to include region for efficient queries
-- Drop old index and create new one with region
DROP INDEX IF EXISTS idx_user_insights_user_page;
CREATE INDEX idx_user_insights_user_page_region
  ON user_insights(user_id, page_type, region, priority DESC, generated_at DESC);

-- Backfill existing markets insights with 'us' region (default for existing data)
UPDATE user_insights
SET region = 'us'
WHERE page_type = 'markets' AND region IS NULL;

-- Update comment for documentation
COMMENT ON COLUMN user_insights.region IS 'Market region for markets page_type: us, eu, china, korea, japan. NULL for crypto and macro pages.';

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
