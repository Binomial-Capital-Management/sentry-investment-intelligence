"""
045_gamma_themes

Revision ID: 629da5e21f0e
Revises: 4f962021da59
Create Date: 2025-12-31T16:05:17.200391

Original SQL file: 045_gamma_themes.sql
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "629da5e21f0e"
down_revision = "4f962021da59"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration from 045_gamma_themes.sql."""
    op.execute("""
-- Migration: Add Gamma theme management
-- Created: 2025-01-15
-- Purpose: Provide 12 default visual themes + 4 custom themes per user
--
-- Structure:
-- - gamma_themes: 12 system-wide default visual themes (read-only)
-- - user_custom_themes: User's custom themes (max 4 per user)
--
-- IMPORTANT: After creating these themes on Gamma's platform, update gamma_theme_id values

BEGIN;

-- Table 1: Default system themes (12 total)
CREATE TABLE IF NOT EXISTS gamma_themes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    gamma_theme_id VARCHAR(100) NOT NULL,  -- Actual Gamma platform theme ID
    color_description VARCHAR(200) NOT NULL,  -- Display in UI: "Olive, Sage, Ivory"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table 2: User custom themes (max 4 per user)
CREATE TABLE IF NOT EXISTS user_custom_themes (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- Clerk user ID
    name VARCHAR(50) NOT NULL,  -- User-provided theme name
    gamma_theme_id VARCHAR(100) NOT NULL,  -- Actual Gamma platform theme ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_user_theme_name UNIQUE(user_id, name),
    CONSTRAINT valid_theme_name CHECK(LENGTH(TRIM(name)) >= 1)
);

-- Index for fast user lookups
CREATE INDEX idx_user_custom_themes_user_id ON user_custom_themes(user_id);

-- Insert 12 default system themes with actual Gamma platform theme IDs

INSERT INTO gamma_themes (name, gamma_theme_id, color_description) VALUES
('Galilee', 'glncucs7ja1zd7z', 'Olive, Sage, Ivory'),
('Alpine', 'copa7cq2a5e0wy3', 'Crisp White, Cool Gray, Ice Blue'),
('Carmel', '5hewj2m62e1kri8', 'Sandstone, Beige, Taupe'),
('Sedona', 'etder5cw4uul08z', 'Terracotta, Desert Sand, Umber'),
('Sequoia', 'p202z9u1k1wtgyx', 'Forest, White, Sage'),
('Summit', 'fql88xjtxbj3c33', 'Charcoal, Slate, Ivory'),
('Riviera', 'hqy36oqk58v98x1', 'Azure, White, Navy'),
('Highlands', 'bpuqsp86u1i4zjy', 'Midnight, White, Charcoal'),
('Appalachia', 'yskyuvtiahqs0dk', 'Umber, Tan, Linen'),
('Manhattan', 'cwmrdypiczggsmd', 'Eggshell, Black, Charcoal'),
('Valais', 'j05gh12vebuzsx2', 'Pristine White, Mountain Gray, Powder Blue'),
('Yangtze', 'c12xyffxgniimu6', 'Burgundy, White, Black');

-- Verification queries (run manually after migration)
-- SELECT * FROM gamma_themes ORDER BY name;
-- SELECT user_id, COUNT(*) as theme_count FROM user_custom_themes GROUP BY user_id;

""")


def downgrade() -> None:
    """Reverse migration - manual intervention may be required.
    
    This downgrade was auto-generated and may not fully reverse all changes.
    Review and modify as needed before running downgrade.
    """
    # Auto-generated downgrade is a no-op
    # Add manual downgrade SQL here if needed
    pass
